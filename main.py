from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, HTTPException, Security, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from anthropic import Anthropic
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set
import logging
import os
import base64
from io import BytesIO
from PIL import Image
from contextlib import asynccontextmanager
from config import (
    ANTHROPIC_API_KEY, 
    AI_NAME, 
    AI_TAGLINE, 
    HTML_TEMPLATE, 
    GALLERY_TEMPLATE,
    SYSTEM_PROMPTS,
    ARTWORK_TEMPLATE
)
from pprint import pformat
import math
import anthropic
from cloudinary.uploader import upload
import cloudinary
import cloudinary.api
from fastapi.security.api_key import APIKeyHeader, APIKey
import uuid
import os
import time
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import aiohttp
import MySQLdb
from contextlib import contextmanager
import urllib.request
import certifi
import socket
import psutil

# Setup logging with minimal WebSocket logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('IRIS')

# Silence WebSocket-related logging completely
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('uvicorn.protocols.websockets').setLevel(logging.ERROR)
logging.getLogger('fastapi').setLevel(logging.WARNING)
logging.getLogger('uvicorn').setLevel(logging.WARNING)

# Only show errors for asyncio
logging.getLogger('asyncio').setLevel(logging.ERROR)

# Create necessary directories if they don't exist
os.makedirs("static/gallery", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Initialize gallery data file if it doesn't exist
gallery_file = "data/gallery_data.json"
try:
    if not os.path.exists("data"):
        os.makedirs("data")
    if not os.path.exists(gallery_file):
        with open(gallery_file, "w") as f:
            json.dump([], f)
    else:
        # Validate existing gallery data
        with open(gallery_file, "r") as f:
            try:
                data = json.load(f)
                if not isinstance(data, list):
                    logger.warning("Invalid gallery data format, resetting...")
                    json.dump([], f)
            except json.JSONDecodeError:
                logger.warning("Corrupted gallery data, resetting...")
                json.dump([], f)
except Exception as e:
    logger.error(f"Error initializing gallery file: {e}")
    # Create empty gallery as fallback
    with open(gallery_file, "w") as f:
        json.dump([], f)

# Update the Cloudinary configuration
cloudinary.config(
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key = os.getenv('CLOUDINARY_API_KEY'),
    api_secret = os.getenv('CLOUDINARY_API_SECRET')
)

# First define the class
class FileLock:
    def __init__(self, path):
        self.lock_file = Path(str(path) + '.lock')
        self.locked = False

    def acquire(self):
        while True:
            try:
                # Try to create lock file
                with open(self.lock_file, 'x') as f:
                    f.write(str(os.getpid()))
                self.locked = True
                break
            except FileExistsError:
                # Check if the process holding the lock is still alive
                try:
                    with open(self.lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    # On Windows, just wait and retry
                    time.sleep(0.1)
                except (ValueError, FileNotFoundError):
                    # Lock file exists but is invalid/deleted, try to remove it
                    try:
                        self.lock_file.unlink()
                    except FileNotFoundError:
                        pass

    def release(self):
        if self.locked:
            try:
                self.lock_file.unlink()
                self.locked = False
            except FileNotFoundError:
                pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

class CircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open

    async def call(self, func, *args, **kwargs):
        current_time = time.time()

        if self.state == "open":
            if current_time - self.last_failure_time > self.reset_timeout:
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = current_time
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
            raise e

class ArtGenerator:
    def __init__(self):
        self.viewers: Set[WebSocket] = set()
        self.current_drawing: Dict[str, Any] = None
        self.current_state: List[Dict[str, Any]] = []
        self.current_status = "waiting"
        self.current_phase = "initializing"
        self.current_idea = None
        self.current_reflection = None
        self.total_creations = 0
        self.is_running = False
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.messages = self.client.messages
        self.generation_interval = 120  # Increase to 2 minutes
        self.total_pixels_drawn = 0
        self.complexity_score = 0
        self.last_generation_time = datetime.now()
        
        # Initialize stats from gallery
        self._load_initial_stats()

        # Add lock
        self.generation_lock = asyncio.Lock()
        self.file_lock = FileLock("data/gallery_data.json")
        self.min_generation_interval = 120  # Match generation interval
        self.max_retries = 3  # Add retry count
        self.retry_delay = 10  # Seconds between retries
        self.api_breaker = CircuitBreaker()

        # Initialize last_generation_time from database
        self.last_generation_time = asyncio.run(db_service.get_last_generation_time())

    def _load_initial_stats(self):
        """Synchronously initialize statistics from gallery"""
        try:
            gallery_file = "data/gallery_data.json"
            if os.path.exists(gallery_file):
                with open(gallery_file, "r") as f:
                    gallery_data = json.load(f)
                    self.total_creations = len(gallery_data)
                    
                    # Calculate total pixels from existing artworks
                    for item in gallery_data:
                        if "pixel_count" in item:
                            self.total_pixels_drawn += item.get("pixel_count", 0)
                    
                logger.info(f"Initialized with {self.total_creations} creations and {self.total_pixels_drawn} pixels")
        except Exception as e:
            logger.error(f"Error initializing stats: {e}")

    async def get_art_idea(self) -> str:
        """Generate art idea using Claude"""
        return await self.api_breaker.call(self._get_art_idea)

    async def _get_art_idea(self) -> str:
        """Generate art idea using Claude"""
        retries = 0
        while retries < self.max_retries:
            try:
                logger.info("🤖 IRIS awakening creative processes...")
                
                message = await asyncio.to_thread(
                    self.messages.create,
                    model="claude-3-sonnet-20240229",
                    max_tokens=1024,
                    temperature=0.9,
                    system=SYSTEM_PROMPTS["creative_idea"],
                    messages=[{"role": "user", "content": "Generate a new geometric art concept."}]
                )
                
                idea = message.content[0].text.strip()
                logger.info(f"🎨 IRIS envisions: {idea}")
                return idea
                
            except Exception as e:
                retries += 1
                logger.error(f"❌ Error in IRIS's creative process (attempt {retries}): {str(e)}")
                if retries < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("Max retries reached, skipping generation")
                    return None

    async def get_drawing_instructions(self, idea: str) -> Dict[str, Any]:
        """Generate drawing instructions using Claude"""
        try:
            logger.info("Requesting drawing instructions from Claude...")
            
            prompt = f"""Convert this artistic vision into precise JSON drawing instructions:

Original Vision: {idea}

Generate a JSON object with these exact specifications:
{{
    "description": "Brief description",
    "background": "#000000",
    "elements": [
        {{
            "type": "circle|line|wave|spiral",
            "description": "Element purpose",
            "points": [[x1,y1], [x2,y2], ...],  // Max 20 points for waves/spirals, 32 for circles
            "color": "#00ff00",
            "stroke_width": 1-3,
            "animation_speed": 0.02,
            "closed": true/false
        }}
    ]
}}

IMPORTANT: 
- Ensure all JSON is properly formatted and complete
- All arrays must be properly closed
- All points must be complete [x,y] pairs
- Maximum 20 points for spirals and waves
- Maximum 32 points for circles
- All coordinates must be within 800x400 canvas
- Return ONLY valid JSON, no markdown formatting"""

            message = await asyncio.to_thread(
                self.client.messages.create,
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                temperature=0.3,
                system="""You are a mathematical artist that generates precise geometric coordinates.
                You must:
                1. Return only valid, complete JSON
                2. Ensure all arrays are properly closed
                3. Keep all coordinates within canvas bounds (800x400)
                4. Use proper mathematical formulas
                5. Never exceed maximum points (20 for spirals/waves, 32 for circles)""",
                messages=[{
                    "role": "user", 
                    "content": prompt
                }]
            )

            try:
                response_text = message.content[0].text.strip()
                
                # Clean up the response
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                # Remove any trailing commas in arrays
                response_text = response_text.replace(',]', ']')
                response_text = response_text.replace(',}', '}')
                
                logger.info("Received drawing instructions:")
                logger.info(response_text)

                try:
                    instructions = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parsing error: {e}")
                    # Attempt to fix common JSON issues
                    response_text = response_text.replace(',,', ',')  # Remove double commas
                    response_text = response_text.replace('][', '],[')  # Fix array separators
                    instructions = json.loads(response_text)

                # Validate and clean up instructions
                if instructions and "elements" in instructions:
                    for element in instructions["elements"]:
                        # Ensure points are within canvas bounds
                        element["points"] = [
                            [min(max(x, 0), 800), min(max(y, 0), 400)]
                            for x, y in element["points"]
                        ]
                        
                        # Limit number of points
                        if element["type"] in ["wave", "spiral"] and len(element["points"]) > 20:
                            element["points"] = element["points"][:20]
                        elif element["type"] == "circle" and len(element["points"]) > 32:
                            element["points"] = element["points"][:32]
                        
                        # Ensure required properties
                        element["animation_speed"] = element.get("animation_speed", 0.02)
                        element["stroke_width"] = min(max(element.get("stroke_width", 2), 1), 3)
                        element["closed"] = element.get("closed", True)

                    return instructions
                else:
                    logger.error("Invalid instructions format")
                    return None

            except Exception as e:
                logger.error(f"Error processing drawing instructions: {e}")
                logger.error(f"Raw response: {message.content[0].text}")
                return None

        except Exception as e:
            logger.error(f"Error generating drawing instructions: {e}")
            return None

    def _validate_instructions_match_idea(self, instructions: Dict[str, Any], idea: str) -> bool:
        """Validate that generated instructions match the original idea"""
        try:
            # Extract key elements from idea (basic validation)
            idea_lower = idea.lower()
            
            # Check if mentioned shapes are present in instructions
            shapes = {
                'circle': 'circle' in idea_lower,
                'line': 'line' in idea_lower,
                'wave': 'wave' in idea_lower or 'sine' in idea_lower,
                'spiral': 'spiral' in idea_lower
            }
            
            element_types = [elem["type"] for elem in instructions["elements"]]
            
            # Verify that mentioned shapes are included
            for shape, should_exist in shapes.items():
                if should_exist and shape not in element_types:
                    logger.warning(f"⚠️ Missing {shape} in instructions")
                    return False
            
            # Verify center point if mentioned
            if "(400,200)" in idea and not any(
                elem["points"][0] == [400, 200] for elem in instructions["elements"]
            ):
                logger.warning("⚠️ Missing center point (400,200)")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating instructions: {e}")
            return False

    async def broadcast_state(self, data: Dict[str, Any]):
        """Broadcast state update to all viewers"""
        # Add stats to all broadcasts
        if "type" in data and data["type"] == "display_update":
            data.update({
                "total_creations": self.total_creations,
                "total_pixels": self.total_pixels_drawn,
                "viewers": len(self.viewers),
                "generation_time": (datetime.now() - self.last_generation_time).seconds
            })
        
        disconnected = set()
        for viewer in self.viewers:
            try:
                await viewer.send_json(data)
            except Exception as e:
                logger.error(f"Error broadcasting to viewer: {e}")
                disconnected.add(viewer)
        
        # Remove disconnected viewers
        self.viewers -= disconnected

    async def update_status(self, status: str, phase: str = None, idea: str = None, progress: float = None):
        """Update and broadcast status"""
        self.current_status = status
        if phase:
            self.current_phase = phase
        if idea:
            self.current_idea = idea

        # More professional status messages
        status_messages = {
            "thinking": "Analyzing geometric possibilities",
            "drawing": "Generating artwork",
            "reflecting": "Processing results",
            "completed": "Creation complete",
            "error": "Process interrupted"
        }

        await self.broadcast_state({
            "type": "display_update",
            "status": status_messages.get(status, status),
            "phase": self.current_phase,
            "idea": self.current_idea,
            "reflection": self.current_reflection,
            "timestamp": datetime.now().isoformat(),
            "progress": progress,
            "total_creations": self.total_creations,
            "viewers": len(self.viewers)  # Add viewer count to every update
        })

    async def execute_drawing(self, instructions: Dict[str, Any]):
        """Execute drawing instructions"""
        try:
            logger.info("🎨 Starting drawing execution...")
            total_elements = len(instructions["elements"])
            total_points = sum(len(element["points"]) for element in instructions["elements"])
            points_drawn = 0
            pixels_in_stroke = 0  # Initialize here
            
            # Clear canvas and set background
            logger.info("🧹 Clearing canvas and setting background...")
            self.current_state = [
                {"type": "clear"},
                {"type": "setBackground", "color": instructions["background"]}
            ]
            await self.broadcast_state({"type": "clear"})
            await self.broadcast_state({"type": "setBackground", "color": instructions["background"]})
            
            # Draw each element
            for i, element in enumerate(instructions["elements"], 1):
                logger.info(f"✏️ Drawing element {i}/{total_elements}: {element['description']}")
                points = element["points"]
                stroke_width = element["stroke_width"]
                
                if not points:
                    logger.warning(f"⚠️ Element {i} has no points, skipping")
                    continue
                
                # Calculate pixels for this element
                for j in range(len(points) - 1):
                    x1, y1 = points[j]
                    x2, y2 = points[j + 1]
                    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    pixels_in_stroke += distance * stroke_width
                
                # Start drawing element
                logger.info(f"▶️ Starting element {i} with {len(points)} points")
                start_cmd = {
                    "type": "startDrawing",
                    "x": points[0][0],
                    "y": points[0][1],
                    "color": element["color"],
                    "width": element["stroke_width"],
                    "element_description": element["description"]
                }
                self.current_state.append(start_cmd)
                await self.broadcast_state(start_cmd)
                
                # Draw points
                for j, (x, y) in enumerate(points[1:], 1):
                    draw_cmd = {"type": "draw", "x": x, "y": y}
                    self.current_state.append(draw_cmd)
                    await self.broadcast_state(draw_cmd)
                    
                    # Update progress
                    points_drawn += 1
                    progress = (points_drawn / total_points) * 100
                    await self.update_status(
                        "drawing",
                        "drawing",
                        self.current_idea,
                        progress=progress
                    )
                    
                    await asyncio.sleep(element.get("animation_speed", 0.02))
                
                # Close path if needed
                if element.get("closed", False) and len(points) > 2:
                    logger.info("🔄 Closing path")
                    close_cmd = {"type": "draw", "x": points[0][0], "y": points[0][1]}
                    self.current_state.append(close_cmd)
                    await self.broadcast_state(close_cmd)
                    
                    # Add pixels for closing line
                    x1, y1 = points[-1]
                    x2, y2 = points[0]
                    distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
                    pixels_in_stroke += distance * stroke_width
                
                stop_cmd = {"type": "stopDrawing"}
                self.current_state.append(stop_cmd)
                await self.broadcast_state(stop_cmd)
                logger.info(f"✅ Element {i} completed")
            
            logger.info("🎉 Drawing completed successfully")
            
            # Update current drawing data
            self.current_drawing.update({
                "description": instructions.get("description", ""),
                "background": instructions.get("background", "#000000"),
                "timestamp": datetime.now().isoformat(),
                "pixel_count": int(pixels_in_stroke)
            })

            # Request canvas data for gallery
            logger.info("📸 Requesting canvas data for gallery...")
            await self.broadcast_state({
                "type": "request_canvas_data",
                "drawing_id": self.current_drawing["id"]
            })

            # Add a small delay to ensure canvas data is received
            await asyncio.sleep(0.5)

            # Notify frontend that a new gallery item is available
            await self.broadcast_state({
                "type": "gallery_update",
                "action": "new_item",
                "item": {
                    "id": self.current_drawing["id"],
                    "description": self.current_drawing["idea"]
                }
            })

        except Exception as e:
            logger.error(f"❌ Error executing drawing: {e}")
            raise

    async def reflect_on_creation(self, idea: str) -> str:
        """IRIS reflects on its creation"""
        retries = 0
        while retries < self.max_retries:
            try:
                prompt = f"""As IRIS, reflect briefly on your latest creation:
                Original Idea: {idea}
                Share your thoughts in 2-3 sentences."""

                message = await asyncio.to_thread(
                    self.messages.create,
                    model="claude-3-sonnet-20240229",
                    max_tokens=512,  # Reduced token count
                    temperature=0.9,
                    system="""You are IRIS, an introspective AI artist. Keep reflections brief and focused.""",
                    messages=[{"role": "user", "content": prompt}]
                )
                
                reflection = message.content[0].text.strip()
                logger.info(f"💭 IRIS reflects: {reflection}")
                return reflection

            except Exception as e:
                retries += 1
                logger.error(f"❌ Error in IRIS's reflection (attempt {retries}): {str(e)}")
                if retries < self.max_retries:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logger.error("Max retries reached for reflection")
                    return "I find myself contemplating this creation in silence."

    async def start(self):
        """Main generation loop"""
        self.is_running = True
        logger.info("🚀 IRIS awakens")
        
        while self.is_running:
            try:
                async with self.generation_lock:
                    # Get latest time from database
                    self.last_generation_time = await db_service.get_last_generation_time()
                    
                    # Check if enough time has passed
                    time_since_last = (datetime.now() - self.last_generation_time).total_seconds()
                    if time_since_last < self.min_generation_interval:
                        wait_time = self.min_generation_interval - time_since_last
                        logger.info(f"Waiting {wait_time}s before next creation...")
                        await self.update_status("resting", "waiting")
                        await asyncio.sleep(wait_time)
                        continue

                    # Ideation phase
                    logger.info("🤔 IRIS contemplates new possibilities...")
                    await self.update_status("thinking", "ideation")
                    idea = await self.get_art_idea()
                    
                    if idea:
                        # Update last generation time before starting
                        self.last_generation_time = datetime.now()
                        
                        # Generation phase
                        logger.info("✨ Inspiration strikes!")
                        await self.update_status("drawing", "generation", idea)
                        instructions = await self.get_drawing_instructions(idea)
                        
                        if instructions:
                            # Creation phase
                            logger.info("🎨 Bringing vision to life...")
                            self.total_creations += 1
                            new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                            
                            # Check if ID already exists in gallery
                            gallery_file = "data/gallery_data.json"
                            if os.path.exists(gallery_file):
                                with open(gallery_file, "r") as f:
                                    existing_items = json.load(f)
                                    if any(item["id"] == new_id for item in existing_items):
                                        logger.warning(f"ID {new_id} already exists, skipping creation")
                                        continue
                            
                            self.current_drawing = {
                                "id": new_id,
                                "idea": idea,
                                "instructions": instructions,
                                "timestamp": datetime.now().isoformat()
                            }
                            await self.execute_drawing(instructions)
                            
                            # Reflection phase with timeout
                            logger.info("💭 IRIS contemplates the creation...")
                            await self.update_status("reflecting", "reflection", idea)
                            try:
                                reflection_task = asyncio.create_task(self.reflect_on_creation(idea))
                                reflection = await asyncio.wait_for(reflection_task, timeout=30.0)
                            except asyncio.TimeoutError:
                                logger.warning("Reflection timed out, using fallback")
                                reflection = "I find myself contemplating this creation in silence."
                            except Exception as e:
                                logger.error(f"Reflection error: {e}")
                                reflection = "I find myself contemplating this creation in silence."

                            self.current_reflection = reflection

                            # Save to gallery immediately after reflection
                            logger.info("📸 Requesting canvas data for gallery...")
                            await self.broadcast_state({
                                "type": "request_canvas_data",
                                "drawing_id": self.current_drawing["id"]
                            })

                            # Add a longer wait for canvas data
                            await asyncio.sleep(2)

                            # Broadcast updates
                            await self.broadcast_state({
                                "type": "reflection_update",
                                "reflection": reflection,
                                "total_creations": self.total_creations
                            })

                            logger.info("✅ Creative cycle complete")
                            await self.update_status("completed", "display", idea)
                    
                    # Rest before next creation
                    logger.info("😌 IRIS rests before next creation...")
                    await self.update_status("resting", "waiting")
                    
                    # Update last generation time in database after successful generation
                    self.last_generation_time = datetime.now()
                    await db_service.update_last_generation_time(self.last_generation_time)

            except Exception as e:
                logger.error(f"❌ Error in creative process: {e}")
                await self.update_status("error", "error")
                await asyncio.sleep(self.retry_delay)
                continue

    async def save_to_gallery(self, canvas_data: str):
        """Save drawing to gallery using Cloudinary and PlanetScale"""
        try:
            # Use generation lock to ensure only one save at a time
            async with self.generation_lock:
                if not self.current_drawing:
                    logger.error("No current drawing to save")
                    return False

                # Generate unique ID
                unique_id = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                # Upload to Cloudinary
                logger.info("Uploading to Cloudinary...")
                img_data = canvas_data.split(',')[1]
                img_bytes = base64.b64decode(img_data)
                upload_result = upload(
                    img_bytes,
                    folder="iris_gallery",
                    public_id=f"drawing_{unique_id}",
                    resource_type="image"
                )
                
                image_url = upload_result.get('secure_url')
                if not image_url:
                    logger.error("No URL in upload result")
                    return False
                    
                # Create new entry
                new_entry = {
                    "id": unique_id,
                    "url": image_url,
                    "description": self.current_drawing.get("idea", "Geometric pattern"),
                    "reflection": self.current_reflection or "Contemplating this creation in digital silence...",
                    "timestamp": datetime.now().isoformat(),
                    "votes": 0,
                    "pixel_count": self.current_drawing.get("pixel_count", 0)
                }

                # Save to database
                with db_service.get_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO gallery 
                            (id, url, description, reflection, timestamp, votes, pixel_count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            new_entry["id"],
                            new_entry["url"],
                            new_entry["description"],
                            new_entry["reflection"],
                            new_entry["timestamp"],
                            new_entry["votes"],
                            new_entry["pixel_count"]
                        ))

                logger.info(f"Successfully saved artwork {unique_id} to gallery")
                
                # Update last generation time
                self.last_generation_time = datetime.now()
                
                # Broadcast update
                await self.broadcast_state({
                    "type": "gallery_update",
                    "action": "new_item",
                    "item": new_entry
                })
                
                return True
                    
        except Exception as e:
            logger.error(f"Error in save_to_gallery: {e}")
            return False

    def _calculate_circle_points(self, center_x: float, center_y: float, radius: float, points: int = 32) -> List[List[float]]:
        """Calculate points for a circle"""
        return [
            [
                center_x + radius * math.cos(2 * math.pi * i / points),
                center_y + radius * math.sin(2 * math.pi * i / points)
            ]
            for i in range(points + 1)
        ]

    def _calculate_spiral_points(self, center_x: float, center_y: float, start_radius: float, 
                               end_radius: float, revolutions: float, points: int = 20) -> List[List[float]]:
        """Calculate points for a spiral"""
        points_list = []
        for i in range(points):
            t = i * (revolutions * 2 * math.pi) / (points - 1)
            r = start_radius + (end_radius - start_radius) * t / (revolutions * 2 * math.pi)
            x = center_x + r * math.cos(t)
            y = center_y + r * math.sin(t)
            points_list.append([x, y])
        return points_list

    def _calculate_wave_points(self, start_x: float, end_x: float, center_y: float, 
                              amplitude: float, frequency: float, points: int = 20) -> List[List[float]]:
        """Calculate points for a sine wave"""
        points_list = []
        for i in range(points):
            x = start_x + (end_x - start_x) * i / (points - 1)
            y = center_y + amplitude * math.sin(frequency * (x - start_x))
            points_list.append([x, y])
        return points_list

    def _calculate_polygon_points(self, center_x: float, center_y: float, radius: float, 
                                sides: int, rotation: float = 0) -> List[List[float]]:
        """Calculate points for a regular polygon"""
        points = []
        for i in range(sides + 1):
            angle = rotation + i * 2 * math.pi / sides
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append([x, y])
        return points

    def _calculate_complexity(self, instructions: Dict[str, Any]) -> float:
        """Calculate complexity score of the drawing"""
        score = 0
        total_points = 0
        unique_colors = set()
        
        for element in instructions["elements"]:
            total_points += len(element["points"])
            unique_colors.add(element["color"])
            
            # Add complexity based on element type
            if element["type"] == "spiral":
                score += 3
            elif element["type"] == "wave":
                score += 2
            elif element["type"] == "circle":
                score += 1
                
        # Factor in variety
        score += len(unique_colors) * 0.5
        score += (total_points / 20) * 0.5
        
        return round(score, 2)

# Add this function to migrate old gallery data
async def migrate_gallery_data():
    """Migrate old gallery data to use Cloudinary URLs"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            return
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
            
        updated = False
        for item in items:
            if "filename" in item and not item.get("url"):
                try:
                    # Upload to Cloudinary
                    filepath = os.path.join("static/gallery", item["filename"])
                    if os.path.exists(filepath):
                        with open(filepath, "rb") as img_file:
                            upload_result = upload(
                                img_file,
                                folder="iris_gallery",
                                public_id=f"drawing_{item['id']}",
                                resource_type="image"
                            )
                            item["url"] = upload_result["secure_url"]
                            updated = True
                except Exception as e:
                    logger.error(f"Error migrating item {item['id']}: {e}")
                    
        if updated:
            with open(gallery_file, "w") as f:
                json.dump(items, f, indent=2)
                logger.info("Gallery data migrated to use Cloudinary URLs")
                
    except Exception as e:
        logger.error(f"Error migrating gallery data: {e}")

# Add this class near the top after imports
class DatabaseService:
    def __init__(self):
        logger.info("Initializing PlanetScale database service...")
        if os.name == 'nt':  # Windows
            import certifi
            ssl_cert = certifi.where()
            self.config = {
                "host": os.getenv("DATABASE_HOST"),
                "user": os.getenv("DATABASE_USERNAME"),
                "passwd": os.getenv("DATABASE_PASSWORD"),
                "db": os.getenv("DATABASE"),
                "autocommit": True,
                "ssl": {
                    "ca": ssl_cert,
                    "verify_mode": "VERIFY_IDENTITY"
                }
            }
        else:  # Linux/Unix
            self.config = {
                "host": os.getenv("DATABASE_HOST"),
                "user": os.getenv("DATABASE_USERNAME"),
                "passwd": os.getenv("DATABASE_PASSWORD"),
                "db": os.getenv("DATABASE"),
                "autocommit": True,
                "ssl_mode": "VERIFY_IDENTITY",
                "ssl": {"ca": "/etc/ssl/certs/ca-certificates.crt"}
            }
        self._initialize_database()

    def _initialize_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS gallery (
                        id VARCHAR(255) PRIMARY KEY,
                        url TEXT NOT NULL,
                        description TEXT,
                        reflection TEXT,
                        timestamp DATETIME NOT NULL,
                        votes INT DEFAULT 0,
                        pixel_count INT DEFAULT 0
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS system_state (
                        state_key VARCHAR(255) PRIMARY KEY,
                        state_value TEXT NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                """)
                logger.info("Database tables initialized successfully")

    @contextmanager
    def get_connection(self):
        """Get database connection context"""
        conn = MySQLdb.connect(**self.config)
        try:
            yield conn
        finally:
            conn.close()

    async def get_last_generation_time(self):
        """Get last generation time from database"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        SELECT state_value FROM system_state 
                        WHERE state_key = 'last_generation_time'
                    """)
                    result = cursor.fetchone()
                    if result:
                        return datetime.fromisoformat(result[0])
                    return datetime.now() - timedelta(minutes=5)
        except Exception as e:
            logger.error(f"Error getting last generation time: {e}")
            return datetime.now() - timedelta(minutes=5)

    async def update_last_generation_time(self, timestamp):
        """Update last generation time in database"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO system_state (state_key, state_value, updated_at)
                    VALUES ('last_generation_time', %s, NOW())
                    ON DUPLICATE KEY UPDATE 
                    state_value = VALUES(state_value),
                    updated_at = NOW()
                """, (timestamp.isoformat(),))

# Then create the service instance
db_service = DatabaseService()

# Then create the generator
generator = ArtGenerator()

# Then define the lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Initializing IRIS...")
        await generator.initialize()  # Initialize async components
        asyncio.create_task(generator.start())
        logger.info("IRIS initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        generator.is_running = False
        logger.info("IRIS shutting down")

# Finally create the FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}

    async def dispatch(self, request, call_next):
        client_ip = request.client.host
        now = time.time()
        
        # Clean old requests
        self.requests = {ip: reqs for ip, reqs in self.requests.items() 
                        if now - reqs["timestamp"] < self.window_seconds}
        
        if client_ip in self.requests:
            if self.requests[client_ip]["count"] >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"error": "Too many requests"}
                )
            self.requests[client_ip]["count"] += 1
        else:
            self.requests[client_ip] = {"count": 1, "timestamp": now}
        
        response = await call_next(request)
        return response

# Add middleware to app
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.debug("New WebSocket connection established")
    
    try:
        # Add to viewers
        generator.viewers.add(websocket)
        logger.debug(f"Active viewers: {len(generator.viewers)}")
        
        # Send initial state
        initial_state = {
            "type": "display_update",
            "status": generator.current_status,
            "phase": generator.current_phase,
            "idea": generator.current_idea,
            "reflection": generator.current_reflection,
            "timestamp": datetime.now().isoformat(),
            "viewers": len(generator.viewers),
            "is_running": generator.is_running,
            "total_creations": generator.total_creations,
            "total_pixels": generator.total_pixels_drawn
        }
        await websocket.send_json(initial_state)
        
        # If there's a current drawing, send its state
        if generator.current_state:
            for cmd in generator.current_state:
                await websocket.send_json(cmd)
        
        while True:
            data = await websocket.receive_json()
            if data.get("type") != "subscribe_status":
                logger.debug(f"Received WebSocket message: {data}")
            
            if data.get("type") == "subscribe_status":
                await websocket.send_json(initial_state)
            elif data.get("type") == "canvas_data":
                # Handle canvas data for gallery save
                logger.info("Received canvas data, saving to gallery...")
                success = await generator.save_to_gallery(data.get("data", ""))
                if success:
                    logger.info("Successfully saved to gallery")
                    await websocket.send_json({
                        "type": "save_success",
                        "message": "Artwork saved to gallery"
                    })
                else:
                    logger.error("Failed to save to gallery")
                    await websocket.send_json({
                        "type": "save_error",
                        "message": "Failed to save artwork"
                    })
                
    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Safely remove from viewers set
        try:
            if websocket in generator.viewers:
                generator.viewers.remove(websocket)
                logger.debug(f"Removed viewer. Active viewers: {len(generator.viewers)}")
        except Exception as e:
            logger.error(f"Error removing viewer: {e}")
        
        # Broadcast viewer count update only if there are still viewers
        if generator.viewers:
            try:
                await generator.broadcast_state({
                    "type": "display_update",
                    "viewers": len(generator.viewers)
                })
            except Exception as e:
                logger.error(f"Error broadcasting viewer count update: {e}")

@app.get("/")
async def home():
    return HTMLResponse(HTML_TEMPLATE)

@app.get("/gallery")
async def gallery():
    return HTMLResponse(GALLERY_TEMPLATE)

@app.get("/api/current-art")
async def get_current_art():
    """Get current art state"""
    try:
        if generator.current_drawing:
            return {
                "status": generator.current_status,
                "phase": generator.current_phase,
                "drawing": {
                    "id": generator.current_drawing["id"],
                    "idea": generator.current_drawing["idea"],
                    "timestamp": generator.current_drawing["timestamp"]
                },
                "canvas_state": generator.current_state
            }
        return {
            "status": generator.current_status,
            "message": "No art currently generating"
        }
    except Exception as e:
        logger.error(f"Error in get_current_art: {e}")
        return {
            "status": "error",
            "message": "Error fetching current art state"
        }

@app.get("/api/status")
async def get_status():
    """Get generator status"""
    return {
        "status": generator.current_status,
        "phase": generator.current_phase,
        "timestamp": datetime.now().isoformat(),
        "viewers": len(generator.viewers),
        "is_running": generator.is_running
    }

# Update the gallery endpoints to use the database service
@app.get("/api/gallery")
async def get_gallery(sort: str = "new", limit: int = 50, offset: int = 0):
    try:
        items = await db_service.get_gallery_items(sort, limit, offset)
        return {
            "success": True,
            "items": items,
            "total": len(items)
        }
    except Exception as e:
        logger.error(f"Error in get_gallery: {e}")
        return {"success": False, "error": str(e)}

@app.get("/static/gallery/{filename}")
async def get_gallery_image(filename: str):
    """Serve gallery images"""
    try:
        filepath = os.path.join("static/gallery", filename)
        if os.path.exists(filepath):
            return FileResponse(filepath)
        return Response(status_code=404)
    except Exception as e:
        logger.error(f"Error serving image {filename}: {e}")
        return Response(status_code=500)

API_KEY_NAME = "X-API-Key"
API_KEY = os.getenv('API_KEY', 'your-default-key')  # Set this in your .env file
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(
        status_code=403, 
        detail="Could not validate API key"
    )

@app.post("/api/gallery/{image_id}/upvote")
async def upvote_image(image_id: str, api_key: APIKey = Depends(get_api_key)):
    """Upvote a gallery image with proper error handling and data validation"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            raise HTTPException(status_code=404, detail="Gallery not found")
        
        # Create backup before modification
        backup_file = f"{gallery_file}.backup"
        try:
            with open(gallery_file, "r") as f:
                items = json.load(f)
                with open(backup_file, "w") as bf:
                    json.dump(items, bf, indent=2)
        except Exception as backup_error:
            logger.error(f"Error creating backup: {backup_error}")
            raise HTTPException(status_code=500, detail="Error processing vote")
        
        # Find and update the image
        image_found = False
        for item in items:
            if str(item.get("id", "")) == str(image_id):
                image_found = True
                try:
                    # Ensure votes is an integer and increment
                    current_votes = int(item.get("votes", 0))
                    item["votes"] = current_votes + 1
                    
                    # Save updated data
                    with open(gallery_file, "w") as f:
                        json.dump(items, f, indent=2)
                    
                    # Remove backup after successful save
                    if os.path.exists(backup_file):
                        os.remove(backup_file)
                    
                    # Broadcast update to all connected clients
                    await generator.broadcast_state({
                        "type": "vote_update",
                        "image_id": image_id,
                        "votes": item["votes"]
                    })
                    
                    return {
                        "success": True,
                        "votes": item["votes"],
                        "image_id": image_id
                    }
                except Exception as save_error:
                    logger.error(f"Error saving votes: {save_error}")
                    # Restore from backup
                    if os.path.exists(backup_file):
                        os.replace(backup_file, gallery_file)
                    raise HTTPException(status_code=500, detail="Error saving vote")
        
        if not image_found:
            raise HTTPException(status_code=404, detail="Image not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upvoting image: {e}")
        raise HTTPException(status_code=500, detail="Error processing upvote")

@app.get("/api/gallery/{image_id}/reflection")
async def get_reflection(image_id: str):
    """Get reflection for a specific image"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            raise HTTPException(status_code=404, detail="Gallery not found")
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
        
        for item in items:
            if item["id"] == image_id:
                return {
                    "success": True,
                    "reflection": item.get("reflection", "No reflection available"),
                    "description": item.get("description", "")
                }
        
        raise HTTPException(status_code=404, detail="Image not found")
            
    except Exception as e:
        logger.error(f"Error getting reflection: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving reflection")

@app.get("/api/gallery/{image_id}")
async def get_gallery_item(image_id: str):
    """Get a single gallery item by ID"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            raise HTTPException(status_code=404, detail="Gallery not found")
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
        
        for item in items:
            if item["id"] == image_id:
                filepath = os.path.join("static/gallery", item["filename"])
                if os.path.exists(filepath):
                    return item
                    
        raise HTTPException(status_code=404, detail="Image not found")
        
    except Exception as e:
        logger.error(f"Error getting gallery item: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving gallery item")

@app.get("/api/debug/versions")
async def get_versions():
    return {
        "anthropic_version": anthropic.__version__,
        "api_key_prefix": ANTHROPIC_API_KEY[:10] + "...",
        "model": "claude-3-sonnet-20240229"  # Current model we're using
    }

@app.get("/artwork/{artwork_id}")
async def get_artwork_page(artwork_id: str):
    """Serve individual artwork page"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            logger.error(f"Gallery file not found: {gallery_file}")
            raise HTTPException(status_code=404, detail="Gallery not found")
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
            
        # Log for debugging
        logger.info(f"Looking for artwork ID: {artwork_id}")
        logger.info(f"Found {len(items)} items in gallery")
        
        for item in items:
            if str(item["id"]) == str(artwork_id):
                logger.info(f"Found artwork: {item}")
                try:
                    # Validate required fields
                    artwork_url = item.get("url")
                    if not artwork_url:
                        logger.error("Missing URL for artwork")
                        raise HTTPException(status_code=500, detail="Invalid artwork data")

                    # Safely get timestamp
                    timestamp = item.get("timestamp")
                    if timestamp:
                        try:
                            formatted_timestamp = datetime.fromisoformat(timestamp).strftime("%B %d, %Y, %I:%M %p")
                        except ValueError as e:
                            logger.error(f"Invalid timestamp format: {e}")
                            formatted_timestamp = "Date unknown"
                    else:
                        formatted_timestamp = "Date unknown"

                    # Create a formatted HTML string with the artwork data
                    artwork_html = ARTWORK_TEMPLATE.format(
                        artwork_url=artwork_url,
                        artwork_description=item.get("description", "No description available"),
                        artwork_reflection=item.get("reflection", "No reflection available"),
                        artwork_id=str(artwork_id),
                        artwork_timestamp=formatted_timestamp,
                        artwork_votes=str(item.get("votes", 0))
                    )
                    
                    return HTMLResponse(artwork_html)
                    
                except Exception as format_error:
                    logger.error(f"Error formatting artwork data: {format_error}")
                    logger.error(f"Item data: {item}")
                    raise HTTPException(status_code=500, detail=f"Error formatting artwork: {str(format_error)}")
                
        # If we get here, artwork wasn't found
        logger.error(f"Artwork not found: {artwork_id}")
        raise HTTPException(status_code=404, detail="Artwork not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error loading artwork: {str(e)}")
        logger.error(f"Full error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error loading artwork: {str(e)}")

# Add this utility function to main.py
@app.get("/api/export-gallery")
async def export_gallery(api_key: APIKey = Depends(get_api_key)):
    """Export gallery data for backup/migration"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            raise HTTPException(status_code=404, detail="Gallery not found")
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
            
        # Return as downloadable JSON file
        return Response(
            content=json.dumps(items, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=gallery_backup.json"
            }
        )
    except Exception as e:
        logger.error(f"Error exporting gallery: {e}")
        raise HTTPException(status_code=500, detail="Error exporting gallery")

@app.post("/api/import-gallery")
async def import_gallery(gallery_data: List[dict], api_key: APIKey = Depends(get_api_key)):
    """Import gallery data from backup"""
    try:
        gallery_file = "data/gallery_data.json"
        
        # Backup existing data first
        if os.path.exists(gallery_file):
            backup_file = f"{gallery_file}.backup"
            with open(gallery_file, "r") as f:
                existing_data = json.load(f)
            with open(backup_file, "w") as f:
                json.dump(existing_data, f, indent=2)
        
        # Merge new data with existing data, avoiding duplicates
        existing_ids = {item["id"] for item in existing_data}
        new_items = [item for item in gallery_data if item["id"] not in existing_ids]
        
        # Combine and sort by timestamp
        combined_data = existing_data + new_items
        combined_data.sort(key=lambda x: x["timestamp"], reverse=True)
        
        # Save merged data
        with open(gallery_file, "w") as f:
            json.dump(combined_data, f, indent=2)
            
        return {
            "success": True,
            "message": f"Imported {len(new_items)} new items",
            "total_items": len(combined_data)
        }
        
    except Exception as e:
        logger.error(f"Error importing gallery: {e}")
        raise HTTPException(status_code=500, detail="Error importing gallery")

@app.get("/api/download-gallery")
async def download_gallery():
    """Download gallery data as JSON file"""
    try:
        gallery_file = "data/gallery_data.json"
        if not os.path.exists(gallery_file):
            raise HTTPException(status_code=404, detail="Gallery not found")
            
        with open(gallery_file, "r") as f:
            items = json.load(f)
            
        return Response(
            content=json.dumps(items, indent=2),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=gallery_backup.json"
            }
        )
    except Exception as e:
        logger.error(f"Error downloading gallery: {e}")
        raise HTTPException(status_code=500, detail="Error downloading gallery")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        with db_service.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")

        # Check Cloudinary
        cloudinary.api.ping()

        # Check Anthropic
        test_message = await generator.client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=10,
            messages=[{"role": "user", "content": "test"}]
        )

        return {
            "status": "healthy",
            "database": "connected",
            "cloudinary": "connected",
            "anthropic": "connected",
            "uptime": time.time() - startup_time,
            "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024  # MB
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

class RequestTracer(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        logger.info(f"Request {request_id} started: {request.method} {request.url}")
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            logger.info(f"Request {request_id} completed in {duration:.2f}s")
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            logger.error(f"Request {request_id} failed: {e}")
            raise

app.add_middleware(RequestTracer)

async def shutdown_event():
    """Graceful shutdown"""
    logger.info("Shutting down...")
    
    # Stop art generation
    generator.is_running = False
    
    # Close all WebSocket connections
    for viewer in generator.viewers:
        try:
            await viewer.close()
        except:
            pass
    
    # Close database connections
    for conn in db_service.pool:
        try:
            conn.close()
        except:
            pass
    
    logger.info("Shutdown complete")

app.add_event_handler("shutdown", shutdown_event)

if __name__ == "__main__":
    import uvicorn
    import socket

    def find_available_port(start_port=8000, max_tries=10):
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + max_tries):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise RuntimeError(f"No available ports in range {start_port}-{start_port + max_tries}")

    try:
        port = find_available_port()
        print(f"\n=== {AI_NAME} Drawing System v2.0 ===")
        print(f"{AI_TAGLINE}")
        print(f"Starting server on port {port}")
        print("================================\n")
        
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="error",
            access_log=False
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        print(f"Failed to start server: {e}")