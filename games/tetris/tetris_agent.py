import time
import traceback
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
import win32gui

# Set up logging configuration
def setup_logging():
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Create a timestamped log file name
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"tetris_agent_{timestamp}.log")
    
    # Configure logging with UTF-8 encoding to handle all characters
    handlers = [
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # Console handler
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )
    
    # Get the logger for this module
    logger = logging.getLogger("TetrisAgent")
    logger.info(f"Logging initialized - writing to {log_file}")
    
    return logger

# Set up logging
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
    
    # Ensure highscore.txt exists
    highscore_path = os.path.join(game_dir, 'highscore.txt')
    os.makedirs(game_dir, exist_ok=True)
    logger.debug(f"Highscore path: {highscore_path}")
    
    if not os.path.exists(highscore_path):
        with open(highscore_path, 'w') as f:
            f.write('0\n')
    
    # Check that the custom font is available
    font_dir = os.path.join(game_dir, "font")
    os.makedirs(font_dir, exist_ok=True)
    
    # Font files to check - ensure we have at least comicsans.ttf
    required_fonts = ["comicsans.ttf"]
    font_paths = {}
    
    for font in required_fonts:
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
                font_paths[font] = font_path
            else:
                logger.warning(f"Could not find font file: {font}")
                # Use system font as fallback
                font_paths[font] = None
        else:
            font_paths[font] = font_path
    
    return highscore_path, font_paths

def run_game():
    global game_running, game_state
    import pygame
    
    try:
        # Initialize pygame properly
        pygame.init()  # Ensure pygame is fully initialized
        logger.info("Initializing game...")
        
        # Get paths
        highscore_path, font_paths = ensure_game_files()
        logger.debug(f"Font paths: {font_paths}")
        
        # Set paths in Tetris module
        from games.tetris.game import Tetris
        Tetris.filepath = highscore_path
        
        # Set the fontpath in Tetris module
        custom_font = font_paths.get("comicsans.ttf")
        if custom_font and os.path.exists(custom_font):
            Tetris.fontpath = custom_font
            logger.info(f"Using custom font at {Tetris.fontpath}")
        else:
            # Let the safe_font function handle fallbacks
            Tetris.fontpath = None
            logger.info("Using system font as fallback")
            
        # Create the window after proper initialization
        win = pygame.display.set_mode((800, 750))
        pygame.display.set_caption('Tetris')  # Important: This title must match what we use in the screenshot capture
        
        # Explicitly show the window and make sure it's visible
        pygame.display.update()
        pygame.time.delay(500)  # Give the window some time to become visible
        logger.info("Game window opened, starting main game loop...")
        
        # Start the main game directly (not through tetris_main)
        try:
            # Call main_menu to show the start screen and then enter the main game
            Tetris.main_menu(win)
            
            # If main_menu returns (i.e., doesn't start the game)
            # we can call main directly as a fallback
            logger.info("Main menu exited without starting game. Starting game directly...")
            Tetris.main(win)
            
        except Exception as e:
            logger.error(f"Game crashed: {str(e)}")
            logger.error(traceback.format_exc())
            game_running = False
    
    except Exception as e:
        logger.error(f"Error initializing game: {str(e)}")
        logger.error(traceback.format_exc())
        game_running = False
    finally:
        logger.info("Game loop ended")
        # Clean up
        try:
            pygame.quit()
        except:
            pass

def main():
    global game_running
    
    # Start the game thread first
    game_thread = threading.Thread(target=run_game)
    game_thread.daemon = True
    game_thread.start()
    
    # Wait for game window to initialize
    logger.info("Waiting for game window to initialize...")
    time.sleep(3)  # Increased wait time to ensure pygame initializes
    
    if not game_running:
        logger.error("Game failed to initialize. Exiting...")
        return
    
    # Make sure window is created before proceeding
    attempts = 0
    while attempts < 10:  # Try for up to 10 seconds
        logger.info("Checking for Tetris window...")
        hwnd = win32gui.FindWindow(None, 'Tetris')
        if hwnd != 0:
            logger.info(f"Tetris window found! Window handle: {hwnd}")
            break
        time.sleep(1)
        attempts += 1
    
    if attempts >= 10:
        logger.error("Could not find Tetris window after multiple attempts. Workers may not be able to capture screenshots.")
    
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