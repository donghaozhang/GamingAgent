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

Return your decision as a simple Python code that clearly returns the key constant.
Use pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, or pygame.K_DOWN to represent keyboard inputs.

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

def worker_tetris(thread_id, window_name, region, api_provider, model_name, system_prompt, concurrency=1):
    global game_running
    all_response_time = []
    
    # Add increased delay to make sure Tetris window is fully started
    logger.info(f"[Thread {thread_id}] Worker starting with {api_provider} {model_name}. Waiting for Tetris window...")
    time.sleep(5)  # Give the game more time to fully initialize
    
    # First check if the game is still running
    if not game_running:
        logger.warning(f"[Thread {thread_id}] Game is not running. Worker exiting.")
        return

    consecutive_failures = 0
    max_consecutive_failures = 10  # After this many failures in a row, assume game is gone
    
    while game_running:
        try:
            # Check for Q key pressed - global exit
            try:
                if keyboard.is_pressed('q'):
                    logger.info(f"[Thread {thread_id}] Q key detected at worker level - terminating")
                    game_running = False
                    # Use pygame event system to signal quit
                    try:
                        pygame.event.post(pygame.event.Event(pygame.QUIT))
                    except:
                        pass
                    # Only use os._exit as a last resort
                    # os._exit(0)  # Force immediate termination
                    return  # Exit worker function cleanly
            except Exception as e:
                logger.debug(f"[Thread {thread_id}] Error checking keyboard: {str(e)}")
                pass  # Keyboard module not available
                
            start_time = time.time()
            
            # Capture screenshot of the game window
            logger.debug(f"[Thread {thread_id}] Capturing game state...")
            
            # Try window capture
            image = capture_window(window_name)
            
            # Fallback to region capture if window capture fails
            if image is None:
                logger.warning(f"[Thread {thread_id}] Window '{window_name}' not found. Falling back to region capture.")
                
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(f"[Thread {thread_id}] Too many consecutive failures to find game window. Exiting worker.")
                    game_running = False
                    break
                    
                # Try region capture if configured
                if region:
                    logger.debug(f"[Thread {thread_id}] Using region capture: {region}")
                    image = capture_screen_region(region)
                else:
                    logger.error(f"[Thread {thread_id}] No fallback region specified. Skipping this iteration.")
                    time.sleep(1)
                    continue
            else:
                consecutive_failures = 0  # Reset failure counter on success
            
            # Resize image to save bandwidth if needed
            # image = resize_image(image, 640, 480)
            
            # Convert image to base64 for API transmission
            buffered = BytesIO()
            image.save(buffered, format="PNG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            # Get API response based on provider
            logger.debug(f"[Thread {thread_id}] Getting AI response...")
            
            if api_provider == "anthropic":
                generated_code_str = anthropic_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "openai":
                generated_code_str = openai_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "gemini":
                generated_code_str = gemini_completion(system_prompt, model_name, base64_image, tetris_prompt)
            else:
                raise NotImplementedError(f"API provider: {api_provider} is not supported.")

            end_time = time.time()
            latency = end_time - start_time
            all_response_time.append(latency)

            logger.debug(f"[Thread {thread_id}] Request latency: {latency:.2f}s")
            avg_latency = np.mean(all_response_time)
            logger.debug(f"[Thread {thread_id}] Average latency: {avg_latency:.2f}s\n")

            # Extract and execute code
            try:
                if not game_running:
                    break
                    
                clean_code = extract_python_code(generated_code_str)
                log_output(thread_id, f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n", "tetris")
                
                # Print agent's analysis and actions for visibility
                logger.info("\n==== AGENT #{thread_id} OUTPUT ====")
                logger.info(f"Response time: {latency:.2f}s")
                
                # Extract and print thought process from the full response
                thought_lines = []
                for line in generated_code_str.split('\n'):
                    if "```python" in line or "```" == line.strip():
                        break
                    thought_lines.append(line)
                
                thought_process = '\n'.join(thought_lines).strip()
                if thought_process:
                    logger.info("AGENT ANALYSIS:")
                    logger.info(thought_process[:500] + "..." if len(thought_process) > 500 else thought_process)
                
                logger.info("\nAGENT ACTION:")
                logger.info(clean_code)
                logger.info("=" * 30 + "\n")
                
                # Check if no code was extracted or if the AI detected no game state
                if "not appear to be a Tetris game" in clean_code or "no Tetris game" in clean_code:
                    logger.info("[Thread {}] AI detected no valid Tetris game in screenshot. Skipping action.".format(thread_id))
                    time.sleep(1)  # Wait and try again
                    continue
                
                # Execute the code to get the key
                try:
                    # Create a namespace with pygame keys
                    namespace = {
                        'pygame': pygame,
                        'K_LEFT': pygame.K_LEFT,
                        'K_RIGHT': pygame.K_RIGHT,
                        'K_UP': pygame.K_UP,
                        'K_DOWN': pygame.K_DOWN,
                        'K_q': pygame.K_q,
                        'None': None
                    }
                    
                    # Execute in this namespace
                    exec(clean_code, namespace)
                    
                    # Find the key in the namespace (last value that's not a built-in or module)
                    key = None
                    for var_name, var_value in namespace.items():
                        if var_name not in ['__builtins__', 'pygame'] and var_name in ['K_LEFT', 'K_RIGHT', 'K_UP', 'K_DOWN', 'K_q', 'None']:
                            continue  # Skip imported constants
                        
                        if isinstance(var_value, int) or var_value is None:
                            key = var_value
                            logger.info(f"[Thread {thread_id}] Found key in namespace: {var_name} = {var_value}")
                    
                    # Use the key if found
                    if key is not None and key != pygame.K_q:  # Don't allow AI to press Q
                        try:
                            # Send the key to the game
                            if key == pygame.K_LEFT:
                                logger.debug("[Thread {}] Sending physical LEFT key".format(thread_id))
                                keyboard.press_and_release('left')
                            elif key == pygame.K_RIGHT:
                                logger.debug("[Thread {}] Sending physical RIGHT key".format(thread_id))
                                keyboard.press_and_release('right') 
                            elif key == pygame.K_UP:
                                logger.debug("[Thread {}] Sending physical UP key".format(thread_id))
                                keyboard.press_and_release('up')
                            elif key == pygame.K_DOWN:
                                logger.debug("[Thread {}] Sending physical DOWN key".format(thread_id))
                                keyboard.press_and_release('down')
                        except Exception as e:
                            logger.error(f"[Thread {thread_id}] Error sending physical key: {e}")
                            
                        # Add a short delay to ensure the key is processed
                        time.sleep(0.1)
                    else:
                        logger.info(f"[Thread {thread_id}] No valid key found in AI response")
                        
                except Exception as e:
                    logger.error(f"[Thread {thread_id}] Error executing code for key extraction: {e}")
                
            except Exception as e:
                logger.error(f"[Thread {thread_id}] Error executing code: {e}")
                
            # Small pause between iterations
            time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"[Thread {thread_id}] Error in worker loop: {e}")
            # Don't exit the thread on non-critical errors
            time.sleep(1)
            
    # Thread cleanup
    logger.info(f"[Thread {thread_id}] Worker thread exiting.")

def worker_thread_function(thread_id, game_state_queue, action_queue, game_running, worker_type='standard'):
    # ... existing code ...
    
    while game_running.value:
        # Check for Q key to quit
        check_for_quit()
        
        # ... existing code ...
