from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from anthropic import Anthropic
import json
import asyncio
from datetime import datetime
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
    SYSTEM_PROMPTS
)
from pprint import pformat

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('IRIS')

# Create necessary directories if they don't exist
os.makedirs("static/gallery", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Initialize gallery data file if it doesn't exist
gallery_file = "data/gallery_data.json"
if not os.path.exists(gallery_file):
    with open(gallery_file, "w") as f:
        json.dump([], f)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    asyncio.create_task(generator.start())
    yield
    # Shutdown
    generator.is_running = False

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")

class ArtGenerator:
    def __init__(self):
        self.viewers: Set[WebSocket] = set()
        self.current_drawing: Dict[str, Any] = None
        self.current_state: List[Dict[str, Any]] = []
        self.current_status = "waiting"
        self.current_phase = "initializing"
        self.current_idea = None
        self.is_running = False
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.generation_interval = 5  # seconds between generations

    async def get_art_idea(self) -> str:
        """Generate art idea using Claude"""
        try:
            logger.info("🤖 Requesting new art idea from Claude...")
            
            prompt = """Generate ONE visually striking geometric art concept.

Available Elements:
1. Circles & Arcs
   - Concentric, overlapping, or spiraling
   - Radii between 50-200px
   - Can be partial/segmented

2. Lines & Polygons
   - Straight lines at precise angles
   - Regular polygons (triangle to octagon)
   - Grid or mesh patterns

3. Waves & Curves
   - Sinusoidal waves with varying amplitude/frequency
   - Spiral patterns (Archimedean, logarithmic)
   - Lissajous curves

4. Mathematical Concepts:
   - Golden ratio (φ ≈ 1.618)
   - Symmetry (rotational, reflective)
   - Fibonacci sequence
   - Sacred geometry

Required Components:
- Center point at (400,200)
- At least 2 different element types
- Specific numerical values for:
  * Coordinates
  * Radii
  * Angles
  * Wave properties
- Clear geometric relationships
- Interesting intersections

Example Output:
"Three nested golden spirals (start radius 50px) at (400,200), rotated 120° apart, intersected by sine waves (amplitude 30px, frequency 0.05) at 45° angles, with connecting lines forming an equilateral triangle."

Return ONLY the geometric pattern description with exact numerical values."""

            message = await asyncio.to_thread(
                self.client.messages.create,
                model="claude-3-sonnet-20240229",
                max_tokens=1024,
                temperature=0.9,
                system="""You are a mathematical artist specializing in geometric patterns.
                Focus on creating visually striking compositions using precise mathematical relationships.
                Always include exact numerical values and clear geometric relationships.
                Think in terms of coordinates, angles, and mathematical functions.
                Return ONLY the pattern description, no explanations.""",
                messages=[{"role": "user", "content": prompt}]
            )
            
            idea = message.content[0].text.strip()
            logger.info(f"🎨 Generated idea: {idea}")
            return idea
            
        except Exception as e:
            logger.error(f"❌ Error getting art idea: {e}")
            return None

    async def get_drawing_instructions(self, idea: str) -> Dict[str, Any]:
        """Generate drawing instructions using Claude"""
        try:
            logger.info(f"🤖 Requesting drawing instructions for idea: '{idea}'")
            
            # Define expected structure
            expected_keys = ["description", "background", "elements"]
            
            prompt = """Generate drawing instructions as a JSON object.
DO NOT include markdown code blocks, backticks, or any other formatting.
Return ONLY the raw JSON object.

Example format:
{
    "description": "Pattern description",
    "background": "#000000",
    "elements": [
        {
            "type": "circle",
            "description": "Element description",
            "points": [[400, 200], [450, 200]],
            "color": "#00ff00",
            "stroke_width": 2,
            "animation_speed": 0.02,
            "closed": true
        }
    ]
}

Rules:
1. Return ONLY the JSON object above
2. No markdown, no code blocks, no explanations
3. Pre-calculate all coordinates
4. Maximum 5 elements
5. Maximum 32 points per circle
6. Maximum 20 points per wave
7. All coordinates within 800x400 canvas
8. animation_speed between 0.01 and 0.05
9. stroke_width between 1 and 3
10. Valid hex colors only"""

            logger.info("🎯 Sending prompt to Claude...")
            message = await asyncio.to_thread(
                self.client.messages.create,
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                temperature=0.7,
                system="""You are a JSON generator that outputs ONLY raw JSON objects.
                Never use markdown formatting or code blocks.
                Never include explanations or comments.
                Return ONLY the requested JSON structure.""",
                messages=[{
                    "role": "user", 
                    "content": prompt + f"\n\nGenerate JSON for this idea: {idea}"
                }]
            )

            try:
                # Clean up response - remove any markdown or code blocks
                response_text = message.content[0].text.strip()
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                response_text = response_text.strip()
                
                logger.info("📝 Raw response:")
                logger.info(response_text)

                # Parse JSON
                instructions = json.loads(response_text)
                logger.info("📝 Parsed instructions:")
                logger.info(pformat(instructions, indent=2))

                # Validate structure
                if not isinstance(instructions, dict) or not all(k in instructions for k in expected_keys):
                    raise ValueError("Response missing required keys")

                # Validate and normalize elements
                if not instructions["elements"]:
                    raise ValueError("No elements provided")

                if len(instructions["elements"]) > 5:
                    logger.warning(f"⚠️ Too many elements ({len(instructions['elements'])}), truncating to 5")
                    instructions["elements"] = instructions["elements"][:5]

                # Process each element
                for i, element in enumerate(instructions["elements"]):
                    # Validate required fields
                    required_fields = ["type", "description", "points", "color", "stroke_width", "animation_speed", "closed"]
                    if not all(k in element for k in required_fields):
                        raise ValueError(f"Element {i} missing required fields")

                    # Normalize points based on type
                    if element["type"] == "circle":
                        if len(element["points"]) > 32:
                            step = len(element["points"]) // 32
                            element["points"] = element["points"][::step][:32]
                    elif element["type"] == "wave":
                        if len(element["points"]) > 20:
                            step = len(element["points"]) // 20
                            element["points"] = element["points"][::step][:20]
                    elif element["type"] == "line":
                        element["points"] = element["points"][:2]

                    # Ensure coordinates are within canvas
                    element["points"] = [
                        [max(0, min(800, x)), max(0, min(400, y))]
                        for x, y in element["points"]
                    ]

                    # Normalize other values
                    element["stroke_width"] = max(1, min(3, element["stroke_width"]))
                    element["animation_speed"] = max(0.01, min(0.05, element["animation_speed"]))

                logger.info("✅ Validation and normalization complete")
                return instructions

            except json.JSONDecodeError as e:
                logger.error(f"❌ Invalid JSON response: {e}")
                logger.error(f"Raw response: {message.content[0].text}")
                return None

        except Exception as e:
            logger.error(f"❌ Error getting drawing instructions: {e}")
            return None

    async def broadcast_state(self, data: Dict[str, Any]):
        """Broadcast state update to all viewers"""
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

        await self.broadcast_state({
            "type": "display_update",
            "status": self.current_status,
            "phase": self.current_phase,
            "idea": self.current_idea,
            "timestamp": datetime.now().isoformat(),
            "progress": progress
        })

    async def execute_drawing(self, instructions: Dict[str, Any]):
        """Execute drawing instructions"""
        try:
            logger.info("🎨 Starting drawing execution...")
            total_elements = len(instructions["elements"])
            total_points = sum(len(element["points"]) for element in instructions["elements"])
            points_drawn = 0
            
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
                
                if not points:
                    logger.warning(f"⚠️ Element {i} has no points, skipping")
                    continue
                
                # Calculate progress
                element_progress = 0
                points_per_element = len(points)
                
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
                
                stop_cmd = {"type": "stopDrawing"}
                self.current_state.append(stop_cmd)
                await self.broadcast_state(stop_cmd)
                logger.info(f"✅ Element {i} completed")
            
            logger.info("🎉 Drawing completed successfully")
            
            # Request canvas data for gallery
            logger.info("📸 Requesting canvas data for gallery...")
            await self.broadcast_state({"type": "request_canvas_data"})
            
        except Exception as e:
            logger.error(f"❌ Error executing drawing: {e}")
            raise

    async def start(self):
        """Main generation loop"""
        self.is_running = True
        logger.info("🚀 Art generator started")
        
        while self.is_running:
            try:
                # Generate new art
                logger.info("🤔 Starting new generation cycle...")
                await self.update_status("thinking", "ideation")
                idea = await self.get_art_idea()
                
                if idea:
                    logger.info("✨ Got new idea, generating drawing instructions...")
                    await self.update_status("drawing", "generation", idea)
                    instructions = await self.get_drawing_instructions(idea)
                    
                    if instructions:
                        logger.info("🎨 Starting drawing execution...")
                        self.current_drawing = {
                            "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                            "idea": idea,
                            "instructions": instructions,
                            "timestamp": datetime.now().isoformat()
                        }
                        await self.execute_drawing(instructions)
                        logger.info("✅ Drawing completed")
                        await self.update_status("completed", "display", idea)
                    else:
                        logger.error("❌ Failed to generate valid drawing instructions")
                
                # Wait before next generation
                logger.info(f"⏳ Waiting {self.generation_interval} seconds before next generation...")
                await asyncio.sleep(self.generation_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in art generation: {e}")
                await self.update_status("error", "error")
                await asyncio.sleep(2)

    async def save_to_gallery(self, canvas_data: str):
        """Save drawing to gallery"""
        try:
            if not self.current_drawing:
                return False

            # Remove data URL prefix and decode
            img_data = canvas_data.split(',')[1]
            img_bytes = base64.b64decode(img_data)
            
            # Save image file
            filename = f"drawing_{self.current_drawing['id']}.png"
            filepath = os.path.join("static/gallery", filename)
            
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            
            # Save metadata
            gallery_file = "data/gallery_data.json"
            gallery_data = []
            
            if os.path.exists(gallery_file):
                with open(gallery_file, "r") as f:
                    gallery_data = json.load(f)
            
            gallery_data.append({
                "id": self.current_drawing["id"],
                "filename": filename,
                "description": self.current_drawing["idea"],
                "timestamp": self.current_drawing["timestamp"],
                "price": "100,000 $IRIS"
            })
            
            with open(gallery_file, "w") as f:
                json.dump(gallery_data, f, indent=2)
                
            logger.info(f"Saved to gallery: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to gallery: {e}")
            return False

# Create global art generator
generator = ArtGenerator()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connection_id = f"ws_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    logger.info(f"New viewer connected: {connection_id}")
    
    try:
        # Add to viewers
        generator.viewers.add(websocket)
        
        # Broadcast updated viewer count to all clients
        await generator.broadcast_state({
            "type": "display_update",
            "viewers": len(generator.viewers)
        })
        
        # Send current state if available
        if generator.current_state:
            try:
                for cmd in generator.current_state:
                    await websocket.send_json(cmd)
                    await asyncio.sleep(0.02)
            except Exception as e:
                logger.error(f"Error sending initial state: {e}")
                
        # Keep connection alive and handle incoming messages
        while True:
            try:
                msg = await websocket.receive_json()
                if msg.get('type') == 'canvas_data':
                    await generator.save_to_gallery(msg.get('data', ''))
                elif msg.get('type') == 'subscribe_status':
                    # Send immediate status update
                    await websocket.send_json({
                        "type": "display_update",
                        "status": generator.current_status,
                        "phase": generator.current_phase,
                        "idea": generator.current_idea,
                        "timestamp": datetime.now().isoformat(),
                        "viewers": len(generator.viewers),
                        "is_running": generator.is_running,
                        "progress": generator.current_progress if hasattr(generator, 'current_progress') else None
                    })
            except WebSocketDisconnect:
                logger.info(f"Viewer disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                break
                
    except Exception as e:
        logger.error(f"Error in connection {connection_id}: {e}")
    finally:
        if websocket in generator.viewers:
            generator.viewers.remove(websocket)
            # Broadcast updated viewer count when someone disconnects
            await generator.broadcast_state({
                "type": "display_update",
                "viewers": len(generator.viewers)
            })

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

@app.get("/api/gallery")
async def get_gallery(sort: str = "new"):
    """Get all gallery items with sorting"""
    try:
        gallery_file = "data/gallery_data.json"
        if os.path.exists(gallery_file):
            with open(gallery_file, "r") as f:
                items = json.load(f)
            
            # Initialize votes if not present
            for item in items:
                if "votes" not in item:
                    item["votes"] = 0
            
            # Verify files exist and sort
            valid_items = [item for item in items 
                         if os.path.exists(os.path.join("static/gallery", item["filename"]))]
            
            if sort == "votes":
                valid_items.sort(key=lambda x: x.get("votes", 0), reverse=True)
            else:  # sort by new (default)
                valid_items.sort(key=lambda x: x["timestamp"], reverse=True)
                
            return valid_items
        return []
    except Exception as e:
        logger.error(f"Error loading gallery: {e}")
        return []

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

@app.post("/api/gallery/{image_id}/upvote")
async def upvote_image(image_id: str):
    """Upvote a gallery image"""
    try:
        gallery_file = "data/gallery_data.json"
        if os.path.exists(gallery_file):
            with open(gallery_file, "r") as f:
                items = json.load(f)
            
            # Find and update the image
            for item in items:
                if item["id"] == image_id:
                    # Initialize votes if not present
                    if "votes" not in item:
                        item["votes"] = 0
                    item["votes"] += 1
                    
                    # Save updated data
                    with open(gallery_file, "w") as f:
                        json.dump(items, f, indent=2)
                    return {"success": True, "votes": item["votes"]}
            
            raise HTTPException(status_code=404, detail="Image not found")
    except Exception as e:
        logger.error(f"Error upvoting image: {e}")
        raise HTTPException(status_code=500, detail="Error processing upvote")

if __name__ == "__main__":
    import uvicorn
    print(f"\n=== {AI_NAME} Drawing System v2.0 ===")
    print(f"{AI_TAGLINE}")
    print("Open http://localhost:8000 in your browser")
    print("================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)