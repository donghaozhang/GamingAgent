import time
import numpy as np
import concurrent.futures
import argparse
import threading
import os
import logging
import datetime
import sys
from dotenv import load_dotenv
from queue import Queue, Empty
import pygame
from pygame.locals import KEYDOWN, K_LEFT, K_RIGHT, K_UP, K_DOWN, K_q

# Set up logging configuration
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a timestamped log file name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"tetris_agent_{timestamp}.log")
    
    # Configure the root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # File handler that writes to the log file
            logging.FileHandler(log_file, mode='w'),
            # Console handler that prints to stdout
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger("TetrisAgent")
    logger.info(f"Logging initialized - writing to {log_file}")
    return logger

# Initialize logger
logger = setup_logging()

# 加载 .env 文件
load_dotenv()

# Define system prompt as constant
SYSTEM_PROMPT = (
    "You are an expert AI agent specialized in playing Tetris gameplay, search for and execute optimal moves given each game state. Prioritize line clearing over speed."
)

# Update import path to use the game module
from games.tetris.game.Tetris import main as tetris_main
# Import worker_tetris later to avoid circular imports
# from .workers import worker_tetris

# Global variables declaration
game_running = True
game_state = Queue()

def ensure_highscore():
    # Get absolute path for highscore.txt
    highscore_path = os.path.join(os.path.dirname(__file__), 'game', 'highscore.txt')
    os.makedirs(os.path.dirname(highscore_path), exist_ok=True)
    if not os.path.exists(highscore_path):
        with open(highscore_path, 'w') as f:
            f.write('0\n')
    return highscore_path  # Return the path

def ensure_game_files():
    # Get the absolute path for the game directory
    game_dir = os.path.join(os.path.dirname(__file__), "game")
    logger.debug(f"Game directory: {game_dir}")
    
    # Ensure highscore file exists
    highscore_path = os.path.join(game_dir, 'highscore.txt')
    os.makedirs(game_dir, exist_ok=True)
    logger.debug(f"Highscore path: {highscore_path}")
    
    if not os.path.exists(highscore_path):
        with open(highscore_path, 'w') as f:
            f.write('0\n')
    
    # Check that the custom font is available
    font_dir = os.path.join(game_dir, "font")
    os.makedirs(font_dir, exist_ok=True)
    
    # Font files to check
    fonts = ["comicsans.ttf"]
    
    for font in fonts:
        font_path = os.path.join(font_dir, font)
        logger.debug(f"Checking font file: {font_path}")
        
        if not os.path.exists(font_path):
            logger.debug(f"Font file missing: {font}")
            # Try to copy from the tools directory
            src_path = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "assets", "fonts", font)
            logger.debug(f"Trying to copy from: {src_path}")
            
            if os.path.exists(src_path):
                import shutil
                shutil.copy(src_path, font_path)
                logger.debug(f"Successfully copied font file: {font}")
            else:
                logger.warning(f"Could not find font file: {font}")
    
    return highscore_path, font_dir

def run_game():
    global game_running, game_state  # 在函数开始处声明全局变量
    import pygame
    
    try:
        # Initialize pygame properly
        pygame.init()  # Ensure pygame is fully initialized
        logger.info("Initializing game...")
        
        # Get paths
        highscore_path, font_dir = ensure_game_files()
        logger.debug(f"Font paths: {font_dir}")
        
        # Set paths in Tetris module
        from .game import Tetris
        Tetris.filepath = highscore_path
        Tetris.fontpath = os.path.join(font_dir, "comicsans.ttf")
        
        # Create the window after proper initialization
        win = pygame.display.set_mode((800, 750))
        pygame.display.set_caption('Tetris')  # Important: This title must match what we use in the screenshot capture
        
        # 修改游戏主循环，降低速度
        clock = pygame.time.Clock()
        last_update = time.time()
        update_interval = 1.0  # 增加状态更新间隔到1秒
        last_debug_time = time.time()
        debug_interval = 5  # 每5秒输出一次调试信息
        
        while game_running:
            # Process events first to prevent event queue overflow
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    logger.info("Window closed. Terminating game.")
                    game_running = False
                    break
                
                # Add direct Q key handling here to catch it early
                if event.type == KEYDOWN and event.key == K_q:
                    logger.info("Q key detected in main event loop. Terminating game.")
                    game_running = False
                    # Force termination - this is more reliable
                    pygame.quit()
                    return
                    
            if not game_running:
                break
                
            clock.tick(30)  # 限制帧率为30fps
            
            current_time = time.time()
            if current_time - last_update >= update_interval:
                # Pass a reference to the game state queue directly to the game
                current_state = tetris_main(win)
                
                # Check if we got the QUIT signal from the Q key
                if current_state == "QUIT":
                    logger.info("Received QUIT signal from game (Q key pressed), terminating all processes...")
                    game_running = False
                    pygame.quit()
                    # Exit the function immediately for more reliable termination
                    return
                
                # Debug print to verify what we're getting back from tetris_main
                if current_state:
                    logger.debug(f"Got game state: {current_state}")
                    if current_time - last_debug_time >= debug_interval:
                        last_debug_time = current_time
                    # Put the game state in the queue for the worker to analyze
                    # This was intended for the worker to analyze the state, not for control
                    game_state.put(current_state)
                last_update = current_time
            
            # 处理 AI 控制事件
            try:
                action = game_state.get_nowait()  # 非阻塞获取
                if action:
                    logger.info(f"Executing AI action: {action}")
                    # Ensure action is one of the valid key constants
                    if action in [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN]:
                        # Instead of posting an event, we'll simulate a key press directly
                        # Using both methods for redundancy
                        
                        # Method 1: Post event with correct attributes
                        key_event = pygame.event.Event(KEYDOWN, key=action, mod=0)
                        pygame.event.post(key_event)
                        
                        # Method 2: Modify key state directly (more reliable in some cases)
                        keys = pygame.key.get_pressed()
                        
                        # Since we can't modify the tuple directly, we'll create a new event
                        # that simulates a key press in the next frame
                        if action == pygame.K_LEFT:
                            logger.debug("Sending direct LEFT key press")
                            pygame.event.post(pygame.event.Event(KEYDOWN, key=pygame.K_LEFT))
                        elif action == pygame.K_RIGHT:
                            logger.debug("Sending direct RIGHT key press")
                            pygame.event.post(pygame.event.Event(KEYDOWN, key=pygame.K_RIGHT))
                        elif action == pygame.K_UP:
                            logger.debug("Sending direct UP key press")
                            pygame.event.post(pygame.event.Event(KEYDOWN, key=pygame.K_UP))
                        elif action == pygame.K_DOWN:
                            logger.debug("Sending direct DOWN key press")
                            pygame.event.post(pygame.event.Event(KEYDOWN, key=pygame.K_DOWN))
                    else:
                        logger.warning(f"Invalid key constant received: {action}")
            except Empty:  # 使用正确的 Empty 异常
                pass  # 队列为空时继续
    
    except Exception as e:
        logger.error(f"Game crashed: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # Proper cleanup of pygame
        game_running = False
        try:
            pygame.quit()
        except:
            pass  # Already quit or not initialized

def main():
    global game_running
    
    # 启动游戏线程
    game_thread = threading.Thread(target=run_game)
    game_thread.daemon = True  # 设置为守护线程，这样主程序退出时游戏也会退出
    game_thread.start()
    
    # 等待游戏窗口初始化
    logger.info("Waiting for game window to initialize...")
    time.sleep(3)  # 增加等待时间以确保pygame完全初始化
    
    if not game_running:
        logger.error("Game failed to initialize. Exiting...")
        return
    
    logger.info("Game initialized successfully, starting AI workers...")
    
    # Import worker_tetris here to avoid circular imports
    from games.tetris.workers import worker_tetris
    
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

    logger.info(f"Starting with {num_threads} threads using policy '{args.policy}'...")
    logger.info(f"API Provider: {args.api_provider}, Model Name: {args.model_name}")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for i in range(num_threads):
                if args.policy == "fixed":
                    futures.append(executor.submit(
                        worker_tetris, i, offsets[i], SYSTEM_PROMPT,
                        args.api_provider, args.model_name, args.control_time
                    ))
                else:
                    raise NotImplementedError(f"policy: {args.policy} not implemented.")

            try:
                # Monitor the game thread
                while game_running and game_thread.is_alive():
                    time.sleep(0.25)
                    
                    # Add keyboard listener for direct Q key termination
                    check_for_quit()  # Check for Q key periodically
                
                if not game_thread.is_alive():
                    logger.info("Game thread has stopped. Shutting down AI workers...")
                    game_running = False
                    
            except KeyboardInterrupt:
                logger.info("\nMain thread interrupted. Exiting all threads...")
                game_running = False

    finally:
        # Ensure we set game_running to False on exit
        game_running = False
        
        # Wait a moment for threads to clean up
        time.sleep(1)
        logger.info("Exiting main program.")

def check_for_quit():
    try:
        import keyboard
        if keyboard.is_pressed('q'):
            logger.info("Q key pressed - force quit")
            pygame.quit()
            os._exit(0)
    except ImportError:
        # Keyboard module not available
        pass

if __name__ == "__main__":
    main()