import time
import os
import numpy as np
import concurrent.futures
import argparse
import json
import threading
import sys
import signal
from datetime import datetime

try:
    import keyboard  # 尝试导入keyboard库
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("Warning: keyboard library not available. Using fallback method.")

from games.tetris.workers import worker_tetris

# 创建一个全局变量，作为停止标志
STOP_ALL_THREADS = threading.Event()  # 使用Event代替简单的布尔值

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
    
    # 初始化手动窗口区域变量
    manual_window_region = None
    # 如果用户手动指定了窗口位置，显示相关信息
    if args.manual_window:
        manual_window_region = (args.window_left, args.window_top, args.window_width, args.window_height)
        print(f"Using manually specified window region: {manual_window_region}")

    # Create a shared response dictionary for all threads
    responses = {
        "start_time": datetime.now().isoformat(),
        "threads": {}
    }
    
    # 启动键盘监听
    key_listener()
    print("Keyboard listener started. Press 'q' to stop all threads.")

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

if __name__ == "__main__":
    main()