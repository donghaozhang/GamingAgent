"""
Tetris Runner Script with Claude 3.7 Sonnet (thinking variant) via OpenRouter

This script makes it easy to run the Tetris agent with Claude 3.7 Sonnet (thinking variant) 
via OpenRouter, which provides high-quality responses with enhanced reasoning capabilities.
"""

import sys
import argparse
import subprocess
import os
from dotenv import load_dotenv
import pathlib

# Check if running in the game_cua conda environment
conda_env = os.environ.get("CONDA_DEFAULT_ENV")
if conda_env != "game_cua":
    print(f"WARNING: You are not running in the 'game_cua' conda environment. Current environment: {conda_env or 'None'}")
    print("This script requires dependencies installed in the 'game_cua' environment.")
    print("\nTo activate the correct environment:")
    print("  conda activate game_cua")
    print("Then run this script again.")
    sys.exit(1)

# Get the absolute path to the .env file
env_path = pathlib.Path(__file__).parent / '.env'
print(f"Looking for .env file at: {env_path}")

# Load environment variables from .env file with verbose output
load_dotenv(dotenv_path=env_path, verbose=True)

# Debug: Print the value (safely) to verify it was loaded
api_key = os.getenv("OPENROUTER_API_KEY")
if api_key:
    print(f"OpenRouter API key found: {api_key[:5]}...{api_key[-5:]}")
else:
    print("OpenRouter API key not found after loading .env")

def main():
    parser = argparse.ArgumentParser(description='Run Tetris with Claude 3.7 (thinking) via OpenRouter')
    parser.add_argument('--cooldown', type=float, default=0.0, 
                        help='API cooldown in seconds (default: 0 - no cooldown)')
    parser.add_argument('--model', type=str, default="anthropic/claude-3-7-sonnet:thinking",
                        help='Model to use from OpenRouter (default: anthropic/claude-3-7-sonnet:thinking)')
    
    args = parser.parse_args()
    
    # Check for OpenRouter API key
    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY environment variable is not set.")
        print("Please set your OpenRouter API key with:")
        print("  export OPENROUTER_API_KEY=your_api_key_here")
        sys.exit(1)
    
    # Construct command
    cmd = [
        "python", "-m", "games.tetris.tetris_agent",
        "--provider", "openrouter",
        "--model", args.model,
        "--cooldown", str(args.cooldown)
    ]
    
    print(f"Starting Tetris with {args.model} via OpenRouter (cooldown: {args.cooldown}s)")
    print("Press Ctrl+C to stop the game")
    
    try:
        # Set Python path to include the current directory
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd() + os.pathsep + env.get('PYTHONPATH', '')
        
        # Run the command
        subprocess.run(cmd, env=env)
    except KeyboardInterrupt:
        print("\nGame stopped by user")
    except Exception as e:
        print(f"Error running Tetris: {e}")

if __name__ == "__main__":
    main() 