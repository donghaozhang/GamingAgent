import time
import os
import pyautogui
import numpy as np
from PIL import Image, ImageDraw, ImageFont  # 添加绘图功能
import threading
from datetime import datetime

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
    
    # 为了调试，输出所有可用窗口
    print("DEBUG: All available windows:")
    
    try:
        # 先尝试使用pygetwindow
        import pygetwindow as gw
        
        # 列出所有窗口，用于调试
        all_windows = gw.getAllWindows()
        for win in all_windows:
            # 打印每个窗口的标题和位置
            print(f"  - '{win.title}' at {win.left}, {win.top}, {win.width}, {win.height}")
        
        # 尝试匹配窗口标题
        for keyword in window_title_keywords:
            matching_windows = [win for win in all_windows if keyword in win.title]
            if matching_windows:
                window = matching_windows[0]  # 使用第一个匹配的窗口
                # 确保坐标是有效的，不是负数
                left = max(0, window.left)
                top = max(0, window.top)
                print(f"Found matching window: {window.title} at {window.left}, {window.top}, {window.width}, {window.height}")
                
                # 检查窗口是否可见
                if window.isMinimized:
                    print(f"Window '{window.title}' is minimized, trying to restore...")
                    try:
                        window.restore()
                        window.activate()
                    except Exception as e:
                        print(f"Failed to restore window: {e}")
                
                # 窗口可能在屏幕外或有负坐标，调整为有效值
                # 获取屏幕尺寸
                screen_width, screen_height = pyautogui.size()
                
                # 确保窗口在屏幕内，并且坐标不是负数
                left = max(0, min(left, screen_width - 100))
                top = max(0, min(top, screen_height - 100))
                width = min(window.width, screen_width - left)
                height = min(window.height, screen_height - top)
                
                return (left, top, width, height)
        
        print("DEBUG: No window matching Tetris criteria was found")
    except ImportError:
        print("pygetwindow not available, using alternative window detection")
    except Exception as e:
        print(f"Error finding window: {e}")
    
    # 如果PyGetWindow不可用或者找不到窗口，使用其他方法
    try:
        # 使用PyAutoGUI直接寻找
        import pyautogui
        
        # 获取屏幕尺寸
        screen_width, screen_height = pyautogui.size()
        
        # 尝试查找标题中包含关键词的窗口
        windows = pyautogui.getAllWindows()
        for window in windows:
            for keyword in window_title_keywords:
                if keyword.lower() in window.title.lower():
                    print(f"Found matching window using pyautogui: {window.title}")
                    # 获取窗口位置
                    left, top, width, height = window.left, window.top, window.width, window.height
                    
                    # 检查坐标是否合法（不是负数）
                    left = max(0, min(left, screen_width - 100))
                    top = max(0, min(top, screen_height - 100))
                    width = min(width, screen_width - left)
                    height = min(height, screen_height - top)
                    
                    return (left, top, width, height)
    except (ImportError, AttributeError):
        # PyAutoGUI的getAllWindows()在某些平台上可能不可用
        print("pyautogui.getAllWindows() not available")
    except Exception as e:
        print(f"Error using pyautogui for window detection: {e}")
    
    # 如果上述方法都失败，尝试使用一个合理的默认值
    # 这依赖于Tetris游戏通常会在一个固定位置启动
    print("Using default window region as fallback")
    default_left = 100
    default_top = 100
    default_width = 400  # 适合大多数Tetris游戏
    default_height = 600  # 适合大多数Tetris游戏
    
    return (default_left, default_top, default_width, default_height)

def safe_screenshot(region, thread_id=0, output_dir="model_responses"):
    """
    安全地截取屏幕区域，确保坐标有效
    
    Args:
        region: 要截取的区域 (left, top, width, height)
        thread_id: 线程ID，用于命名截图文件
        output_dir: 保存截图的目录
        
    Returns:
        tuple: (截图路径, 截图对象)
    """
    try:
        left, top, width, height = region
        
        # 确保坐标是有效的正数
        screen_width, screen_height = pyautogui.size()
        left = max(0, min(left, screen_width - 100))
        top = max(0, min(top, screen_height - 100))
        width = min(width, screen_width - left)
        height = min(height, screen_height - top)
        
        # 确保宽度和高度至少为10像素
        width = max(10, width)
        height = max(10, height)
        
        print(f"Taking screenshot of region: ({left}, {top}, {width}, {height})")
        
        # 使用pyautogui截图
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        
        # 创建目录保存截图
        thread_folder = os.path.join(output_dir, f"thread_{thread_id}")
        os.makedirs(thread_folder, exist_ok=True)
        
        # 保存截图
        screenshot_path = os.path.join(thread_folder, f"screenshot_iter_{int(time.time())}.png")
        screenshot.save(screenshot_path)
        
        # 检查图像是否全黑或全白
        img_array = np.array(screenshot)
        is_black = np.mean(img_array) < 10
        is_white = np.mean(img_array) > 245
        
        if is_black:
            print("Warning: Screenshot appears to be completely black")
        elif is_white:
            print("Warning: Screenshot appears to be completely white")
            
        return screenshot_path, screenshot
    except Exception as e:
        print(f"Error taking screenshot: {e}")
        # 返回一个空白图像
        blank_img = Image.new('RGB', (400, 600), color=(255, 255, 255))
        blank_path = os.path.join(output_dir, f"thread_{thread_id}", f"blank_screenshot_{int(time.time())}.png")
        os.makedirs(os.path.dirname(blank_path), exist_ok=True)
        blank_img.save(blank_path)
        return blank_path, blank_img

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
        """检查是否应该停止线程"""
        if stop_flag is None:
            return False
        elif callable(stop_flag):
            return stop_flag()
        elif isinstance(stop_flag, threading.Event):
            return stop_flag.is_set()
        else:
            return bool(stop_flag)
    
    # Initialize this thread in the shared responses dictionary if tracking responses
    if responses_dict is not None:
        if "threads" not in responses_dict:
            responses_dict["threads"] = {}
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
            
            # 确定窗口区域 - 优先使用手动指定的区域
            if manual_window_region:
                # 使用手动指定的窗口区域
                region = manual_window_region
                print(f"[Thread {thread_id}] Using manually specified window region: {region}")
                region_type = "manual_region"
                window_missing_count = 0  # 重置计数
            else:
                # 尝试自动检测窗口
                tetris_region = find_tetris_window()
                
                if tetris_region:
                    # Use the detected Tetris window region
                    region = tetris_region
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
                    region = (100, 100, 400, 600)  # 使用一个更可靠的默认值
                    print(f"[Thread {thread_id}] Using default region: {region}, Screen size: {screen_width}x{screen_height}")
                    region_type = "default_region"

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected after window detection. Exiting...")
                break

            # 使用安全截图功能截取屏幕
            try:
                screenshot_path, screenshot = safe_screenshot(
                    region, 
                    thread_id=thread_id, 
                    output_dir=output_dir
                )
                print(f"[Thread {thread_id}] Screenshot saved to: {screenshot_path}")
                
                # 添加红色边框和线程ID标记，便于调试
                draw = ImageDraw.Draw(screenshot)
                draw.rectangle([(0, 0), (screenshot.width-1, screenshot.height-1)], outline="red", width=3)
                # 添加文本（如果可能）
                try:
                    # 添加文本(在有PIL.ImageFont的环境中)
                    draw.text((10, 10), f"Thread {thread_id}", fill="red")
                except Exception as e:
                    print(f"[Thread {thread_id}] Could not add text to screenshot: {e}")
                
                # 保存带标记的截图
                screenshot.save(screenshot_path)
                
                # 获取截图的Base64编码
                base64_image = encode_image(screenshot_path)
                print(f"[Thread {thread_id}] Screenshot encoded, preparing to call API...")
            except Exception as e:
                print(f"[Thread {thread_id}] Error processing screenshot: {e}")
                # 继续到下一个迭代
                time.sleep(5)
                continue

            # 如果启用了调试暂停，等待一段时间
            if debug_pause:
                print(f"[Thread {thread_id}] DEBUG: Pausing for 5 seconds to allow log inspection...")
                time.sleep(5)
            
            # 调用API获取响应
            start_time = time.time()
            
            if api_provider == "anthropic":
                print(f"[Thread {thread_id}] Calling Anthropic API with model {model_name}...")
                generated_code_str = anthropic_completion(
                    system_prompt,
                    model_name,
                    base64_image,
                    tetris_prompt
                )
            elif api_provider == "openai":
                print(f"[Thread {thread_id}] Calling OpenAI API with model {model_name}...")
                generated_code_str = openai_completion(
                    system_prompt,
                    model_name,
                    base64_image,
                    tetris_prompt
                )
            elif api_provider == "gemini":
                print(f"[Thread {thread_id}] Calling Gemini API with model {model_name}...")
                generated_code_str = gemini_completion(
                    system_prompt,
                    model_name,
                    base64_image,
                    tetris_prompt
                )
            else:
                raise NotImplementedError(f"API provider: {api_provider} is not supported.")

            end_time = time.time()
            latency = end_time - start_time
            all_response_time.append(latency)

            print(f"[Thread {thread_id}] Request latency: {latency:.2f}s")
            avg_latency = np.mean(all_response_time)
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
                thread_folder = os.path.join(output_dir, f"thread_{thread_id}")
                os.makedirs(thread_folder, exist_ok=True)
                response_file = os.path.join(thread_folder, f"response_{iteration}.json")
                try:
                    with open(response_file, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(response_data, f, indent=2, ensure_ascii=False)
                    print(f"[Thread {thread_id}] Response saved to: {response_file}")
                except Exception as e:
                    print(f"[Thread {thread_id}] Error saving response: {e}")

            # 是否打印详细输出
            if verbose_output:
                print(f"\n[Thread {thread_id}] === DETAILED MODEL RESPONSE (Iteration {iteration}) ===")
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
            print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")

            try:
                # 在执行代码前最后检查一次停止标志
                if should_stop():
                    print(f"[Thread {thread_id}] Stop flag detected before code execution. Exiting...")
                    break
                
                # 首先点击游戏窗口中心确保窗口激活
                if region:
                    left, top, width, height = region
                    try:
                        pyautogui.click(left + width // 2, top + height // 2)
                        time.sleep(0.2)  # 等待窗口激活
                    except Exception as e:
                        print(f"[Thread {thread_id}] Error activating window: {e}")
                
                # 检查代码是否是有效的Python代码
                # 如果模型没有返回可执行的Python代码，我们需要创建一个安全的替代代码
                try:
                    # 尝试编译代码，看是否有语法错误
                    compile(clean_code, '<string>', 'exec')
                    # 如果没有语法错误，执行代码
                    print(f"[Thread {thread_id}] Executing Python code...")
                    exec(clean_code)
                    print(f"[Thread {thread_id}] Code execution completed.")
                except SyntaxError:
                    # 代码有语法错误，模型可能返回了纯文本回应
                    print(f"[Thread {thread_id}] Syntax error in code. Using fallback random moves.")
                    
                    # 使用随机移动作为替代
                    fallback_code = """
# Fallback code: Random Tetris moves
import pyautogui
import time
import random

# Random actions
possible_actions = ['left', 'right', 'up', 'space']
actions_to_take = random.sample(possible_actions, k=min(3, len(possible_actions)))

for action in actions_to_take:
    print(f"Pressing {action}")
    pyautogui.press(action)
    time.sleep(0.3)

# Always try to drop at the end
if 'space' not in actions_to_take:
    print("Dropping piece")
    pyautogui.press('space')
"""
                    print(f"[Thread {thread_id}] Executing fallback code:")
                    print(fallback_code)
                    exec(fallback_code)
                    print(f"[Thread {thread_id}] Fallback code execution completed.")
                
            except Exception as e:
                print(f"[Thread {thread_id}] Error executing code: {e}")
                import traceback
                traceback.print_exc()
                
            print(f"[Thread {thread_id}] Cycle completed, beginning next cycle...")
            
            # 计算并等待到下一个计划周期
            elapsed = time.time() - end_time  # 计算代码执行耗时
            wait_time = max(0, plan_seconds - elapsed - latency)  # 减去API调用和代码执行的时间
            print(f"[Thread {thread_id}] Waiting {wait_time:.2f}s until next cycle...")
            
            # 分段睡眠，以便能够及时响应停止信号
            sleep_interval = 0.5  # 每0.5秒检查一次停止标志
            for _ in range(int(wait_time / sleep_interval)):
                if should_stop():
                    break
                time.sleep(sleep_interval)
            
            # 处理可能的小数部分
            remainder = wait_time % sleep_interval
            if remainder > 0 and not should_stop():
                time.sleep(remainder)

    except KeyboardInterrupt:
        print(f"[Thread {thread_id}] Interrupted by user. Exiting...")
    except Exception as e:
        print(f"[Thread {thread_id}] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"[Thread {thread_id}] Thread execution completed.")

    # 最后保存此线程的所有响应，如果要求保存的话
    if save_responses and thread_responses:
        all_responses_file = os.path.join(output_dir, f"all_responses_thread_{thread_id}.json")
        try:
            with open(all_responses_file, 'w', encoding='utf-8') as f:
                import json
                json.dump(thread_responses, f, indent=2, ensure_ascii=False)
            print(f"[Thread {thread_id}] All responses saved to: {all_responses_file}")
        except Exception as e:
            print(f"[Thread {thread_id}] Error saving all responses: {e}")
    
    return 0
