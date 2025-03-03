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

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion
# Remove circular import
# from tetris_agent import check_for_quit

# Get the logger
logger = logging.getLogger("TetrisAgent.Worker")

# Define our own check_for_quit function to avoid circular imports
def check_for_quit():
    try:
        import keyboard
        if keyboard.is_pressed('q'):
            logger.info("Q key pressed - force quit")
            pygame.quit()
            os._exit(0)
    except ImportError:
        # Keyboard module not available
        pass

# Function to capture a specific window by title
def capture_window_by_title(window_title):
    """Capture a screenshot of a window with the specified title"""
    try:
        # Find the window handle
        hwnd = win32gui.FindWindow(None, window_title)
        if hwnd == 0:
            logger.warning(f"Window '{window_title}' not found. Falling back to region capture.")
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
# Moving left to position the piece
import pygame
pygame.K_LEFT  # This will be returned as the key to press
```

If you cannot see a valid Tetris game in the screenshot, respond like this:
```python
# No valid Tetris game detected in the screenshot
import pygame
# Please ensure the Tetris game window is visible and not obscured
```

IMPORTANT: 
- If you can see a Tetris game, only return ONE key constant (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, or pygame.K_DOWN)
- Make sure the key constant is the LAST line of your code so it gets returned
- Do not include functions, loops, conditionals, or complex logic
- Just analyze the game state and return a single key constant
- If no Tetris game is visible, clearly indicate that in your code comments
"""

# 添加全局变量
game_running = True
game_state = Queue()

def worker_tetris(thread_id, offset, system_prompt, api_provider, model_name, plan_seconds):
    logger.info(f"[Worker {thread_id}] Initializing...")
    global game_running, game_state
    
    try:
        time.sleep(offset)
        logger.info(f"[Thread {thread_id}] Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")
        
        all_response_time = []
        last_state = None
        
        # Wait for game to start
        time.sleep(2)  # Initial wait to make sure the game window is created

        # Main worker loop
        while game_running:
            try:
                # Check if the game is still running
                if not game_running:
                    logger.info(f"[Thread {thread_id}] Game no longer running, exiting...")
                    break
                    
                # Check for Q key press to terminate
                try:
                    check_for_quit()  # Use the shared check_for_quit function
                except:
                    # Fallback to direct keyboard check
                    try:
                        if keyboard.is_pressed('q'):
                            logger.info(f"[Thread {thread_id}] Q key detected - terminating")
                            game_running = False
                            os._exit(0)  # Force immediate termination
                    except:
                        pass  # Keyboard module might not be available
                    
                # Create a unique folder for this thread's cache
                thread_folder = f"cache/tetris/thread_{thread_id}"
                os.makedirs(thread_folder, exist_ok=True)
                screenshot_path = os.path.join(thread_folder, "screenshot.png")
                
                # Try to capture the Tetris window
                img = capture_window_by_title("Tetris")
                
                if img is not None:
                    # Save the captured window screenshot
                    img.save(screenshot_path)
                    logger.debug(f"[Thread {thread_id}] Successfully captured Tetris window")
                else:
                    # Fallback to region capture
                    logger.warning(f"[Thread {thread_id}] Falling back to region capture")
                    screen_width, screen_height = pyautogui.size()
                    window_width = 800
                    window_height = 750
                    x = (screen_width - window_width) // 2
                    y = (screen_height - window_height) // 2
                    region = (x, y, window_width, window_height)
                    fallback_screenshot = pyautogui.screenshot(region=region)
                    fallback_screenshot.save(screenshot_path)

                # Encode the screenshot
                base64_image = encode_image(screenshot_path)

                # Get AI response
                start_time = time.time()
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
                    
                    # Check if there's actual Python code in the response
                    if not any(keyword in clean_code for keyword in ["pygame.K_", "K_LEFT", "K_RIGHT", "K_UP", "K_DOWN"]):
                        logger.info("[Thread {}] No valid move command found in AI response. Skipping.".format(thread_id))
                        time.sleep(1)  # Wait and try again
                        continue
                    
                    # Only execute if game is still running
                    if game_running:
                        try:
                            # Execute the code to get the key
                            # We need to capture the result of executing the code
                            # Create a namespace for execution
                            namespace = {}
                            exec(clean_code, namespace)
                            
                            # Find the key in the namespace (last value that's not a built-in or module)
                            key = None
                            for var_name, var_value in namespace.items():
                                if (not var_name.startswith('__') and 
                                    not isinstance(var_value, type(os)) and
                                    isinstance(var_value, int)):
                                    key = var_value
                                    logger.info(f"[Thread {thread_id}] Found key in namespace: {var_name} = {var_value}")
                            
                            if key is None:
                                logger.info(f"[Thread {thread_id}] No key found in namespace, searching in code text")
                                # Try to find pygame key constants directly in the code
                                key_mapping = {
                                    'pygame.K_LEFT': pygame.K_LEFT,
                                    'pygame.K_RIGHT': pygame.K_RIGHT,
                                    'pygame.K_UP': pygame.K_UP,
                                    'pygame.K_DOWN': pygame.K_DOWN,
                                    'K_LEFT': pygame.K_LEFT,
                                    'K_RIGHT': pygame.K_RIGHT,
                                    'K_UP': pygame.K_UP,
                                    'K_DOWN': pygame.K_DOWN
                                }
                                for key_str, key_value in key_mapping.items():
                                    if key_str in clean_code:
                                        key = key_value
                                        logger.info(f"[Thread {thread_id}] Found key in code text: {key_str} = {key_value}")
                                        break
                            
                            if key is not None:
                                logger.info(f"[Thread {thread_id}] Executing key: {key}")
                                # Put the key into the game state queue
                                # IMPORTANT FIX: Make sure the queue is emptied before adding new keys
                                # This prevents queue build-up that could cause delayed responses
                                try:
                                    # Clear the queue first to prevent buildup
                                    while not game_state.empty():
                                        _ = game_state.get_nowait()
                                except:
                                    pass
                                
                                # Now add our new key
                                game_state.put(key)
                                
                                # ALTERNATIVE METHOD: Also use direct keyboard presses
                                # This is a backup method in case the queue approach isn't working
                                try:
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
                
    except KeyboardInterrupt:
        logger.info(f"[Thread {thread_id}] Interrupted by user. Exiting...")
    except Exception as e:
        logger.error(f"[Thread {thread_id}] Critical error: {e}")
    finally:
        logger.info(f"[Thread {thread_id}] Worker thread exiting.")

def worker_thread_function(thread_id, game_state_queue, action_queue, game_running, worker_type='standard'):
    # ... existing code ...
    
    while game_running.value:
        # Check for Q key to quit
        check_for_quit()
        
        # ... existing code ...
