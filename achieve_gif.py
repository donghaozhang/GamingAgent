#!/usr/bin/env python
"""
Achieve GIF - Simple Tetris Animation Creator

A streamlined tool to create GIF animations from Tetris screenshots.
This is a simplified version of create_tetris_animation.py focusing on quick GIF creation.

Usage:
    python achieve_gif.py [SESSION_DIR] [OUTPUT_PATH] [--fps FPS]

If SESSION_DIR is not provided, it will scan for the latest session directory.
If OUTPUT_PATH is not provided, it will create a GIF in the session's animations folder.
"""

import os
import sys
import glob
import argparse
import time
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import re

def find_latest_session(base_dir="game_logs"):
    """Find the most recent session directory"""
    if not os.path.exists(base_dir):
        print(f"Error: Base directory '{base_dir}' not found")
        return None
        
    session_dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("session_")]
    
    if not session_dirs:
        print(f"No session directories found in '{base_dir}'")
        return None
        
    # Sort by creation time (most recent first)
    session_dirs.sort(key=lambda x: os.path.getctime(os.path.join(base_dir, x)), reverse=True)
    
    return os.path.join(base_dir, session_dirs[0])

def collect_screenshots(session_dir):
    """Find all screenshot images in the session directory"""
    screenshots_dir = os.path.join(session_dir, "screenshots")
    
    if not os.path.exists(screenshots_dir):
        # Check if screenshots are in the session dir itself
        if any(f.endswith('.png') for f in os.listdir(session_dir)):
            screenshots_dir = session_dir
        else:
            print(f"No screenshots found in {session_dir}")
            return []
    
    # Get all PNG files
    image_paths = glob.glob(os.path.join(screenshots_dir, "*.png"))
    
    if not image_paths:
        print(f"No PNG screenshots found in {screenshots_dir}")
        return []
    
    # Sort images by iteration number
    def get_iteration_number(path):
        filename = os.path.basename(path)
        # Try different patterns
        iter_match = re.search(r'iter_(\d+)', filename)
        screenshot_match = re.search(r'screenshot_(\d+)', filename)
        exec_match = re.search(r'execution_(\d+)', filename)
        
        if iter_match:
            return int(iter_match.group(1))
        elif screenshot_match:
            return int(screenshot_match.group(1))
        elif exec_match:
            return int(exec_match.group(1))
        else:
            # Fall back to modification time as a last resort
            return float('inf')  # Place at the end
    
    return sorted(image_paths, key=get_iteration_number)

def enhance_frames(image_paths):
    """Add labels and enhance frames for the animation"""
    frames = []
    
    for i, path in enumerate(image_paths):
        try:
            # Open image
            img = Image.open(path)
            
            # Create a copy for drawing
            draw_img = img.copy()
            draw = ImageDraw.Draw(draw_img)
            
            # Determine frame type
            filename = os.path.basename(path)
            if "post_execution" in filename:
                frame_type = "After Move"
            elif "pre_execution" in filename or "screenshot" in filename:
                frame_type = "Before Move"
            elif "simulated_iter" in filename:
                frame_type = "Simulated"
            else:
                frame_type = "Frame"
            
            # Get iteration number if available
            iter_match = re.search(r'(?:iter|screenshot|execution)_(\d+)', filename)
            iter_num = iter_match.group(1) if iter_match else f"{i+1}"
            
            # Add label text
            label = f"Iteration {iter_num}: {frame_type}"
            
            # Try to load a nice font, fall back to default
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Add semi-transparent background for text
            text_width = len(label) * 8
            text_height = 20
            draw.rectangle([(10, 10), (10 + text_width, 10 + text_height)], fill=(0, 0, 0, 128))
            
            # Draw text
            draw.text((15, 12), label, fill=(255, 255, 255), font=font)
            
            # Add to frames list
            frames.append(draw_img)
            
        except Exception as e:
            print(f"Error processing {path}: {e}")
            try:
                # Try to add unmodified image
                frames.append(Image.open(path))
            except:
                pass
    
    return frames

def create_gif(frames, output_path, fps=2):
    """Create a GIF animation from the frames"""
    if not frames:
        print("No frames to create GIF")
        return False
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Calculate duration between frames in milliseconds
    duration = int(1000 / fps)
    
    # Ensure all frames are the same size
    base_size = frames[0].size
    uniform_frames = []
    
    for frame in frames:
        if frame.size != base_size:
            # Resize to match first frame
            frame = frame.resize(base_size, Image.LANCZOS)
        uniform_frames.append(frame)
    
    # Save as GIF
    print(f"Creating GIF with {len(uniform_frames)} frames at {fps} fps...")
    
    try:
        uniform_frames[0].save(
            output_path,
            save_all=True,
            append_images=uniform_frames[1:],
            optimize=True,
            duration=duration,
            loop=0  # Loop forever
        )
        print(f"GIF successfully saved to: {output_path}")
        return True
    except Exception as e:
        print(f"Error creating GIF: {e}")
        return False

def achieve_gif(session_dir=None, output_path=None, fps=2):
    """Main function to create a GIF animation from a session directory"""
    # Find latest session if none provided
    if not session_dir:
        session_dir = find_latest_session()
        if not session_dir:
            print("Error: Could not find a valid session directory")
            return False
    
    print(f"Using session directory: {session_dir}")
    
    # Set default output path if none provided
    if not output_path:
        # Create animations directory in the session folder
        animations_dir = os.path.join(session_dir, "animations")
        os.makedirs(animations_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(animations_dir, f"tetris_animation_{timestamp}.gif")
    
    # Collect screenshots
    image_paths = collect_screenshots(session_dir)
    
    if not image_paths:
        print("No screenshots found to create GIF")
        return False
    
    print(f"Found {len(image_paths)} screenshots")
    
    # Enhance frames with labels
    frames = enhance_frames(image_paths)
    
    # Create GIF
    return create_gif(frames, output_path, fps)

def main():
    parser = argparse.ArgumentParser(description="Create a GIF animation from Tetris screenshots")
    parser.add_argument("session_dir", nargs='?', help="Path to the session directory (optional)")
    parser.add_argument("output_path", nargs='?', help="Path to save the GIF (optional)")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second (default: 2)")
    
    args = parser.parse_args()
    
    achieve_gif(args.session_dir, args.output_path, args.fps)

if __name__ == "__main__":
    main() 