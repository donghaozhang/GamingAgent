#!/usr/bin/env python
"""
Tetris Gemini Iterator

This script creates a simple loop to:
1. Capture the Tetris game screen
2. Call Gemini API through OpenRouter to suggest moves
3. Output the response
4. Wait for space key press to continue
5. Repeat the process

Usage:
    python tetris_gemini_iterator.py

Requirements:
    - PIL (Pillow)
    - pyautogui
    - pynput
    - requests
    - python-dotenv
    - openai (for OpenRouter API)
"""

import os
import sys
import time
import base64
import json
import pyautogui
import traceback
import random
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pynput import keyboard
from pathlib import Path
import argparse
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file"""
    try:
        # Use dotenv to load environment variables
        load_dotenv()
        print(f"Loading environment variables from .env file")
        
        # Check if the OPENROUTER_API_KEY is loaded
        if os.environ.get("OPENROUTER_API_KEY"):
            print("Successfully loaded OPENROUTER_API_KEY")
        else:
            print("Warning: OPENROUTER_API_KEY not found in environment variables")
    except Exception as e:
        print(f"Error loading .env file: {e}")

# Load environment variables from .env file
load_env_file()

# Configuration
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    print("Error: OPENROUTER_API_KEY environment variable not found.")
    print("Please create a .env file with your API key.")
    print("Example: OPENROUTER_API_KEY=your_api_key_here")
    sys.exit(1)

# Available models
MODEL_GEMINI_FLASH = "google/gemini-2.0-flash-001"
MODEL_GEMINI_PRO_EXP = "google/gemini-2.0-pro-exp-02-05:free"
MODEL_QWEN_VL = "qwen/qwen2.5-vl-72b-instruct:free"
MODEL = MODEL_GEMINI_FLASH  # Default model (via OpenRouter)

# Output directories
OUTPUT_DIR_GEMINI = "gemini_tetris_outputs"
OUTPUT_DIR_QWEN = "qwen_tetris_outputs"
OUTPUT_DIR = OUTPUT_DIR_GEMINI  # Default output directory

TETRIS_WINDOW_TITLE = "Simple Tetris"  # Window title to look for


class OpenRouterProvider:
    """
    Provider class for OpenRouter API integration.
    This class allows access to various LLMs, including Gemini, through the OpenRouter API.
    """
    
    def __init__(self, model=MODEL_GEMINI_FLASH):
        """
        Initialize the OpenRouter provider with the specified model.
        
        Args:
            model (str): The name of the model to use on OpenRouter, default is Gemini 2.0 Flash.
                        Available models:
                        - "google/gemini-2.0-flash-001" (Gemini 2.0 Flash)
                        - "google/gemini-2.0-pro-exp-02-05:free" (Gemini 2.0 Pro Experimental)
                        - "qwen/qwen2.5-vl-72b-instruct:free" (Qwen2.5 VL 72B Instruct)
        """
        self.model = model
        # Verify API key is available
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set. Please check your .env file.")
        
        # Initialize the OpenAI client with OpenRouter base URL and default headers
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
    def get_response(self, prompt, base64_image=None):
        """
        Get a response from the model through OpenRouter API.
        
        Args:
            prompt (str): The text prompt to send to the model.
            base64_image (str, optional): Base64-encoded image data.
            
        Returns:
            str: The model's response text.
        """
        # Create a messages array for the API request
        messages = []
        
        # Create content array to hold image and text if Claude model
        if "anthropic/claude" in self.model:
            # Claude format with content array
            content = []
            
            # Add image to content if provided
            if base64_image:
                try:
                    # If the base64 string has a data URL prefix, remove it
                    if ',' in base64_image:
                        base64_image = base64_image.split(',', 1)[1]
                    
                    # Add image to content array in Claude format
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64_image,
                        },
                    })
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add text prompt to content
            content.append({
                "type": "text",
                "text": prompt
            })
            
            # Add the message with content array
            messages.append({
                "role": "user",
                "content": content
            })
        else:
            # For non-Claude models use standard OpenAI format
            message_content = []
            
            # Add text content
            message_content.append({
                "type": "text", 
                "text": prompt
            })
            
            # Add image if provided
            if base64_image:
                try:
                    # Add full data URL if not present
                    if not base64_image.startswith("data:"):
                        base64_image = f"data:image/png;base64,{base64_image}"
                        
                    # Add image in OpenAI format
                    message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": base64_image
                        }
                    })
                except Exception as e:
                    print(f"Error processing image: {e}")
            
            # Add message with content
            messages.append({
                "role": "user",
                "content": message_content
            })
        
        # System prompt for Tetris
        system_prompt = """You are an AI assistant that helps play Tetris. 
        Analyze the current game state and suggest the best move for the current piece.
        Return valid PyAutoGUI commands to move the current piece.
        Use pyautogui.press("left"), pyautogui.press("right"), pyautogui.press("up") for rotation, and pyautogui.press("down") for faster drop.
        Your goal is to clear as many lines as possible.
        
        IMPORTANT: First describe what you see on the board (current piece type, next piece, and any existing pieces).
        Then format your response as Python code within triple backticks, like this:
        ```python
        # Move left to position better
        pyautogui.press("left")
        # Rotate for better fit
        pyautogui.press("up")
        ```
        """
        
        try:
            # Call the OpenRouter API using OpenAI client format
            response = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "https://github.com/lmgame-org/GamingAgent",  # Site URL for OpenRouter
                    "X-Title": "Tetris AI Player"  # Site title for OpenRouter
                },
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                max_tokens=1024,
                temperature=0.2
            )
            
            # Return the text from the response
            if hasattr(response, 'choices') and len(response.choices) > 0:
                return response.choices[0].message.content
            return "No valid response from OpenRouter"
        
        except Exception as e:
            # Print the error for debugging
            print(f"Error calling OpenRouter API: {e}")
            
            # Fallback responses for when the API call fails
            fallback_responses = [
                "```python\n# Move left to position the piece better\npyautogui.press('left')\n# Rotate to fit better\npyautogui.press('up')\n```",
                "```python\n# Move right to position the piece\npyautogui.press('right')\n# Drop the piece\npyautogui.press('space')\n```",
                "```python\n# Rotate the piece for better fit\npyautogui.press('up')\n# Position it correctly\npyautogui.press('right')\n```"
            ]
            return random.choice(fallback_responses)


class TetrisAIIterator:
    def __init__(self, model=None, output_dir=None, window_title=None, save_responses=False):
        self.client = OpenRouterProvider(model=model or MODEL)
        self.iteration = 0
        self.stop_flag = False
        
        # Use provided arguments or fall back to global defaults
        self.model = model or MODEL
        self.output_dir = output_dir or OUTPUT_DIR
        self.window_title = window_title or TETRIS_WINDOW_TITLE
        self.save_responses = save_responses
        
        self.session_dir = os.path.join(self.output_dir, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        self.responses_dir = os.path.join(self.session_dir, "responses") if save_responses else None
        self.manual_window_position = None
        
        # Simulation mode flag and state
        self.use_simulated_board = True  # Default to True
        self.simulated_board = None
        self.board_state = None
        self.current_piece = None
        self.next_piece = None
        
        # Create output directories
        os.makedirs(self.screenshots_dir, exist_ok=True)
        if self.save_responses:
            os.makedirs(self.responses_dir, exist_ok=True)
        
        # Create log file
        self.log_path = os.path.join(self.session_dir, "session_log")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"=== Tetris AI Iterator Session started at {datetime.now()} ===\n\n")
            f.write(f"Model: {self.model}\n")
            f.write(f"Window title: {self.window_title}\n")
            f.write(f"Output directory: {self.session_dir}\n\n")
        
        # System prompt
        self.system_prompt = """You are an expert Tetris player. 
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
1. Prioritize keeping the stack flat and balanced
2. Avoid creating holes
3. If you see a chance to clear lines, do it
4. Only control the current piece visible at the top

### Output Format:
First, briefly describe what you see on the board (current piece type, next piece, and any existing pieces).
Then provide your move recommendations as Python code within triple backticks:

```python
# Move left to position better
pyautogui.press("left")
# Rotate for better fit
pyautogui.press("up")
```

Here's the current Tetris game state image:
"""

    # All other methods are the same as TetrisClaudeIterator except for the call_claude_api method
    # which needs to be replaced with call_gemini_api

    def log_message(self, message):
        """Log a message to the console and log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] {message}"
        
        # Print to console
        print(log_entry)
        
        # Save to log file
        try:
            with open(self.log_path, "a", encoding="utf-8", errors="replace") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            print(f"Error writing to log file: {e}")

    def find_tetris_window(self):
        """Find the Tetris window coordinates"""
        # If manual window position is provided, use it
        if self.manual_window_position:
            self.log_message(f"Using manually specified window position: {self.manual_window_position}")
            return self.manual_window_position
            
        try:
            import pygetwindow as gw
            
            # Look for window with Tetris in the title
            tetris_windows = gw.getWindowsWithTitle(self.window_title)
            
            if tetris_windows:
                window = tetris_windows[0]
                self.log_message(f"Found Tetris window: {window.title} at {window.left}, {window.top}, {window.width}, {window.height}")
                return window.left, window.top, window.width, window.height
            else:
                # If we can't find the window, use a default region
                self.log_message("Tetris window not found. Using default screen area.")
                
                # List all available windows to help user
                self.log_message("Available windows:")
                try:
                    all_windows = gw.getAllWindows()
                    for window in all_windows:
                        if window.title:  # Only show windows with titles
                            self.log_message(f"  - '{window.title}' at {window.left}, {window.top}, {window.width}, {window.height}")
                except Exception as e:
                    self.log_message(f"Error listing windows: {e}")
                
                # Use default left portion of the screen
                screen_width, screen_height = pyautogui.size()
                return 0, 0, int(screen_width * 0.4), screen_height
                
        except ImportError:
            self.log_message("pygetwindow not found. Please install with: pip install pygetwindow")
            self.log_message("Using default screen area...")
            
            # Use default screen area (left half of the screen)
            screen_width, screen_height = pyautogui.size()
            return 0, 0, int(screen_width * 0.4), screen_height

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
            self.board_state = board_state
        if current_piece is not None:
            self.current_piece = current_piece
        if next_piece is not None:
            self.next_piece = next_piece
            
        # If any are still None, initialize with defaults
        if self.board_state is None:
            self.board_state = [[0 for _ in range(10)] for _ in range(20)]
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
        for y, row in enumerate(self.board_state):
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
        if self.use_simulated_board and self.simulated_board:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_simulated_iter_{self.iteration}")
            self.simulated_board.save(screenshot_path + ".png")  # Still need .png for PIL to save properly
            self.log_message(f"Simulated Tetris board saved to: {screenshot_path}")
            return screenshot_path + ".png", self.simulated_board
            
        # Otherwise capture a real screenshot
        try:
            # Find Tetris window
            region = self.find_tetris_window()
            
            # Capture screenshot
            self.log_message(f"Capturing screenshot of region: {region}")
            screenshot = pyautogui.screenshot(region=region)
            
            # Save screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_iter_{self.iteration}")
            screenshot.save(screenshot_path + ".png")  # Still need .png for PIL to save properly
            
            # Add timestamp to screenshot
            draw = ImageDraw.Draw(screenshot)
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            draw.text((10, 10), f"{timestamp} - Iteration {self.iteration}", fill="white", font=font)
            screenshot.save(screenshot_path + ".png")
            
            self.log_message(f"Screenshot saved to: {screenshot_path}")
            
            return screenshot_path + ".png", screenshot
            
        except Exception as e:
            self.log_message(f"Error capturing screenshot: {str(e)}")
            traceback.print_exc()
            return None, None

    def encode_image(self, image):
        """Encode image to base64"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

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
            if board_y >= 0 and self.board_state[board_y][board_x] > 0:
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
                self.board_state[board_y][board_x] = color_index
    
    def clear_lines(self):
        """Clear completed lines and shift the board down"""
        lines_to_clear = []
        
        # Find completed lines
        for y in range(20):
            if all(cell > 0 for cell in self.board_state[y]):
                lines_to_clear.append(y)
        
        # Clear lines from bottom to top
        for y in sorted(lines_to_clear, reverse=True):
            # Remove the completed line
            self.board_state.pop(y)
            # Add a new empty line at the top
            self.board_state.insert(0, [0 for _ in range(10)])
            
        return len(lines_to_clear)

    def create_simple_tetris_board(self, piece_type='T'):
        """
        Create a simple Tetris board with only one current piece at the top
        
        Args:
            piece_type: Piece type ('I', 'J', 'L', 'O', 'S', 'T', 'Z')
            
        Returns:
            PIL.Image: Simple Tetris board image
        """
        # Create empty board (no placed pieces)
        self.board_state = [[0 for _ in range(10)] for _ in range(20)]
        
        # Current piece at the top center
        self.current_piece = {
            'type': piece_type,
            'x': 4,
            'y': 0,
            'rotation': 0
        }
        
        # Next piece is I-type
        self.next_piece = {'type': 'I'}
        
        # Create and return simulated board
        return self.create_simulated_tetris_board(
            board_state=self.board_state,
            current_piece=self.current_piece,
            next_piece=self.next_piece
        )

    def call_model_api(self, image):
        """Call model API via OpenRouter with the Tetris screenshot"""
        try:
            self.log_message(f"Calling model API via OpenRouter with model {self.model} (iteration {self.iteration})...")
            start_time = time.time()
            
            # Encode image
            base64_image = self.encode_image(image)
            
            # Call model API via OpenRouter
            response = self.client.get_response(self.instruction_prompt, base64_image)
            
            elapsed_time = time.time() - start_time
            self.log_message(f"Model API response received in {elapsed_time:.2f}s")
            
            # Log response to session log
            self.log_message(f"=== Model API Response (Iteration {self.iteration}) ===")
            self.log_message(f"Model: {self.model}")
            self.log_message(f"API Latency: {elapsed_time:.2f}s")
            
            # Save the response if enabled
            if self.save_responses:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                response_path = os.path.join(self.responses_dir, f"{timestamp}_response_{self.iteration}")
                with open(response_path, "w", encoding="utf-8") as f:
                    f.write(f"=== Model API Response (Iteration {self.iteration}) ===\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Model: {self.model}\n")
                    f.write(f"API Latency: {elapsed_time:.2f}s\n\n")
                    f.write(response)
                
                self.log_message(f"Response saved to: {response_path}")
            
            return response
            
        except Exception as e:
            self.log_message(f"Error calling model API: {str(e)}")
            traceback.print_exc()
            
            # Return fallback response if API call fails
            fallback_responses = [
                "```python\n# Move left to position the piece better\npyautogui.press('left')\n# Rotate to fit better\npyautogui.press('up')\n```",
                "```python\n# Move right to position the piece\npyautogui.press('right')\n# Drop the piece\npyautogui.press('space')\n```",
                "```python\n# Rotate the piece for better fit\npyautogui.press('up')\n# Position it correctly\npyautogui.press('right')\n```"
            ]
            return random.choice(fallback_responses)

    def wait_for_space_key(self):
        """Wait for the user to press the space key"""
        self.log_message("Press SPACE to continue or Q to quit...")
        
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
        
        # Start listener with a timeout mechanism
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        
        # Wait for key press with timeout to allow for interruption
        max_wait = 60  # Maximum 60 seconds wait time
        for _ in range(max_wait * 10):  # Check every 0.1 seconds
            if space_pressed or quit_pressed or self.stop_flag:
                break
            time.sleep(0.1)
            
        # Ensure listener is stopped
        if listener.is_alive():
            listener.stop()
        
        if quit_pressed:
            self.stop_flag = True
            self.log_message("Quit requested. Stopping...")
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
        """Execute the code from Gemini's response and simulate the movement"""
        if not code:
            self.log_message("No executable code found in response.")
            return
        
        self.log_message("Executing code...")
        self.log_message(f"Code to execute:\n{code}")
        
        # Create a new dictionary to store the actions that will be performed
        actions = []
        
        # Extract actions from the code
        lines = code.strip().split('\n')
        for line in lines:
            if 'pyautogui.press' in line:
                # Extract key from the press command
                import re
                match = re.search(r'press\([\'"](.+?)[\'"]\)', line)
                if match:
                    key = match.group(1)
                    actions.append(key)
        
        self.log_message(f"Extracted actions: {actions}")
        
        if not actions:
            self.log_message("No valid actions found in code.")
            return
        
        # Check if there's already a space (hard drop) in the actions
        has_hard_drop = 'space' in actions
        
        # If no hard drop is included, add one at the end to ensure the piece drops to the floor
        if not has_hard_drop:
            actions.append('space')
            self.log_message("Automatically adding 'space' action to drop piece to floor")
        
        # Take a pre-execution screenshot of the initial state
        if self.use_simulated_board and self.simulated_board:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            pre_screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_pre_execution_{self.iteration}")
            self.simulated_board.save(pre_screenshot_path + ".png")
        
        # Simulate piece movement based on actions
        if self.use_simulated_board and self.current_piece:
            # Clone the current piece for simulation
            piece = self.current_piece.copy()
            
            for action in actions:
                # Apply action to the piece
                if action == 'left':
                    piece['x'] -= 1
                    # Check if valid (not outside board or colliding)
                    if not self.is_valid_position(piece):
                        piece['x'] += 1  # Undo if invalid
                
                elif action == 'right':
                    piece['x'] += 1
                    # Check if valid
                    if not self.is_valid_position(piece):
                        piece['x'] -= 1  # Undo if invalid
                
                elif action == 'up' or action == 'rotate':
                    # Rotate piece (clockwise)
                    piece_type = piece['type']
                    max_rotation = len(self.piece_shapes[piece_type])
                    piece['rotation'] = (piece['rotation'] + 1) % max_rotation
                    # Check if valid
                    if not self.is_valid_position(piece):
                        # Try kick (wall kick) - move left or right if rotation causes collision
                        # First try moving right
                        piece['x'] += 1
                        if not self.is_valid_position(piece):
                            # If right doesn't work, try left
                            piece['x'] -= 2
                            if not self.is_valid_position(piece):
                                # If left doesn't work either, undo rotation
                                piece['x'] += 1  # Reset to original x
                                piece['rotation'] = (piece['rotation'] - 1) % max_rotation
                
                elif action == 'down':
                    piece['y'] += 1
                    # Check if valid
                    if not self.is_valid_position(piece):
                        piece['y'] -= 1  # Undo if invalid
                
                elif action == 'space':
                    # Hard drop - move down until collision
                    while self.is_valid_position(piece):
                        piece['y'] += 1
                    # Move back up one step after finding invalid position
                    piece['y'] -= 1
                    
                    # Lock the piece in place
                    self.lock_piece(piece)
                    
                    # Use next piece as current piece
                    import random
                    piece_types = ['I', 'J', 'L', 'O', 'S', 'T', 'Z']
                    self.current_piece = {
                        'type': self.next_piece['type'],
                        'x': 4,
                        'y': 0,
                        'rotation': 0
                    }
                    self.next_piece = {'type': random.choice(piece_types)}
                    
                    # Update piece for further actions
                    piece = self.current_piece.copy()
                    
                    # Check and clear lines
                    self.clear_lines()
            
            # Update current piece with the final position
            self.current_piece = piece
        
        # Create updated board after movement
        if self.use_simulated_board:
            self.create_simulated_tetris_board()
        
            # Take a post-execution screenshot of the updated state
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            post_screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_post_execution_{self.iteration}")
            self.simulated_board.save(post_screenshot_path + ".png")
            self.log_message(f"Post-execution screenshot saved to: {post_screenshot_path}")
        
        # Also execute the code using PyAutoGUI for real-game scenarios
        try:
            # Add necessary imports
            if "import pyautogui" not in code:
                code = "import pyautogui\nimport time\n" + code
            
            # If we automatically added a space action, add it to the code too
            if not has_hard_drop and not self.use_simulated_board:
                code += "\n# Automatically added to drop piece to floor\npyautogui.press('space')"
            
            # Execute the code (only for real game mode)
            if not self.use_simulated_board:
                exec(code, {"pyautogui": pyautogui, "time": time})
            
            self.log_message("Code execution completed.")
            
        except Exception as e:
            self.log_message(f"Error executing code: {str(e)}")
            traceback.print_exc()

    def run(self):
        """Main loop"""
        self.log_message("=== Starting Tetris AI Iterator ===")
        self.log_message(f"Output directory: {self.session_dir}")
        self.log_message("Press space to start...")
        
        # Determine the model name for display
        if "qwen" in self.model.lower():
            model_display_name = "Qwen"
        elif "gemini" in self.model.lower():
            model_display_name = "Gemini"
        else:
            model_display_name = "AI"
        
        try:
            # Wait for initial space press
            if not self.wait_for_space_key():
                return
            
            while not self.stop_flag:
                try:
                    self.iteration += 1
                    self.log_message(f"\n=== Iteration {self.iteration} ===")
                    
                    # Capture screenshot
                    screenshot_path, screenshot = self.capture_screenshot()
                    if screenshot is None:
                        self.log_message("Failed to capture screenshot. Waiting for next iteration...")
                        if not self.wait_for_space_key():
                            break
                        continue
                    
                    # Call model API
                    response = self.call_model_api(screenshot)
                    
                    # Display response
                    print("\n" + "="*50)
                    print(f"{model_display_name}'s Response:")
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
            self.log_message("=== Tetris AI Iterator finished ===")


def cleanup_txt_files():
    """Remove any .txt files in the gemini_tetris_outputs directory"""
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
    """Main function"""
    # Check if the script is run directly
    if __name__ != "__main__":
        return
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tetris AI Iterator - Control Tetris with AI models via OpenRouter")
    parser.add_argument("--window", type=str, help="Manually specify window position as 'x,y,width,height'")
    parser.add_argument("--model", type=str, default=MODEL, help=f"Model to use via OpenRouter (default: {MODEL})")
    parser.add_argument("--use-pro-exp", action="store_true", help=f"Use Gemini Pro 2.0 Experimental model ({MODEL_GEMINI_PRO_EXP})")
    parser.add_argument("--use-qwen", action="store_true", help=f"Use Qwen2.5 VL 72B Instruct model ({MODEL_QWEN_VL})")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR, help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--window-title", type=str, default=TETRIS_WINDOW_TITLE, 
                        help=f"Window title to look for (default: '{TETRIS_WINDOW_TITLE}')")
    
    # Simulation mode options
    parser.add_argument("--no-simulate", action="store_true", help="Don't use simulated board (capture real screenshots)")
    parser.add_argument("--complex", action="store_true", help="Use complex board with multiple pieces (not simple)")
    parser.add_argument("--piece", type=str, default='T', choices=['I', 'J', 'L', 'O', 'S', 'T', 'Z'], 
                        help="Piece type for simple simulation (default: T)")
    parser.add_argument("--fill", type=int, default=30, help="Fill percentage for complex board (default: 30)")
    parser.add_argument("--height", type=int, default=15, help="Maximum height for complex board (default: 15)")
    
    # Output options
    parser.add_argument("--save-responses", action="store_true", help="Save API responses to files")
    parser.add_argument("--cleanup", action="store_true", help="Remove any existing .txt files in the output directory")
    
    args = parser.parse_args()
    
    # Clean up .txt files if requested
    if args.cleanup:
        cleanup_txt_files()
    
    # Set the model based on command-line arguments
    selected_model = args.model
    selected_output_dir = args.output_dir
    
    if args.use_pro_exp:
        selected_model = MODEL_GEMINI_PRO_EXP
        print(f"Using Gemini Pro 2.0 Experimental model: {selected_model}")
        if not args.output_dir:
            selected_output_dir = OUTPUT_DIR_GEMINI
    elif args.use_qwen:
        selected_model = MODEL_QWEN_VL
        print(f"Using Qwen2.5 VL 72B Instruct model: {selected_model}")
        if not args.output_dir:
            selected_output_dir = OUTPUT_DIR_QWEN
    else:
        # For default or custom models, set output dir based on model name
        if not args.output_dir:
            if "qwen" in selected_model.lower():
                selected_output_dir = OUTPUT_DIR_QWEN
            else:
                selected_output_dir = OUTPUT_DIR_GEMINI
    
    # Create and run the iterator with custom settings
    iterator = TetrisAIIterator(
        model=selected_model, 
        output_dir=selected_output_dir, 
        window_title=args.window_title,
        save_responses=args.save_responses
    )
    
    # Set manual window position if provided
    if args.window:
        try:
            x, y, width, height = map(int, args.window.split(','))
            iterator.manual_window_position = (x, y, width, height)
            print(f"Using manual window position: {iterator.manual_window_position}")
        except (ValueError, TypeError) as e:
            print(f"Error parsing window position: {e}")
            print("Format should be: x,y,width,height (e.g., 0,0,500,600)")
            return
    
    # Enable simulation mode based on command-line options
    if args.no_simulate:
        print("Using real screenshots instead of simulated board")
        iterator.use_simulated_board = False
    else:
        # Default is to use simple simulated board
        if args.complex:
            print("Using complex simulated Tetris board with multiple pieces")
            # Generate random board state
            board, current_piece, next_piece = iterator.simulate_random_board_state(
                fill_percentage=args.fill,
                max_height=args.height
            )
            
            # Create simulated board
            iterator.create_simulated_tetris_board(
                board_state=board,
                current_piece=current_piece,
                next_piece=next_piece
            )
        else:
            print(f"Using simple simulated Tetris board with a single {args.piece} piece")
            # Create simple board with just one piece
            iterator.create_simple_tetris_board(piece_type=args.piece)
    
    # Run the iterator
    iterator.run()


if __name__ == "__main__":
    main() 