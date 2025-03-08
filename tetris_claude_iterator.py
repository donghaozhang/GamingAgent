#!/usr/bin/env python
"""
Tetris Claude Iterator

This script creates a simple loop to:
1. Capture the Tetris game screen
2. Call Claude API to suggest moves
3. Output the response
4. Wait for space key press to continue
5. Repeat the process

Usage:
    python tetris_claude_iterator.py

Requirements:
    - PIL (Pillow)
    - pyautogui
    - pynput
    - requests
    - anthropic (pip install anthropic)
"""

import os
import sys
import time
import base64
import json
import re
import io
import traceback
import tempfile
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import pyautogui
from pynput import keyboard
import anthropic
import subprocess

# Try to import from local module if available
try:
    from create_tetris_animation import create_animation, find_images
    CREATE_ANIMATION_AVAILABLE = True
except ImportError:
    CREATE_ANIMATION_AVAILABLE = False

# Try to load optional dependencies
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Default values (can be overridden by .env or command-line args)
MODEL = os.environ.get('CLAUDE_MODEL', 'claude-3-7-sonnet-20250219')
OUTPUT_DIR = os.environ.get('OUTPUT_DIR', '.')
TETRIS_WINDOW_TITLE = os.environ.get('TETRIS_WINDOW_TITLE', None)

def load_env_file():
    """Load environment variables from .env file if available"""
    if load_dotenv:
        # Try to load from .env file
        if os.path.exists('.env'):
            print("Loading environment variables from .env file")
            load_dotenv('.env')
            
            # Check if key variables were loaded
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if api_key:
                print("Successfully loaded ANTHROPIC_API_KEY")
            else:
                print("Warning: ANTHROPIC_API_KEY not found in .env file")
                
            # Also check for OpenAI key
            openai_key = os.environ.get('OPENAI_API_KEY')
            if openai_key:
                print("Loaded OPENAI_API_KEY from .env file")
                
            # Check for other API keys
            for key in ['GEMINI_API_KEY', 'OPENROUTER_API_KEY', 'OPENROUTER_MODEL']:
                if os.environ.get(key):
                    print(f"Loaded {key} from .env file")
    else:
        print("python-dotenv not installed. Skipping .env file loading.")
        print("Install with: pip install python-dotenv")

# Load environment variables from .env file
load_env_file()

class TetrisClaudeIterator:
    def __init__(self, model=None, output_dir=None, window_title=None, save_responses=False):
        """Initialize the TetrisClaudeIterator"""
        # Initialize Claude API
        self.model = model or "claude-3-7-sonnet-20250219"
        
        # Set up simulated mode flag
        self.simulated_mode = True  # Default to simulated mode
        self.simulated_board = None
        self.board = [[0 for _ in range(10)] for _ in range(20)]
        self.current_piece = None
        self.next_piece = None
        
        # Initialize output directories
        self.session_dir = os.path.join(output_dir or "game_logs", f"session_{time.strftime('%Y%m%d_%H%M%S')}")
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        self.responses_dir = os.path.join(self.session_dir, "responses")
        self.log_file = os.path.join(self.session_dir, "log.txt")
        
        # Create output directories
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # Save responses flag
        self.save_responses = save_responses
        
        # Window title for finding Tetris window
        self.window_title = window_title
        self.window_rect = None
        
        # Set up tracking variables
        self.iteration = 0
        self.stop_flag = False
        self.quit_with_q = False
        
        # Auto-space settings (to avoid pressing space after each iteration)
        self.max_auto_spaces = 4  # Max number of automatic spaces, 0 to disable
        self.auto_spaces_used = 0
        
        # Animation settings
        self.auto_gif = True     # Auto-generate GIF when quitting
        self.gif_fps = 2         # Frames per second for GIF

        # Load prompt templates
        self.system_prompt = """You are a Tetris game-playing AI assistant. Your job is to analyze the given Tetris game state image and provide the best possible move using PyAutoGUI commands."""
        
        self.instruction_prompt = """Analyze this Tetris game board and recommend the optimal next move(s).
I'm using a simulated Tetris environment that can be controlled with PyAutoGUI commands:

### Available commands:
- pyautogui.press("left"): move piece left
- pyautogui.press("right"): move piece right
- pyautogui.press("up"): rotate piece clockwise
- pyautogui.press("down"): move piece down
- space: drop piece immediately

### Strategies and Caveats:
0. Clear the horizontal rows as soon as possible.
1. If you see a chance to clear lines, do it
2. Prioritize keeping the stack flat and balanced
3. Avoid creating holes 
4. Only control the current piece visible at the top

### Output Format:
- Output ONLY the Python code for PyAutoGUI commands, e.g. `pyautogui.press("left")`
- Include brief comments for each action
- Do not print anything else besides these Python commands

Here's the current Tetris game state image:"""

        # Initialize the simulated board
        if self.simulated_mode:
            self.create_simple_tetris_board()

    def log_message(self, message):
        """Log a message to the console and log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] {message}"
        
        # Print to console
        print(log_entry)
        
        # Save to log file
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

    def find_tetris_window(self):
        """Find the Tetris window by title or default to the entire screen"""
        try:
            # If a specific window title is provided, try to find it
            if self.window_title:
                windows = pyautogui.getWindowsWithTitle(self.window_title)
                if windows:
                    window = windows[0]
                    self.log_message(f"Found Tetris window: {window.title} at {window.left}, {window.top}, {window.width}, {window.height}")
                    # Set window rectangle
                    self.window_rect = (window.left, window.top, window.width, window.height)
                    return
            
            # List all available windows for debugging
            self.log_message("Available windows:")
            for window in pyautogui.getAllWindows():
                self.log_message(f"  - '{window.title}' at {window.left}, {window.top}, {window.width}, {window.height}")
            
            # Default to a standard size for the left half of the screen
            self.window_rect = (0, 0, 768, 1080)  # Default to left side of screen
            
        except Exception as e:
            self.log_message(f"Error finding Tetris window: {str(e)}")
            traceback.print_exc()
            # Default to a standard size for the left half of the screen
            self.window_rect = (0, 0, 768, 1080)  # Default to left side of screen

    def create_simulated_tetris_board(self, board_state=None, current_piece=None, next_piece=None):
        """Create a simulated Tetris board as an image for visualization"""
        # Define dimensions and colors
        cell_size = 30
        board_width = 10
        board_height = 20
        sidebar_width = 200
        
        # Define vibrant colors for pieces (improved color scheme)
        colors = {
            0: (0, 0, 0),       # Background (black)
            1: (0, 255, 255),    # I-piece (cyan)
            2: (0, 0, 255),      # J-piece (blue)
            3: (255, 165, 0),    # L-piece (orange)
            4: (255, 255, 0),    # O-piece (yellow)
            5: (0, 255, 0),      # S-piece (green)
            6: (128, 0, 128),    # T-piece (purple)
            7: (255, 0, 0)       # Z-piece (red)
        }
        
        # Define piece shapes for all rotations
        piece_shapes = {
            'I': [
                [(0, 0), (0, 1), (0, 2), (0, 3)],     # Horizontal
                [(0, 0), (1, 0), (2, 0), (3, 0)]      # Vertical
            ],
            'J': [
                [(0, 0), (1, 0), (1, 1), (1, 2)],     # ┌
                [(0, 0), (0, 1), (1, 0), (2, 0)],     # ┘
                [(0, 0), (0, 1), (0, 2), (1, 2)],     # └
                [(0, 1), (1, 1), (2, 1), (2, 0)]      # ┐
            ],
            'L': [
                [(0, 2), (1, 0), (1, 1), (1, 2)],     # ┐
                [(0, 0), (1, 0), (2, 0), (2, 1)],     # └
                [(0, 0), (0, 1), (0, 2), (1, 0)],     # ┌
                [(0, 0), (0, 1), (1, 1), (2, 1)]      # ┘
            ],
            'O': [
                [(0, 0), (0, 1), (1, 0), (1, 1)]      # Square (single rotation)
            ],
            'S': [
                [(0, 1), (0, 2), (1, 0), (1, 1)],     # Horizontal
                [(0, 0), (1, 0), (1, 1), (2, 1)]      # Vertical
            ],
            'T': [
                [(0, 1), (1, 0), (1, 1), (1, 2)],     # ┬
                [(0, 0), (1, 0), (1, 1), (2, 0)],     # ├
                [(0, 0), (0, 1), (0, 2), (1, 1)],     # ┴
                [(0, 1), (1, 0), (1, 1), (2, 1)]      # ┤
            ],
            'Z': [
                [(0, 0), (0, 1), (1, 1), (1, 2)],     # Horizontal
                [(0, 1), (1, 0), (1, 1), (2, 0)]      # Vertical
            ]
        }
        
        # Map piece type to color index
        piece_colors = {
            'I': 1,  # cyan
            'J': 2,  # blue
            'L': 3,  # orange
            'O': 4,  # yellow
            'S': 5,  # green
            'T': 6,  # purple
            'Z': 7   # red
        }
        
        # Store the board state and pieces for later use
        if board_state is not None:
            self.board = board_state
        if current_piece is not None:
            self.current_piece = current_piece
        if next_piece is not None:
            self.next_piece = next_piece
        
        # If any are still None, initialize with defaults
        if self.board is None:
            self.board = [[0 for _ in range(10)] for _ in range(20)]
        if self.current_piece is None:
            self.current_piece = {
                'type': 'T', 
                'x': 4, 
                'y': 0, 
                'rotation': 0
            }
        if self.next_piece is None:
            self.next_piece = {'type': 'I'}
        
        # Create a black board with gridlines
        width = board_width * cell_size + sidebar_width
        height = board_height * cell_size
        board_image = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(board_image)
        
        # Draw grid lines (slightly brighter)
        grid_color = (40, 40, 40)  # Dark gray
        for i in range(board_width + 1):
            draw.line([(i * cell_size, 0), (i * cell_size, height)], fill=grid_color)
        for i in range(board_height + 1):
            draw.line([(0, i * cell_size), (board_width * cell_size, i * cell_size)], fill=grid_color)
        
        # Draw board state (existing pieces)
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell > 0:
                    # Draw filled cell with a slight 3D effect
                    cell_color = colors[cell]
                    highlight = tuple(min(c + 60, 255) for c in cell_color)
                    shadow = tuple(max(c - 60, 0) for c in cell_color)
                    
                    # Fill cell
                    draw.rectangle(
                        [(x * cell_size + 1, y * cell_size + 1), 
                         ((x + 1) * cell_size - 1, (y + 1) * cell_size - 1)], 
                        fill=cell_color
                    )
                    
                    # Top and left edges (highlight)
                    draw.line([(x * cell_size + 1, y * cell_size + 1), ((x+1) * cell_size - 1, y * cell_size + 1)], fill=highlight, width=2)
                    draw.line([(x * cell_size + 1, y * cell_size + 1), (x * cell_size + 1, (y+1) * cell_size - 1)], fill=highlight, width=2)
                    
                    # Bottom and right edges (shadow)
                    draw.line([(x * cell_size + 1, (y+1) * cell_size - 1), ((x+1) * cell_size - 1, (y+1) * cell_size - 1)], fill=shadow, width=2)
                    draw.line([((x+1) * cell_size - 1, y * cell_size + 1), ((x+1) * cell_size - 1, (y+1) * cell_size - 1)], fill=shadow, width=2)
        
        # Draw current piece if it exists
        if self.current_piece:
            piece_type = self.current_piece['type']
            piece_x = self.current_piece['x']
            piece_y = self.current_piece['y']
            rotation = self.current_piece.get('rotation', 0)
            
            # Get color and shape based on type and rotation
            color_idx = piece_colors.get(piece_type, 6)  # Default to purple (T) if unknown
            color = colors[color_idx]
            
            # Ensure rotation is valid for the piece type
            max_rotations = len(piece_shapes[piece_type])
            rotation = rotation % max_rotations
            
            # Get the shape for this rotation
            shape = piece_shapes[piece_type][rotation]
            
            # Draw each cell of the piece
            for dx, dy in shape:
                # Calculate actual position
                px = piece_x + dx
                py = piece_y + dy
                
                # Only draw if within the board boundaries
                if 0 <= px < board_width and 0 <= py < board_height:
                    # Draw filled cell with 3D effect
                    highlight = tuple(min(c + 60, 255) for c in color)
                    shadow = tuple(max(c - 60, 0) for c in color)
                    
                    # Fill cell
                    draw.rectangle(
                        [(px * cell_size + 1, py * cell_size + 1), 
                         ((px + 1) * cell_size - 1, (py + 1) * cell_size - 1)], 
                        fill=color
                    )
                    
                    # Top and left edges (highlight)
                    draw.line([(px * cell_size + 1, py * cell_size + 1), ((px+1) * cell_size - 1, py * cell_size + 1)], fill=highlight, width=2)
                    draw.line([(px * cell_size + 1, py * cell_size + 1), (px * cell_size + 1, (py+1) * cell_size - 1)], fill=highlight, width=2)
                    
                    # Bottom and right edges (shadow)
                    draw.line([(px * cell_size + 1, (py+1) * cell_size - 1), ((px+1) * cell_size - 1, (py+1) * cell_size - 1)], fill=shadow, width=2)
                    draw.line([((px+1) * cell_size + 1, py * cell_size + 1), ((px+1) * cell_size - 1, (py+1) * cell_size - 1)], fill=shadow, width=2)
        
        # Draw sidebar
        sidebar_start = board_width * cell_size
        draw.rectangle([(sidebar_start, 0), (width, height)], fill=(20, 20, 20))
        
        # Draw labels
        try:
            font = ImageFont.truetype("arial.ttf", 24)
            small_font = ImageFont.truetype("arial.ttf", 18)
        except:
            # Fallback to default font if Arial is not available
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Draw "NEXT" label
        draw.text((sidebar_start + 20, 10), "NEXT", fill=(255, 255, 255), font=font)
        
        # Draw next piece preview
        next_type = self.next_piece.get('type', 'I')
        next_color = colors[piece_colors.get(next_type, 1)]
        next_shape = piece_shapes[next_type][0]  # Use the first rotation
        
        # Draw next piece centered in the preview area
        preview_cell_size = 25
        preview_x = sidebar_start + 60
        preview_y = 50
        
        # Determine the dimensions of the piece
        min_dx = min(dx for dx, _ in next_shape)
        max_dx = max(dx for dx, _ in next_shape)
        min_dy = min(dy for _, dy in next_shape)
        max_dy = max(dy for _, dy in next_shape)
        width_cells = max_dx - min_dx + 1
        height_cells = max_dy - min_dy + 1
        
        # Calculate center offsets
        offset_x = (4 - width_cells) // 2  # Assuming 4x4 preview area
        offset_y = (2 - height_cells) // 2
        
        # Draw the next piece
        for dx, dy in next_shape:
            # Adjust for center and size
            px = preview_x + (dx + offset_x) * preview_cell_size
            py = preview_y + (dy + offset_y) * preview_cell_size
            
            # Draw with 3D effect
            highlight = tuple(min(c + 60, 255) for c in next_color)
            shadow = tuple(max(c - 60, 0) for c in next_color)
            
            # Fill cell
            draw.rectangle(
                [(px, py), (px + preview_cell_size, py + preview_cell_size)],
                fill=next_color
            )
            
            # 3D effect
            draw.line([(px, py), (px + preview_cell_size, py)], fill=highlight, width=2)
            draw.line([(px, py), (px, py + preview_cell_size)], fill=highlight, width=2)
            draw.line([(px, py + preview_cell_size), (px + preview_cell_size, py + preview_cell_size)], fill=shadow, width=2)
            draw.line([(px + preview_cell_size, py), (px + preview_cell_size, py + preview_cell_size)], fill=shadow, width=2)
        
        # Draw score and level (placeholders for a real game)
        draw.text((sidebar_start + 20, 190), "SCORE", fill=(255, 255, 255), font=font)
        draw.text((sidebar_start + 20, 220), "0", fill=(255, 255, 255), font=font)
        
        draw.text((sidebar_start + 20, 270), "LEVEL", fill=(255, 255, 255), font=font)
        draw.text((sidebar_start + 20, 300), "1", fill=(255, 255, 255), font=font)
        
        # Add "SIMULATED" text at the bottom
        draw.text((sidebar_start + 20, height - 30), "SIMULATED", fill=(255, 80, 80), font=small_font)
        
        # Store the board image for later use
        self.simulated_board = board_image
        return board_image

    def simulate_random_board_state(self, fill_percentage=30, max_height=15):
        """
        Generate a random board state for testing
        
        Args:
            fill_percentage: Percentage of filled cells (0-100)
            max_height: Maximum height of filled cells
            
        Returns:
            tuple: (board_state, current_piece, next_piece)
        """
        import random
        
        # Generate random board
        board = [[0 for _ in range(10)] for _ in range(20)]
        
        # Fill bottom part randomly
        for y in range(20 - 1, 20 - max_height, -1):
            for x in range(10):
                if random.randint(1, 100) <= fill_percentage:
                    # Random piece color (1-7)
                    board[y][x] = random.randint(1, 7)
        
        # Make sure top few rows are empty for piece placement
        for y in range(3):
            for x in range(10):
                board[y][x] = 0
        
        # Generate random current piece
        piece_types = ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
        current_piece = {
            'type': random.choice(piece_types),
            'x': random.randint(2, 7),
            'y': 0,
            'rotation': random.randint(0, 3)
        }
        
        # Generate random next piece
        next_piece = {
            'type': random.choice(piece_types)
        }
        
        return board, current_piece, next_piece
    
    def capture_screenshot(self):
        """Capture the current Tetris game screen"""
        try:
            if self.simulated_mode:
                # For simulated mode, we use our generated board
                if self.simulated_board is None:
                    self.log_message("Creating initial simulated board for screenshot...")
                    self.create_simulated_tetris_board()
                
                # Save the screenshot
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(
                    self.screenshots_dir, 
                    f"screenshot_{self.iteration}_{timestamp}.png"
                )
                
                # Create a copy of the board to avoid modifying the original
                if self.simulated_board:
                    screenshot = self.simulated_board.copy()
                    screenshot.save(screenshot_path)
                    self.log_message(f"Saved simulated screenshot: {os.path.basename(screenshot_path)}")
                    return screenshot
                else:
                    self.log_message("Error: simulated_board is None")
                    return None
            else:
                # For real mode, capture the screen
                self.log_message("Capturing real screenshot...")
                
                if self.window_rect:
                    # Capture just the Tetris window
                    screenshot = pyautogui.screenshot(region=self.window_rect)
                else:
                    # Capture the entire screen
                    screenshot = pyautogui.screenshot()
                
                # Save the screenshot
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                screenshot_path = os.path.join(
                    self.screenshots_dir, 
                    f"screenshot_{self.iteration}_{timestamp}.png"
                )
                screenshot.save(screenshot_path)
                self.log_message(f"Saved real screenshot: {os.path.basename(screenshot_path)}")
                return screenshot
        except Exception as e:
            self.log_message(f"Error capturing screenshot: {str(e)}")
            traceback.print_exc()
            return None

    def encode_image(self, image):
        """Encode an image to base64 for API usage"""
        if image is None:
            self.log_message("Error: Cannot encode None image")
            return None
            
        try:
            # Check if image is a PIL Image, if not try to open it
            if not isinstance(image, Image.Image):
                # If it's a path string, try to open it
                if isinstance(image, str) and os.path.exists(image):
                    image = Image.open(image)
                else:
                    self.log_message(f"Error: Invalid image type: {type(image)}")
                    return None
                    
            # Convert image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        except Exception as e:
            self.log_message(f"Error encoding image: {str(e)}")
            traceback.print_exc()
            return None

    def call_claude_api(self, screenshot):
        """Call Claude API with the screenshot"""
        try:
            # Create timestamp for this API call
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # Convert screenshot to base64 for API
            buffered = io.BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            
            # Prepare messages - fixed format to use system parameter at top level
            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY", "")
            )
            
            self.log_message(f"Calling Claude API (model: {self.model})...")
            
            response = client.messages.create(
                model=self.model,
                system=self.system_prompt,  # Use system at top level
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": self.instruction_prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": img_str
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1024,
                temperature=0.0
            )
            
            # Extract text response
            text_response = response.content[0].text
            
            # Save response if requested
            if self.save_responses:
                response_path = os.path.join(
                    self.responses_dir, 
                    f"response_{self.iteration}_{timestamp}.json"
                )
                with open(response_path, "w", encoding="utf-8") as f:
                    json.dump(response.model_dump(), f, indent=2)
                self.log_message(f"Saved API response to: {os.path.basename(response_path)}")
            
            return text_response
        
        except Exception as e:
            self.log_message(f"Error calling Claude API: {str(e)}")
            traceback.print_exc()
            return f"Error: {str(e)}"

    def extract_python_code(self, text):
        """Extract Python code from the response"""
        import re
        
        # Try to find code blocks
        code_blocks = re.findall(r"```(?:python)?(.*?)```", text, re.DOTALL)
        if code_blocks:
            return code_blocks[0].strip()
        
        # If no code blocks, look for lines with pyautogui
        lines = text.split("\n")
        code_lines = []
        for line in lines:
            if "pyautogui" in line:
                code_lines.append(line.strip())
        
        if code_lines:
            return "\n".join(code_lines)
        
        return None
        
    def execute_code(self, code):
        """Execute the extracted Python code in a safe environment"""
        if not code:
            self.log_message("No code to execute")
            return "No code provided"
        
        # Ensure we have a simulated board for screenshot saving if in simulated mode
        if self.simulated_mode and self.simulated_board is None:
            self.log_message("Creating initial simulated Tetris board...")
            self.create_simple_tetris_board()  # Create a default board if none exists
        
        # Save pre-execution screenshot
        pre_screenshot_path = os.path.join(
            self.screenshots_dir, 
            f"pre_execution_{self.iteration}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        )
        
        if self.simulated_mode:
            # In simulated mode, save the current board
            if self.simulated_board:
                self.simulated_board.save(pre_screenshot_path)
                self.log_message(f"Saved pre-execution screenshot: {os.path.basename(pre_screenshot_path)}")
            else:
                self.log_message("Cannot save pre-execution screenshot: simulated board is None")
        else:
            # For real Tetris, take a screenshot
            screenshot = self.capture_screenshot()
            if screenshot:
                screenshot.save(pre_screenshot_path)
                self.log_message(f"Saved pre-execution screenshot: {os.path.basename(pre_screenshot_path)}")
            else:
                self.log_message("Failed to capture pre-execution screenshot")
        
        # Clean up the code (remove any imports or unsafe calls)
        code = re.sub(r'import\s+(?!random|time|pyautogui)', '', code)
        code = re.sub(r'from\s+.+\s+import', '', code)
        
        # Create a temporary file to execute
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
            temp_filename = f.name
            
            # Add helper code for pyautogui simulation
            if self.simulated_mode:
                # Create a simulated pyautogui object
                simulated_pyautogui = SimulatedPyAutoGUI(self)
                
                # Write imports and setup code
                f.write("import time\nimport random\n\n")
                f.write("# Simulated pyautogui object\n")
                f.write("pyautogui = globals()['pyautogui_obj']\n\n")
                
            else:
                # For real Tetris, just import pyautogui normally
                f.write("import pyautogui\nimport time\nimport random\n\n")
            
            # Add the extracted code
            f.write("# Claude's code begins here:\n")
            f.write(code)
        
        # Execute the code
        try:
            result = None
            error = None
            
            with open(temp_filename, 'r') as f:
                code_content = f.read()
                
            try:
                # Create namespace with iterator and import the local random module
                global_namespace = {
                    '__builtins__': __builtins__, 
                    'random': __import__('random'),
                    'time': __import__('time')
                }
                
                if self.simulated_mode:
                    # Add simulated pyautogui to namespace
                    global_namespace['pyautogui_obj'] = simulated_pyautogui
                
                # Execute the code
                exec(code_content, global_namespace)
                
                # After execution, force an update of the board image to reflect changes
                if self.simulated_mode and simulated_pyautogui.changes_made:
                    self.log_message("Changes made to game state. Updating board image...")
                    
            except Exception as e:
                error = str(e)
                self.log_message(f"Error executing code: {error}")
                traceback.print_exc()
        
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_filename)
            except:
                pass
        
        # Save post-execution screenshot
        post_screenshot_path = os.path.join(
            self.screenshots_dir, 
            f"post_execution_{self.iteration}_{time.strftime('%Y%m%d_%H%M%S')}.png"
        )
        
        if self.simulated_mode:
            # Force recreate the board image with the latest state
            self.create_simulated_tetris_board(
                board_state=self.board,
                current_piece=self.current_piece,
                next_piece=self.next_piece
            )
            
            if self.simulated_board:
                # Create a copy of the board image to avoid modifying the original
                post_image = self.simulated_board.copy()
                
                # Add text to indicate this is the post-execution state
                try:
                    draw = ImageDraw.Draw(post_image)
                    try:
                        font = ImageFont.truetype("arial.ttf", 16)
                    except:
                        font = ImageFont.load_default()
                        
                    # Add "AFTER MOVE" text at the top of the game area
                    draw.rectangle([(5, 5), (150, 25)], fill=(0, 0, 0))
                    draw.text((10, 7), "AFTER MOVE", fill=(255, 255, 0), font=font)
                except Exception as e:
                    self.log_message(f"Error adding text to post image: {e}")
                
                # Save the annotated image
                post_image.save(post_screenshot_path)
                self.log_message(f"Saved post-execution screenshot: {os.path.basename(post_screenshot_path)}")
            else:
                self.log_message("Cannot save post-execution screenshot: simulated board is None")
        else:
            # For real Tetris, take another screenshot
            screenshot = self.capture_screenshot()
            if screenshot:
                screenshot.save(post_screenshot_path)
                self.log_message(f"Saved post-execution screenshot: {os.path.basename(post_screenshot_path)}")
            else:
                self.log_message("Failed to capture post-execution screenshot")
        
        if error:
            return error
        return None

    def wait_for_space_key(self):
        """Wait for the user to press the space key or auto-press if within limit"""
        # If we haven't reached the auto-space limit, simulate a space press
        if self.auto_spaces_used < self.max_auto_spaces:
            self.auto_spaces_used += 1
            self.log_message(f"Auto-pressing SPACE ({self.auto_spaces_used}/{self.max_auto_spaces}) - Will stop after {self.max_auto_spaces} iterations...")
            # Small delay to simulate real keypress and make auto-progress visible
            time.sleep(1)
            return True
        
        # Otherwise, wait for manual input
        self.log_message(f"Auto-space limit reached ({self.max_auto_spaces}). MANUAL INPUT REQUIRED...")
        self.log_message(f"Press SPACE to continue or Q/ESC to quit...")

        space_pressed = False
        quit_pressed = False

        def on_press(key):
            nonlocal space_pressed, quit_pressed
            try:
                if key == keyboard.Key.space:
                    space_pressed = True
                    return False  # Stop listener
                elif hasattr(key, 'char') and key.char == 'q':
                    quit_pressed = True
                    self.quit_with_q = True  # Flag to indicate q was pressed
                    return False  # Stop listener
                elif key == keyboard.Key.esc:
                    quit_pressed = True
                    return False  # Stop listener
            except AttributeError:
                pass

        # Collect events until space or q is pressed
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()

        if quit_pressed:
            self.log_message("Quit requested by user")
            return False
            
        return True
        
    def generate_animation(self):
        """Generate an animation from the screenshots taken during this session"""
        # Check if we should generate an animation
        if not hasattr(self, 'auto_gif') or not self.auto_gif:
            self.log_message("Auto GIF generation is disabled. Skipping animation creation.")
            return
            
        try:
            # Create animations directory if it doesn't exist
            animations_dir = os.path.join(self.session_dir, "animations")
            os.makedirs(animations_dir, exist_ok=True)
            
            # Get timestamp for filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(animations_dir, f"tetris_session_{timestamp}.gif")
            
            # Load the script path
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "create_tetris_animation.py")
            
            # Check if the script exists
            if os.path.exists(script_path):
                # Execute the animation script directly
                self.log_message(f"Creating animation using {script_path}")
                
                # Build command
                cmd = [
                    sys.executable,
                    script_path,
                    "--session", self.session_dir,
                    "--output", output_file,
                    "--fps", str(getattr(self, 'gif_fps', 2))
                ]
                
                # Run the command
                self.log_message(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                # Log output
                if result.stdout:
                    self.log_message(f"Animation script output: {result.stdout}")
                if result.stderr:
                    self.log_message(f"Animation script error: {result.stderr}")
                    
                if result.returncode == 0 and os.path.exists(output_file):
                    self.log_message(f"Animation saved to: {output_file}")
                else:
                    self.log_message("Failed to create animation")
            else:
                self.log_message(f"Animation script not found: {script_path}")
                self.log_message("Please create a GIF manually from the screenshots")
        except Exception as e:
            self.log_message(f"Error generating animation: {str(e)}")
            traceback.print_exc()
            
    def run(self):
        """Main loop"""
        self.log_message("=== Starting Tetris Claude Iterator ===")
        self.log_message(f"Output directory: {self.session_dir}")
        
        # Ensure we have a simulated board if in simulated mode
        if self.simulated_mode and self.simulated_board is None:
            self.log_message("Creating initial simulated Tetris board...")
            self.create_simple_tetris_board()
            
        # Show startup message based on auto-iterations setting
        if self.max_auto_spaces > 0:
            self.log_message(f"Auto-space enabled for {self.max_auto_spaces} iterations. Starting automatically...")
            # Small delay to give time to read the message
            time.sleep(2)
        else:
            self.log_message("Press space to start...")
            # Wait for initial space press if auto-space is disabled
            if not self.wait_for_space_key():
                self.log_message("=== Tetris Claude Iterator finished ===")
                self.generate_animation()  # Generate animation if quitting at startup
                return

        try:
            while not self.stop_flag:
                try:
                    self.iteration += 1
                    self.log_message(f"\n=== Iteration {self.iteration} ===")
                    
                    # Capture screenshot
                    screenshot = self.capture_screenshot()
                    if screenshot is None:
                        self.log_message("Failed to capture screenshot. Retrying in 3 seconds...")
                        time.sleep(3)
                        continue
                    
                    # Call Claude API
                    response = self.call_claude_api(screenshot)
                    
                    # Display response
                    print("\n" + "="*50)
                    print("Claude's Response:")
                    print(response)
                    print("="*50 + "\n")
                    
                    # Extract and execute code
                    code = self.extract_python_code(response)
                    error = self.execute_code(code)
                    
                    # If there was an error and we're in real mode, try switching to simulated mode
                    if error and not self.simulated_mode:
                        self.log_message("Error in real mode. Would you like to switch to simulated mode? (y/n)")
                        # Simple input without using pynput
                        user_input = input().strip().lower()
                        if user_input == 'y':
                            self.log_message("Switching to simulated mode...")
                            self.simulated_mode = True
                            self.create_simple_tetris_board()
                    
                    # Wait for space key
                    self.log_message("Waiting for space key to continue...")
                    if not self.wait_for_space_key():
                        break
                    
                except Exception as e:
                    self.log_message(f"Error in iteration {self.iteration}: {str(e)}")
                    traceback.print_exc()
                    
                    # Wait for space key to continue
                    if not self.wait_for_space_key():
                        break
        except KeyboardInterrupt:
            self.log_message("Keyboard interrupt detected. Shutting down...")
        finally:
            self.log_message("=== Tetris Claude Iterator finished ===")
            # Generate animation if quitting with 'q'
            if hasattr(self, 'quit_with_q') and self.quit_with_q:
                self.generate_animation()
            
    def create_simple_tetris_board(self, piece_type='T'):
        """
        创建一个简单的Tetris棋盘，只有一个当前方块在顶部
        
        Args:
            piece_type: 方块类型 ('I', 'J', 'L', 'O', 'S', 'T', 'Z')
            
        Returns:
            PIL.Image: 简单的Tetris棋盘图像
        """
        # 创建空棋盘 (没有任何已放置的方块)
        self.board = [[0 for _ in range(10)] for _ in range(20)]
        
        # 当前方块在顶部中间
        self.current_piece = {
            'type': piece_type,
            'x': 4,
            'y': 0,
            'rotation': 0
        }
        
        # 下一个方块是I型
        self.next_piece = {'type': 'I'}
        
        # 创建并返回模拟棋盘
        return self.create_simulated_tetris_board(
            board_state=self.board,
            current_piece=self.current_piece,
            next_piece=self.next_piece
        )

    def is_valid_position(self, piece):
        """
        Check if a piece position is valid (not colliding or out of bounds)
        """
        if not piece:
            return False
            
        # Define piece shapes for all rotations (same as in create_simulated_tetris_board)
        piece_shapes = {
            'I': [
                [(0, 0), (0, 1), (0, 2), (0, 3)],     # Horizontal
                [(0, 0), (1, 0), (2, 0), (3, 0)]      # Vertical
            ],
            'J': [
                [(0, 0), (1, 0), (1, 1), (1, 2)],     # ┌
                [(0, 0), (0, 1), (1, 0), (2, 0)],     # ┘
                [(0, 0), (0, 1), (0, 2), (1, 2)],     # └
                [(0, 1), (1, 1), (2, 1), (2, 0)]      # ┐
            ],
            'L': [
                [(0, 2), (1, 0), (1, 1), (1, 2)],     # ┐
                [(0, 0), (1, 0), (2, 0), (2, 1)],     # └
                [(0, 0), (0, 1), (0, 2), (1, 0)],     # ┌
                [(0, 0), (0, 1), (1, 1), (2, 1)]      # ┘
            ],
            'O': [
                [(0, 0), (0, 1), (1, 0), (1, 1)]      # Square (single rotation)
            ],
            'S': [
                [(0, 1), (0, 2), (1, 0), (1, 1)],     # Horizontal
                [(0, 0), (1, 0), (1, 1), (2, 1)]      # Vertical
            ],
            'T': [
                [(0, 1), (1, 0), (1, 1), (1, 2)],     # ┬
                [(0, 0), (1, 0), (1, 1), (2, 0)],     # ├
                [(0, 0), (0, 1), (0, 2), (1, 1)],     # ┴
                [(0, 1), (1, 0), (1, 1), (2, 1)]      # ┤
            ],
            'Z': [
                [(0, 0), (0, 1), (1, 1), (1, 2)],     # Horizontal
                [(0, 1), (1, 0), (1, 1), (2, 0)]      # Vertical
            ]
        }
        
        piece_type = piece['type']
        x = piece['x']
        y = piece['y']
        rotation = piece['rotation'] % len(piece_shapes[piece_type])
        
        # Get the blocks for this piece and rotation
        blocks = piece_shapes[piece_type][rotation]
        
        # Check each block of the piece
        for dx, dy in blocks:
            # Calculate board position
            board_x = x + dx
            board_y = y + dy
            
            # Check boundaries
            if board_x < 0 or board_x >= 10 or board_y < 0 or board_y >= 20:
                return False
                
            # Collision with existing blocks
            if board_y >= 0 and self.board[board_y][board_x] > 0:
                return False
        
        # If we get here, position is valid
        return True

    def lock_piece(self, piece):
        """
        Lock the piece onto the board
        """
        if not piece:
            return
            
        # Define piece shapes for all rotations (same as in create_simulated_tetris_board)
        piece_shapes = {
            'I': [
                [(0, 0), (0, 1), (0, 2), (0, 3)],     # Horizontal
                [(0, 0), (1, 0), (2, 0), (3, 0)]      # Vertical
            ],
            'J': [
                [(0, 0), (1, 0), (1, 1), (1, 2)],     # ┌
                [(0, 0), (0, 1), (1, 0), (2, 0)],     # ┘
                [(0, 0), (0, 1), (0, 2), (1, 2)],     # └
                [(0, 1), (1, 1), (2, 1), (2, 0)]      # ┐
            ],
            'L': [
                [(0, 2), (1, 0), (1, 1), (1, 2)],     # ┐
                [(0, 0), (1, 0), (2, 0), (2, 1)],     # └
                [(0, 0), (0, 1), (0, 2), (1, 0)],     # ┌
                [(0, 0), (0, 1), (1, 1), (2, 1)]      # ┘
            ],
            'O': [
                [(0, 0), (0, 1), (1, 0), (1, 1)]      # Square (single rotation)
            ],
            'S': [
                [(0, 1), (0, 2), (1, 0), (1, 1)],     # Horizontal
                [(0, 0), (1, 0), (1, 1), (2, 1)]      # Vertical
            ],
            'T': [
                [(0, 1), (1, 0), (1, 1), (1, 2)],     # ┬
                [(0, 0), (1, 0), (1, 1), (2, 0)],     # ├
                [(0, 0), (0, 1), (0, 2), (1, 1)],     # ┴
                [(0, 1), (1, 0), (1, 1), (2, 1)]      # ┤
            ],
            'Z': [
                [(0, 0), (0, 1), (1, 1), (1, 2)],     # Horizontal
                [(0, 1), (1, 0), (1, 1), (2, 0)]      # Vertical
            ]
        }
        
        # Map piece type to color index
        piece_colors = {
            'I': 1,  # cyan
            'J': 2,  # blue
            'L': 3,  # orange
            'O': 4,  # yellow
            'S': 5,  # green
            'T': 6,  # purple
            'Z': 7   # red
        }
        
        piece_type = piece['type']
        x = piece['x']
        y = piece['y']
        rotation = piece['rotation'] % len(piece_shapes[piece_type])
        
        # Get color for this piece type
        color_index = piece_colors.get(piece_type, 6)  # Default to purple (T) if unknown
        
        # Get the blocks for this piece and rotation
        blocks = piece_shapes[piece_type][rotation]
        
        # Lock each block onto the board
        for dx, dy in blocks:
            # Calculate board position
            board_x = x + dx
            board_y = y + dy
            
            # Only place if within board
            if 0 <= board_x < 10 and 0 <= board_y < 20:
                self.board[board_y][board_x] = color_index
    
    def clear_lines(self):
        """
        Clear completed lines and return the number of lines cleared
        """
        lines_to_clear = []
        
        # Find completed lines
        for y in range(20):
            if all(cell > 0 for cell in self.board[y]):
                lines_to_clear.append(y)
        
        # Clear lines from bottom to top
        for y in sorted(lines_to_clear, reverse=True):
            # Remove the completed line
            self.board.pop(y)
            # Add a new empty line at the top
            self.board.insert(0, [0 for _ in range(10)])
        
        if lines_to_clear:
            self.log_message(f"Cleared {len(lines_to_clear)} lines at rows: {', '.join(map(str, lines_to_clear))}")
            
        return len(lines_to_clear)

class SimulatedPyAutoGUI:
    """Simulates PyAutoGUI for Tetris control in a virtual environment"""
    
    def __init__(self, iterator):
        """Initialize with reference to the TetrisClaudeIterator"""
        self.iterator = iterator
        self.changes_made = False  # Flag to track if any successful moves were made
    
    def press(self, key):
        """Simulate pressing a key"""
        if not self.iterator or not self.iterator.current_piece:
            print("Error: No iterator or current piece available")
            return
        
        try:
            # Reset the changes made flag at the start of a press sequence
            self.changes_made = False
            
            # Get current state
            piece = dict(self.iterator.current_piece)  # Create a copy to avoid modifying original directly
            
            # Move based on key
            if key == 'left':
                # Try moving left
                piece['x'] -= 1
                if self.iterator.is_valid_position(piece):
                    self.iterator.current_piece = piece
                    self.changes_made = True
                    print(f"DEBUG: Moved piece left to x={piece['x']}")
                else:
                    print(f"DEBUG: Cannot move left from x={self.iterator.current_piece['x']}")
                    
            elif key == 'right':
                # Try moving right
                piece['x'] += 1
                if self.iterator.is_valid_position(piece):
                    self.iterator.current_piece = piece
                    self.changes_made = True
                    print(f"DEBUG: Moved piece right to x={piece['x']}")
                else:
                    print(f"DEBUG: Cannot move right from x={self.iterator.current_piece['x']}")
                    
            elif key == 'up':
                # Try rotating
                old_rotation = piece['rotation']
                piece['rotation'] = (piece['rotation'] + 1) % 4  # Assume 4 rotations max
                
                # Check if valid
                if self.iterator.is_valid_position(piece):
                    self.iterator.current_piece = piece
                    self.changes_made = True
                    print(f"DEBUG: Rotated piece from {old_rotation} to {piece['rotation']}")
                else:
                    print(f"DEBUG: Cannot rotate piece at x={piece['x']}, y={piece['y']}")
                    
            elif key == 'down':
                # Try moving down
                piece['y'] += 1
                if self.iterator.is_valid_position(piece):
                    self.iterator.current_piece = piece
                    self.changes_made = True
                    print(f"DEBUG: Moved piece down to y={piece['y']}")
                else:
                    # If can't move down, lock the piece
                    print(f"DEBUG: Cannot move down further. Locking piece at y={self.iterator.current_piece['y']}")
                    self.iterator.lock_piece(self.iterator.current_piece)
                    
                    # Check for completed lines
                    lines_cleared = self.iterator.clear_lines()
                    if lines_cleared > 0:
                        print(f"DEBUG: Cleared {lines_cleared} lines!")
                    
                    # Set current piece to next piece
                    if self.iterator.next_piece:
                        self.iterator.current_piece = {
                            'type': self.iterator.next_piece['type'],
                            'x': 4,  # Start in middle
                            'y': 0,  # Start at top
                            'rotation': 0
                        }
                        
                        # Generate new next piece
                        import random
                        piece_types = ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
                        self.iterator.next_piece = {'type': random.choice(piece_types)}
                        
                        self.changes_made = True
                        print(f"DEBUG: New piece: {self.iterator.current_piece['type']}, Next piece: {self.iterator.next_piece['type']}")
                    else:
                        print("DEBUG: No next piece available. Game might be over.")
                    
            elif key == 'space':
                # Hard drop
                drop_distance = 0
                while True:
                    piece['y'] += 1
                    drop_distance += 1
                    if not self.iterator.is_valid_position(piece):
                        # Move back up one step and lock
                        piece['y'] -= 1
                        drop_distance -= 1
                        break
                
                # Only update if we actually dropped
                if drop_distance > 0:
                    self.iterator.current_piece = piece
                    print(f"DEBUG: Hard dropped piece {drop_distance} rows to y={piece['y']}")
                    self.changes_made = True
                    
                    # Lock the piece
                    self.iterator.lock_piece(self.iterator.current_piece)
                    
                    # Check for completed lines
                    lines_cleared = self.iterator.clear_lines()
                    if lines_cleared > 0:
                        print(f"DEBUG: Cleared {lines_cleared} lines!")
                    
                    # Set current piece to next piece
                    if self.iterator.next_piece:
                        self.iterator.current_piece = {
                            'type': self.iterator.next_piece['type'],
                            'x': 4,  # Start in middle
                            'y': 0,  # Start at top
                            'rotation': 0
                        }
                        
                        # Generate new next piece
                        import random
                        piece_types = ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
                        self.iterator.next_piece = {'type': random.choice(piece_types)}
                        
                        print(f"DEBUG: New piece: {self.iterator.current_piece['type']}, Next piece: {self.iterator.next_piece['type']}")
                    else:
                        print("DEBUG: No next piece available. Game might be over.")
                else:
                    print("DEBUG: Piece couldn't be dropped further")
            
            # Update the board image after any changes
            if self.changes_made:
                self.iterator.create_simulated_tetris_board(
                    board_state=self.iterator.board,
                    current_piece=self.iterator.current_piece,
                    next_piece=self.iterator.next_piece
                )
        
        except Exception as e:
            print(f"ERROR in SimulatedPyAutoGUI.press: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def sleep(self, seconds):
        """Simulate sleep function"""
        # We can just pass in simulation
        pass

def cleanup_txt_files():
    """Remove any .txt files in the claude_tetris_outputs directory"""
    try:
        base_dir = OUTPUT_DIR
        if not os.path.exists(base_dir):
            return
            
        # Walk through all subdirectories
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                        print(f"Removed: {file_path}")
                    except Exception as e:
                        print(f"Error removing {file_path}: {e}")
    except Exception as e:
        print(f"Error cleaning up .txt files: {e}")

def main():
    """Main function to parse args and run the iterator"""
    parser = argparse.ArgumentParser(description="Tetris Claude Iterator")
    
    # Model selection
    parser.add_argument("--model", type=str, default="claude-3-7-sonnet-20250219",
                      help="Claude model to use")
    
    # Output directory
    parser.add_argument("--output", type=str, default="game_logs",
                      help="Directory to save output")
    
    # Window options
    parser.add_argument("--window", type=str, default=None,
                      help="Title of Tetris window to capture")
    
    # Auto-iteration options
    parser.add_argument("--auto-iterations", type=int, default=None,
                      help="Number of iterations to automatically run (default: 4)")
    
    # Simulation options
    parser.add_argument("--force-simulate", action="store_true",
                      help="Force simulated Tetris board instead of screenshots")
    parser.add_argument("--no-simulate", action="store_true",
                      help="Force real screenshots instead of simulated board")
    
    # GIF options
    parser.add_argument("--auto-gif", action="store_true",
                      help="Automatically generate GIF when quitting with 'q'")
    parser.add_argument("--no-auto-gif", action="store_true",
                      help="Disable automatic GIF generation")
    parser.add_argument("--gif-fps", type=int, default=2,
                      help="Frames per second for GIF animation")
    
    # Single-shot mode
    parser.add_argument("--image", type=str, default=None,
                      help="Analyze a single image instead of running interactively")
    
    # Response saving
    parser.add_argument("--save-responses", action="store_true",
                      help="Save API responses to JSON files")
    
    args = parser.parse_args()
    
    # Load environment variables
    load_env_file()
    
    # Get model and output directory
    model = args.model
    output_dir = args.output
    window_title = args.window
    
    # Create and run the iterator
    iterator = TetrisClaudeIterator(
        model=model,
        output_dir=output_dir,
        window_title=window_title,
        save_responses=args.save_responses
    )
    
    # Set maximum number of auto-iterations if specified
    if args.auto_iterations is not None:
        iterator.max_auto_spaces = args.auto_iterations
        if args.auto_iterations == 0:
            print("Auto-space feature disabled. Manual input required for each iteration.")
        else:
            print(f"Auto-space feature enabled for {args.auto_iterations} iterations.")
    
    # Configure GIF generation
    if args.no_auto_gif:
        iterator.auto_gif = False
        print("Automatic GIF generation disabled")
    elif args.auto_gif:
        iterator.auto_gif = True
        iterator.quit_with_q = True  # Set this to be triggered when quitting with 'q'
        print("Automatic GIF generation enabled when quitting with 'q'")
    
    # Set GIF FPS if specified
    if args.gif_fps:
        iterator.gif_fps = args.gif_fps
        print(f"GIF animation will be generated at {args.gif_fps} frames per second")
    
    # Determine simulation mode
    if args.force_simulate:
        print("Forcing simulated Tetris board mode")
        iterator.simulated_mode = True
        # Create the simulated board
        iterator.create_simple_tetris_board()
    elif args.no_simulate:
        print("Using real screenshots instead of simulated board")
        iterator.simulated_mode = False
    
    # Single-shot mode - analyze a specific image
    if args.image:
        if os.path.exists(args.image):
            print(f"Single-shot mode: Analyzing image {args.image}")
            image = Image.open(args.image)
            response = iterator.call_claude_api(image)
            print("\n" + "="*50)
            print("Claude's Response:")
            print(response)
            print("="*50 + "\n")
            
            # Extract and execute code if requested
            code = iterator.extract_python_code(response)
            if code and not args.no_simulate:
                print("Executing extracted code in simulated mode:")
                iterator.simulated_mode = True
                iterator.create_simple_tetris_board()
                iterator.execute_code(code)
                # Save the result
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = os.path.join(output_dir, f"result_{timestamp}.png")
                iterator.simulated_board.save(output_path)
                print(f"Result saved to: {output_path}")
        else:
            print(f"Error: Image file not found: {args.image}")
        return
    
    # Regular interactive mode
    iterator.run()


if __name__ == "__main__":
    main() 