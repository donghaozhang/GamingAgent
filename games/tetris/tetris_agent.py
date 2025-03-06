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

from games.tetris.workers import worker_tetris, find_tetris_window

# 创建一个全局变量，作为停止标志
STOP_ALL_THREADS = threading.Event()  # 使用Event代替简单的布尔值
TETRIS_PROCESS = None  # 用于存储启动的Tetris进程
GAME_WINDOW = None  # 用于存储游戏窗口引用

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
    global TETRIS_PROCESS, GAME_WINDOW
    
    # 获取当前conda环境信息
    conda_env, conda_prefix = get_conda_env_info()
    
    # 获取Tetris路径
    current_dir = Path(__file__).parent
    
    # 根据选择使用不同的Tetris版本
    if use_simplified:
        tetris_path = current_dir / "simple_tetris.py"
        window_title_keywords = ["Simple Tetris", "pygame", "Pygame"]
    else:
        tetris_path = current_dir / "tetris-pygame-master" / "Tetris.py"
        window_title_keywords = ["Tetris", "pygame", "Pygame"]
    
    if not tetris_path.exists():
        print(f"Error: Cannot find Tetris game at {tetris_path}")
        return False
    
    print(f"Launching Tetris game from: {tetris_path}")
    
    # 先检查是否已有Tetris进程在运行
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # 查找Python进程，且命令行中包含Tetris关键词
            if 'python' in proc.name().lower() and any(
                keyword.lower() in arg.lower() 
                for arg in proc.cmdline() if arg
                for keyword in ['tetris', 'simple_tetris']
            ):
                print(f"Found existing Tetris process (PID: {proc.pid}), terminating it first...")
                proc.kill()
                time.sleep(1)  # 给进程一些时间来结束
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    try:
        # 设置环境变量以控制Pygame窗口标题和位置
        env = os.environ.copy()
        env["SDL_VIDEO_WINDOW_POS"] = "100,100"  # 放在屏幕可见位置
        env["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"  # 隐藏Pygame初始化消息
        
        # 为不同操作系统设置不同的启动选项
        creation_flags = 0
        if platform.system() == "Windows":
            # Windows上创建新控制台窗口
            creation_flags = subprocess.CREATE_NEW_CONSOLE
        
        # 根据是否在conda环境中选择启动方式
        if conda_env and conda_prefix:
            # 使用conda环境启动Tetris
            print(f"Launching Tetris with conda environment: {conda_env}")
            
            if platform.system() == "Windows":
                # Windows上使用conda运行
                activate_cmd = f"conda activate {conda_env} && "
                python_cmd = sys.executable
                
                # 使用cmd通过conda环境运行Python脚本
                TETRIS_PROCESS = subprocess.Popen(
                    f'start cmd /c "{activate_cmd} {python_cmd} {str(tetris_path)}"',
                    shell=True,
                    env=env,
                )
            else:
                # Linux/Mac上使用conda运行
                conda_bin = Path(conda_prefix).parent / "bin" / "conda"
                TETRIS_PROCESS = subprocess.Popen(
                    [str(conda_bin), "run", "-n", conda_env, "python", str(tetris_path)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                )
        else:
            # 直接使用当前Python解释器启动
            print(f"Launching Tetris with current Python interpreter: {sys.executable}")
            TETRIS_PROCESS = subprocess.Popen(
                [sys.executable, str(tetris_path)], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                env=env,
                creationflags=creation_flags
            )
        
        print("Tetris game launched successfully. Waiting for window to appear...")
        
        # 给游戏一些时间来启动和显示窗口
        # 然后检查窗口是否出现
        max_wait = 15  # 最多等待15秒
        wait_interval = 0.5  # 每0.5秒检查一次
        window_found = False
        
        for i in range(int(max_wait / wait_interval)):
            time.sleep(wait_interval)
            
            # Windows上使用conda启动时，我们无法直接获取进程对象
            if platform.system() == "Windows" and conda_env and conda_prefix:
                # 只检查窗口是否出现
                pass
            else:
                # 检查进程是否还在运行
                if TETRIS_PROCESS and TETRIS_PROCESS.poll() is not None:
                    print(f"Error: Tetris process exited prematurely with code {TETRIS_PROCESS.returncode}")
                    # 尝试读取错误输出
                    try:
                        _, stderr = TETRIS_PROCESS.communicate(timeout=1)
                        print(f"Error output: {stderr.decode('utf-8', errors='ignore')}")
                    except:
                        print("Could not read error output")
                    return False
                
            # 尝试查找Tetris窗口
            window_region = find_tetris_window(window_title_keywords)
            if window_region is not None:
                window_found = True
                print(f"Tetris window found at {window_region}!")
                
                # 尝试激活窗口（如果pygetwindow可用）
                if PYGETWINDOW_AVAILABLE:
                    try:
                        # 查找所有窗口，尝试找到pygame窗口
                        pygame_windows = [
                            win for win in gw.getAllWindows() 
                            if any(keyword.lower() in win.title.lower() for keyword in window_title_keywords)
                        ]
                        if pygame_windows:
                            GAME_WINDOW = pygame_windows[0]
                            GAME_WINDOW.activate()
                            print(f"Successfully activated window: {GAME_WINDOW.title}")
                        else:
                            print("Could not find pygame window to activate")
                    except Exception as e:
                        print(f"Could not activate window: {e}")
                
                break
            else:
                print(f"Waiting for Tetris window to appear ({i+1}/{int(max_wait / wait_interval)})...")
        
        if not window_found:
            print("Warning: Could not find Tetris window after waiting. The game might still be starting...")
            
        return True
    except Exception as e:
        print(f"Error launching Tetris game: {e}")
        return False

# 游戏进程监控线程
def tetris_monitor_thread(use_simplified=True):
    global TETRIS_PROCESS, STOP_ALL_THREADS
    
    print("Starting Tetris process monitor thread...")
    
    while not STOP_ALL_THREADS.is_set():
        time.sleep(2)  # 每2秒检查一次
        
        if TETRIS_PROCESS is None:
            continue
            
        # Windows上使用conda启动时，我们无法直接获取进程状态
        if platform.system() == "Windows" and get_conda_env_info()[0]:
            # 检查窗口是否仍然存在
            window_title_keywords = ["Simple Tetris", "pygame", "Pygame"] if use_simplified else ["Tetris", "pygame", "Pygame"]
            if find_tetris_window(window_title_keywords) is None:
                print("Warning: Tetris window not found. The game might have closed.")
                
                # 如果主线程还在运行，尝试重启游戏
                if not STOP_ALL_THREADS.is_set():
                    print("Attempting to restart Tetris game...")
                    if launch_tetris_game(use_simplified):
                        print("Successfully restarted Tetris game")
                    else:
                        print("Failed to restart Tetris game")
        else:
            # 检查进程是否还在运行
            if TETRIS_PROCESS.poll() is not None:
                print(f"Warning: Tetris process has exited with code {TETRIS_PROCESS.returncode}")
                
                # 如果主线程还在运行，尝试重启游戏
                if not STOP_ALL_THREADS.is_set():
                    print("Attempting to restart Tetris game...")
                    if launch_tetris_game(use_simplified):
                        print("Successfully restarted Tetris game")
                    else:
                        print("Failed to restart Tetris game")
                        
                        # 如果启动失败且有很多次尝试失败，可以考虑停止所有线程
                        # 这里只是记录警告，不强制停止
                        print("Warning: Tetris game could not be restarted. Agent might not work correctly.")

# 停止Tetris游戏
def stop_tetris_game():
    global TETRIS_PROCESS, GAME_WINDOW
    
    # 先尝试关闭窗口
    if PYGETWINDOW_AVAILABLE and GAME_WINDOW:
        try:
            print(f"Closing game window: {GAME_WINDOW.title}")
            GAME_WINDOW.close()
            time.sleep(0.5)  # 给窗口一些时间来关闭
        except Exception as e:
            print(f"Error closing game window: {e}")
    
    # 然后终止进程
    if TETRIS_PROCESS:
        print("Terminating Tetris game process...")
        try:
            # 检查是否是Windows上使用conda启动的进程
            if platform.system() == "Windows" and get_conda_env_info()[0]:
                # 对于使用shell启动的进程，我们无法直接终止它
                # 只能通过taskkill终止相关进程
                print("Using taskkill to terminate Tetris process...")
                os.system("taskkill /f /im python.exe /fi \"WINDOWTITLE eq *Tetris*\"")
                os.system("taskkill /f /im python.exe /fi \"WINDOWTITLE eq *pygame*\"")
                os.system("taskkill /f /im python.exe /fi \"WINDOWTITLE eq *Simple Tetris*\"")
            else:
                # 直接终止进程
                TETRIS_PROCESS.terminate()
                TETRIS_PROCESS.wait(timeout=5)
        except Exception as e:
            print(f"Error terminating Tetris game: {e}")
            try:
                print("Trying to forcefully kill the process...")
                if hasattr(TETRIS_PROCESS, 'kill'):
                    TETRIS_PROCESS.kill()
            except Exception as e2:
                print(f"Error killing process: {e2}")
    
    # 清理可能残留的Python进程（运行Tetris的）
    try:
        print("Cleaning up leftover Tetris processes...")
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if 'python' in proc.name().lower() and any(
                    keyword.lower() in arg.lower() 
                    for arg in proc.cmdline() if arg
                    for keyword in ['tetris', 'simple_tetris']
                ):
                    print(f"Killing leftover Tetris process (PID: {proc.pid})...")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # 在Windows上，检查pygame窗口进程
        if platform.system() == "Windows":
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if 'python' in proc.name().lower():
                        # 尝试检查窗口标题
                        window_titles = [window.title.lower() for window in pyautogui.getAllWindows()]
                        for title in window_titles:
                            if any(keyword in title for keyword in ['pygame', 'tetris', 'simple tetris']):
                                print(f"Killing Python process with pygame window (PID: {proc.pid})...")
                                proc.kill()
                                break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
                except Exception as e:
                    print(f"Error checking process: {e}")
    except Exception as e:
        print(f"Error cleaning up processes: {e}")

# 键盘监听函数，使用keyboard库接收"q"键
def key_listener():
    global STOP_ALL_THREADS
    print("Press 'q' to stop all threads...")
    
    if KEYBOARD_AVAILABLE:
        def on_q_pressed(e):
            if e.name == 'q':
                print("\nQ key pressed. Stopping all threads...")
                STOP_ALL_THREADS.set()  # 设置事件
        
        # 注册q键的按下事件
        keyboard.on_press_key('q', on_q_pressed)
    else:
        # 备用方法：创建一个线程专门监听输入
        def input_thread():
            while not STOP_ALL_THREADS.is_set():
                try:
                    # 等待输入
                    if sys.stdin.isatty():  # 确保有可用的标准输入
                        user_input = input("Press 'q' and Enter to stop: ")
                        if user_input.lower() == 'q':
                            print("\nQ key pressed. Stopping all threads...")
                            STOP_ALL_THREADS.set()  # 设置事件
                            break
                except Exception as e:
                    print(f"Error in input thread: {e}")
                time.sleep(0.5)
        
        input_thread = threading.Thread(target=input_thread)
        input_thread.daemon = True
        input_thread.start()

# 信号处理函数，用于处理Ctrl+C等信号
def signal_handler(sig, frame):
    print("\nReceived signal. Stopping all threads...")
    STOP_ALL_THREADS.set()  # 设置事件

system_prompt = (
    "You are an expert AI agent specialized in playing Tetris gameplay, search for and execute optimal moves given each game state. Prioritize line clearing over speed."
)

def main():
    """
    Spawns a number of short-term and/or long-term Tetris workers based on user-defined parameters.
    Each worker will analyze the Tetris board and choose moves accordingly.
    """
    global STOP_ALL_THREADS
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # 处理Ctrl+C
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)  # Windows上的Ctrl+Break
    
    parser = argparse.ArgumentParser(
        description="Tetris gameplay agent with configurable concurrent workers."
    )
    parser.add_argument("--api_provider", type=str, default="anthropic",
                        help="API provider to use.")
    parser.add_argument("--model_name", type=str, default="claude-3-7-sonnet-20250219",
                        help="Model name.")
    parser.add_argument("--concurrency_interval", type=float, default=1,
                        help="Interval in seconds between workers.")
    parser.add_argument("--api_response_latency_estimate", type=float, default=5,
                        help="Estimated API response latency in seconds.")
    parser.add_argument("-control_time", type=float, default=4,
                        help="Worker control time.")
    parser.add_argument("--policy", type=str, default="fixed", 
                        choices=["fixed"],
                        help="Worker policy")
    parser.add_argument("--save_responses", action="store_true",
                        help="Save model responses to files")
    parser.add_argument("--verbose_output", action="store_true", 
                        help="Print detailed model responses")
    parser.add_argument("--output_dir", type=str, default="model_responses",
                        help="Directory to save model responses")
    
    # 添加手动指定窗口位置的命令行参数
    parser.add_argument("--manual_window", action="store_true",
                        help="Manually specify the game window region")
    parser.add_argument("--window_left", type=int, default=0,
                        help="Left position of game window")
    parser.add_argument("--window_top", type=int, default=0,
                        help="Top position of game window")
    parser.add_argument("--window_width", type=int, default=540,
                        help="Width of game window")
    parser.add_argument("--window_height", type=int, default=640,
                        help="Height of game window")
    
    # 添加调试暂停选项
    parser.add_argument("--debug_pause", action="store_true",
                        help="Enable 5 second pause before API calls for log inspection")
                        
    # 添加控制是否自动启动Tetris游戏的选项
    parser.add_argument("--no_launch_game", action="store_true",
                        help="Do not automatically launch Tetris game")
    
    # 添加选择Tetris游戏版本的选项
    parser.add_argument("--use_original_tetris", action="store_true",
                        help="Use original Tetris.py instead of simple_tetris.py")
                        
    # 添加窗口激活间隔选项
    parser.add_argument("--activate_window_interval", type=int, default=10,
                        help="Interval (in seconds) to re-activate the game window (0 to disable)")

    args = parser.parse_args()

    worker_span = args.control_time + args.concurrency_interval
    num_threads = int(args.api_response_latency_estimate // worker_span)
    
    if args.api_response_latency_estimate % worker_span != 0:
        num_threads += 1
    
    # Create an offset list
    offsets = [i * (args.control_time + args.concurrency_interval) for i in range(num_threads)]

    # Create output directory if saving responses
    if args.save_responses:
        os.makedirs(args.output_dir, exist_ok=True)
        print(f"Model responses will be saved to: {args.output_dir}")
    
    print(f"Starting with {num_threads} threads using policy '{args.policy}'...")
    print(f"API Provider: {args.api_provider}, Model Name: {args.model_name}")
    print(f"Verbose output: {args.verbose_output}, Save responses: {args.save_responses}")
    print(f"Debug pause: {args.debug_pause}")
    print(f"Tetris version: {'Original' if args.use_original_tetris else 'Simplified'}")
    
    # 初始化手动窗口区域变量
    manual_window_region = None
    # 如果用户手动指定了窗口位置，显示相关信息
    if args.manual_window:
        manual_window_region = (args.window_left, args.window_top, args.window_width, args.window_height)
        print(f"Using manually specified window region: {manual_window_region}")
    
    # 如果没有指定--no_launch_game，则自动启动Tetris游戏
    if not args.no_launch_game:
        if not launch_tetris_game(not args.use_original_tetris):
            print("Warning: Failed to launch Tetris game. Agent will try to find an existing Tetris window.")
    
    # 启动Tetris进程监控线程
    monitor_thread = threading.Thread(target=tetris_monitor_thread, args=(not args.use_original_tetris,))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 创建窗口激活线程（如果启用）
    if args.activate_window_interval > 0 and PYGETWINDOW_AVAILABLE:
        def window_activation_thread():
            while not STOP_ALL_THREADS.is_set():
                try:
                    time.sleep(args.activate_window_interval)
                    if GAME_WINDOW:
                        GAME_WINDOW.activate()
                        print(f"Re-activated game window: {GAME_WINDOW.title}")
                except Exception as e:
                    print(f"Error activating window: {e}")
        
        activation_thread = threading.Thread(target=window_activation_thread)
        activation_thread.daemon = True
        activation_thread.start()
        print(f"Window activation thread started (interval: {args.activate_window_interval}s)")

    # Create a shared response dictionary for all threads
    responses = {
        "start_time": datetime.now().isoformat(),
        "threads": {}
    }
    
    # 启动键盘监听
    key_listener()
    print("Keyboard listener started. Press 'q' to stop all threads.")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            future_to_thread = {}
            for i in range(num_threads):
                if args.policy == "fixed":
                    future = executor.submit(
                        worker_tetris, i, offsets[i], system_prompt,
                        args.api_provider, args.model_name, args.control_time, 
                        args.verbose_output, args.save_responses, args.output_dir, responses,
                        manual_window_region, args.debug_pause, STOP_ALL_THREADS  # 传递停止标志
                    )
                    future_to_thread[future] = i
                else:
                    raise NotImplementedError(f"policy: {args.policy} not implemented.")
    
            try:
                # 检查线程是否完成或者是否要求停止
                while not STOP_ALL_THREADS.is_set():
                    # 检查是否所有线程都已完成
                    all_done = all(future.done() for future in future_to_thread)
                    if all_done:
                        print("All threads have completed.")
                        break
                    time.sleep(0.25)
            except KeyboardInterrupt:
                print("\nMain thread interrupted. Exiting all threads...")
                STOP_ALL_THREADS.set()  # 设置事件
                
            if STOP_ALL_THREADS.is_set():
                print("Stop flag set. Waiting for threads to finish...")
                
            # 等待所有线程完成
            print("Waiting for all threads to finish...")
            for future in concurrent.futures.as_completed(future_to_thread):
                thread_id = future_to_thread[future]
                try:
                    future.result()  # 获取结果以捕获异常
                except Exception as e:
                    print(f"Thread {thread_id} generated an exception: {e}")
                
            # Save final responses if requested
            if args.save_responses:
                final_path = os.path.join(args.output_dir, f"final_responses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                try:
                    with open(final_path, 'w') as f:
                        json.dump(responses, f, indent=2)
                    print(f"Final responses saved to: {final_path}")
                except Exception as e:
                    print(f"Error saving final responses: {e}")
    finally:
        # 确保在程序退出时关闭Tetris游戏
        stop_tetris_game()

if __name__ == "__main__":
    main()