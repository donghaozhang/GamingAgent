#!/usr/bin/env python
"""
Tetris Agent Runner Script

This script runs the Tetris agent from the correct directory structure,
ensuring that all imports work properly.
"""

import os
import sys
import subprocess
import argparse

def main():
    """Run the Tetris agent with the given parameters."""
    parser = argparse.ArgumentParser(description="Run the Tetris AI agent")
    parser.add_argument("--provider", default="anthropic", help="AI provider to use (anthropic, openai, gemini)")
    parser.add_argument("--model", default="claude-3-7-sonnet-20250219", help="Model name to use")
    parser.add_argument("--cooldown", type=float, default=10.0, help="API cooldown in seconds")
    parser.add_argument("--playback", action="store_true", help="Run in playback mode (no API calls)")
    args = parser.parse_args()
    
    # Set the current directory to the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Add the current directory to the Python path
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    try:
        # Import the tetris_agent module directly
        from games.tetris import tetris_agent
        
        # Set API cooldown if specified
        if hasattr(tetris_agent, 'API_COOLDOWN_SECONDS'):
            tetris_agent.API_COOLDOWN_SECONDS = args.cooldown
        
        # Run the agent
        print(f"Starting Tetris agent with {args.provider} {args.model} (cooldown: {args.cooldown}s)")
        tetris_agent.main(args=[
            "--provider", args.provider,
            "--model", args.model,
            "--playback" if args.playback else "",
        ])
    except ImportError as e:
        print(f"Error importing tetris_agent module: {e}")
        print("Falling back to subprocess method...")
        
        # Fall back to subprocess method
        cmd = [sys.executable, "-m", "games.tetris.tetris_agent", 
               "--provider", args.provider, 
               "--model", args.model]
        
        if args.playback:
            cmd.append("--playback")
            
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd)

if __name__ == "__main__":
    main() 