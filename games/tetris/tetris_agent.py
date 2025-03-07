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
def key_listener(event_flag=None):
    """
    启动一个键盘监听线程，监听'q'键来停止所有线程
    
    Args:
        event_flag: 停止标志，通常是threading.Event对象
    """
    if not KEYBOARD_AVAILABLE:
        print("Keyboard library not available. Press Ctrl+C to stop.")
        return
    
    # 获取全局变量的引用
    global stop_flag
    
    def on_q_pressed(e):
        """当按下q键时停止所有线程"""
        if e.name == 'q':
            print("'q' key pressed, stopping all threads...")
            
            # 设置传入的Event对象（如果有）
            if event_flag is not None and isinstance(event_flag, threading.Event):
                event_flag.set()
            
            # 同时设置全局stop_flag变量
            global stop_flag
            stop_flag = True
            
            # 停止游戏进程
            stop_tetris_game()
            # 停止监听器
            return False
    
    # 创建并启动监听器
    keyboard.on_press(on_q_pressed)
    print("Starting keyboard listener. Press 'q' to stop all threads.")

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
    """主函数，解析命令行参数并启动代理"""
    parser = argparse.ArgumentParser(description='Tetris AI Agent')
    parser.add_argument('--threads', type=int, default=1, help='Number of threads to run')
    parser.add_argument('--offset', type=float, default=0, help='Delay offset (seconds) between threads')
    parser.add_argument('--policy', type=str, default='fixed', choices=['fixed', 'cyclic'], help='Thread spawn policy')
    parser.add_argument('--system_prompt', type=str, default='You are a helpful expert Tetris player. Your task is to help the user play Tetris by providing the best moves for the current board state.', help='System prompt for the model')
    parser.add_argument('--execution_mode', type=str, default='adaptive', choices=['adaptive', 'fast', 'slow'], help='Execution mode for model code')
    parser.add_argument('--piece_limit', type=int, default=0, help='Maximum pieces to control per API call (0=unlimited)')
    parser.add_argument('--api_provider', type=str, default='anthropic', choices=['anthropic', 'claude', 'openai', 'gpt4'], help='API provider')
    parser.add_argument('--model', type=str, default='claude-3-7-sonnet-20250219', help='Model name')
    parser.add_argument('--plan_seconds', type=float, default=60, help='Planning horizon (seconds)')
    parser.add_argument('--manual_mode', action='store_true', help='Manual mode - wait for space key between API calls')
    parser.add_argument('--save_responses', action='store_true', help='Save model responses to files')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--debug_pause', action='store_true', help='Pause before executing code')
    parser.add_argument('--output_dir', type=str, default='game_logs', help='Output directory for logs')
    parser.add_argument('--log_folder', type=str, default=None, help='Custom log folder')
    parser.add_argument('--manual_window_pos', type=str, default=None, help='Manual window position (x,y,width,height)')
    parser.add_argument('--no_launch_game', action='store_true', help='Do not launch the Tetris game')
    parser.add_argument('--simplified', action='store_true', help='Use simplified Tetris game')
    parser.add_argument('--screenshot_interval', type=float, default=0, help='Screenshot interval (seconds), 0 to disable')
    parser.add_argument('--save_all_states', action='store_true', help='Save all game states')
    parser.add_argument('--enhanced_logging', action='store_true', help='Enable enhanced logging')
    
    args = parser.parse_args()
    
    # 检查是否安装了PyAutoGUI
    try:
        import pyautogui
    except ImportError:
        print("Error: PyAutoGUI is not installed. Please install it using: pip install pyautogui")
        return

    # 打印环境信息
    conda_env = get_conda_env_info()
    if conda_env:
        print(f"Running in conda environment: {conda_env}")
    
    # 创建日志文件夹
    if args.log_folder is None:
        args.log_folder = os.path.join(args.output_dir, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    os.makedirs(args.log_folder, exist_ok=True)
    
    # 创建主日志文件
    log_file = os.path.join(args.log_folder, "game_log.txt")
    
    # 如果启用了增强日志，记录启动信息
    if args.enhanced_logging:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"=== Tetris AI Agent Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"Threads: {args.threads}, Policy: {args.policy}\n")
            f.write(f"API Provider: {args.api_provider}, Model: {args.model}\n")
            f.write(f"Plan Seconds: {args.plan_seconds}\n")
            f.write(f"Manual Mode: {args.manual_mode}\n")
            f.write(f"Screenshot Interval: {args.screenshot_interval}\n")
            f.write(f"Enhanced Logging: {args.enhanced_logging}\n")
            f.write("="*50 + "\n\n")
        
        print(f"Enhanced logging enabled. Logs will be saved to {log_file}")
    
    # 解析手动窗口位置（如果提供）
    manual_window_region = None
    if args.manual_window_pos:
        try:
            parts = [int(x) for x in args.manual_window_pos.split(',')]
            if len(parts) == 4:
                manual_window_region = tuple(parts)
                print(f"Using manual window region: {manual_window_region}")
            else:
                print(f"Invalid manual window position format. Expected: x,y,width,height")
        except ValueError:
            print(f"Invalid manual window position format. Expected: x,y,width,height")
    
    # 如果没有使用--no_launch_game参数，启动Tetris游戏
    if not args.no_launch_game:
        game_process = launch_tetris_game(use_simplified=args.simplified)
        if not game_process:
            print("Failed to start Tetris game. Exiting...")
            return
        
        # 给游戏一些时间启动
        print("Waiting for game to start...")
        time.sleep(3)
    
    # 设置停止标志
    stop_flag = threading.Event()
    
    # 创建并启动键盘监听器 - 修复：传递Event对象
    keyboard_thread = threading.Thread(target=key_listener, args=(stop_flag,))
    keyboard_thread.daemon = True
    keyboard_thread.start()
    print("Starting keyboard listener. Press 'q' to stop all threads.")
    
    # 启动线程
    print(f"Starting with {args.threads} threads using policy '{args.policy}'...")
    
    # 创建共享的响应字典
    responses_dict = {}
    
    # 启动工作线程
    threads = []
    for i in range(args.threads):
        # 计算偏移
        if args.policy == 'fixed':
            offset = args.offset
        else:  # 'cyclic'
            offset = i * (args.plan_seconds / args.threads)
        
        thread = threading.Thread(
            target=worker_tetris,
            args=(
                i,
                offset,
                args.system_prompt,
                args.api_provider,
                args.model,
                args.plan_seconds,
                args.verbose,
                args.save_responses,
                args.output_dir,
                responses_dict,
                manual_window_region,
                args.debug_pause,
                stop_flag,
                args.log_folder,
                log_file,
                args.screenshot_interval,
                args.save_all_states,
                args.enhanced_logging,
                args.execution_mode,
                args.piece_limit,
                args.manual_mode  # 添加manual_mode参数
            )
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)
    
    # 等待所有线程完成
    try:
        # 循环检查所有线程是否完成
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            
            # 如果停止标志被设置，尝试优雅地停止线程
            if stop_flag.is_set():
                print("\nStop flag detected, waiting for threads to complete...")
                
                # 给线程一些时间优雅地关闭
                for _ in range(10):  # 最多等待5秒
                    if not any(t.is_alive() for t in threads):
                        break
                    time.sleep(0.5)
                
                # 如果线程仍在运行，尝试强制终止
                if any(t.is_alive() for t in threads):
                    print("Some threads are still running. They will be terminated when the main thread exits.")
                
                # 确保游戏进程被停止
                if not args.no_launch_game:
                    stop_tetris_game()
                
                break
        
        # 如果没有停止标志但所有线程都结束，优雅地退出
        if not stop_flag.is_set() and not any(t.is_alive() for t in threads):
            print("\nAll threads completed.")
            
            # 确保所有监视线程都结束
            for monitor_thread in [keyboard_thread]:
                if monitor_thread.is_alive():
                    stop_flag.set()
                    monitor_thread.join(timeout=5)
    
    except KeyboardInterrupt:
        print("\nInterrupted by user, stopping all threads...")
        stop_flag.set()
        # 确保游戏进程被停止
        stop_tetris_game()
    
    # 如果不是自动启动的游戏，提示用户
    if args.no_launch_game:
        print("Using --no_launch_game, not searching for other Tetris processes")
    else:
        # 停止Tetris游戏
        stop_tetris_game()
    
    print("Main thread exiting...")

if __name__ == "__main__":
    main()