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
import pyautogui
import traceback
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pynput import keyboard
from pathlib import Path
import argparse

# Load environment variables from .env file
def load_env_file():
    """Load environment variables from .env file"""
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        print(f"Loading environment variables from {env_path}")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, value = line.split('=', 1)
                os.environ[key] = value
                print(f"Loaded {key} from .env file")
    else:
        print(f"Warning: .env file not found at {env_path}")

# Load environment variables from .env file
load_env_file()

# Import Anthropic client - install with: pip install anthropic
try:
    import anthropic
except ImportError:
    print("Please install Anthropic Python client: pip install anthropic")
    sys.exit(1)

# Configuration
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not CLAUDE_API_KEY:
    print("Error: ANTHROPIC_API_KEY environment variable not found.")
    print("Please create a .env file in the GamingAgent directory with your API key.")
    print("Example: ANTHROPIC_API_KEY=sk-ant-api03-...")
    sys.exit(1)
else:
    print("Successfully loaded ANTHROPIC_API_KEY")

MODEL = "claude-3-7-sonnet-20250219"  # Change to the desired model
OUTPUT_DIR = "claude_tetris_outputs"
TETRIS_WINDOW_TITLE = "Simple Tetris"  # Window title to look for


class TetrisClaudeIterator:
    def __init__(self, model=None, output_dir=None, window_title=None):
        self.client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
        self.iteration = 0
        self.stop_flag = False
        
        # Use provided arguments or fall back to global defaults
        self.model = model or MODEL
        self.output_dir = output_dir or OUTPUT_DIR
        self.window_title = window_title or TETRIS_WINDOW_TITLE
        
        self.session_dir = os.path.join(self.output_dir, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.screenshots_dir = os.path.join(self.session_dir, "screenshots")
        self.responses_dir = os.path.join(self.session_dir, "responses")
        self.manual_window_position = None
        
        # Create output directories
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        
        # Create log file
        self.log_path = os.path.join(self.session_dir, "session_log.txt")
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write(f"=== Tetris Claude Iterator Session started at {datetime.now()} ===\n\n")
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
1. Prioritize keeping the stack flat and balanced
2. Avoid creating holes
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
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")

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

    def capture_screenshot(self):
        """Capture screenshot of the Tetris game"""
        try:
            # Find Tetris window
            region = self.find_tetris_window()
            
            # Capture screenshot
            self.log_message(f"Capturing screenshot of region: {region}")
            screenshot = pyautogui.screenshot(region=region)
            
            # Save screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_iter_{self.iteration}.png")
            screenshot.save(screenshot_path)
            
            # Add timestamp to screenshot
            draw = ImageDraw.Draw(screenshot)
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
            
            draw.text((10, 10), f"{timestamp} - Iteration {self.iteration}", fill="white", font=font)
            screenshot.save(screenshot_path)
            
            self.log_message(f"Screenshot saved to: {screenshot_path}")
            
            return screenshot_path, screenshot
            
        except Exception as e:
            self.log_message(f"Error capturing screenshot: {str(e)}")
            traceback.print_exc()
            return None, None

    def encode_image(self, image):
        """Encode image to base64"""
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def call_claude_api(self, image):
        """Call Claude API with the Tetris screenshot"""
        try:
            self.log_message(f"Calling Claude API with model {self.model} (iteration {self.iteration})...")
            start_time = time.time()
            
            # Encode image
            base64_image = self.encode_image(image)
            
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.instruction_prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64_image}}
                        ]
                    }
                ]
            )
            
            elapsed_time = time.time() - start_time
            self.log_message(f"Claude API response received in {elapsed_time:.2f}s")
            
            # Extract content
            response_content = response.content[0].text
            
            # Save the response
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            response_path = os.path.join(self.responses_dir, f"{timestamp}_response_{self.iteration}.txt")
            with open(response_path, "w", encoding="utf-8") as f:
                f.write(f"=== Claude API Response (Iteration {self.iteration}) ===\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"Model: {self.model}\n")
                f.write(f"API Latency: {elapsed_time:.2f}s\n\n")
                f.write(response_content)
            
            self.log_message(f"Response saved to: {response_path}")
            
            return response_content
            
        except Exception as e:
            self.log_message(f"Error calling Claude API: {str(e)}")
            traceback.print_exc()
            return f"Error: {str(e)}"

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
        """Execute the code from Claude's response"""
        if not code:
            self.log_message("No executable code found in response.")
            return
        
        self.log_message("Executing code...")
        self.log_message(f"Code to execute:\n{code}")
        
        try:
            # Add necessary imports
            if "import pyautogui" not in code:
                code = "import pyautogui\nimport time\n" + code
            
            # Execute the code
            exec(code, {"pyautogui": pyautogui, "time": time})
            self.log_message("Code execution completed.")
            
            # Take a post-execution screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            post_screenshot_path = os.path.join(self.screenshots_dir, f"{timestamp}_post_execution_{self.iteration}.png")
            post_screenshot = pyautogui.screenshot(region=self.find_tetris_window())
            post_screenshot.save(post_screenshot_path)
            self.log_message(f"Post-execution screenshot saved to: {post_screenshot_path}")
            
        except Exception as e:
            self.log_message(f"Error executing code: {str(e)}")
            traceback.print_exc()

    def run(self):
        """Main loop"""
        self.log_message("=== Starting Tetris Claude Iterator ===")
        self.log_message(f"Output directory: {self.session_dir}")
        self.log_message("Press space to start...")
        
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


def main():
    """Main function"""
    # Check if the script is run directly
    if __name__ != "__main__":
        return
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Tetris Claude Iterator - Control Tetris with Claude API")
    parser.add_argument("--window", type=str, help="Manually specify window position as 'x,y,width,height'")
    parser.add_argument("--model", type=str, default=MODEL, help=f"Claude model to use (default: {MODEL})")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR, help=f"Output directory (default: {OUTPUT_DIR})")
    parser.add_argument("--window-title", type=str, default=TETRIS_WINDOW_TITLE, 
                        help=f"Window title to look for (default: '{TETRIS_WINDOW_TITLE}')")
    
    args = parser.parse_args()
    
    # Create and run the iterator with custom settings
    iterator = TetrisClaudeIterator(model=args.model, output_dir=args.output_dir, window_title=args.window_title)
    
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
    
    # Run the iterator
    iterator.run()


if __name__ == "__main__":
    main() 