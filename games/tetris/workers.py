import time
import os
import pyautogui
import numpy as np
from PIL import Image, ImageDraw, ImageFont  # 添加绘图功能
import threading
from datetime import datetime
import json

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
            "pygame", "Pygame", "PyGame", # Pygame通常会在窗口标题中
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

def safe_screenshot(region, thread_id=0, output_dir="model_responses", suffix=""):
    """
    安全地截取屏幕区域，确保坐标有效
    
    Args:
        region: 要截取的区域 (left, top, width, height)
        thread_id: 线程ID，用于命名截图文件
        output_dir: 保存截图的目录
        suffix: 截图文件名后缀
        
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
        screenshot_path = os.path.join(thread_folder, f"screenshot_iter_{int(time.time())}{suffix}.png")
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
        blank_path = os.path.join(output_dir, f"thread_{thread_id}", f"blank_screenshot_{int(time.time())}{suffix}.png")
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
    stop_flag=None,     # 停止标志，可以是布尔值引用或threading.Event
    log_folder=None,    # 日志文件夹，用于保存增强的日志和截图
    log_file=None,      # 日志文件路径
    screenshot_interval=0,  # 截图间隔(秒)，0表示禁用
    save_all_states=False,  # 是否保存所有状态的截图
    enhanced_logging=False,  # 是否启用增强日志
    execution_mode='adaptive',  # 控制执行模式：adaptive, fast, or slow
    piece_limit=0  # 每次API调用最多控制的方块数量，0表示不限制
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
        log_folder: 日志文件夹，用于保存增强的日志和截图
        log_file: 日志文件路径
        screenshot_interval: 截图间隔(秒)，0表示禁用
        save_all_states: 是否保存所有状态的截图
        enhanced_logging: 是否启用增强日志
        execution_mode: 控制执行模式 - adaptive (自适应), fast (快速), slow (慢速)
        piece_limit: 每次API调用最多控制的方块数量，0表示不限制
    """
    all_response_time = []
    thread_responses = []
    
    # 初始化线程日志文件
    thread_log_file = None
    if enhanced_logging and log_folder:
        thread_log_file = os.path.join(log_folder, f"thread_{thread_id}_log.txt")
        with open(thread_log_file, 'w') as f:
            f.write(f"=== Thread {thread_id} Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Plan seconds: {plan_seconds}\n")
            f.write(f"API Provider: {api_provider}, Model: {model_name}\n")
            f.write("="*50 + "\n\n")
        
    # 记录日志的辅助函数
    def log_message(message, print_message=True):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] [Thread {thread_id}] {message}"
        
        if print_message:
            print(f"[Thread {thread_id}] {message}")
            
        if enhanced_logging:
            try:
                # 写入主日志文件
                if log_file:
                    try:
                        with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
                            f.write(log_entry + "\n")
                    except Exception as e:
                        print(f"[Thread {thread_id}] 写入主日志文件失败: {str(e)}")
                
                # 写入线程日志文件
                if thread_log_file:
                    try:
                        with open(thread_log_file, 'a', encoding='utf-8', errors='replace') as f:
                            f.write(log_entry + "\n")
                    except Exception as e:
                        print(f"[Thread {thread_id}] 写入线程日志文件失败: {str(e)}")
            except Exception as e:
                print(f"[Thread {thread_id}] 日志记录失败: {str(e)}")
    
    # 创建增强版截图函数
    def enhanced_screenshot(region, suffix="", description=""):
        if not log_folder:
            # 如果没有指定日志文件夹，使用普通的截图函数
            return safe_screenshot(region, thread_id, output_dir)
        
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
            
            log_message(f"Taking screenshot of region: ({left}, {top}, {width}, {height})", print_message=False)
            
            # 使用pyautogui截图
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            
            # 创建时间戳目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # 保存截图到两个位置
            # 1. 原来的位置
            thread_folder = os.path.join(output_dir, f"thread_{thread_id}")
            os.makedirs(thread_folder, exist_ok=True)
            original_path = os.path.join(thread_folder, f"screenshot_iter_{int(time.time())}{suffix}.png")
            screenshot.save(original_path)
            
            # 2. 日志文件夹
            screenshot_folder = os.path.join(log_folder, f"thread_{thread_id}_screenshots")
            os.makedirs(screenshot_folder, exist_ok=True)
            enhanced_path = os.path.join(screenshot_folder, f"{timestamp}_{suffix}.png")
            
            # 添加信息到截图
            enhanced_img = screenshot.copy()
            draw = ImageDraw.Draw(enhanced_img)
            draw.rectangle([(0, 0), (enhanced_img.width-1, enhanced_img.height-1)], outline="blue", width=2)
            try:
                draw.text((10, 10), f"Thread {thread_id} - {timestamp} - {description}", fill="blue")
            except Exception as e:
                log_message(f"Could not add text to screenshot: {e}", print_message=False)
            
            enhanced_img.save(enhanced_path)
            
            # 检查图像是否全黑或全白
            img_array = np.array(screenshot)
            is_black = np.mean(img_array) < 10
            is_white = np.mean(img_array) > 245
            
            if is_black:
                log_message("Warning: Screenshot appears to be completely black", print_message=False)
            elif is_white:
                log_message("Warning: Screenshot appears to be completely white", print_message=False)
                
            return enhanced_path, screenshot
        except Exception as e:
            log_message(f"Error taking screenshot: {e}")
            # 返回一个空白图像
            blank_img = Image.new('RGB', (400, 600), color=(255, 255, 255))
            blank_path = os.path.join(log_folder, f"thread_{thread_id}_screenshots", f"blank_screenshot_{int(time.time())}{suffix}.png")
            os.makedirs(os.path.dirname(blank_path), exist_ok=True)
            blank_img.save(blank_path)
            return blank_path, blank_img
    
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
    
    # 如果启用了增强日志，使用log_message代替print
    if enhanced_logging:
        log_message(f"Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")
    
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
        
        # 启动定时截图线程
        screenshot_thread = None
        screenshot_stop_flag = False
        
        if screenshot_interval > 0 and log_folder:
            def take_interval_screenshots():
                log_message(f"Started interval screenshot thread with {screenshot_interval}s delay", print_message=False)
                count = 0
                while not screenshot_stop_flag and not should_stop():
                    try:
                        # 查找窗口区域
                        region_to_capture = find_tetris_window()
                        if not region_to_capture and manual_window_region:
                            region_to_capture = manual_window_region
                        
                        if region_to_capture:
                            count += 1
                            interval_path, _ = enhanced_screenshot(
                                region_to_capture, 
                                suffix=f"_interval_{count}", 
                                description=f"Interval {count}"
                            )
                            log_message(f"Took interval screenshot #{count}: {interval_path}", print_message=False)
                    except Exception as e:
                        log_message(f"Error taking interval screenshot: {e}", print_message=False)
                    
                    # 检查是否应该停止
                    for _ in range(screenshot_interval * 2):  # 分段睡眠以便更快响应停止信号
                        if screenshot_stop_flag or should_stop():
                            break
                        time.sleep(0.5)
        
            # 创建并启动线程
            screenshot_thread = threading.Thread(target=take_interval_screenshots)
            screenshot_thread.daemon = True
            screenshot_thread.start()
        
        # 主循环
        while not should_stop():
            iteration += 1
            if enhanced_logging:
                log_message(f"=== Iteration {iteration} ===")
            else:
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
                if enhanced_logging or save_all_states:
                    initial_screenshot_path, initial_screenshot = enhanced_screenshot(
                        region, 
                        suffix="_start",
                        description="Initial State"
                    )
                    log_message(f"Initial screenshot saved to: {initial_screenshot_path}")
                else:
                    initial_screenshot_path, initial_screenshot = safe_screenshot(
                        region, 
                        thread_id=thread_id, 
                        output_dir=output_dir
                    )
                    print(f"[Thread {thread_id}] Initial screenshot saved to: {initial_screenshot_path}")
                
                # 添加红色边框和线程ID标记，便于调试
                draw = ImageDraw.Draw(initial_screenshot)
                draw.rectangle([(0, 0), (initial_screenshot.width-1, initial_screenshot.height-1)], outline="red", width=3)
                # 添加文本（如果可能）
                try:
                    # 添加文本(在有PIL.ImageFont的环境中)
                    draw.text((10, 10), f"Thread {thread_id}", fill="red")
                except Exception as e:
                    print(f"[Thread {thread_id}] Could not add text to screenshot: {e}")
                
                # 保存带标记的截图
                initial_screenshot.save(initial_screenshot_path)
                
                # 获取截图的Base64编码
                base64_image = encode_image(initial_screenshot_path)
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
            
            # 【步骤2：调用API】获取模型响应
            try:
                print(f"[Thread {thread_id}] Calling {api_provider.capitalize()} API with model {model_name}...")
                
                start_time = time.time()
                try:
                    if api_provider == "anthropic":
                        print(f"[Thread {thread_id}] Calling Anthropic API with model {model_name}...")
                        generated_code_str, full_response = anthropic_completion(
                            system_prompt,
                            model_name,
                            base64_image,
                            tetris_prompt,
                        )
                    elif api_provider == "openai":
                        print(f"[Thread {thread_id}] Calling OpenAI API with model {model_name}...")
                        generated_code_str, full_response = openai_completion(
                            system_prompt,
                            model_name,
                            base64_image,
                            tetris_prompt,
                        )
                    elif api_provider == "gemini":
                        print(f"[Thread {thread_id}] Calling Gemini API with model {model_name}...")
                        generated_code_str, full_response = gemini_completion(
                            system_prompt,
                            model_name,
                            base64_image,
                            tetris_prompt,
                        )
                    else:
                        raise ValueError(f"Unsupported API provider: {api_provider}")
                except Exception as api_error:
                    error_message = f"API调用错误: {str(api_error)}"
                    print(f"[Thread {thread_id}] {error_message}")
                    
                    # 如果启用了增强日志，记录API错误
                    if enhanced_logging:
                        log_message(error_message)
                        
                        # 将API错误保存到单独的日志文件
                        if log_folder:
                            try:
                                error_log_path = os.path.join(log_folder, f"thread_{thread_id}_responses", f"api_error_{int(time.time())}.txt")
                                os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
                                with open(error_log_path, 'w', encoding='utf-8', errors='replace') as f:
                                    f.write(f"=== API错误 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                                    f.write(f"API Provider: {api_provider}\n")
                                    f.write(f"Model: {model_name}\n")
                                    f.write("="*50 + "\n\n")
                                    f.write(f"错误信息: {str(api_error)}\n")
                                    import traceback
                                    f.write(traceback.format_exc())
                                log_message(f"API错误已保存到: {error_log_path}")
                            except Exception as e:
                                log_message(f"保存API错误日志时出错: {str(e)}")
                    
                    # 重新抛出异常以便外层捕获
                    raise
                
                end_time = time.time()
                
                # 计算延迟
                latency = end_time - start_time
                all_response_time.append(latency)
                avg_latency = sum(all_response_time) / len(all_response_time)
                
                print(f"[Thread {thread_id}] Request latency: {latency:.2f}s")
                print(f"[Thread {thread_id}] Average latency: {avg_latency:.2f}s")
                
                # 记录模型回复到日志文件
                if enhanced_logging:
                    try:
                        log_message("模型回复已完成")
                        log_message(f"请求延迟: {latency:.2f}s")
                        log_message(f"平均延迟: {avg_latency:.2f}s")
                        
                        # 将完整回复保存到单独的日志文件
                        if log_folder:
                            response_log_path = os.path.join(log_folder, f"thread_{thread_id}_responses", f"response_{int(time.time())}.txt")
                            os.makedirs(os.path.dirname(response_log_path), exist_ok=True)
                            
                            try:
                                # 使用UTF-8编码写入，处理无法编码的字符
                                with open(response_log_path, 'w', encoding='utf-8', errors='replace') as f:
                                    f.write(f"=== 模型回复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                                    f.write(f"API Provider: {api_provider}\n")
                                    f.write(f"Model: {model_name}\n")
                                    f.write(f"Latency: {latency:.2f}s\n")
                                    f.write("="*50 + "\n\n")
                                    f.write(full_response)
                                    f.write("\n\n" + "="*50 + "\n")
                                    f.write("\n提取的代码:\n")
                                    f.write(generated_code_str)
                                
                                log_message(f"完整回复已保存到: {response_log_path}")
                            except Exception as file_error:
                                # 如果写入还是失败，尝试保存简化版本
                                log_message(f"保存完整回复时出错: {str(file_error)}")
                                try:
                                    with open(response_log_path, 'w', encoding='utf-8', errors='replace') as f:
                                        f.write(f"=== 模型回复 (简化版) - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                                        f.write(f"API Provider: {api_provider}\n")
                                        f.write(f"Model: {model_name}\n")
                                        f.write(f"Latency: {latency:.2f}s\n")
                                        f.write("="*50 + "\n\n")
                                        f.write("由于编码问题，无法保存完整回复。以下是提取的代码:\n\n")
                                        f.write(generated_code_str if generated_code_str else "无法提取代码")
                                    
                                    log_message(f"简化回复已保存到: {response_log_path}")
                                except Exception as e:
                                    log_message(f"保存简化回复也失败: {str(e)}")
                    except Exception as logging_error:
                        print(f"[Thread {thread_id}] 记录模型回复时出错: {str(logging_error)}")
                
                # 打印模型输出
                if verbose_output:
                    print(f"\n[Thread {thread_id}] === DETAILED MODEL RESPONSE (Iteration {iteration}) ===")
                    print(f"Response length: {len(full_response)} characters")
                    print(f"Full response:\n{'='*80}\n{full_response}\n{'='*80}\n")
                else:
                    # 只打印响应的简短版本
                    truncated_response = full_response[:200] + "..." if len(full_response) > 200 else full_response
                    print(f"\n[Thread {thread_id}] --- API output ---\n{truncated_response}\n[truncated]")
                
                # 保存响应到字典
                if responses_dict is not None and str(thread_id) in responses_dict["threads"]:
                    response_data = {
                        "iteration": iteration,
                        "timestamp": time.time(),
                        "latency": latency,
                        "prompt": tetris_prompt,
                        "full_response": full_response,
                        "extracted_code": generated_code_str
                    }
                    responses_dict["threads"][str(thread_id)]["responses"].append(response_data)
                
                # 如果需要保存响应到文件
                if save_responses:
                    response_file = os.path.join(output_dir, f"thread_{thread_id}", f"response_iter_{int(time.time())}.json")
                    os.makedirs(os.path.dirname(response_file), exist_ok=True)
                    
                    try:
                        with open(response_file, 'w', encoding='utf-8') as f:
                            json.dump(response_data, f, indent=2, ensure_ascii=False)
                        print(f"[Thread {thread_id}] Response saved to: {response_file}")
                    except Exception as e:
                        print(f"[Thread {thread_id}] Error saving response: {e}")
                
                thread_responses.append(response_data)
                
            except Exception as e:
                print(f"[Thread {thread_id}] Error calling API: {e}")
                time.sleep(5)
                continue

            # 是否打印详细输出
            if verbose_output:
                print(f"\n[Thread {thread_id}] === DETAILED MODEL RESPONSE (Iteration {iteration}) ===")
                print(f"Response length: {len(full_response)} characters")
                print(f"Full response:\n{'='*80}\n{full_response}\n{'='*80}\n")
            else:
                # 只打印响应的简短版本
                truncated_response = full_response[:200] + "..." if len(full_response) > 200 else full_response
                print(f"\n[Thread {thread_id}] --- API output ---\n{truncated_response}\n[truncated]")

            # 再次检查停止标志
            if should_stop():
                print(f"[Thread {thread_id}] Stop flag detected before code execution. Exiting...")
                break
            
            # 【步骤4：执行代码】尝试执行模型生成的代码
            try:
                # Extract Python code for execution
                print(f"[Thread {thread_id}] Extracting Python code from response...")
                clean_code = extract_python_code(generated_code_str)
                print(f"[Thread {thread_id}] Python code to be executed:\n{clean_code}\n")
                
                try:
                    # 检查是否需要启用紧急模式(新方块刚出现)
                    def check_new_piece(screenshot_path):
                        """
                        检查是否有新方块刚出现在顶部
                        """
                        try:
                            # 打开截图
                            img = Image.open(screenshot_path)
                            # 转换为numpy数组
                            img_array = np.array(img)
                            
                            # 仅检查顶部区域的一小部分
                            # 假设游戏区域顶部是新方块出现的地方
                            # 取前2行(根据Tetris的特性，足够检测新方块出现)
                            top_rows = 2
                            game_area_start_x = img.width // 3  # 假设游戏区域在窗口左侧
                            top_area = img_array[:top_rows, :game_area_start_x]
                            
                            # 检查是否有彩色像素(非黑色背景)
                            # 简化检测：如果有足够多的像素亮度超过阈值，认为有新方块
                            is_bright = np.mean(top_area) > 20  # 亮度阈值
                            
                            return is_bright
                        except Exception as e:
                            print(f"Error checking for new piece: {e}")
                            return False
                    
                    # 检查是否有新方块出现，如果有，使用紧急模式
                    urgent_mode = check_new_piece(pre_exec_screenshot_path)
                    if urgent_mode:
                        print(f"[Thread {thread_id}] !!! URGENT MODE: New piece detected !!!")
                    
                    # 尝试编译代码，看是否有语法错误
                    compile(clean_code, '<string>', 'exec')
                    # 如果没有语法错误，执行代码
                    print(f"[Thread {thread_id}] Executing Python code...")
                    
                    # 将代码中的time.sleep替换为同步游戏的等待
                    # 首先，提取所有的time.sleep调用
                    import re
                    
                    # 修改代码，替换time.sleep为特殊标记
                    modified_code = re.sub(
                        r'time\.sleep\(([0-9.]+)\)',
                        r'# SLEEP: \1',
                        clean_code
                    )
                    # 同样处理pyautogui.sleep
                    modified_code = re.sub(
                        r'pyautogui\.sleep\(([0-9.]+)\)',
                        r'# SLEEP: \1',
                        modified_code
                    )
                    
                    # 分成多行
                    code_lines = modified_code.splitlines()
                    
                    # 逐行执行代码，处理sleep语句
                    local_vars = {}
                    global_vars = {
                        'pyautogui': pyautogui,
                        'time': time,
                        'random': __import__('random')
                    }
                    
                    # 如果是紧急模式，提取并优先执行第一组移动命令
                    urgent_commands = []
                    if urgent_mode:
                        # 查找前几个press指令
                        for line in code_lines:
                            line = line.strip()
                            if 'press' in line and not line.startswith('#'):
                                urgent_commands.append(line)
                                # 只取前3个命令
                                if len(urgent_commands) >= 3:
                                    break
                        
                        if urgent_commands:
                            print(f"[Thread {thread_id}] Executing urgent commands first: {urgent_commands}")
                            # 执行紧急命令
                            for cmd in urgent_commands:
                                try:
                                    # 查找按键名称
                                    key_match = re.search(r'press\(["\']([^"\']+)["\']', cmd)
                                    if key_match:
                                        key_name = key_match.group(1)
                                        print(f"[Thread {thread_id}] URGENT: Pressing key: {key_name}")
                                        
                                        # 执行按键
                                        exec(cmd, global_vars, local_vars)
                                        
                                        # 按键后极短暂等待，紧急模式下需要快速操作
                                        time.sleep(0.1)
                                        
                                        # 截图记录按键后的状态
                                        try:
                                            key_screenshot_path, key_screenshot = safe_screenshot(
                                                region, 
                                                thread_id=thread_id, 
                                                output_dir=output_dir,
                                                suffix=f"_urgent_key_{key_name}"
                                            )
                                            # 红色边框表示紧急
                                            draw = ImageDraw.Draw(key_screenshot)
                                            draw.rectangle([(0, 0), (key_screenshot.width-1, key_screenshot.height-1)], outline="red", width=2)
                                            draw.text((5, 5), f"Urgent: {key_name}", fill="red")
                                            key_screenshot.save(key_screenshot_path)
                                        except Exception as e:
                                            print(f"[Thread {thread_id}] Error taking urgent key screenshot: {e}")
                                except Exception as e:
                                    print(f"[Thread {thread_id}] Error executing urgent command: {cmd}")
                                    print(f"[Thread {thread_id}] Error: {e}")
                    
                    # 计算每个动作的大约等待时间，让代码执行能填满大部分plan_seconds
                    # 假设model回复已经使用了部分时间
                    remaining_time = plan_seconds - latency
                    # 以实际的操作数量为基准分配时间
                    action_count = sum(1 for line in code_lines if 'press' in line and not line.startswith('#'))
                    # 加上sleep指令的时间
                    sleep_time_sum = 0
                    for line in code_lines:
                        sleep_match = re.search(r'# SLEEP: ([0-9.]+)', line)
                        if sleep_match:
                            sleep_time_sum += float(sleep_match.group(1))
                    
                    # 计算基本动作时间，确保总执行时间能填满大部分plan_seconds
                    # 但留出一些余量给下一次API调用
                    target_time = max(remaining_time * 0.85, 5.0)  # 至少给5秒执行时间
                    actual_time = sleep_time_sum + action_count * 0.3  # 预估的执行时间
                    
                    # 调整action_timeout，确保代码有足够时间执行
                    action_timeout = target_time / action_count if action_count > 0 else 0.3
                    action_timeout = min(max(action_timeout, 0.2), 1.0)  # 范围限制在0.2-1.0秒之间
                    
                    if enhanced_logging:
                        log_message(f"Adjusting action timing - actions: {action_count}, sleep time: {sleep_time_sum:.1f}s, target time: {target_time:.1f}s")
                        log_message(f"Action timeout: {action_timeout:.2f}s per key press")
                    
                    # 正常执行其余代码行
                    executed_actions = 0
                    for line in code_lines:
                        line = line.strip()
                        # 跳过空行和注释行(不含sleep标记的)
                        if not line or (line.startswith('#') and '# SLEEP:' not in line):
                            continue
                            
                        # 处理sleep指令
                        sleep_match = re.search(r'# SLEEP: ([0-9.]+)', line)
                        if sleep_match:
                            sleep_time = float(sleep_match.group(1))
                            print(f"[Thread {thread_id}] Waiting for {sleep_time:.1f}s...")
                            time.sleep(sleep_time)
                            
                            # 等待后截图，确保游戏状态更新被捕获
                            try:
                                wait_screenshot_path, wait_screenshot = safe_screenshot(
                                    region, 
                                    thread_id=thread_id, 
                                    output_dir=output_dir,
                                    suffix=f"_wait_{sleep_time:.1f}s"
                                )
                                # 绿色表示等待
                                draw = ImageDraw.Draw(wait_screenshot)
                                draw.rectangle([(0, 0), (wait_screenshot.width-1, wait_screenshot.height-1)], outline="green", width=1)
                                draw.text((5, 5), f"Wait: {sleep_time:.1f}s", fill="green")
                                wait_screenshot.save(wait_screenshot_path)
                            except Exception as e:
                                print(f"[Thread {thread_id}] Error taking wait screenshot: {e}")
                        # 处理按键命令
                        elif 'press' in line and not line.startswith('#'):
                            try:
                                # 查找按键名称
                                key_match = re.search(r'press\(["\']([^"\']+)["\']', line)
                                if key_match:
                                    key_name = key_match.group(1)
                                    print(f"[Thread {thread_id}] Pressing key: {key_name}")
                                    
                                    # 执行按键
                                    exec(line, global_vars, local_vars)
                                    executed_actions += 1
                                    
                                    # 按键后等待，让游戏有时间响应，使用动态计算的等待时间
                                    # 给不同的按键应用不同的等待时间，使得整体执行时间更适应游戏速度
                                    if key_name in ['space']:  # 对于空格键（落下），等待时间更长
                                        wait_time = 1.0
                                    else:
                                        wait_time = action_timeout
                                    
                                    time.sleep(wait_time)
                                    
                                    # 截图记录按键后的状态
                                    try:
                                        key_screenshot_path, key_screenshot = safe_screenshot(
                                            region, 
                                            thread_id=thread_id, 
                                            output_dir=output_dir,
                                            suffix=f"_key_{key_name}"
                                        )
                                        # 简单标记
                                        draw = ImageDraw.Draw(key_screenshot)
                                        draw.rectangle([(0, 0), (key_screenshot.width-1, key_screenshot.height-1)], outline="cyan", width=1)
                                        draw.text((5, 5), f"Key: {key_name}", fill="cyan")
                                        key_screenshot.save(key_screenshot_path)
                                    except Exception as e:
                                        print(f"[Thread {thread_id}] Error taking key screenshot: {e}")
                                else:
                                    # 普通执行
                                    exec(line, global_vars, local_vars)
                            except Exception as e:
                                print(f"[Thread {thread_id}] Error executing line: {line}")
                                print(f"[Thread {thread_id}] Error: {e}")
                        else:
                            # 普通执行其他代码行
                            try:
                                exec(line, global_vars, local_vars)
                            except Exception as e:
                                print(f"[Thread {thread_id}] Error executing line: {line}")
                                print(f"[Thread {thread_id}] Error: {e}")
                    
                    # 代码执行后，等待一小段时间让游戏状态稳定下来
                    if executed_actions > 0:
                        stabilize_time = min(2.0, executed_actions * 0.2)
                        print(f"[Thread {thread_id}] Stabilizing game state for {stabilize_time:.1f}s...")
                        time.sleep(stabilize_time)
                    
                    print(f"[Thread {thread_id}] Code execution completed.")
                except Exception as e:
                    print(f"[Thread {thread_id}] Error executing code: {e}")
                    import traceback
                    traceback.print_exc()
                
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

    # 记录所有回复到文件
    if save_responses and thread_responses:
        try:
            thread_response_file = os.path.join(output_dir, f"thread_{thread_id}_responses.json")
            with open(thread_response_file, 'w') as f:
                json.dump({
                    'thread_id': thread_id,
                    'responses': thread_responses,
                    'avg_response_time': sum(all_response_time) / len(all_response_time) if all_response_time else 0,
                    'total_responses': len(thread_responses)
                }, f, indent=2)
            print(f"[Thread {thread_id}] Saved {len(thread_responses)} responses to {thread_response_file}")
        except Exception as e:
            print(f"[Thread {thread_id}] Error saving all responses: {e}")
    
    # 停止截图线程
    if screenshot_thread and screenshot_thread.is_alive():
        screenshot_stop_flag = True
        # 等待截图线程退出（最多等待2秒）
        screenshot_thread.join(timeout=2)
        if enhanced_logging:
            log_message("Screenshot interval thread stopped")
    
    # 记录线程退出信息
    if enhanced_logging:
        log_message(f"Thread completed after {iteration} iterations")
        if thread_log_file:
            with open(thread_log_file, 'a') as f:
                f.write(f"\n=== Thread {thread_id} Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(f"Total iterations: {iteration}\n")
                f.write(f"Average response time: {sum(all_response_time) / len(all_response_time) if all_response_time else 0:.2f}s\n")
    
    return iteration  # 返回完成的迭代次数
