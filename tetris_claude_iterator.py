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

# Try to load optional dependencies
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Default values (can be overridden by .env or command-line args)
MODEL = os.environ.get('CLAUDE_MODEL', 'claude-3-opus-20240229')
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
        # Initialize Claude API
        self.model = model or "claude-3-opus-20240229"
        
        # Set up logging and directories
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.base_dir = output_dir or "."
        
        # Create session directory
        self.session_name = f"session_{timestamp}"
        self.session_dir = os.path.join(self.base_dir, "game_logs", self.session_name)
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        self.responses_dir = os.path.join(self.session_dir, "responses")
        
        # Create directories
        os.makedirs(self.session_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        if save_responses:
            os.makedirs(self.responses_dir, exist_ok=True)
        
        # Set up log file
        self.log_file = os.path.join(self.session_dir, "log.txt")
        with open(self.log_file, "w") as f:
            f.write(f"=== Tetris Claude Iterator Log - {timestamp} ===\n\n")
        
        # Track iteration
        self.iteration = 0
        
        # Set window title to find for real Tetris
        self.window_title = window_title
        
        # Save API response JSON
        self.save_responses = save_responses
        
        # For window detection
        self.window_rect = None
        self.stop_flag = False
        
        # Simulation mode flag and state
        self.simulated_mode = True  # Default to True now
        self.simulated_board = None
        self.board = None
        self.current_piece = None
        self.next_piece = None
        
        # Add auto-space counter (maximum 4 automatic space presses)
        self.auto_space_counter = 0
        self.max_auto_spaces = 4
        
        # Define prompts for Claude
        self.system_prompt = """You are a Tetris game-playing assistant. 
Your task is to analyze the current Tetris board and suggest the best moves for the current piece.
Be strategic about your moves, considering the current piece and the next piece if visible."""

        # User instruction prompt
        self.instruction_prompt = """Analyze the current Tetris board state and generate PyAutoGUI code to control Tetris 
for the current piece. Your code will be executed to control the game.

The speed pieces drop is at around ~0.75s/grid block.

### General Tetris Controls (keybinds):
- left: move piece left
- right: move piece right
- up: rotate piece clockwise
- down: accelerated drop (if necessary)
- space: drop piece immediately

### Strategies and Caveats:
0. Clear the horizontal rows as soon as possible.
2. Prioritize keeping the stack flat and balanced
1. Avoid creating holes you know you can rotate piece to match
3. If you see a chance to clear lines, do it
4. Only control the current piece visible at the top

### Output Format:
- Output ONLY the Python code for PyAutoGUI commands, e.g. `pyautogui.press("left")`
- Include brief comments for each action
- Do not print anything else besides these Python commands

Here's the current Tetris game state image:
"""

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
        """
        Create a simulated Tetris board image
        
        Args:
            board_state: 2D list representing the board state (0=empty, 1-7=piece colors)
            current_piece: Dict with 'type', 'x', 'y', 'rotation'
            next_piece: Dict with 'type'
            
        Returns:
            PIL.Image: Simulated Tetris board image
        """
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
            
        # Define colors for Tetris pieces
        colors = {
            0: (0, 0, 0),         # Empty (black)
            1: (0, 240, 240),     # I - Cyan
            2: (0, 0, 240),       # J - Blue
            3: (240, 160, 0),     # L - Orange
            4: (240, 240, 0),     # O - Yellow
            5: (0, 240, 0),       # S - Green
            6: (160, 0, 240),     # T - Purple
            7: (240, 0, 0),       # Z - Red
            8: (100, 100, 100),   # Ghost piece (gray)
            9: (50, 50, 50)       # Grid line (dark gray)
        }
        
        # Tetris piece shapes (different rotations)
        piece_shapes = {
            'I': [
                [(0, 0), (1, 0), (2, 0), (3, 0)],  # Horizontal
                [(1, -1), (1, 0), (1, 1), (1, 2)]  # Vertical
            ],
            'J': [
                [(0, 0), (0, 1), (1, 1), (2, 1)],  # ┌──
                [(1, 0), (2, 0), (1, 1), (1, 2)],  # │└─
                [(0, 1), (1, 1), (2, 1), (2, 2)],  # ──┘
                [(1, 0), (1, 1), (1, 2), (0, 2)]   # ─┐
            ],                                       # └┘
            'L': [
                [(0, 1), (1, 1), (2, 1), (2, 0)],  # ──┐
                [(1, 0), (1, 1), (1, 2), (2, 2)],  # └─┘
                [(0, 1), (1, 1), (2, 1), (0, 2)],  # ┌──
                [(0, 0), (1, 0), (1, 1), (1, 2)]   # │└─
            ],
            'O': [
                [(0, 0), (1, 0), (0, 1), (1, 1)]   # Square
            ],
            'S': [
                [(1, 0), (2, 0), (0, 1), (1, 1)],  # ─┐
                [(1, 0), (1, 1), (2, 1), (2, 2)]   # └┘
            ],
            'T': [
                [(1, 0), (0, 1), (1, 1), (2, 1)],  # ─┬─
                [(1, 0), (1, 1), (2, 1), (1, 2)],  # └┼─
                [(0, 1), (1, 1), (2, 1), (1, 2)],  # ─┼┘
                [(1, 0), (0, 1), (1, 1), (1, 2)]   # ─┼┐
            ],                                      # └┘
            'Z': [
                [(0, 0), (1, 0), (1, 1), (2, 1)],  # ┌─┐
                [(2, 0), (1, 1), (2, 1), (1, 2)]   # └─┘
            ]
        }
        
        # Store piece shapes for movement simulation
        self.piece_shapes = piece_shapes
        
        # Mapping from piece type to color index
        piece_colors = {
            'I': 1,
            'J': 2,
            'L': 3,
            'O': 4,
            'S': 5,
            'T': 6,
            'Z': 7
        }
        
        # Store piece colors for later use
        self.piece_colors = piece_colors
        
        # Create image (board + UI elements)
        # Grid cell size in pixels
        cell_size = 30
        
        # Main board dimensions
        board_width = 10 * cell_size
        board_height = 20 * cell_size
        
        # UI panel width
        ui_width = 6 * cell_size
        
        # Total image dimensions
        img_width = board_width + ui_width
        img_height = board_height
        
        # Create blank image with black background
        image = Image.new('RGB', (img_width, img_height), colors[0])
        draw = ImageDraw.Draw(image)
        
        # Draw grid lines
        for x in range(11):
            x_pos = x * cell_size
            draw.line([(x_pos, 0), (x_pos, board_height)], fill=colors[9], width=1)
        
        for y in range(21):
            y_pos = y * cell_size
            draw.line([(0, y_pos), (board_width, y_pos)], fill=colors[9], width=1)
        
        # Draw board state (existing pieces)
        for y, row in enumerate(self.board):
            for x, cell in enumerate(row):
                if cell > 0:
                    # Draw filled cell
                    rect = [
                        x * cell_size + 1,
                        y * cell_size + 1,
                        (x + 1) * cell_size - 1,
                        (y + 1) * cell_size - 1
                    ]
                    draw.rectangle(rect, fill=colors[cell])
        
        # Draw current piece
        if self.current_piece:
            piece_type = self.current_piece['type']
            rotation = self.current_piece.get('rotation', 0) % len(piece_shapes[piece_type])
            x_offset = self.current_piece['x']
            y_offset = self.current_piece['y']
            
            for x, y in piece_shapes[piece_type][rotation]:
                rect = [
                    (x_offset + x) * cell_size + 1,
                    (y_offset + y) * cell_size + 1,
                    (x_offset + x + 1) * cell_size - 1,
                    (y_offset + y + 1) * cell_size - 1
                ]
                draw.rectangle(rect, fill=colors[piece_colors[piece_type]])
        
        # Draw UI panel
        ui_start_x = board_width
        
        # Draw panel background
        draw.rectangle([
            ui_start_x, 0,
            img_width, img_height
        ], fill=(30, 30, 30))
        
        # Draw "NEXT" text
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        
        draw.text((ui_start_x + 20, 20), "NEXT", fill=(255, 255, 255), font=font)
        
        # Draw next piece
        if self.next_piece:
            piece_type = self.next_piece['type']
            next_piece_color = piece_colors[piece_type]
            
            # Center the piece in the next piece box
            next_x = ui_start_x + ui_width // 2 - cell_size
            next_y = 60
            
            # Draw only the first rotation
            for x, y in piece_shapes[piece_type][0]:
                rect = [
                    next_x + x * cell_size + 1,
                    next_y + y * cell_size + 1,
                    next_x + (x + 1) * cell_size - 1,
                    next_y + (y + 1) * cell_size - 1
                ]
                draw.rectangle(rect, fill=colors[next_piece_color])
        
        # Draw score or other UI elements
        draw.text((ui_start_x + 10, 180), "SCORE", fill=(255, 255, 255), font=font)
        draw.text((ui_start_x + 10, 210), "0", fill=(255, 255, 255), font=font)
        
        # Draw level
        draw.text((ui_start_x + 10, 260), "LEVEL", fill=(255, 255, 255), font=font)
        draw.text((ui_start_x + 10, 290), "1", fill=(255, 255, 255), font=font)
        
        # Add a watermark to indicate this is a simulated board
        draw.text((ui_start_x + 10, img_height - 30), "SIMULATED", fill=(255, 100, 100), font=font)
        
        self.simulated_board = image
        return image

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
        """Capture screenshot of the Tetris game"""
        # If we're using a simulated board, return that instead
        if self.simulated_mode and self.simulated_board:
            # For simulated mode, save the image and return it
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_simulated_iter_{self.iteration}")
            self.simulated_board.save(f"{screenshot_path}.png")
            self.log_message(f"Screenshot saved to: {screenshot_path}")
            return self.simulated_board
        
        # For real Tetris, try to find the window
        if not self.window_rect:
            self.find_tetris_window()
        
        # If we still don't have a window rect, use default screen area
        if not self.window_rect:
            self.log_message("Tetris window not found. Using default screen area.")
            self.window_rect = (0, 0, 768, 1080)  # Default to capturing left side of screen
        
        # Take screenshot
        try:
            self.log_message(f"Capturing screenshot of region: {self.window_rect}")
            screen_region = self.window_rect
            screenshot = pyautogui.screenshot(region=screen_region)
            
            # Save screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_iter_{self.iteration}")
            screenshot.save(f"{screenshot_path}.png")
            self.log_message(f"Screenshot saved to: {screenshot_path}")
            
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

    def call_claude_api(self, image):
        """Call Claude API with an image"""
        self.log_message(f"Calling Claude API with model {self.model} (iteration {self.iteration})...")

        try:
            # Encode image for API
            base64_image = self.encode_image(image)
            if not base64_image:
                raise ValueError("Failed to encode image")

            # Load API key from environment variable
            api_key = os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

            # Prepare the client
            client = anthropic.Anthropic(api_key=api_key)

            # Prepare message content
            system_prompt = self.system_prompt
            user_prompt = self.instruction_prompt

            # Call the API
            response = client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_prompt
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ]
            )

            # Save the response to a file if enabled
            if self.save_responses:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                response_path = os.path.join(
                    self.responses_dir,
                    f"response_{self.iteration}_{timestamp}.json"
                )
                with open(response_path, "w", encoding="utf-8") as f:
                    json.dump(response.dict(), f, indent=2)

            return response.content[0].text

        except Exception as e:
            error_message = str(e)
            self.log_message(f"Error calling Claude API: {error_message}")
            traceback.print_exc()
            return f"Error: {error_message}"

    def wait_for_space_key(self):
        """Wait for the user to press the space key or auto-press if within limit"""
        # If we haven't reached the auto-space limit, simulate a space press
        if self.auto_space_counter < self.max_auto_spaces:
            self.auto_space_counter += 1
            self.log_message(f"Auto-pressing SPACE ({self.auto_space_counter}/{self.max_auto_spaces}) - Will stop after {self.max_auto_spaces} iterations...")
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
        """Execute the Python code extracted from Claude's response"""
        self.log_message(f"Executing code from iteration {self.iteration}...")
        
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
        
        # Create a secure temp file for the code
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w') as f:
            temp_filename = f.name
            
            # Add imports and helper code for simulated Tetris
            if self.simulated_mode:
                helpers_code = """
import pyautogui as pyautogui_real
import time
import random

# Helper functions for simulated Tetris
def get_current_piece():
    return iterator.current_piece.copy() if iterator.current_piece else None

def get_next_piece():
    return iterator.next_piece

def get_board():
    return [row[:] for row in iterator.board]  # Deep copy

def is_valid_position(piece):
    return iterator.is_valid_position(piece)

def lock_piece(piece):
    return iterator.lock_piece(piece)

def clear_lines():
    return iterator.clear_lines()

# Simulated pyautogui for Tetris moves
class SimulatedPyAutoGUI:
    def __init__(self, iterator):
        self.iterator = iterator
    
    def press(self, key):
        \"\"\"Simulate pressing a key\"\"\"
        # Only process if we have a current piece
        if not self.iterator.current_piece:
            return
            
        # Clone the current piece for simulation
        piece = self.iterator.current_piece.copy()
        
        # Handle key press
        if key == "left":
            # Move left
            piece['x'] -= 1
            # Check if valid
            if not self.iterator.is_valid_position(piece):
                piece['x'] += 1  # Undo if invalid
            else:
                self.iterator.current_piece = piece
                
        elif key == "right":
            # Move right
            piece['x'] += 1
            # Check if valid
            if not self.iterator.is_valid_position(piece):
                piece['x'] -= 1  # Undo if invalid
            else:
                self.iterator.current_piece = piece
                
        elif key == "up" or key == "rotate":
            # Rotate piece (clockwise)
            original_rot = piece['rotation']
            piece['rotation'] = (piece['rotation'] + 1) % 4
            
            # Check if valid
            if not self.iterator.is_valid_position(piece):
                # Try wall kicks (move left/right if rotation causes collision)
                # First try moving right
                piece['x'] += 1
                if not self.iterator.is_valid_position(piece):
                    # If right doesn't work, try left
                    piece['x'] -= 2
                    if not self.iterator.is_valid_position(piece):
                        # If left doesn't work either, undo rotation
                        piece['x'] += 1  # Reset to original position
                        piece['rotation'] = original_rot
            
            # Update piece
            self.iterator.current_piece = piece
                
        elif key == "down":
            # Move down
            piece['y'] += 1
            # Check if valid
            if not self.iterator.is_valid_position(piece):
                piece['y'] -= 1  # Undo if invalid
            else:
                self.iterator.current_piece = piece
                
        elif key == "space":
            # Hard drop - move down until collision
            while self.iterator.is_valid_position(piece):
                piece['y'] += 1
            
            # Move back up one step
            piece['y'] -= 1
            
            # Lock the piece on the board
            self.iterator.lock_piece(piece)
            
            # Clear any completed lines
            self.iterator.clear_lines()
            
            # Generate a new piece
            piece_types = ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
            self.iterator.current_piece = {
                'type': self.iterator.next_piece['type'] if self.iterator.next_piece else random.choice(piece_types),
                'x': 4,
                'y': 0,
                'rotation': 0
            }
            self.iterator.next_piece = {'type': random.choice(piece_types)}
            
    def sleep(self, seconds):
        \"\"\"Simulate waiting\"\"\"
        pass

# Use simulated or real pyautogui based on mode
pyautogui = SimulatedPyAutoGUI(iterator) if iterator.simulated_mode else pyautogui_real
"""
                f.write(helpers_code)
            else:
                # For real Tetris, just import pyautogui normally
                f.write("import pyautogui\nimport time\n")
            
            # Add the extracted code
            f.write("\n# Claude's code begins here:\n")
            f.write(code)
        
        # Execute the code
        try:
            result = None
            error = None
            
            with open(temp_filename, 'r') as f:
                code_content = f.read()
                
            try:
                # Create namespace with iterator
                local_namespace = {"iterator": self}
                
                # Execute the code
                exec(code_content, {}, local_namespace)
                
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
            # Recreate the board image with updated state
            self.create_simulated_tetris_board(
                board_state=self.board,
                current_piece=self.current_piece,
                next_piece=self.next_piece
            )
            if self.simulated_board:
                self.simulated_board.save(post_screenshot_path)
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
    
    def is_valid_position(self, piece):
        """Check if the piece position is valid (not outside board or colliding)"""
        if not piece:
            return False
            
        piece_type = piece['type']
        x_offset = piece['x']
        y_offset = piece['y']
        rotation = piece['rotation'] % len(self.piece_shapes[piece_type])
        
        for x, y in self.piece_shapes[piece_type][rotation]:
            # Check if piece is within board boundaries
            board_x = x_offset + x
            board_y = y_offset + y
            
            # Outside board boundaries
            if (board_x < 0 or board_x >= 10 or 
                board_y < 0 or board_y >= 20):
                return False
                
            # Collision with existing blocks
            if board_y >= 0 and self.board[board_y][board_x] > 0:
                return False
                
        return True
    
    def lock_piece(self, piece):
        """Lock the piece in place on the board"""
        if not piece:
            return
            
        piece_type = piece['type']
        x_offset = piece['x']
        y_offset = piece['y']
        rotation = piece['rotation'] % len(self.piece_shapes[piece_type])
        color_index = self.piece_colors[piece_type]
        
        for x, y in self.piece_shapes[piece_type][rotation]:
            board_x = x_offset + x
            board_y = y_offset + y
            
            # Only place if within board
            if 0 <= board_x < 10 and 0 <= board_y < 20:
                self.board[board_y][board_x] = color_index
    
    def clear_lines(self):
        """Clear completed lines and shift the board down"""
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
            
        return len(lines_to_clear)

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

    def run(self):
        """Main loop"""
        self.log_message("=== Starting Tetris Claude Iterator ===")
        self.log_message(f"Output directory: {self.session_dir}")
        
        # Show startup message based on auto-iterations setting
        if self.max_auto_spaces > 0:
            self.log_message(f"Auto-space enabled for {self.max_auto_spaces} iterations. Starting automatically...")
            # Small delay to give time to read the message
            time.sleep(2)
        else:
            self.log_message("Press space to start...")
            # Wait for initial space press if auto-space is disabled
            if not self.wait_for_space_key():
                return

        try:
            while not self.stop_flag:
                try:
                    self.iteration += 1
                    self.log_message(f"\n=== Iteration {self.iteration} ===")
                    
                    # Capture screenshot
                    screenshot = self.capture_screenshot()
                    if screenshot is None:
                        self.log_message("Failed to capture screenshot. Retrying...")
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
                    self.execute_code(code)
                    
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
    parser = argparse.ArgumentParser(description='Tetris Claude Iterator')
    parser.add_argument('--model', type=str, help='Claude model to use (default: claude-3-opus-20240229)')
    parser.add_argument('--output', type=str, help='Output directory')
    parser.add_argument('--window', type=str, help='Window title to capture')
    parser.add_argument('--no-simulate', action='store_true', help='Disable simulated board mode')
    parser.add_argument('--save-responses', action='store_true', help='Save API responses to JSON files')
    parser.add_argument('--auto-iterations', type=int, default=4, help='Number of automatic iterations before requiring manual input (default: 4)')
    
    args = parser.parse_args()
    
    # Configure from environment variables if not provided as args
    model = args.model or os.environ.get('CLAUDE_MODEL', 'claude-3-opus-20240229')
    output_dir = args.output or os.environ.get('OUTPUT_DIR', '.')
    window_title = args.window or os.environ.get('TETRIS_WINDOW_TITLE', None)
    
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
    
    if args.no_simulate:
        print("Using real screenshots instead of simulated board")
        iterator.simulated_mode = False
    else:
        # Default is to use simple simulated board
        pass
    
    iterator.run()


if __name__ == "__main__":
    main() 