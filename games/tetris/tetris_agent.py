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
import pyautogui
import keyboard

# Set up logging configuration
def setup_logging():
    try:
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Create a timestamped log file name
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"tetris_agent_{timestamp}.log")
        
        # Make sure we have write permissions to the log directory
        test_file = os.path.join(log_dir, "test_write.tmp")
        try:
            with open(test_file, 'w') as f:
                f.write("Test write permission")
            os.remove(test_file)
        except Exception as e:
            print(f"WARNING: Cannot write to log directory: {str(e)}")
            # Fall back to a different location, like the user's temp directory
            import tempfile
            log_dir = tempfile.gettempdir()
            log_file = os.path.join(log_dir, f"tetris_agent_{timestamp}.log")
            print(f"Using alternative log location: {log_file}")
        
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
        
        # Verify that log file is created
        if os.path.exists(log_file):
            logger.info("Log file created successfully")
        else:
            logger.warning(f"Log file not created at {log_file}")
        
        return logger
    except Exception as e:
        # If all else fails, set up a basic console logger
        print(f"Failed to set up file logging: {str(e)}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logger = logging.getLogger("TetrisAgent")
        logger.warning(f"Using console-only logging due to error: {str(e)}")
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
    import time
    
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
            logger.warning(f"Could not find font file: comicsans.ttf")
            logger.info("Using system font as fallback")
            
        # Create the window after proper initialization
        win = pygame.display.set_mode((800, 750))
        pygame.display.set_caption('Tetris')  # Important: This title must match what we use in the screenshot capture
        
        # Explicitly show the window and make sure it's visible
        pygame.display.update()
        pygame.time.delay(1000)  # Give the window a full second to become visible
        logger.info("Game window opened, starting main game loop...")
        
        # Set game_running to True to indicate the game is active
        game_running = True
        
        # Start the main game directly
        try:
            # Skip main_menu and directly start the game
            result = Tetris.main(win)
            
            # Check if the game was quit using the Q key
            if result == "QUIT":
                logger.info("User quit the game with Q key")
                game_running = False
            else:
                logger.info(f"Game completed with result: {result}")
                
                # After the game ends, keep the window open for a bit to allow AI to capture final state
                logger.info("Game finished. Keeping window open for a moment...")
                pygame.display.update()
                
                # Keep the window open until Q is pressed to quit
                quit_wait = True
                while quit_wait and game_running:
                    for event in pygame.event.get():
                        if event.type == pygame.QUIT:
                            quit_wait = False
                        elif event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_q:
                                logger.info("Q key pressed after game end")
                                quit_wait = False
                    
                    # Also check for system-level Q key press
                    try:
                        if keyboard.is_pressed('q'):
                            logger.info("System-level Q key detected after game end")
                            quit_wait = False
                    except:
                        pass
                    
                    # Update display and prevent CPU hogging
                    win.fill((0, 0, 0))
                    font = Tetris.safe_font(60)
                    label = font.render('Game Over! Press Q to quit', 1, (255, 255, 255))
                    win.blit(label, (Tetris.top_left_x + Tetris.play_width/2 - (label.get_width()/2), 
                                   Tetris.top_left_y + Tetris.play_height/2 - label.get_height()/2))
                    pygame.display.update()
                    pygame.time.delay(100)  # Small delay to prevent CPU hogging
                    
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
        # Set game_running to False to signal worker threads to exit
        game_running = False
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
    window_found = False
    tetris_window_name = 'Tetris'
    
    while attempts < 10:  # Try for up to 10 seconds
        logger.info("Checking for Tetris window...")
        hwnd = win32gui.FindWindow(None, tetris_window_name)
        if hwnd != 0:
            logger.info(f"Tetris window found! Window handle: {hwnd}")
            window_found = True
            break
        time.sleep(1)
        attempts += 1
    
    if not window_found:
        logger.warning("Could not find Tetris window after multiple attempts. Using region capture as fallback.")
    
    logger.info("Game initialized successfully, starting AI workers...")
    
    # Import worker_tetris here to avoid circular imports
    from games.tetris.workers import worker_tetris
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Tetris gameplay agent with configurable concurrent workers."
    )
    parser.add_argument("--workers", type=int, default=1, help="Number of concurrent workers")
    parser.add_argument("--model", type=str, default="claude-3-7-sonnet-20250219", help="Model name to use")
    parser.add_argument("--provider", type=str, default="anthropic", help="API provider (anthropic, openai, or gemini)")
    parser.add_argument("--playback", action="store_true", help="Run in playback mode (no AI calls)")
    args = parser.parse_args()
    
    # Define a fallback screen region in case window capture fails
    # This captures the center of the screen where Tetris is likely to be
    screen_width, screen_height = pyautogui.size()
    window_width = 800
    window_height = 750
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    region = (x, y, window_width, window_height)
    
    # System prompt for the AI
    system_prompt = "You are an expert Tetris player. Analyze the game state and determine the optimal next move."
    
    # Create a simple mock model provider if the real modules aren't available
    class MockProvider:
        def __init__(self, model=None):
            self.model = model
            logger.info(f"Created Mock Provider with model {model}")
        
        def get_response(self, prompt):
            logger.info("Mock provider generating random response")
            import random
            responses = [
                "I'll use pygame.K_LEFT to move the piece left.",
                "I'll use pygame.K_RIGHT to move the piece right.",
                "I'll use pygame.K_UP to rotate the piece.",
                "I'll use pygame.K_DOWN to move the piece down faster."
            ]
            return random.choice(responses)

    # Create model provider object based on command line args
    model_provider = None
    if not args.playback:
        try:
            if args.provider.lower() == "anthropic":
                try:
                    from model_providers.anthropic_provider import AnthropicProvider
                    model_provider = AnthropicProvider(model=args.model)
                except ImportError:
                    logger.warning("Could not import AnthropicProvider, using mock provider instead")
                    model_provider = MockProvider(model=args.model)
                logger.info(f"Created Anthropic provider with model {args.model}")
            elif args.provider.lower() == "openai":
                try:
                    from model_providers.openai_provider import OpenAIProvider
                    model_provider = OpenAIProvider(model=args.model)
                except ImportError:
                    logger.warning("Could not import OpenAIProvider, using mock provider instead")
                    model_provider = MockProvider(model=args.model)
                logger.info(f"Created OpenAI provider with model {args.model}")
            elif args.provider.lower() == "gemini":
                try:
                    from model_providers.gemini_provider import GeminiProvider
                    model_provider = GeminiProvider(model=args.model)
                except ImportError:
                    logger.warning("Could not import GeminiProvider, using mock provider instead")
                    model_provider = MockProvider(model=args.model)
                logger.info(f"Created Gemini provider with model {args.model}")
            else:
                logger.warning(f"Unknown provider {args.provider}. Using mock provider.")
                model_provider = MockProvider(model=args.model)
        except Exception as e:
            logger.error(f"Error creating model provider: {e}")
            logger.error(traceback.format_exc())
            logger.warning("Running in playback mode due to provider initialization error")
    else:
        logger.info("Running in playback mode (no AI calls)")
    
    # Start worker threads
    workers = []
    stop_events = []
    result_queues = []
    
    for i in range(args.workers):
        # Create a result queue and stop event for this worker
        result_queue = Queue()
        stop_event = threading.Event()
        result_queues.append(result_queue)
        stop_events.append(stop_event)
        
        worker = threading.Thread(
            target=worker_tetris,
            args=(result_queue, stop_event, i, model_provider, system_prompt, args.playback)
        )
        worker.daemon = True
        worker.start()
        workers.append(worker)
        logger.info(f"Started worker {i} with {args.provider} {args.model}")
        
    # Monitor for Q key press to terminate
    try:
        while game_running:
            time.sleep(0.1)
            try:
                if keyboard.is_pressed('q'):
                    logger.info("Q key pressed - terminating all threads")
                    game_running = False
                    # Signal any running pygame instances to quit
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
                    break
            except Exception as e:
                # More detailed logging for keyboard issues
                logger.debug(f"Error checking keyboard: {str(e)}")
                pass  # Keyboard module might not be available
    except KeyboardInterrupt:
        logger.info("Interrupted by user. Shutting down...")
    finally:
        game_running = False
        # Try to force quit pygame
        try:
            pygame.quit()
        except:
            pass
            
        logger.info("Waiting for worker threads to exit...")
        # Signal all workers to stop
        for stop_event in stop_events:
            stop_event.set()
        
        for worker in workers:
            worker.join(timeout=1.0)
        logger.info("All workers terminated. Exiting.")

if __name__ == "__main__":
    main()