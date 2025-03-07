#!/usr/bin/env python
"""
Tetris workers
这个文件包含用于控制Tetris游戏的工作线程函数
"""

import os
import time
import base64
import threading
import random
import re
import pyautogui
import numpy as np
import traceback
from io import BytesIO, StringIO
import json
import sys
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

try:
    from tools.utils import encode_image, extract_python_code
except ImportError:
    def encode_image(image_path):
        """
        将图像编码为base64格式
        
        Args:
            image_path: 图像路径
            
        Returns:
            str: base64编码的图像
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def extract_python_code(text):
        """
        从文本中提取Python代码块
        
        Args:
            text: 包含代码的文本
            
        Returns:
            str: 提取的Python代码
        """
        # 尝试查找标准的```python 代码块
        pattern = r"```(?:python|py)?\s*([\s\S]*?)```"
        matches = re.findall(pattern, text)
        
        if matches:
            # 使用第一个匹配的代码块
            return matches[0].strip()
        
        # 如果找不到标准格式的代码块，尝试查找所有import pyautogui的部分
        if "import pyautogui" in text:
            # 识别可能的Python代码行
            lines = text.split('\n')
            code_lines = []
            in_code_block = False
            
            for line in lines:
                if "import pyautogui" in line:
                    in_code_block = True
                    code_lines.append(line)
                elif in_code_block:
                    # 假设空行或不像代码的行表示代码块的结束
                    if line.strip() == "" or not any(keyword in line for keyword in ["import", "pyautogui", "time", "sleep", "press", "#", "="]):
                        # 但如果下一行看起来还是代码，就继续
                        continue
                    code_lines.append(line)
            
            return "\n".join(code_lines)
        
        # 最后的尝试：直接搜索包含pyautogui.press的行
        pattern = r"pyautogui\.press\(['\"].*?['\"]\)"
        if re.search(pattern, text):
            # 如果找到pyautogui命令，提取相关行
            lines = text.split('\n')
            code_lines = []
            
            for line in lines:
                if any(keyword in line for keyword in ["pyautogui", "time.sleep", "import "]):
                    code_lines.append(line)
            
            # 添加必要的import语句
            if code_lines and not any("import" in line for line in code_lines):
                code_lines.insert(0, "import pyautogui")
                code_lines.insert(1, "import time")
            
            return "\n".join(code_lines)
        
        # 如果什么都找不到，返回空字符串
        return ""

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
    # 确保pyautogui已导入
    import pyautogui
    
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
        # pyautogui 已在函数开始导入，无需再次导入
        
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

def safe_screenshot(region, thread_id=0, output_dir="game_logs", suffix=""):
    """
    安全地截取屏幕区域，确保坐标有效
    
    Args:
        region: 要截取的区域 (left, top, width, height)
        thread_id: 线程ID，用于命名截图文件
        output_dir: 保存截图的目录，默认为game_logs
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
        
        # 添加时间戳到文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存截图
        screenshot_path = os.path.join(thread_folder, f"{timestamp}{suffix}.png")
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
        blank_path = os.path.join(output_dir, f"thread_{thread_id}", f"blank_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}.png")
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
    output_dir="game_logs",
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
    piece_limit=0,  # 每次API调用最多控制的方块数量，0表示不限制
    manual_mode=True  # 新增参数：手动模式，需要用户按空格键继续
):
    """
    Tetris游戏工作线程
    
    Args:
        thread_id: 线程ID
        offset: 启动延迟(秒)
        system_prompt: 系统提示词
        api_provider: API提供商名称
        model_name: 模型名称
        plan_seconds: 计划时间(秒)
        verbose_output: 是否输出详细信息
        save_responses: 是否保存模型响应
        output_dir: 输出目录
        responses_dict: 用于存储响应的字典
        manual_window_region: 手动指定的窗口区域
        debug_pause: 是否在执行代码前暂停等待确认
        stop_flag: 停止标志
        log_folder: 日志文件夹
        log_file: 日志文件路径
        screenshot_interval: 截图间隔(秒)
        save_all_states: 是否保存所有状态的截图
        enhanced_logging: 是否启用增强日志
        execution_mode: 控制执行模式
        piece_limit: 每次API调用最多控制的方块数量
        manual_mode: 是否启用手动模式（等待用户按下空格键）
        
    Returns:
        str: 执行状态
    """
    import time
    import datetime
    import os
    import base64
    import random
    import re
    import pyautogui
    import numpy as np
    import threading
    import traceback
    from io import BytesIO
    import json
    import sys
    from PIL import Image, ImageDraw, ImageFont
    from datetime import datetime
    
    # 存储所有响应时间以计算平均值
    all_response_time = []
    
    # 如果提供了线程字典，则初始化存储
    if responses_dict is not None and thread_id not in responses_dict:
        responses_dict[thread_id] = []
    
    # 线程级别存储
    thread_responses = []
    thread_screenshots = []
    
    # 如果提供了log_folder，创建线程特定的日志目录
    thread_log_folder = None
    screenshot_folder = None
    if log_folder:
        # 创建会话时间戳文件夹
        session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_folder = os.path.join(log_folder, f"session_{session_timestamp}")
        os.makedirs(session_folder, exist_ok=True)
        
        # 线程特定目录
        thread_log_folder = os.path.join(session_folder, f"thread_{thread_id}")
        os.makedirs(thread_log_folder, exist_ok=True)
        
        # 截图目录
        screenshot_folder = os.path.join(thread_log_folder, f"thread_{thread_id}_screenshots")
        os.makedirs(screenshot_folder, exist_ok=True)
        
        # 创建线程日志文件
        thread_log_file = os.path.join(thread_log_folder, f"thread_{thread_id}_log.txt")
        log_file = thread_log_file
        
        # 创建主日志文件
        main_log_file = os.path.join(session_folder, "game_log.txt")
        
        # 记录初始信息到主日志
        with open(main_log_file, 'a', encoding='utf-8') as f:
            f.write(f"=== Session Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Plan seconds: {plan_seconds}\n")
            f.write(f"API Provider: {api_provider}, Model: {model_name}\n")
            f.write("==================================================\n\n")
        
        # 记录线程启动到线程日志
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"=== Thread {thread_id} Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Plan seconds: {plan_seconds}\n")
            f.write(f"API Provider: {api_provider}, Model: {model_name}\n")
            f.write("==================================================\n\n")
    
    # 停止标志，用于在外部控制线程停止
    local_stop_flag = False
    if stop_flag is None:
        # 如果没有提供外部停止标志，创建本地标志
        stop_flag = False
    
    def log_message(message, print_message=True):
        """记录消息到日志文件和控制台"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] [Thread {thread_id}] {message}"
        
        # 如果启用了增强日志，记录到文件
        if log_file and enhanced_logging:
            try:
                with open(log_file, 'a', encoding='utf-8', errors='replace') as f:
                    f.write(log_entry + "\n")
            except Exception as e:
                print(f"Error writing to log file: {e}")
        
        # 同时打印到控制台（如果需要）
        if print_message:
            # 添加线程前缀，方便区分不同线程的输出
            print(f"[Thread {thread_id}] {message}")
    
    # 增强版截图函数，包含更多信息
    def enhanced_screenshot(region, suffix="", description=""):
        """
        增强版截图，带有时间戳和描述
        
        Args:
            region: 截图区域 (x, y, w, h)
            suffix: 文件名后缀
            description: 截图描述
            
        Returns:
            tuple: (截图路径, 截图对象)
        """
        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        formatted_time = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 格式化时间，精确到毫秒
        
        # 确保截图目录存在
        if not screenshot_folder:
            # 使用默认输出目录创建截图目录
            os.makedirs(output_dir, exist_ok=True)
            full_path = os.path.join(output_dir, f"screenshot_{thread_id}_{timestamp}{suffix}.png")
        else:
            # 使用线程特定的截图目录
            os.makedirs(screenshot_folder, exist_ok=True)
            full_path = os.path.join(screenshot_folder, f"{formatted_time}{suffix}.png")
        
        try:
            # 截取屏幕
            screenshot = pyautogui.screenshot(region=region)
            
            # 添加时间戳和描述
            draw = ImageDraw.Draw(screenshot)
            
            # 使用简单的字体
            try:
                font = ImageFont.truetype("arial.ttf", 14)
            except:
                # 如果找不到字体，使用默认字体
                font = ImageFont.load_default()
            
            # 添加时间戳和描述
            timestamp_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            draw.text((10, 10), f"{timestamp_text}", fill="white", font=font)
            
            if description:
                draw.text((10, 30), description, fill="white", font=font)
            
            # 保存截图
            screenshot.save(full_path)
            thread_screenshots.append(full_path)
            
            return full_path, screenshot
        except Exception as e:
            log_message(f"Error taking enhanced screenshot: {e}")
            return None, None
    
    # 检查是否应该停止
    def should_stop():
        """检查是否应该停止线程"""
        if isinstance(stop_flag, bool):
            return stop_flag or local_stop_flag
        elif hasattr(stop_flag, 'is_set'):  # threading.Event
            return stop_flag.is_set() or local_stop_flag
        return local_stop_flag  # 默认使用局部标志
    
    # 函数：检测游戏窗口
    def detect_game_window():
        """
        检测游戏窗口并返回区域
        
        Returns:
            tuple: (窗口区域, 区域类型)
        """
        # 如果提供了手动区域，直接使用
        if manual_window_region:
            return manual_window_region, "manual"
        
        # 查找Tetris窗口
        tetris_region = find_tetris_window()
        if tetris_region:
            log_message(f"Capturing Tetris window at region: {tetris_region}")
            return tetris_region, "tetris"
        
        # 如果没有找到窗口，使用默认区域
        log_message("Warning: Tetris window not found, using default region.")
        default_region = (0, 0, 800, 600)
        return default_region, "default"
    
    # 函数：捕获游戏画面并编码为base64
    def capture_game_screen(region):
        """
        捕获游戏画面并编码为base64
        
        Args:
            region: 截图区域
            
        Returns:
            tuple: (截图路径, 截图对象, base64编码)
        """
        log_message(f"Taking screenshot of region: {region}")
        if enhanced_logging or save_all_states:
            screenshot_path, screenshot = enhanced_screenshot(
                region, 
                suffix="_start",
                description="Initial Game State"
            )
        else:
            screenshot_path, screenshot = safe_screenshot(
                region, 
                thread_id=thread_id, 
                output_dir=output_dir,
                suffix="_start"
            )
        
        log_message(f"Initial screenshot saved to: {screenshot_path}")
        
        # 转换为base64 - 使用BytesIO处理二进制数据
        buffered = BytesIO()
        screenshot.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        log_message(f"Screenshot encoded, preparing to call API...")
        
        return screenshot_path, screenshot, base64_image
    
    # 函数：调用API获取模型响应
    def call_model_api(base64_image):
        """
        调用API获取模型响应
        
        Args:
            base64_image: base64编码的图像
            
        Returns:
            tuple: (生成的代码, 完整响应, 延迟时间)
        """
        # 构建提示词
        log_message(f"Calling {api_provider.capitalize()} API with model {model_name}...")
        
        # 构建提示词
        if api_provider.lower() in ["anthropic", "claude"]:
            instruction = tetris_prompt + f"""
            
            Here's the current Tetris game state image:
            
            <image>
            """
            
            # 专门为Anthropic API准备的请求格式
            log_message(f"Calling Anthropic API with model {model_name}...")
            
            # 调用Anthropic Claude API
            start_time = time.time()
            
            # 记录到控制台
            if verbose_output:
                print("Starting Anthropic API call...")
            
            try:
                from tools.serving.api_providers import call_anthropic_with_image
                response = call_anthropic_with_image(
                    system_prompt=system_prompt,
                    user_message=instruction,
                    image_base64=base64_image,
                    model=model_name
                )
                
                # 提取生成的代码和完整响应
                generated_code_str = response
                full_response = response
            except Exception as e:
                log_message(f"Error calling Anthropic API: {e}")
                traceback.print_exc()
                # 返回空响应和错误信息
                return f"# API Error: {str(e)}", f"ERROR: {str(e)}", 0
            
        elif api_provider.lower() in ["openai", "gpt4"]:
            instruction = tetris_prompt
            
            log_message(f"Calling OpenAI API with model {model_name}...")
            
            # 调用OpenAI API
            start_time = time.time()
            
            try:
                from tools.serving.api_providers import call_openai_with_image
                response = call_openai_with_image(
                    system_prompt=system_prompt,
                    user_message=instruction,
                    image_base64=base64_image,
                    model=model_name
                )
                
                # 提取生成的代码和完整响应
                generated_code_str = response
                full_response = response
            except Exception as e:
                log_message(f"Error calling OpenAI API: {e}")
                traceback.print_exc()
                # 返回空响应和错误信息
                return f"# API Error: {str(e)}", f"ERROR: {str(e)}", 0
            
        else:
            log_message(f"Unsupported API provider: {api_provider}")
            return "# Unsupported API provider", f"ERROR: Unsupported API provider {api_provider}", 0
        
        end_time = time.time()
        latency = end_time - start_time
        
        # 输出摘要
        if enhanced_logging:
            log_message("\n--- API output ---")
            # 只显示前100个字符，避免日志过长
            preview = full_response[:100].replace('\n', ' ')
            if len(full_response) > 100:
                preview += "..."
            log_message(preview)
            log_message("[truncated]")
        
        return generated_code_str, full_response, latency
    
    # 新函数：等待用户按下空格键
    def wait_for_space_key():
        """
        等待用户按下空格键继续
        
        Returns:
            bool: 如果用户按下了空格键返回True，如果应该停止返回False
        """
        from pynput import keyboard
        
        space_pressed = False
        stop_listening = False
        
        def on_press(key):
            nonlocal space_pressed, stop_listening
            try:
                # 检查是否按下空格键
                if key == keyboard.Key.space:
                    space_pressed = True
                    stop_listening = True
                    return False  # 停止监听
                # 检查是否按下q键停止
                elif hasattr(key, 'char') and key.char == 'q':
                    stop_listening = True
                    return False  # 停止监听
            except AttributeError:
                # 部分特殊键可能没有char属性，忽略这些错误
                pass
        
        log_message("等待用户按下空格键继续，或按q键停止...")
        
        # 创建监听器
        listener = keyboard.Listener(on_press=on_press)
        listener.start()
        
        # 等待用户按键或停止信号
        while not space_pressed and not stop_listening and not should_stop():
            time.sleep(0.1)
        
        # 确保监听器停止
        if listener.is_alive():
            listener.stop()
        
        if should_stop() or (stop_listening and not space_pressed):
            return False
        
        return True
    
    # 开始线程执行
    log_message(f"Using Tetris prompt with {plan_seconds}s planning time.")
    if verbose_output:
        log_message(f"Full prompt: {tetris_prompt}")
    
    # 检查初始stop_flag
    if should_stop():
        log_message(f"Stop flag already set. Thread not starting.")
        return "Thread not started due to stop flag"
    
    time.sleep(offset)
    log_message(f"Starting after {offset}s delay... (Plan: {plan_seconds} seconds)")
    
    # 主循环
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
                        # 截图并保存
                        screenshot_path, _ = safe_screenshot(
                            region_to_capture, 
                            thread_id=thread_id, 
                            output_dir=output_dir,
                            suffix=f"_interval_{count}"
                        )
                        log_message(f"Took interval screenshot #{count}: {screenshot_path}", print_message=False)
                except Exception as e:
                    log_message(f"Error in interval screenshot: {e}", print_message=False)
                
                # 等待下一次截图
                time.sleep(screenshot_interval)
        
        # 启动截图线程
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
        
        try:
            # 检测游戏窗口并获取区域
            region, region_type = detect_game_window()
            
            # 再次检查停止标志
            if should_stop():
                log_message(f"Stop flag detected after window detection. Exiting...")
                break
            
            # 截取游戏画面
            initial_screenshot_path, initial_screenshot, base64_image = capture_game_screen(region)
            
            # 调用API获取模型响应
            try:
                generated_code_str, full_response, latency = call_model_api(base64_image)
                
                # 更新响应时间统计
                all_response_time.append(latency)
                avg_latency = sum(all_response_time) / len(all_response_time)
                
                log_message(f"Request latency: {latency:.2f}s")
                log_message(f"Average latency: {avg_latency:.2f}s")
                
                # 记录模型回复到日志文件
                if enhanced_logging:
                    log_message("模型回复已完成")
                    log_message(f"请求延迟: {latency:.2f}s")
                    log_message(f"平均延迟: {avg_latency:.2f}s")
                    
                    # 保存完整回复到文件
                    try:
                        response_folder = os.path.join(log_folder, f"thread_{thread_id}_responses")
                        os.makedirs(response_folder, exist_ok=True)
                        response_file = os.path.join(response_folder, f"response_{int(time.time())}.txt")
                        
                        with open(response_file, 'w', encoding='utf-8', errors='replace') as f:
                            f.write(f"=== 模型回复 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                            f.write(full_response)
                            f.write("\n\n")
                        
                        log_message(f"完整回复已保存到: {response_file}")
                    except Exception as e:
                        log_message(f"Error saving response: {e}")
                
                # 如果提供了响应存储字典，添加响应
                if responses_dict is not None:
                    response_data = {
                        'timestamp': time.time(),
                        'iteration': iteration,
                        'full_response': full_response,
                        'generated_code': generated_code_str,
                        'latency': latency
                    }
                    responses_dict[thread_id].append(response_data)
                    thread_responses.append(response_data)
            except Exception as e:
                log_message(f"Error calling API: {e}")
                time.sleep(5)
                continue
            
            # 检查是否应该停止
            if should_stop():
                log_message(f"Stop flag detected before code execution. Exiting...")
                break
            
            # 提取和执行代码
            try:
                # Extract Python code for execution
                log_message(f"Extracting Python code from response...")
                clean_code = extract_python_code(generated_code_str)
                
                if clean_code:
                    # 输出代码内容用于确认
                    log_message(f"Python code to be executed:")
                    log_message(clean_code)
                    
                    if debug_pause:
                        input(f"[Thread {thread_id}] Press Enter to continue with code execution...")
                    
                    # 执行代码
                    execution_time = execute_model_code(clean_code, initial_screenshot_path, region)
                else:
                    log_message("No executable Python code found in response.")
                    execution_time = 0
            except Exception as e:
                log_message(f"Error in code extraction or execution: {e}")
                traceback.print_exc()
            
            # 如果启用了手动模式，等待用户按下空格键继续
            if manual_mode:
                if not wait_for_space_key():
                    log_message("用户停止了执行。")
                    break
                else:
                    log_message("用户按下了空格键，继续执行...")
            
            log_message(f"Cycle completed, beginning next cycle...")
            
            # 计算并等待到下一个计划周期
            elapsed = execution_time  # 使用execute_model_code返回的执行时间
            wait_time = max(0, plan_seconds - elapsed - latency)  # 减去API调用和代码执行的时间
            log_message(f"Waiting {wait_time:.2f}s until next cycle...")
            
            # 分段等待，便于及时响应停止请求
            segment_size = 0.5  # 每段0.5秒
            segments = int(wait_time / segment_size)
            remainder = wait_time - (segments * segment_size)
            
            for _ in range(segments):
                if should_stop():
                    log_message("Stop flag detected during wait time.")
                    break
                time.sleep(segment_size)
            
            if not should_stop() and remainder > 0:
                time.sleep(remainder)
                
        except Exception as main_loop_error:
            log_message(f"Error in main loop: {main_loop_error}")
            import traceback
            traceback.print_exc()
            # 休息一下再继续
            time.sleep(5)
            
            # 如果连续多次找不到窗口，考虑退出
            if "window" in str(main_loop_error).lower():
                window_missing_count += 1
                if window_missing_count > 5:
                    log_message("Too many window detection failures, exiting...")
                    break
            else:
                # 重置计数器
                window_missing_count = 0
    
    # 停止截图线程
    if screenshot_thread and screenshot_thread.is_alive():
        screenshot_stop_flag = True
        screenshot_thread.join(timeout=2)
    
    log_message("Thread execution completed.")
    return "Thread execution completed."
