"""
Tetris Runner Script with Gemini 1.5 Flash

This script makes it easy to run the Tetris agent with Google's Gemini 1.5 Flash model,
which provides extremely fast responses and is optimized for real-time gameplay.
"""

import sys
import argparse
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description='Run Tetris with Gemini 1.5 Flash')
    parser.add_argument('--cooldown', type=float, default=0.0, 
                        help='API cooldown in seconds (default: 0 - no cooldown)')
    
    args = parser.parse_args()
    
    # Construct command
    cmd = [
        "python", "-m", "games.tetris.tetris_agent",
        "--provider", "gemini",
        "--model", "gemini-1.5-flash",
        "--cooldown", str(args.cooldown)
    ]
    
    print(f"Starting Tetris with Gemini 1.5 Flash (cooldown: {args.cooldown}s)")
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