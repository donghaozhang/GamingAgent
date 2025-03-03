import time
import os
import pyautogui
import numpy as np
from queue import Queue
import pygame
import win32gui
import win32ui
import win32con
from ctypes import windll
from PIL import Image
import keyboard  # Add this import for direct keyboard control
import logging
import sys
from io import BytesIO
import base64
import datetime
from contextlib import redirect_stdout, redirect_stderr
from pygame.locals import *
import traceback

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion
# Remove circular import
# from tetris_agent import check_for_quit

# Get the logger
logger = logging.getLogger("TetrisAgent.Worker")

# Global variables
game_running = True
game_state = Queue()

# Define our own check_for_quit function to avoid circular imports
def check_for_quit():
    global game_running
    try:
        if keyboard.is_pressed('q'):
            logger.info("Q key pressed at system level - terminating game")
            game_running = False
            # Try to use pygame's event system to quit cleanly
            try:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            except:
                pass
            return True
        return False
    except ImportError:
        # Keyboard module not available
        return False

# Function to capture a specific window by title
def capture_window(window_title):
    """Capture a screenshot of a window with the specified title"""
    try:
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd == 0:
            return None
            
        # Get window dimensions
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top
        
        # Create device context and bitmap
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        
        # Create bitmap object to store screen capture
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)
        
        # Copy screen to bitmap
        result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
        
        # Convert to PIL Image
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1)
            
        # Clean up
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        
        if result == 1:
            logger.debug(f"Successfully captured window: {window_title}")
            return img
        else:
            logger.warning("Failed to capture window. Falling back to region capture.")
            return None
    except Exception as e:
        logger.error(f"Error capturing window: {e}")
        return None

# Capture a specific region of the screen
def capture_screen_region(region):
    """Capture a specific region of the screen"""
    try:
        if region:
            screenshot = pyautogui.screenshot(region=region)
            return screenshot
        else:
            return None
    except Exception as e:
        logger.error(f"Error capturing screen region: {e}")
        return None

# Define the Tetris prompt used for all AI interactions
tetris_prompt = """
You are an expert Tetris AI agent. I'll provide you with a screenshot of a Tetris game in progress.

Your task is to:
1. Analyze the current game state, including the falling piece, next piece, and the playing field
2. Determine the optimal move (LEFT, RIGHT, UP for rotation, DOWN for soft drop)
3. Return ONLY a Python code that outputs the appropriate pygame key constant

IMPORTANT: Your response MUST include ONLY ONE of these exact constants as the last line of your code:
- pygame.K_LEFT
- pygame.K_RIGHT
- pygame.K_UP
- pygame.K_DOWN

The system only recognizes these exact constants to control the game.

Example response if you can see a valid Tetris game:
```python
# I can see a Tetris game with an L piece falling.
# The best move is to move left to fill the gap.
pygame.K_LEFT
```

If you can't see a Tetris game in the image:
```python
# I don't see a valid Tetris game in this image.
None
```
"""

# Maximum failures before quitting
max_consecutive_failures = 10

# Function to ensure screenshots directory exists
def ensure_screenshot_dir():
    """Create screenshot directory if it doesn't exist"""
    try:
        # Create logs/screenshots directory if it doesn't exist
        screenshot_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tetris", "logs", "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        return screenshot_dir
    except Exception as e:
        logger.error(f"Error creating screenshots directory: {e}")
        return None

# Function to save screenshot with timestamp
def save_screenshot(image, thread_id, action=None):
    """Save screenshot with timestamp and action information"""
    try:
        screenshot_dir = ensure_screenshot_dir()
        if not screenshot_dir:
            return
            
        # Create timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Create filename with thread_id, timestamp, and action if available
        if action:
            filename = f"thread_{thread_id}_{timestamp}_{action}.png"
        else:
            filename = f"thread_{thread_id}_{timestamp}.png"
            
        # Save screenshot
        filepath = os.path.join(screenshot_dir, filename)
        image.save(filepath)
        logger.debug(f"[Thread {thread_id}] Saved screenshot to {filepath}")
    except Exception as e:
        logger.error(f"[Thread {thread_id}] Error saving screenshot: {e}")

def worker_tetris(result_queue, stop_event, worker_id, model_provider, tetris_prompt, is_playback):
    """
    A worker that plays Tetris.
    """
    import os
    import sys
    import pygame
    import time
    import random
    import tempfile
    import numpy as np
    from io import StringIO
    from PIL import Image
    from contextlib import redirect_stdout, redirect_stderr
    # Import specific pygame constants instead of using wildcard import
    from pygame.locals import KEYDOWN, KEYUP, QUIT
    
    # Create a logger for this worker
    import logging
    logger = logging.getLogger(f"TetrisAgent.Worker{worker_id}")
    logger.info(f"Worker {worker_id} started")
    
    # Create a directory for screenshots if it doesn't exist
    screenshot_dir = os.path.join("games", "tetris", "logs", "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    logger.info(f"Screenshots will be saved to {screenshot_dir}")
    
    # Setup pygame for key presses
    pygame.init()
    
    # Add these helper functions for key presses
    def send_key_event(key_code):
        """Send a key down and up event to pygame."""
        logger.info(f"Sending key event for {key_code}")
        # Create and post key down event
        key_down = pygame.event.Event(pygame.KEYDOWN, {"key": key_code})
        pygame.event.post(key_down)
        # Small delay to ensure the event is processed
        time.sleep(0.05)
        # Create and post key up event
        key_up = pygame.event.Event(pygame.KEYUP, {"key": key_code})
        pygame.event.post(key_up)
        return True
    
    def press_key_directly(key_code):
        """Press a key directly using pygame key state modifications."""
        logger.info(f"Directly pressing key {key_code}")
        # Create a key state dictionary
        key_state = pygame.key.get_pressed()
        # Modify the key state array
        # Unfortunately, we can't directly modify the key state in pygame
        # But we can simulate it by sending multiple events
        for _ in range(3):  # Send multiple events to ensure it's processed
            send_key_event(key_code)
            time.sleep(0.05)
        return True
    
    def take_screenshot(prefix="move"):
        """Take a screenshot of the current pygame window and save it."""
        try:
            # Get the current timestamp for unique filenames
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            random_suffix = random.randint(1000, 9999)
            filename = f"{prefix}_{timestamp}_{random_suffix}.png"
            filepath = os.path.join(screenshot_dir, filename)
            
            # Get the surface of the current window
            surface = pygame.display.get_surface()
            if surface:
                pygame.image.save(surface, filepath)
                logger.info(f"Screenshot saved to {filepath}")
                return filepath
            else:
                logger.warning("No pygame surface available for screenshot")
                return None
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None
    
    # This maps the key strings to pygame constants
    key_map = {
        "pygame.K_LEFT": pygame.K_LEFT,
        "pygame.K_RIGHT": pygame.K_RIGHT,
        "pygame.K_UP": pygame.K_UP,
        "pygame.K_DOWN": pygame.K_DOWN,
    }
    
    def extract_keys_from_response(response):
        """
        Extract valid pygame key constants from the AI's response.
        """
        if not response or not isinstance(response, str):
            logger.warning("Invalid response format")
            return None
        
        # Clean the response to get just the code
        cleaned_code = response.strip()
        
        try:
            # First attempt: Try to find direct references to pygame key constants
            for key_str, key_code in key_map.items():
                if key_str in cleaned_code:
                    logger.info(f"Found key directly in response: {key_str}")
                    return key_code
            
            # Second attempt: Try to execute the code in a controlled environment
            # Create a namespace with pygame key constants
            namespace = {
                "pygame": pygame
            }
            
            # Redirect stdout to capture any printed output
            output = StringIO()
            with redirect_stdout(output):
                try:
                    # Execute the AI's code in the namespace
                    exec(cleaned_code, namespace)
                    # Check if the code printed any key constant
                    printed_output = output.getvalue().strip()
                    logger.info(f"AI code execution output: {printed_output}")
                    
                    # Check if the output is a valid key
                    for key_str, key_code in key_map.items():
                        if key_str in printed_output:
                            logger.info(f"Found key in executed output: {key_str}")
                            return key_code
                except Exception as e:
                    logger.error(f"Error executing AI code: {e}")
            
            # Third attempt: Check if any namespace variables are valid key constants
            for var_name, var_value in namespace.items():
                if var_name != "pygame" and isinstance(var_value, int):
                    # Check if this value matches any of our key codes
                    for key_code in key_map.values():
                        if var_value == key_code:
                            logger.info(f"Found key in namespace variables: {var_value}")
                            return key_code
            
            # Last resort: See if any literal key constants are present
            if "K_LEFT" in cleaned_code or "LEFT" in cleaned_code.upper():
                logger.info("Detected LEFT direction from text pattern")
                return pygame.K_LEFT
            elif "K_RIGHT" in cleaned_code or "RIGHT" in cleaned_code.upper():
                logger.info("Detected RIGHT direction from text pattern")
                return pygame.K_RIGHT
            elif "K_UP" in cleaned_code or "UP" in cleaned_code.upper() or "ROTATE" in cleaned_code.upper():
                logger.info("Detected UP/ROTATE direction from text pattern")
                return pygame.K_UP
            elif "K_DOWN" in cleaned_code or "DOWN" in cleaned_code.upper():
                logger.info("Detected DOWN direction from text pattern")
                return pygame.K_DOWN
            
            logger.warning("Could not extract any valid key from response")
            return None
        
        except Exception as e:
            logger.error(f"Error extracting keys: {e}")
            return None
    
    # Set the environment variable to skip loading pygame fonts
    os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
    
    # This is needed for pygame to work properly
    os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (0, 0)
    
    # Import the game module here to avoid circular import
    from games.tetris.game import Tetris
    game_module = Tetris
    
    # Track successful actions
    action_count = 0
    success_count = 0
    
    try:
        # Main worker loop
        while not stop_event.is_set():
            logger.info(f"Worker {worker_id} calling run_game")
            
            # Take a screenshot before starting the game
            take_screenshot("before_game")
            
            # The Tetris module doesn't have a run_game function that returns state
            # Instead, we'll capture the current state directly
            try:
                # Get the current state of the game directly
                # This assumes there's already a running game instance
                import pygame.display
                
                # Take a screenshot to analyze
                screenshot_path = take_screenshot("game_state")
                
                # Create a basic state representation
                # In a real implementation, we would extract state from the game
                # For now, we'll create a simple state with the current screen
                state = {
                    "screenshot": screenshot_path,
                    "timestamp": time.time()
                }
                logger.info(f"Captured game state with screenshot: {screenshot_path}")
            except Exception as e:
                logger.error(f"Error capturing game state: {e}")
                logger.error(traceback.format_exc())
                if stop_event.is_set():
                    break
                time.sleep(1)
                continue
            
            if state == "QUIT":
                logger.info("Game returned QUIT signal, stopping worker")
                break
                
            # Continue with AI action if we have a valid game state
            if state:
                # Take a screenshot of the current game state
                screenshot_path = take_screenshot("game_state")
                
                # Format the prompt with the game state
                prompt = tetris_prompt.format(
                    game_state=str(state)
                )
                
                # Get the AI's response
                logger.info(f"Worker {worker_id} getting AI response")
                if model_provider is None:
                    # If no model provider, just randomly select a key
                    key_options = [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN]
                    # Favor DOWN more often for faster gameplay
                    key_options.extend([pygame.K_DOWN] * 2)
                    key = random.choice(key_options)
                    response = f"Random key selected: {key}"
                else:
                    response = model_provider.get_response(prompt)
                
                logger.info(f"Worker {worker_id} received AI response: {response[:100]}...")
                
                # Extract the key from the response
                action_count += 1
                key = extract_keys_from_response(response)
                
                if key is not None:
                    logger.info(f"Worker {worker_id} extracted key: {key}")
                    
                    # Prevent the AI from quitting the game
                    if key == pygame.K_q:
                        logger.warning("AI attempted to press Q to quit - ignoring")
                        continue
                    
                    # Take a screenshot before pressing the key
                    take_screenshot(f"before_key_{key}")
                    
                    # Try multiple methods to ensure the key press is registered
                    try:
                        # Method 1: Send key event (preferred)
                        success1 = send_key_event(key)
                        
                        # Enhanced method: Send the key event multiple times for better detection
                        logger.info(f"Sending key {key} multiple times to ensure detection")
                        # Send the key event multiple times with small delays
                        for _ in range(3):
                            send_key_event(key)
                            time.sleep(0.05)
                        
                        # Method 2: Direct key press using keyboard module (fallback)
                        try:
                            # Map pygame keys to keyboard keys
                            key_mapping = {
                                pygame.K_LEFT: 'left',
                                pygame.K_RIGHT: 'right',
                                pygame.K_UP: 'up',
                                pygame.K_DOWN: 'down'
                            }
                            
                            if key in key_mapping:
                                keyboard_key = key_mapping[key]
                                logger.info(f"Pressing key directly with keyboard module: {keyboard_key}")
                                keyboard.press_and_release(keyboard_key)
                                success2 = True
                            else:
                                success2 = False
                        except Exception as kb_error:
                            logger.error(f"Keyboard module error: {kb_error}")
                            success2 = False
                            
                        # Method 3: Try using pyautogui as a last resort
                        try:
                            key_to_pyautogui = {
                                pygame.K_LEFT: 'left',
                                pygame.K_RIGHT: 'right',
                                pygame.K_UP: 'up',
                                pygame.K_DOWN: 'down'
                            }
                            
                            if key in key_to_pyautogui:
                                pyautogui_key = key_to_pyautogui[key]
                                logger.info(f"Pressing key with pyautogui: {pyautogui_key}")
                                pyautogui.press(pyautogui_key)
                                success3 = True
                            else:
                                success3 = False
                        except Exception as pag_error:
                            logger.error(f"PyAutoGUI error: {pag_error}")
                            success3 = False
                        
                        # Count success if any method worked
                        if success1 or success2 or success3:
                            success_count += 1
                            # Take a screenshot after pressing the key
                            take_screenshot(f"after_key_{key}")
                            logger.info(f"Successfully pressed key {key}")
                        else:
                            logger.warning(f"All key press methods failed for key {key}")
                        
                        # Add a larger delay to see the effect and ensure the game processes the input
                        time.sleep(0.3)
                        
                    except Exception as e:
                        logger.error(f"Error pressing key {key}: {e}")
                else:
                    logger.warning(f"Worker {worker_id} could not extract a valid key from response")
            
            # Short delay to avoid hogging CPU
            time.sleep(0.05)
            
    except Exception as e:
        logger.error(f"Worker {worker_id} encountered an error: {e}")
    finally:
        logger.info(f"Worker {worker_id} stopped. Action count: {action_count}, Success count: {success_count}")
        # Put a signal in the queue to indicate we're done
        if not result_queue.full():
            result_queue.put(f"Worker {worker_id} stopped")
        # Ensure pygame is quit properly
        pygame.quit()

def worker_thread_function(thread_id, game_state_queue, action_queue, game_running, worker_type='standard'):
    # ... existing code ...
    
    while game_running.value:
        # Check for Q key to quit
        check_for_quit()
        
        # ... existing code ...
