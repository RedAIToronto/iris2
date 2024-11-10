from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from anthropic import Anthropic
import json
import asyncio
import math
import random
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from config import (
    HTML_TEMPLATE, 
    ANTHROPIC_API_KEY,
    DRAWING_SCHEMA,
    AI_NAME,
    AI_TAGLINE
)

# Initialize FastAPI and Anthropic
app = FastAPI()
anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

# Utility Classes
class RetryHandler:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.current_attempt = 0
    
    def can_retry(self) -> bool:
        return self.current_attempt < self.max_retries
    
    def increment(self):
        self.current_attempt += 1
    
    def reset(self):
        self.current_attempt = 0

class DrawingCommand:
    def __init__(self, cmd_type: str, x: float = 0, y: float = 0, **kwargs):
        self.type = cmd_type
        self.x = x
        self.y = y
        self.extra = kwargs

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "timestamp": datetime.now().isoformat(),
            **self.extra
        }

# Main Drawing Bot Class
class SmartDrawingBot:
    def __init__(self):
        # Basic configuration
        self.canvas_width = 800
        self.canvas_height = 400
        self.center_x = self.canvas_width / 2
        self.center_y = self.canvas_height / 2
        
        # Handlers and state
        self.retry_handler = RetryHandler(max_retries=3)
        self.current_drawing = None
        
        # Initialize Anthropic client
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = "claude-3-5-sonnet-20241022"

    def create_system_prompt(self) -> str:
        """Create the system prompt for Claude"""
        return f"""You are IRIS (Interactive Recursive Imagination System), a precise geometric artist.
        
        DRAWING CAPABILITIES:
        1. Circles:
           - Center at ({self.center_x}, {self.center_y})
           - Variable radius (10-200)
           - Generate points: x = centerX + radius * cos(angle), y = centerY + radius * sin(angle)
        
        2. Lines:
           - Start and end points within canvas
           - Can create grids, rays, or geometric shapes
        
        3. Waves:
           - Sinusoidal waves with controlled amplitude
           - Formula: y = centerY + amplitude * sin(frequency * x)
        
        CANVAS SPECIFICATIONS:
        - Width: {self.canvas_width}px
        - Height: {self.canvas_height}px
        - Origin (0,0) at top-left
        - Center point: ({self.center_x}, {self.center_y})
        
        Return ONLY valid JSON matching this schema:
        {json.dumps(DRAWING_SCHEMA, indent=2)}"""

    async def generate_creative_idea(self) -> str:
        """Generate a creative drawing idea using Claude"""
        try:
            message = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                temperature=0.7,
                system="""You are IRIS, an AI artist specializing in geometric patterns.
                Your task is to generate ONE simple but elegant geometric drawing idea.
                
                AVAILABLE ELEMENTS:
                - Circles (centered at 400,200)
                - Lines (straight paths between points)
                - Waves (sinusoidal patterns)
                - Spirals (Archimedean or logarithmic)
                
                RULES:
                1. Keep it mathematically precise
                2. Use 2-3 element types maximum
                3. Focus on visual harmony
                4. Consider the 800x400 canvas size
                
                RESPOND WITH ONLY THE DRAWING IDEA IN ONE CLEAR SENTENCE.""",
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": "Generate a geometric drawing idea"}]
                }]
            )
            return message.content[0].text.strip()

        except Exception as e:
            print(f"Idea generation error: {e}")
            return "Concentric circles with radiating lines"

    async def get_drawing_instructions(self, idea: str) -> Dict[str, Any]:
        """Convert creative idea into precise drawing instructions using Claude"""
        while True:
            try:
                print(f"\nGenerating instructions for: {idea}")
                print(f"Attempt {self.retry_handler.current_attempt + 1}/{self.retry_handler.max_retries}")

                message = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=2048,
                    temperature=0.5,
                    system="""You are IRIS, a precise geometric pattern generator.
                    Given a drawing idea, you must generate EXACT JSON instructions.
                    
                    CANVAS:
                    - Width: 800px, Height: 400px
                    - Center: (400, 200)
                    - Coordinates: (0,0) at top-left
                    
                    MATHEMATICAL FORMULAS:
                    - Circles: x = 400 + radius * cos(angle), y = 200 + radius * sin(angle)
                    - Waves: y = 200 + amplitude * sin(frequency * x)
                    - Spirals: r = a + b * angle, then convert to x,y
                    
                    CRITICAL RULES:
                    1. Generate EXACT numerical coordinates
                    2. Keep ALL points within canvas bounds
                    3. Use proper hex colors
                    4. Include ALL required fields
                    5. Return ONLY valid JSON
                    
                    RESPOND WITH ONLY THE JSON OBJECT, NO OTHER TEXT.""",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"""Generate precise drawing instructions for this idea: {idea}
                        
                        Required JSON structure:
                        {{
                            "description": "Brief description",
                            "background": "#hex_color",
                            "elements": [
                                {{
                                    "type": "circle|line|wave|spiral",
                                    "description": "Element purpose",
                                    "points": [[x1,y1], [x2,y2], ...],
                                    "color": "#hex_color",
                                    "stroke_width": 1-3,
                                    "animation_speed": 0.01-0.05,
                                    "closed": true/false
                                }}
                            ]
                        }}"""}
                    ]
                }]
            )

            # Parse and validate the response
            try:
                instructions = self.parse_claude_response(message.content[0].text)
                validation_result = self.validate_against_schema(instructions)
                
                if validation_result is True:
                    print("Instructions validated successfully")
                    return instructions
                else:
                    raise ValueError(f"Validation failed: {validation_result}")

            except Exception as e:
                print(f"Error in attempt {self.retry_handler.current_attempt + 1}: {e}")
                if not self.retry_handler.can_retry():
                    print("Maximum retries reached, using fallback pattern")
                    return self.generate_fallback_pattern()
                self.retry_handler.increment()
                await asyncio.sleep(1)

    # Drawing Execution Methods
    async def execute_drawing(self, websocket: WebSocket, instructions: Dict[str, Any], idea: str):
        """Execute the drawing instructions"""
        try:
            total_elements = len(instructions.get("elements", []))
            await self.update_status(websocket, idea=idea, current_action="Starting new drawing")

            # Setup canvas
            await self.setup_canvas(websocket, instructions)
            
            # Draw elements
            for i, element in enumerate(instructions.get("elements", [])):
                await self.draw_element(websocket, element, i, total_elements, idea)

            # Finalize drawing
            await self.update_status(
                websocket,
                idea=idea,
                current_action="Drawing completed!",
                progress=100
            )

        except Exception as e:
            print(f"Drawing Error: {e}")
            await self.update_status(websocket, current_action=f"Error: {str(e)}")

    # Helper Methods
    def parse_claude_response(self, content: str) -> Dict[str, Any]:
        """Parse Claude's response and extract JSON"""
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            raise ValueError("No JSON found in response")
        return json.loads(json_match.group(0))

    async def setup_canvas(self, websocket: WebSocket, instructions: Dict[str, Any]):
        """Setup the canvas with background"""
        await websocket.send_json(DrawingCommand("clear").to_dict())
        await websocket.send_json(DrawingCommand(
            "setBackground",
            color=instructions.get("background", "#000000")
        ).to_dict())

    async def draw_element(self, websocket: WebSocket, element: Dict[str, Any], 
                          index: int, total: int, idea: str):
        """Draw a single element"""
        try:
            points = element.get("points", [])
            if not points:
                return

            progress = (index / total) * 100
            await self.update_status(
                websocket,
                idea=idea,
                current_action=f"Drawing {element['description']}",
                progress=progress
            )

            # Start drawing
            await websocket.send_json(DrawingCommand(
                "startDrawing",
                x=points[0][0],
                y=points[0][1],
                color=element.get("color", "#00ff00"),
                width=element.get("stroke_width", 2),
                element_description=element.get("description", "")
            ).to_dict())

            # Draw points
            for x, y in points[1:]:
                await websocket.send_json(DrawingCommand("draw", x=x, y=y).to_dict())
                await asyncio.sleep(element.get("animation_speed", 0.02))

            # Close shape if needed
            if element.get("closed", False) and len(points) > 2:
                await websocket.send_json(DrawingCommand(
                    "draw",
                    x=points[0][0],
                    y=points[0][1]
                ).to_dict())

            await websocket.send_json(DrawingCommand("stopDrawing").to_dict())
            await asyncio.sleep(0.1)

        except Exception as e:
            print(f"Error drawing element {index}: {e}")

    # ... (keep other existing methods like validate_against_schema, generate_fallback_pattern)

    # Add this method to the SmartDrawingBot class
    async def run(self, websocket: WebSocket):
        """Main bot loop for generating and drawing patterns"""
        try:
            while True:
                try:
                    # Generate new idea
                    idea = await self.generate_creative_idea()
                    print(f"\n{AI_NAME} decided to draw: {idea}")
                    
                    # Reset retry handler for new attempt
                    self.retry_handler.reset()
                    
                    # Get and execute drawing instructions
                    instructions = await self.get_drawing_instructions(idea)
                    if instructions:
                        print(f"Drawing: {instructions['description']}")
                        await self.execute_drawing(websocket, instructions, idea)
                    
                    # Pause between drawings
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    print(f"Loop Error: {e}")
                    await self.update_status(
                        websocket,
                        current_action="Error occurred, retrying...",
                        error=str(e)
                    )
                    await asyncio.sleep(1)
                    
        except WebSocketDisconnect:
            print("WebSocket disconnected")
            raise
        except Exception as e:
            print(f"{AI_NAME} Error: {e}")

    # Also add the missing update_status method
    async def update_status(self, websocket: WebSocket, **kwargs):
        """Update frontend with current status"""
        status_data = {
            "type": "ai_status",
            "retrying": self.retry_handler.current_attempt > 0,
            "attempt": self.retry_handler.current_attempt + 1,
            "max_retries": self.retry_handler.max_retries,
            **kwargs
        }
        await websocket.send_json(status_data)

    # And add the generate_fallback_pattern method
    def generate_fallback_pattern(self) -> Dict[str, Any]:
        """Generate a simple fallback pattern when other methods fail"""
        return {
            "description": "Simple geometric pattern (fallback)",
            "background": "#000000",
            "elements": [
                {
                    "type": "circle",
                    "description": "Centered circle",
                    "points": [[self.center_x + 100 * math.cos(t), self.center_y + 100 * math.sin(t)] 
                              for t in [2 * math.pi * i / 36 for i in range(37)]],
                    "color": "#00ff00",
                    "stroke_width": 2,
                    "animation_speed": 0.02,
                    "closed": True
                }
            ]
        }

    # Add this method to SmartDrawingBot class
    def validate_against_schema(self, data: Dict[str, Any]) -> Union[bool, str]:
        """Validate data against our schema"""
        try:
            # Check basic structure
            if not isinstance(data, dict):
                return "Response must be an object"
            
            # Required fields
            for field in ["description", "background", "elements"]:
                if field not in data:
                    return f"Missing required field: {field}"
            
            # Background color format
            if not re.match(r'^#[0-9A-Fa-f]{6}$', data["background"]):
                return "Invalid background color format"
            
            # Elements validation
            if not isinstance(data["elements"], list) or not data["elements"]:
                return "Elements must be a non-empty array"
            
            for i, element in enumerate(data["elements"]):
                # Check element structure
                if not isinstance(element, dict):
                    return f"Element {i} must be an object"
                
                # Required element fields
                element_fields = [
                    "type", "description", "points", "color",
                    "stroke_width", "animation_speed", "closed"
                ]
                for field in element_fields:
                    if field not in element:
                        return f"Element {i} missing required field: {field}"
                
                # Type validation
                if element["type"] not in ["circle", "line", "wave", "spiral"]:
                    return f"Element {i} has invalid type: {element['type']}"
                
                # Points validation
                points = element["points"]
                if not isinstance(points, list) or not points:
                    return f"Element {i} must have non-empty points array"
                
                for j, point in enumerate(points):
                    if not isinstance(point, list) or len(point) != 2:
                        return f"Element {i}, point {j} must be [x,y] array"
                    if not all(isinstance(coord, (int, float)) and 0 <= coord <= (800 if idx == 0 else 400)
                          for idx, coord in enumerate(point)):
                        return f"Element {i}, point {j} has invalid coordinates"
                
                # Color validation
                if not re.match(r'^#[0-9A-Fa-f]{6}$', element["color"]):
                    return f"Element {i} has invalid color format"
                
                # Numeric validations
                if not isinstance(element["stroke_width"], (int, float)) or not 1 <= element["stroke_width"] <= 3:
                    return f"Element {i} has invalid stroke_width"
                
                if not isinstance(element["animation_speed"], (int, float)) or not 0.01 <= element["animation_speed"] <= 0.05:
                    return f"Element {i} has invalid animation_speed"
                
                if not isinstance(element["closed"], bool):
                    return f"Element {i} has invalid closed value"
            
            return True

        except Exception as e:
            return f"Validation error: {str(e)}"

# Connection Management
class ConnectionManager:
    def __init__(self):
        self.bot = SmartDrawingBot()
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

# FastAPI Routes
manager = ConnectionManager()

@app.get("/")
async def home():
    return HTMLResponse(HTML_TEMPLATE)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await manager.bot.run(websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Main Entry Point
if __name__ == "__main__":
    import uvicorn
    print(f"\n=== {AI_NAME} Drawing System v2.0 ===")
    print(f"{AI_TAGLINE}")
    print("Open http://localhost:8000 in your browser")
    print("================================\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)