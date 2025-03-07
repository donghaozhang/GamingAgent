import time
import os
import numpy as np
import concurrent.futures
import argparse
import json
import threading
import sys
import signal
import subprocess
import platform
import psutil  # 用于监控进程
from pathlib import Path
from datetime import datetime
import pyautogui

try:
    import keyboard  # 尝试导入keyboard库
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Warning: keyboard library not available. Using fallback method.")

try:
    import pygetwindow as gw  # 用于窗口管理
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False
    print("Warning: pygetwindow library not available. Limited window management.")

# 修复导入路径
# 添加项目根目录到Python路径，以便正确导入模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"Added project root to Python path: {project_root}")

# 导入方式改为绝对导入，以支持作为模块运行
try:
    from games.tetris.workers import worker_tetris, find_tetris_window
except ImportError:
    # 作为普通脚本运行时的导入
    try:
        from workers import worker_tetris, find_tetris_window
        print("Imported workers module using relative path")
    except ImportError:
        print("Error: Could not import workers module. Make sure you are in the correct directory.")
        print(f"Current directory: {os.getcwd()}")
        print(f"Current file: {__file__}")
        sys.exit(1)

# 修复全局变量声明
# 创建一个全局变量，作为停止标志
stop_flag = False
tetris_process = None  # 游戏进程对象
game_window = None  # 游戏窗口对象（仅在PyGetWindow可用时使用）

# 当前conda环境信息
def get_conda_env_info():
    """获取当前conda环境的信息"""
    # 检查是否在conda环境中
    conda_prefix = os.environ.get('CONDA_PREFIX')
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    
    if not conda_prefix or not conda_env:
        print("Warning: Not running in a conda environment or conda environment not detected.")
        return None, None
    
    print(f"Running in conda environment: {conda_env} ({conda_prefix})")
    return conda_env, conda_prefix

# 启动Tetris游戏
def launch_tetris_game(use_simplified=True):
    """
    启动Tetris游戏并返回进程对象
    
    Args:
        use_simplified (bool): 是否使用简化版Tetris游戏
        
    Returns:
        subprocess.Popen: 游戏进程对象
    """
    # 检测是否有已存在的Tetris进程
    global tetris_process
    
    stop_tetris_game()  # 确保先停止任何可能运行的游戏
    
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 设置游戏路径
    if use_simplified:
        game_script = os.path.join(current_dir, "simple_tetris.py")
        print(f"Tetris version: Simplified")
    else:
        game_script = os.path.join(current_dir, "Tetris.py")
        print(f"Tetris version: Standard")
    
    # 打印游戏路径
    print(f"Launching Tetris game from: {game_script}")
    
    # 确保游戏脚本文件存在
    if not os.path.exists(game_script):
        print(f"Error: Game script not found at {game_script}")
        return None
    
    # 设置环境变量以确保Pygame显示窗口
    env = os.environ.copy()
    env["SDL_VIDEO_CENTERED"] = "1"
    # 删除任何可能阻止图形界面的环境变量
    if "SDL_VIDEODRIVER" in env:
        del env["SDL_VIDEODRIVER"]
    
    # Windows系统需要特殊处理
    if platform.system() == "Windows":
        # 使用当前Python解释器启动游戏
        python_executable = sys.executable
        
        # 确保路径不含空格
        if " " in python_executable:
            python_executable = f'"{python_executable}"'
        
        if " " in game_script:
            game_script = f'"{game_script}"'
        
        try:
            # 直接使用subprocess.Popen启动游戏，避免使用shell=True
            cmd = [python_executable, game_script]
            print(f"执行命令: {' '.join(cmd)}")
            
            tetris_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE  # 确保在Windows上创建新控制台
            )
            
            # 检查进程是否成功启动
            if tetris_process.poll() is not None:
                # 进程已退出，读取错误信息
                stderr = tetris_process.stderr.read()
                print(f"Error: Game process exited immediately with code {tetris_process.returncode}")
                print(f"Error details: {stderr}")
                return None
                
            print(f"Tetris game started with PID: {tetris_process.pid}")
            return tetris_process
            
        except Exception as e:
            print(f"Error starting Tetris game: {e}")
            return None
    else:
        # Linux/Mac系统启动游戏
        try:
            tetris_process = subprocess.Popen(
                [sys.executable, game_script],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            print(f"Tetris game started with PID: {tetris_process.pid}")
            return tetris_process
        except Exception as e:
            print(f"Error starting Tetris game: {e}")
            return None

# 游戏进程监控线程
def tetris_monitor_thread(use_simplified=True):
    """
    监控Tetris游戏进程的线程，如果游戏退出则重新启动
    
    Args:
        use_simplified (bool): 是否使用简化版Tetris
    """
    global tetris_process
    no_auto_launch = '--no_launch_game' in sys.argv
    
    # 如果指定了不自动启动游戏，则只监控，不启动
    if no_auto_launch:
        print("Running in monitor-only mode (--no_launch_game)")
        while not stop_flag:
            time.sleep(1)  # 简单睡眠，减少CPU使用
        return
    
    while not stop_flag:
        # 检查Tetris进程是否需要启动或重启
        if tetris_process is None or tetris_process.poll() is not None:
            print("Starting or restarting Tetris game...")
            tetris_process = launch_tetris_game(use_simplified)
            if tetris_process is None:
                print("Failed to launch Tetris game. Retrying in 5 seconds...")
                time.sleep(5)
                continue
                
            # 给游戏一些时间来初始化
            time.sleep(3)
        
        # 监控进程是否还在运行
        if tetris_process.poll() is not None:
            returncode = tetris_process.returncode
            print(f"Tetris game exited with code {returncode}")
            
            # 尝试读取错误输出
            stderr = tetris_process.stderr.read() if tetris_process.stderr else ""
            if stderr:
                print(f"Error output: {stderr}")
                
            # 如果游戏是正常退出（用户关闭），则不重启
            if returncode == 0:
                print("Tetris game closed normally, not restarting.")
                break
                
            # 否则等待一段时间后重启
            print("Tetris game crashed or closed unexpectedly. Restarting in 5 seconds...")
            tetris_process = None
            time.sleep(5)
        else:
            # 进程正在运行中，等待一段时间后再检查
            time.sleep(1)

# 停止Tetris游戏
def stop_tetris_game():
    """
    停止Tetris游戏进程
    """
    # 先检查是否有全局进程变量
    global tetris_process
    if tetris_process:
        try:
            # 检查进程是否还在运行
            if tetris_process.poll() is None:
                print(f"Terminating Tetris process (PID: {tetris_process.pid})")
                tetris_process.kill()
                try:
                    tetris_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    print("Could not wait for Tetris process to terminate")
            tetris_process = None
        except Exception as e:
            print(f"Error terminating Tetris process: {e}")
            tetris_process = None
    
    # 如果使用--no_launch_game参数启动，则不查找其他Tetris进程
    if '--no_launch_game' in sys.argv:
        print("Using --no_launch_game, not searching for other Tetris processes")
        return
    
    # 检查是否有其他Tetris进程在运行
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 查找Python进程，且命令行中包含Tetris关键词
            if 'python' in proc.name().lower() and any(
                keyword.lower() in arg.lower() 
                for arg in proc.cmdline() if arg
                for keyword in ['tetris', 'simple_tetris']
            ):
                print(f"Found existing Tetris process (PID: {proc.pid}), terminating it first...")
                try:
                    proc.kill()  # 直接终止进程
                    proc.wait(timeout=2)  # 等待进程结束，最多2秒
                except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                    print(f"Could not wait for process {proc.pid} to terminate")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            print(f"Error accessing process: {e}")

# 键盘监听函数，使用keyboard库接收"q"键
def key_listener():
    """
    启动一个键盘监听线程，监听'q'键来停止所有线程
    """
    if not KEYBOARD_AVAILABLE:
        print("Keyboard library not available, key listener not started")
        return None
        
    print("Starting keyboard listener. Press 'q' to stop all threads.")
    
    def on_q_pressed(e):
        """按下q键时的回调函数"""
        if e.name == 'q':
            print("'q' key pressed, stopping all threads...")
            global stop_flag
            stop_flag = True
            # 也停止游戏
            stop_tetris_game()
            
    # 注册按键监听
    keyboard.on_press(on_q_pressed)

# 信号处理函数，用于处理Ctrl+C等信号
def signal_handler(sig, frame):
    """处理中断信号，确保程序可以优雅地退出"""
    print("Interrupt signal received, stopping all threads...")
    global stop_flag
    stop_flag = True
    # 停止游戏进程
    stop_tetris_game()
    sys.exit(0)

def wait_for_any_result(futures, timeout=0.5):
    """
    等待任何一个future完成，如果有完成的future，从列表中移除它并返回结果
    
    Args:
        futures (list): Future对象列表
        timeout (float): 每次等待的超时时间（秒）
        
    Returns:
        tuple: (完成的future列表, 剩余的future列表)
    """
    # 如果没有future，直接返回
    if not futures:
        return [], []
    
    # 使用wait方法等待任何一个future完成
    done, not_done = concurrent.futures.wait(
        futures,
        timeout=timeout,
        return_when=concurrent.futures.FIRST_COMPLETED
    )
    
    # 返回完成的和未完成的future
    return list(done), list(not_done)

system_prompt = (
    "You are an expert AI agent specialized in playing Tetris gameplay, search for and execute optimal moves given each game state. Prioritize line clearing over speed."
)

def main():
    """主函数"""
    global stop_flag, tetris_process
    
    # 注册信号处理程序，以便可以用Ctrl+C停止
    signal.signal(signal.SIGINT, signal_handler)
    
    # 设置参数解析
    parser = argparse.ArgumentParser(description='AI agent for playing Tetris')
    parser.add_argument('--model_name', default='claude-3-7-sonnet-20250219', help='AI model name to use (default: claude-3-7-sonnet-20250219)')
    parser.add_argument('--api_provider', default='anthropic', choices=['anthropic', 'openai', 'gemini'], help='API provider to use')
    parser.add_argument('--min_threads', default=1, type=int, help='Minimum number of threads to use')
    parser.add_argument('--max_threads', default=1, type=int, help='Maximum number of threads to use')
    parser.add_argument('--plan_seconds', default=30, type=int, help='Seconds between planning cycles')
    parser.add_argument('--thread_policy', default='fixed', choices=['fixed', 'dynamic'], help='Thread management policy')
    parser.add_argument('--verbose_output', action='store_true', help='Display verbose output')
    parser.add_argument('--save_responses', action='store_true', help='Save AI responses to files')
    parser.add_argument('--output_dir', default='model_responses', help='Directory to save responses')
    parser.add_argument('--manual_window', action='store_true', help='Manually specify window region')
    parser.add_argument('--window_left', type=int, help='Left coordinate of window')
    parser.add_argument('--window_top', type=int, help='Top coordinate of window')
    parser.add_argument('--window_width', type=int, help='Width of window')
    parser.add_argument('--window_height', type=int, help='Height of window')
    parser.add_argument('--debug_pause', action='store_true', help='Pause for debugging between actions')
    parser.add_argument('--no_launch_game', action='store_true', help='Do not launch the Tetris game')
    parser.add_argument('--use_original_tetris', action='store_true', help='Use original Tetris instead of simplified version')
    parser.add_argument('--screenshot_interval', default=0, type=int, help='Take additional screenshots every N seconds (0 to disable)')
    parser.add_argument('--enhanced_logging', action='store_true', help='Enable enhanced logging with timestamps')
    parser.add_argument('--save_all_states', action='store_true', help='Save screenshots for all game states')
    parser.add_argument('--log_folder', default='game_logs', help='Folder for storing logs and additional screenshots')
    
    args = parser.parse_args()
    
    # 打印参数信息
    print(f"Starting with {args.min_threads} threads using policy '{args.thread_policy}'...")
    print(f"API Provider: {args.api_provider}, Model Name: {args.model_name}")
    print(f"Verbose output: {args.verbose_output}, Save responses: {args.save_responses}")
    print(f"Debug pause: {args.debug_pause}")
    
    # 检查conda环境
    conda_env, conda_prefix = get_conda_env_info()
    if conda_env and conda_prefix:
        print(f"Running in conda environment: {conda_env} ({conda_prefix})")
    
    # 创建日志文件夹
    if args.enhanced_logging or args.save_all_states or args.screenshot_interval > 0:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_folder = os.path.join(args.log_folder, f"session_{timestamp}")
        os.makedirs(log_folder, exist_ok=True)
        
        # 创建日志文件
        log_file = os.path.join(log_folder, "game_log.txt")
        with open(log_file, 'w') as f:
            f.write(f"=== Tetris Agent Session Started at {timestamp} ===\n")
            f.write(f"Arguments: {json.dumps(vars(args), indent=2)}\n")
            f.write(f"System info: {platform.system()} {platform.release()}\n")
            f.write("="*50 + "\n\n")
        
        print(f"Enhanced logging enabled. Logs will be saved to {log_file}")
    else:
        log_folder = None
        log_file = None
    
    # 设置手动窗口区域
    manual_window_region = None
    if args.manual_window and args.window_left is not None and args.window_top is not None and args.window_width is not None and args.window_height is not None:
        manual_window_region = (args.window_left, args.window_top, args.window_width, args.window_height)
        print(f"Using manual window region: {manual_window_region}")
    
    # 如果需要，启动Tetris游戏监控线程
    monitor_thread = None
    if not args.no_launch_game:
        monitor_thread = threading.Thread(
            target=tetris_monitor_thread,
            args=(not args.use_original_tetris,),
            daemon=True
        )
        monitor_thread.start()
    
    # 启动键盘监听线程
    key_listener()
    
    # 创建、启动线程池和线程
    try:
        # 创建保存响应的目录
        if args.save_responses:
            os.makedirs(args.output_dir, exist_ok=True)
            
        # 创建用于在线程间共享响应的字典
        responses_dict = {}
        
        # 启动工作线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_threads) as executor:
            # 创建worker线程
            futures = []
            for i in range(args.min_threads):
                future = executor.submit(
                    worker_tetris,
                    i,
                    i % 10 * 100,  # 偏移量
                    "You are a helpful assistant that plays Tetris. When asked to help the player, you should analyze the visible game state from the image, identify the current and next piece, and suggest the best move considering piece placement, line clearing, and maintaining a good board structure. Explain your reasoning based on Tetris strategy principles.",
                    args.api_provider,
                    args.model_name,
                    args.plan_seconds,
                    args.verbose_output,
                    args.save_responses,
                    args.output_dir,
                    responses_dict,
                    manual_window_region,
                    args.debug_pause,
                    lambda: stop_flag,  # 使用lambda获取最新的stop_flag值
                    # 添加新的参数
                    log_folder=log_folder,
                    log_file=log_file,
                    screenshot_interval=args.screenshot_interval,
                    save_all_states=args.save_all_states,
                    enhanced_logging=args.enhanced_logging
                )
                futures.append(future)
            
            # 使用wait_for_any_result函数等待结果
            while futures and not stop_flag:
                done, futures = wait_for_any_result(futures)
                for future in done:
                    try:
                        result = future.result()
                        print(f"Thread completed with result: {result}")
                    except Exception as e:
                        print(f"Thread raised an exception: {e}")
                
                # 如果使用动态线程策略且尚未达到最大线程数，可以添加更多线程
                if args.thread_policy == 'dynamic' and len(futures) < args.max_threads and not stop_flag:
                    new_thread_id = len(futures) + args.min_threads
                    future = executor.submit(
                        worker_tetris,
                        new_thread_id,
                        new_thread_id % 10 * 100,  # 偏移量
                        "You are a helpful assistant that plays Tetris. When asked to help the player, you should analyze the visible game state from the image, identify the current and next piece, and suggest the best move considering piece placement, line clearing, and maintaining a good board structure. Explain your reasoning based on Tetris strategy principles.",
                        args.api_provider,
                        args.model_name,
                        args.plan_seconds,
                        args.verbose_output,
                        args.save_responses,
                        args.output_dir,
                        responses_dict,
                        manual_window_region,
                        args.debug_pause,
                        lambda: stop_flag,  # 使用lambda获取最新的stop_flag值
                        # 添加新的参数
                        log_folder=log_folder,
                        log_file=log_file,
                        screenshot_interval=args.screenshot_interval,
                        save_all_states=args.save_all_states,
                        enhanced_logging=args.enhanced_logging
                    )
                    futures.append(future)
            
            # 如果是因为stop_flag被设置而退出循环，取消所有未完成的任务
            if stop_flag:
                for future in futures:
                    future.cancel()
        
        # 等待monitor_thread退出
        if monitor_thread and monitor_thread.is_alive():
            print("Waiting for monitor thread to exit...")
            monitor_thread.join(timeout=5)
    
    except KeyboardInterrupt:
        print("\nInterrupted by user, stopping all threads...")
        stop_flag = True
        # 确保游戏进程被停止
        stop_tetris_game()
    
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 确保游戏被停止
        stop_tetris_game()
        print("Main thread exiting...")

if __name__ == "__main__":
    main()