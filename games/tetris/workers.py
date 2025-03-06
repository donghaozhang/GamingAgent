import time
import os
import pyautogui
import numpy as np
from PIL import Image, ImageDraw, ImageFont  # 添加绘图功能

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion

# Add this function to find Tetris window directly
def find_tetris_window():
    """
    Uses pyautogui.getWindowsWithTitle to find the Tetris window
    Returns the window region as (left, top, width, height) or None if not found
    """
    # Try to find the Tetris window
    windows = pyautogui.getWindowsWithTitle("Tetris")
    
    # DEBUG: 列出所有可用窗口
    all_windows = pyautogui.getAllWindows()
    print(f"DEBUG: All available windows:")
    for w in all_windows:
        print(f"  - '{w.title}' at {w.left}, {w.top}, {w.width}, {w.height}")
    
    if windows:
        window = windows[0]  # Get the first window with "Tetris" in the title
        print(f"Found Tetris window: {window.title} at {window.left}, {window.top}, {window.width}, {window.height}")
        return (window.left, window.top, window.width, window.height)
    else:
        print("DEBUG: No window with 'Tetris' in title was found")
    
    return None

def worker_tetris(
    thread_id,
    offset,
    system_prompt,
    api_provider,
    model_name,
    plan_seconds,
):
    """
    A single Tetris worker that plans moves for 'plan_seconds'.
    1) Sleeps 'offset' seconds before starting (to stagger starts).
    2) Continuously:
        - Captures a screenshot of the Tetris window
        - Calls the LLM with a Tetris prompt that includes 'plan_seconds'
        - Extracts the Python code from the LLM output
        - Executes the code with `exec()`
    """
    all_response_time = []

    time.sleep(offset)
    print(f"[Thread {thread_id}] Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")

    tetris_prompt = f"""
Analyze the current Tetris board state and generate PyAutoGUI code to control Tetris 
for the next {plan_seconds} second(s). You can move left/right, rotate pieces. Focus on clearing lines and avoiding 
stacking that would cause a top-out.

At the time the code is executed, 3~5 seconds have elapsed. The game might have moved on to the next block if the stack is high.

However, in your code, consider only the current block or the next block.

The speed it drops is at around ~0.75s/grid bock.

### General Tetris Controls (example keybinds):
- left: move piece left
- right: move piece right
- up: rotate piece clockwise
- down: accelerated drop （if necessary)

### Strategies and Caveats:
1. If the stack is high, most likely you are controlling the "next" block due to latency.
2. Prioritize keeping the stack flat. Balance the two sides.
3. Consider shapes ahead of time. DO NOT rotate and quickly move the block again once it's position is decided.
4. Avoid creating holes.
5. If you see a chance to clear lines, rotate and move the block to correct positions.
6. Plan for your next piece as well, but do not top out.
7. The entire sequence of key presses should be feasible within {plan_seconds} second(s).

### Output Format:
- Output ONLY the Python code for PyAutoGUI commands, e.g. `pyautogui.press("left")`.
- Include brief comments for each action.
- Do not print anything else besides these Python commands.
    """

    try:
        iteration = 0
        while True:
            iteration += 1
            print(f"\n[Thread {thread_id}] === Iteration {iteration} ===\n")
            
            # 首先保存一个全屏截图，用于对比参考
            fullscreen = pyautogui.screenshot()
            
            # Create a unique folder for this thread's cache
            thread_folder = f"cache/tetris/thread_{thread_id}"
            os.makedirs(thread_folder, exist_ok=True)
            
            # 保存全屏截图以供分析
            fullscreen_path = os.path.join(thread_folder, "fullscreen.png")
            fullscreen.save(fullscreen_path)
            print(f"[Thread {thread_id}] Full screen screenshot saved to: {fullscreen_path}")
            
            # Try to capture the Tetris window specifically
            tetris_region = find_tetris_window()
            
            if tetris_region:
                # Use the detected Tetris window region
                screenshot = pyautogui.screenshot(region=tetris_region)
                print(f"[Thread {thread_id}] Capturing Tetris window at region: {tetris_region}")
                region_type = "tetris_window"
            else:
                # Fallback to the default method
                print(f"[Thread {thread_id}] No Tetris window found. Using default region.")
                screen_width, screen_height = pyautogui.size()
                region = (0, 0, screen_width // 64 * 18, screen_height // 64 * 40)
                screenshot = pyautogui.screenshot(region=region)
                print(f"[Thread {thread_id}] Using default region: {region}, Screen size: {screen_width}x{screen_height}")
                region_type = "default_region"

            # 添加调试信息到截图上
            draw = ImageDraw.Draw(screenshot)
            # 添加红色边框
            draw.rectangle([(0, 0), (screenshot.width-1, screenshot.height-1)], outline="red", width=3)
            # 添加文本信息
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            debug_text = f"Thread {thread_id} | {timestamp} | {region_type}"
            try:
                # 尝试添加文本（如果没有字体，可能会失败，但不影响主流程）
                draw.text((10, 10), debug_text, fill="red")
            except Exception as e:
                print(f"[Thread {thread_id}] Could not add text to image: {e}")

            screenshot_path = os.path.join(thread_folder, "screenshot.png")
            screenshot.save(screenshot_path)
            
            # 同时保存一个带有迭代号的截图，便于对比历史记录
            iter_screenshot_path = os.path.join(thread_folder, f"screenshot_iter_{iteration}.png")
            screenshot.save(iter_screenshot_path)
            print(f"[Thread {thread_id}] Also saved iteration-specific screenshot to: {iter_screenshot_path}")
            
            # 检查图像是否全黑或全白
            img = Image.open(screenshot_path)
            img_array = np.array(img)
            
            # 检查图像是否全黑
            is_black = np.all(img_array < 10)
            # 检查图像是否全白
            is_white = np.all(img_array > 245)
            # 检查图像统计信息
            avg_pixel = np.mean(img_array)
            std_pixel = np.std(img_array)
            
            print(f"[Thread {thread_id}] Screenshot analysis:")
            print(f"  - Size: {img.width}x{img.height}")
            print(f"  - All black: {is_black}")
            print(f"  - All white: {is_white}")
            print(f"  - Average pixel value: {avg_pixel:.2f}")
            print(f"  - Pixel standard deviation: {std_pixel:.2f}")
            print(f"  - Screenshot saved to: {screenshot_path}")
            
            # 如果图像全黑或全白，发出警告
            if is_black or is_white:
                print(f"[Thread {thread_id}] WARNING: Screenshot appears to be {'black' if is_black else 'white'} only!")
                print(f"[Thread {thread_id}] This may indicate a problem with window detection or permissions.")
                
                # 尝试使用PIL直接截图（替代方案）
                print(f"[Thread {thread_id}] Attempting alternative screenshot method...")
                try:
                    from PIL import ImageGrab
                    alt_screenshot = ImageGrab.grab(bbox=tetris_region if tetris_region else region)
                    alt_path = os.path.join(thread_folder, "alt_screenshot.png")
                    alt_screenshot.save(alt_path)
                    print(f"[Thread {thread_id}] Alternative screenshot saved to: {alt_path}")
                    
                    # 分析替代截图
                    alt_img_array = np.array(alt_screenshot)
                    alt_is_black = np.all(alt_img_array < 10)
                    print(f"[Thread {thread_id}] Alternative screenshot is all black: {alt_is_black}")
                    
                    if not alt_is_black:
                        print(f"[Thread {thread_id}] Using alternative screenshot instead!")
                        screenshot = alt_screenshot
                        screenshot.save(screenshot_path)
                except Exception as e:
                    print(f"[Thread {thread_id}] Alternative screenshot method failed: {e}")

            # Encode the screenshot
            base64_image = encode_image(screenshot_path)
            print(f"[Thread {thread_id}] Screenshot encoded, preparing to call API...")

            # DEBUG: 在继续处理前暂停几秒，让用户检查日志
            print(f"[Thread {thread_id}] DEBUG: Pausing for 5 seconds to allow log inspection...")
            time.sleep(5)

            start_time = time.time()
            if api_provider == "anthropic":
                print(f"[Thread {thread_id}] Calling Anthropic API with model {model_name}...")
                generated_code_str = anthropic_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "openai":
                print(f"[Thread {thread_id}] Calling OpenAI API with model {model_name}...")
                generated_code_str = openai_completion(system_prompt, model_name, base64_image, tetris_prompt)
            elif api_provider == "gemini":
                print(f"[Thread {thread_id}] Calling Gemini API with model {model_name}...")
                generated_code_str = gemini_completion(system_prompt, model_name, base64_image, tetris_prompt)
            else:
                raise NotImplementedError(f"API provider: {api_provider} is not supported.")

            end_time = time.time()
            latency = end_time - start_time
            all_response_time.append(latency)

            print(f"[Thread {thread_id}] Request latency: {latency:.2f}s")
            avg_latency = np.mean(all_response_time)
            print(f"[Thread {thread_id}] Latencies: {all_response_time}")
            print(f"[Thread {thread_id}] Average latency: {avg_latency:.2f}s\n")

            print(f"[Thread {thread_id}] --- API output ---\n{generated_code_str}\n")

            # Extract Python code for execution
            print(f"[Thread {thread_id}] Extracting Python code from response...")
            clean_code = extract_python_code(generated_code_str)
            log_output(thread_id, f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n", "tetris")
            print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")

            try:
                print(f"[Thread {thread_id}] Executing Python code...")
                exec(clean_code)
                print(f"[Thread {thread_id}] Code execution completed.")
            except Exception as e:
                print(f"[Thread {thread_id}] Error executing code: {e}")
                
            print(f"[Thread {thread_id}] Cycle completed, beginning next cycle...")

    except KeyboardInterrupt:
        print(f"[Thread {thread_id}] Interrupted by user. Exiting...")
