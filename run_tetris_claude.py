"""
Tetris Runner Script with Claude 3.7 Sonnet

This script makes it easy to run the Tetris agent with Anthropic's Claude 3.7 Sonnet model,
which provides high-quality responses and excellent reasoning capabilities for gameplay.
"""

import sys
import argparse
import subprocess
import os

def main():
    parser = argparse.ArgumentParser(description='Run Tetris with Claude 3.7 Sonnet')
    parser.add_argument('--cooldown', type=float, default=0.0, 
                        help='API cooldown in seconds (default: 0 - no cooldown)')
    
    args = parser.parse_args()
    
    # Construct command
    cmd = [
        "python", "-m", "games.tetris.tetris_agent",
        "--provider", "anthropic",
        "--model", "claude-3-7-sonnet-20250219",
        "--cooldown", str(args.cooldown)
    ]
    
    print(f"Starting Tetris with Claude 3.7 Sonnet (cooldown: {args.cooldown}s)")
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