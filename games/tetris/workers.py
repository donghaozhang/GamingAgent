import time
import os
import pyautogui
import numpy as np
from PIL import Image, ImageDraw, ImageFont  # 添加绘图功能

from tools.utils import encode_image, log_output, extract_python_code
from tools.serving.api_providers import anthropic_completion, openai_completion, gemini_completion

# Add this function to find Tetris window directly
def find_tetris_window(window_title_keywords=None):
    """
    尝试多种方法寻找Tetris窗口
    1. 首先通过精确标题查找Pygame窗口
    2. 然后通过部分标题匹配
    3. 最后尝试查找可能是游戏的窗口
    
    Args:
        window_title_keywords (list): 用于识别窗口的关键词列表。默认为None，使用内置关键词
    
    Returns:
        tuple: 窗口区域 (left, top, width, height) 或 None
    """
    # 如果未提供关键词，使用默认值
    if window_title_keywords is None:
        window_title_keywords = [
            "Tetris", "tetris", "TETRIS", 
            "pygame", "Pygame", "PyGame",  # Pygame通常会在窗口标题中
            "Simple Tetris", "simple_tetris",
            "俄罗斯方块", "方块", "BlockGame",
            "Game", "game", "Play"
        ]
    
    # 要排除的窗口标题关键词
    exclude_keywords = [
        "Cursor", "cursor",  # 编辑器窗口
        "Chrome", "Edge", "Firefox",  # 浏览器窗口
        ".py", "code", "Code",  # 代码文件
        "Terminal", "Console", "PowerShell", "cmd"  # 终端窗口
    ]
    
    # DEBUG: 列出所有可用窗口
    all_windows = pyautogui.getAllWindows()
    print(f"DEBUG: All available windows:")
    for w in all_windows:
        print(f"  - '{w.title}' at {w.left}, {w.top}, {w.width}, {w.height}")
    
    # 1. 首先尝试通过关键词标题匹配
    for window in all_windows:
        # 检查窗口标题是否包含关键词
        if any(keyword.lower() in window.title.lower() for keyword in window_title_keywords):
            # 检查是否是排除的窗口类型
            excluded = False
            for keyword in exclude_keywords:
                if keyword in window.title:
                    excluded = True
                    break
            
            if not excluded:
                print(f"Found matching window: {window.title} at {window.left}, {window.top}, {window.width}, {window.height}")
                return (window.left, window.top, window.width, window.height)
    
    # 2. 尝试查找小窗口，宽高比接近正方形（Tetris通常是接近正方形的窗口）
    game_candidates = []
    for window in all_windows:
        # 检查是否是排除的窗口类型
        excluded = False
        for keyword in exclude_keywords:
            if keyword in window.title:
                excluded = True
                break
        
        if excluded:
            continue
            
        # 只查找中等大小的窗口（Pygame窗口通常不会很大）
        if 200 <= window.width <= 800 and 200 <= window.height <= 800:
            # 计算宽高比，寻找接近游戏窗口的比例
            aspect_ratio = window.width / window.height
            if 0.5 <= aspect_ratio <= 1.2:  # 俄罗斯方块游戏窗口通常接近正方形或稍微高一些
                game_candidates.append((window, abs(aspect_ratio - 0.8)))
    
    # 如果找到候选窗口，使用最接近0.8宽高比的窗口
    if game_candidates:
        # 按宽高比接近0.8(典型Tetris比例)排序
        game_candidates.sort(key=lambda x: x[1])
        best_window = game_candidates[0][0]
        print(f"Found potential game window by aspect ratio: {best_window.title} at {best_window.left}, {best_window.top}, {best_window.width}, {best_window.height}")
        return (best_window.left, best_window.top, best_window.width, best_window.height)
    
    print("DEBUG: No window matching Tetris criteria was found")
    return None

def worker_tetris(
    thread_id,
    offset,
    system_prompt,
    api_provider,
    model_name,
    plan_seconds,
    verbose_output=False,
    save_responses=False,
    output_dir="model_responses",
    responses_dict=None,
    manual_window_region=None,
    debug_pause=False,  # 添加调试暂停选项，默认为False
    stop_flag=None      # 停止标志，可以是布尔值引用或threading.Event
):
    """
    A single Tetris worker that plans moves for 'plan_seconds'.
    1) Sleeps 'offset' seconds before starting (to stagger starts).
    2) Continuously:
        - Captures a screenshot of the Tetris window
        - Calls the LLM with a Tetris prompt that includes 'plan_seconds'
        - Extracts the Python code from the LLM output
        - Executes the code with `exec()`
    
    Args:
        thread_id (int): Unique ID for this worker thread
        offset (float): Initial sleep delay in seconds
        system_prompt (str): System prompt for the LLM
        api_provider (str): API provider to use (anthropic, openai, or gemini)
        model_name (str): Model name to use
        plan_seconds (float): Number of seconds to plan for
        verbose_output (bool): Whether to print detailed model responses
        save_responses (bool): Whether to save model responses to files
        output_dir (str): Directory to save model responses
        responses_dict (dict): Shared dictionary to store responses across threads
        manual_window_region (tuple): Manually specified window region (left, top, width, height)
        debug_pause (bool): Whether to pause for debugging
        stop_flag: Stop flag, can be a boolean reference or threading.Event
    """
    all_response_time = []
    thread_responses = []
    
    # 初始化检查停止标志的函数
    def should_stop():
        if stop_flag is None:
            return False
        # 如果是threading.Event，调用is_set()
        if hasattr(stop_flag, 'is_set'):
            return stop_flag.is_set()
        # 否则当作布尔值处理
        return bool(stop_flag)
    
    # Initialize this thread in the shared responses dictionary if tracking responses
    if responses_dict is not None:
        responses_dict["threads"][str(thread_id)] = {
            "start_time": time.time(),
            "responses": []
        }

    # 检查是否已经被要求停止
    if should_stop():
        print(f"[Thread {thread_id}] Stop flag already set. Thread not starting.")
        return

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
    
    # 只在启动时打印提示信息，而不是每次迭代都打印
    print(f"[Thread {thread_id}] Using Tetris prompt with {plan_seconds}s planning time.")
    if verbose_output:
        print(f"[Thread {thread_id}] Full prompt: {tetris_prompt}")

    try:
        iteration = 0
        window_missing_count = 0  # 计数找不到窗口的次数
        
        # 主循环
        while not should_stop():
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
            
            # 确定窗口区域 - 优先使用手动指定的区域
            if manual_window_region:
                # 使用手动指定的窗口区域
                region = manual_window_region
                print(f"[Thread {thread_id}] Using manually specified window region: {region}")
                screenshot = pyautogui.screenshot(region=region)
                region_type = "manual_region"
                window_missing_count = 0  # 重置计数
            else:
                # 尝试自动检测窗口
                tetris_region = find_tetris_window()
                
                if tetris_region:
                    # Use the detected Tetris window region
                    region = tetris_region
                    screenshot = pyautogui.screenshot(region=region)
                    print(f"[Thread {thread_id}] Capturing Tetris window at region: {region}")
                    region_type = "tetris_window"
                    window_missing_count = 0  # 重置计数
                else:
                    # 找不到窗口时
                    window_missing_count += 1
                    print(f"[Thread {thread_id}] No Tetris window found ({window_missing_count}/3 attempts). Using default region.")
                    
                    # 如果连续3次找不到窗口，则暂停一段时间
                    if window_missing_count >= 3:
                        print(f"[Thread {thread_id}] WARNING: Failed to find Tetris window for 3 consecutive attempts.")
                        print(f"[Thread {thread_id}] Pausing for 10 seconds to allow Tetris game to start or become visible...")
                        for i in range(10):
                            if should_stop():
                                break
                            time.sleep(1)
                            print(f"[Thread {thread_id}] Waiting... {i+1}/10 seconds")
                        window_missing_count = 0  # 重置计数
                    
                    # Fallback to the default method
                    screen_width, screen_height = pyautogui.size()
                    region = (0, 0, screen_width // 64 * 18, screen_height // 64 * 40)
                    screenshot = pyautogui.screenshot(region=region)
                    print(f"[Thread {thread_id}] Using default region: {region}, Screen size: {screen_width}x{screen_height}")
                    region_type = "default_region"

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected after window detection. Exiting...")
                break

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

            # 如果是保存响应，为当前iteration创建一个唯一的文件夹
            if save_responses:
                response_folder = os.path.join(output_dir, f"thread_{thread_id}")
                os.makedirs(response_folder, exist_ok=True)

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected before API call. Exiting...")
                break

            # Encode the screenshot
            base64_image = encode_image(screenshot_path)
            print(f"[Thread {thread_id}] Screenshot encoded, preparing to call API...")

            # 调试暂停，仅在启用时执行
            if debug_pause:
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

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected after API call. Exiting...")
                break
                
            # 保存响应数据
            response_data = {
                "iteration": iteration,
                "timestamp": time.time(),
                "latency": latency,
                "prompt": tetris_prompt,
                "full_response": generated_code_str,
            }
            
            # 添加到线程响应列表
            thread_responses.append(response_data)
            
            # 如果使用共享响应字典，也添加到那里
            if responses_dict is not None:
                responses_dict["threads"][str(thread_id)]["responses"].append(response_data)
            
            # 如果需要保存响应
            if save_responses:
                response_file = os.path.join(response_folder, f"response_{iteration}.json")
                try:
                    with open(response_file, 'w') as f:
                        import json
                        json.dump(response_data, f, indent=2)
                    print(f"[Thread {thread_id}] Response saved to: {response_file}")
                except Exception as e:
                    print(f"[Thread {thread_id}] Error saving response: {e}")
                    
                # 保存带时间戳的截图副本
                timestamp_str = time.strftime("%Y%m%d_%H%M%S")
                timestamped_screenshot = os.path.join(response_folder, f"screenshot_{iteration}_{timestamp_str}.png")
                try:
                    import shutil
                    shutil.copy2(screenshot_path, timestamped_screenshot)
                except Exception as e:
                    print(f"[Thread {thread_id}] Error saving timestamped screenshot: {e}")

            # 是否打印详细输出
            if verbose_output:
                print(f"\n[Thread {thread_id}] === DETAILED MODEL RESPONSE (Iteration {iteration}) ===")
                print(f"Prompt length: {len(tetris_prompt)} characters")
                print(f"Response length: {len(generated_code_str)} characters")
                print(f"Full response:\n{'='*80}\n{generated_code_str}\n{'='*80}\n")
            else:
                # 只打印响应的简短版本
                print(f"[Thread {thread_id}] --- API output ---\n{generated_code_str[:200]}...\n[truncated]\n")

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected before code execution. Exiting...")
                break

            # Extract Python code for execution
            print(f"[Thread {thread_id}] Extracting Python code from response...")
            clean_code = extract_python_code(generated_code_str)
            log_output(thread_id, f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n", "tetris")
            print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")

            try:
                # 在执行代码前最后检查一次停止标志
                if should_stop():
                    print(f"[Thread {thread_id}] Stop flag detected before code execution. Exiting...")
                    break
                    
                print(f"[Thread {thread_id}] Executing Python code...")
                exec(clean_code)
                print(f"[Thread {thread_id}] Code execution completed.")
            except Exception as e:
                print(f"[Thread {thread_id}] Error executing code: {e}")
                
            print(f"[Thread {thread_id}] Cycle completed, beginning next cycle...")

    except KeyboardInterrupt:
        print(f"[Thread {thread_id}] Interrupted by user. Exiting...")
    except Exception as e:
        print(f"[Thread {thread_id}] Unexpected error: {e}")
    finally:
        print(f"[Thread {thread_id}] Thread execution completed.")

    # 最后保存此线程的所有响应，如果要求保存的话
    if save_responses and thread_responses:
        all_responses_file = os.path.join(output_dir, f"all_responses_thread_{thread_id}.json")
        try:
            with open(all_responses_file, 'w') as f:
                import json
                json.dump(thread_responses, f, indent=2)
            print(f"[Thread {thread_id}] All responses saved to: {all_responses_file}")
        except Exception as e:
            print(f"[Thread {thread_id}] Error saving all responses: {e}")
