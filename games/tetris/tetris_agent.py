import time
import numpy as np
import concurrent.futures
import argparse
import threading
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# Define system prompt as constant
SYSTEM_PROMPT = (
    "You are an expert AI agent specialized in playing Tetris gameplay, search for and execute optimal moves given each game state. Prioritize line clearing over speed."
)

# Update import path to use the game module
from .game.Tetris import main as tetris_main
from .workers import worker_tetris

def ensure_highscore():
    # Get absolute path for highscore.txt
    highscore_path = os.path.join(os.path.dirname(__file__), 'game', 'highscore.txt')
    os.makedirs(os.path.dirname(highscore_path), exist_ok=True)
    if not os.path.exists(highscore_path):
        with open(highscore_path, 'w') as f:
            f.write('0\n')
    return highscore_path  # Return the path

def ensure_game_files():
    game_dir = os.path.join(os.path.dirname(__file__), 'game')
    print(f"[DEBUG] Game directory: {game_dir}")
    
    # Ensure highscore file exists
    highscore_path = os.path.join(game_dir, 'highscore.txt')
    os.makedirs(game_dir, exist_ok=True)
    print(f"[DEBUG] Highscore path: {highscore_path}")
    
    if not os.path.exists(highscore_path):
        with open(highscore_path, 'w') as f:
            f.write('0\n')
    
    # Handle font files
    font_files = ['arcade.TTF', 'mario.ttf']
    font_paths = {}
    
    for font in font_files:
        font_path = os.path.join(game_dir, font)
        print(f"[DEBUG] Checking font file: {font_path}")
        
        if not os.path.exists(font_path):
            print(f"[DEBUG] Font file missing: {font}")
            # Try to copy from tetris-pygame directory
            src_path = os.path.join(os.path.dirname(__file__), '..', '..', 'tetris-pygame', font)
            print(f"[DEBUG] Trying to copy from: {src_path}")
            
            if os.path.exists(src_path):
                import shutil
                shutil.copy2(src_path, font_path)
                print(f"[DEBUG] Successfully copied font file: {font}")
            else:
                print(f"[WARNING] Could not find font file: {font}")
                # Set default system font as fallback
                font_path = None
        
        font_paths[font] = font_path
    
    return highscore_path, font_paths

def run_game():
    import pygame
    print("[DEBUG] Initializing game...")
    
    # Get paths
    highscore_path, font_paths = ensure_game_files()
    print(f"[DEBUG] Font paths: {font_paths}")
    
    # Set paths in Tetris module
    from .game import Tetris
    Tetris.filepath = highscore_path
    Tetris.fontpath = font_paths['arcade.TTF']
    Tetris.fontpath_mario = font_paths['mario.ttf']
    
    # Print current working directory
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    print(f"[DEBUG] Game module location: {os.path.abspath(Tetris.__file__)}")
    
    win = pygame.display.set_mode((800, 750))
    pygame.display.set_caption('Tetris')
    
    try:
        tetris_main(win)
    except Exception as e:
        print(f"[ERROR] Game crashed: {str(e)}")
        import traceback
        traceback.print_exc()
        # Signal other threads to stop
        global game_running
        game_running = False
def main():
    # 启动游戏线程
    game_thread = threading.Thread(target=run_game)
    game_thread.daemon = True  # 设置为守护线程，这样主程序退出时游戏也会退出
    game_thread.start()
    
    # 等待游戏窗口初始化
    time.sleep(2)
    
    # 原有的 AI 代理代码
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
                        help=" orker control time.")
    parser.add_argument("--policy", type=str, default="fixed", 
                        choices=["fixed"],
                        help="Worker policy")

    args = parser.parse_args()

    worker_span = args.control_time + args.concurrency_interval
    num_threads = int(args.api_response_latency_estimate // worker_span)
    
    if args.api_response_latency_estimate % worker_span != 0:
        num_threads += 1
    
    # Create an offset list
    offsets = [i * (args.control_time + args.concurrency_interval) for i in range(num_threads)]

    print(f"Starting with {num_threads} threads using policy '{args.policy}'...")
    print(f"API Provider: {args.api_provider}, Model Name: {args.model_name}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        for i in range(num_threads):
            if args.policy == "fixed":
                executor.submit(
                    worker_tetris, i, offsets[i], SYSTEM_PROMPT,  # Use SYSTEM_PROMPT instead of system_prompt
                    args.api_provider, args.model_name, args.control_time
                )
            else:
                raise NotImplementedError(f"policy: {args.policy} not implemented.")

        try:
            while True:
                time.sleep(0.25)
        except KeyboardInterrupt:
            print("\nMain thread interrupted. Exiting all threads...")

if __name__ == "__main__":
    main()