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
import random  # Make sure random is imported

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion

# Try to import API_COOLDOWN_SECONDS from tetris_agent
try:
    from games.tetris.tetris_agent import API_COOLDOWN_SECONDS as GLOBAL_API_COOLDOWN
except ImportError:
    try:
        # Try relative import if we're running from within the tetris directory
        from tetris_agent import API_COOLDOWN_SECONDS as GLOBAL_API_COOLDOWN
    except ImportError:
        # Default value if we can't import it
        GLOBAL_API_COOLDOWN = 10.0

# Get the logger
logger = logging.getLogger("TetrisAgent.Worker")

# Global variables
game_running = True
game_state = Queue()

# Add API cooldown settings to reduce costs
API_COOLDOWN_SECONDS = GLOBAL_API_COOLDOWN  # Use the global setting
last_api_call_time = 0
cached_response = None
cached_state_hash = None

# Generate a timestamp-based run ID for organizing screenshots
RUN_ID = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
SCREENSHOTS_FOLDER = None  # Will be set during initialization

# Add a function to hash the game state for comparison
def hash_game_state(state):
    """Generate a simple hash of the game state to detect changes"""
    try:
        # If state is a dictionary, convert to a string representation
        if isinstance(state, dict):
            # Only use essential information that affects game decisions
            # Ignore things like timestamps and screenshot paths
            state_str = str(state.get("current_piece", "")) + str(state.get("grid", ""))
            return hash(state_str)
        return hash(str(state))
    except Exception as e:
        logger.error(f"Error hashing game state: {e}")
        return random.randint(0, 100000)  # Fallback random hash

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
    """Ensure the screenshots directory exists"""
    global SCREENSHOTS_FOLDER
    
    # Create base screenshots directory
    screenshots_dir = os.path.join("games", "tetris", "logs", "screenshots")
    if not os.path.exists(screenshots_dir):
        os.makedirs(screenshots_dir, exist_ok=True)
        
    # Create a run-specific directory using the timestamp
    SCREENSHOTS_FOLDER = os.path.join(screenshots_dir, f"run_{RUN_ID}")
    if not os.path.exists(SCREENSHOTS_FOLDER):
        os.makedirs(SCREENSHOTS_FOLDER, exist_ok=True)
        
    # Create specific folders for different types of screenshots
    important_folder = os.path.join(SCREENSHOTS_FOLDER, "important")
    if not os.path.exists(important_folder):
        os.makedirs(important_folder, exist_ok=True)
    
    return SCREENSHOTS_FOLDER

def save_screenshot(image, thread_id, action=None, important=False):
    """Save a screenshot to a file with a timestamp"""
    global SCREENSHOTS_FOLDER
    
    if SCREENSHOTS_FOLDER is None:
        ensure_screenshot_dir()
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    
    # Determine which subfolder to use
    if important:
        save_folder = os.path.join(SCREENSHOTS_FOLDER, "important")
    else:
        save_folder = SCREENSHOTS_FOLDER
    
    # Create the filename
    if action:
        filename = f"{action}_{timestamp}.png"
    else:
        filename = f"screenshot_{timestamp}.png"
    
    filepath = os.path.join(save_folder, filename)
    
    try:
        image.save(filepath)
        return filepath
    except Exception as e:
        logger.error(f"Error saving screenshot: {e}")
        return None

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
    
    def take_screenshot(prefix="move", important=False):
        # Create a screenshot
        hwnd = win32gui.FindWindow(None, 'Tetris')
        if hwnd:
            # Get window position and dimensions
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            
            # Take screenshot of the window
            image = capture_window('Tetris')
            if image:
                # Save to temp path
                return save_screenshot(image, worker_id, prefix, important=important)
            else:
                # Fallback to screen region capture
                return save_screenshot(capture_screen_region((left, top, width, height)), worker_id, prefix, important=important)
        else:
            # Fallback for when window can't be found
            return save_screenshot(pyautogui.screenshot(), worker_id, prefix, important=important)
    
    # This maps the key strings to pygame constants
    key_map = {
        "pygame.K_LEFT": pygame.K_LEFT,
        "pygame.K_RIGHT": pygame.K_RIGHT,
        "pygame.K_UP": pygame.K_UP,
        "pygame.K_DOWN": pygame.K_DOWN,
    }
    
    def extract_keys_from_response(response):
        """
        Extract key commands from AI response.
        """
        if not response:
            return None
        
        # Create a mapping of key strings to pygame key constants
        key_map = {
            "pygame.K_LEFT": pygame.K_LEFT,
            "pygame.K_RIGHT": pygame.K_RIGHT, 
            "pygame.K_UP": pygame.K_UP,
            "pygame.K_DOWN": pygame.K_DOWN,
            "K_LEFT": pygame.K_LEFT,
            "K_RIGHT": pygame.K_RIGHT,
            "K_UP": pygame.K_UP, 
            "K_DOWN": pygame.K_DOWN,
            "LEFT": pygame.K_LEFT,
            "RIGHT": pygame.K_RIGHT,
            "UP": pygame.K_UP,
            "DOWN": pygame.K_DOWN,
            "ROTATE": pygame.K_UP
        }
        
        try:
            # First attempt: Look for key directly in response
            for key_str, key_code in key_map.items():
                if key_str in response:
                    logger.info(f"Found key directly in response: {key_str}")
                    return key_code
            
            # Second attempt: Extract and execute any Python code
            code_blocks = extract_python_code(response)
            if code_blocks:
                # Clean and combine code blocks
                cleaned_code = "\n".join(code_blocks)
                
                # Set up an isolated namespace with pygame constants
                namespace = {"pygame": pygame}
                
                # Capture printed output
                with BytesIO() as output, redirect_stdout(output), redirect_stderr(output):
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
            
            # Last resort: See if any literal key constants are present
            if "K_LEFT" in response or "LEFT" in response.upper():
                logger.info("Detected LEFT direction from text pattern")
                return pygame.K_LEFT
            elif "K_RIGHT" in response or "RIGHT" in response.upper():
                logger.info("Detected RIGHT direction from text pattern")
                return pygame.K_RIGHT
            elif "K_UP" in response or "UP" in response.upper() or "ROTATE" in response.upper():
                logger.info("Detected UP/ROTATE direction from text pattern")
                return pygame.K_UP
            elif "K_DOWN" in response or "DOWN" in response.upper():
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
                    # Calculate the hash of the current game state
                    global last_api_call_time, cached_response, cached_state_hash, API_COOLDOWN_SECONDS
                    current_time = time.time()
                    current_state_hash = hash_game_state(state)
                    time_since_last_call = current_time - last_api_call_time
                    
                    # Decision logic to reduce API calls:
                    # 1. If we're within the cooldown period AND the game state is similar, reuse the cached response
                    # 2. Otherwise, make a new API call
                    if (time_since_last_call < API_COOLDOWN_SECONDS and 
                        cached_response is not None and 
                        cached_state_hash == current_state_hash):
                        logger.info(f"Reusing cached response (cooldown: {time_since_last_call:.1f}s < {API_COOLDOWN_SECONDS}s)")
                        response = cached_response
                    else:
                        # Make an actual API call
                        logger.info(f"Making new API call after {time_since_last_call:.1f}s")
                        response = model_provider.get_response(prompt)
                        last_api_call_time = current_time
                        cached_response = response
                        cached_state_hash = current_state_hash
                
                logger.info(f"Worker {worker_id} received AI response: {response[:100]}...")
                
                # Extract multiple actions from the response
                action_count += 1
                actions = extract_multiple_actions(response)
                
                if actions:
                    logger.info(f"Worker {worker_id} extracted {len(actions)} actions")
                    
                    # Execute each action in sequence
                    for key in actions:
                        # Prevent the AI from quitting the game
                        if key == pygame.K_q:
                            logger.warning("AI attempted to press Q to quit - ignoring")
                            continue
                        
                        # Take a screenshot before pressing the key
                        take_screenshot(f"before_key_{key}", important=True)
                        
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
                                take_screenshot(f"after_key_{key}", important=True)
                                logger.info(f"Successfully pressed key {key}")
                            else:
                                logger.warning(f"All key press methods failed for key {key}")
                            
                            # Delay between sequential actions from the same API response
                            # This can be shorter than the delay after completing all actions
                            time.sleep(0.5)
                            
                        except Exception as e:
                            logger.error(f"Error pressing key {key}: {e}")
                    
                    # Additional delay after executing all actions from this response
                    # to give the game more time before making a new API call
                    time.sleep(1.0)
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

# Add new function to extract multiple actions from a single response
def extract_multiple_actions(response):
    """
    Extract a sequence of actions from the AI's response.
    Returns a list of pygame key codes to execute in sequence.
    """
    if not response:
        return []
    
    # Key mappings - same as in extract_keys_from_response
    key_map = {
        "pygame.K_LEFT": pygame.K_LEFT,
        "pygame.K_RIGHT": pygame.K_RIGHT, 
        "pygame.K_UP": pygame.K_UP,
        "pygame.K_DOWN": pygame.K_DOWN,
        "K_LEFT": pygame.K_LEFT,
        "K_RIGHT": pygame.K_RIGHT,
        "K_UP": pygame.K_UP, 
        "K_DOWN": pygame.K_DOWN,
        "LEFT": pygame.K_LEFT,
        "RIGHT": pygame.K_RIGHT,
        "UP": pygame.K_UP,
        "DOWN": pygame.K_DOWN,
        "ROTATE": pygame.K_UP
    }
    
    actions = []
    
    try:
        # Look for action sequences like "move left, then rotate, then right"
        # or numbered steps like "1. Move left 2. Rotate 3. Move right"
        
        # Method 1: Check if response contains a sequence of actions
        for key_str in key_map.keys():
            if key_str in response:
                actions.append(key_map[key_str])
        
        # Method 2: Look for specific patterns like "first...then..."
        sequence_patterns = [
            r"(?:first|1st|1\.)\s+(?:move\s+)?(left|right|down|up|rotate)",
            r"(?:second|2nd|2\.)\s+(?:move\s+)?(left|right|down|up|rotate)",
            r"(?:third|3rd|3\.)\s+(?:move\s+)?(left|right|down|up|rotate)",
            r"(?:fourth|4th|4\.)\s+(?:move\s+)?(left|right|down|up|rotate)",
            r"(?:then|next)\s+(?:move\s+)?(left|right|down|up|rotate)"
        ]
        
        import re
        for pattern in sequence_patterns:
            matches = re.findall(pattern, response.lower())
            for match in matches:
                direction = match.upper()
                if direction == "ROTATE":
                    direction = "UP"
                if direction in key_map:
                    actions.append(key_map[direction])
        
        # If we couldn't extract a sequence, fall back to simple detection
        if not actions:
            # Simple detection of directions in the response
            if "LEFT" in response.upper() or "K_LEFT" in response:
                actions.append(pygame.K_LEFT)
            elif "RIGHT" in response.upper() or "K_RIGHT" in response:
                actions.append(pygame.K_RIGHT)
            elif "UP" in response.upper() or "K_UP" in response or "ROTATE" in response.upper():
                actions.append(pygame.K_UP)
            elif "DOWN" in response.upper() or "K_DOWN" in response:
                actions.append(pygame.K_DOWN)
        
        # Log the extracted action sequence
        if actions:
            logger.info(f"Extracted action sequence: {actions}")
        
        return actions
        
    except Exception as e:
        logger.error(f"Error extracting action sequence: {e}")
        return []
