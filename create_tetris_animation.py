#!/usr/bin/env python
"""
Tetris Animation Creator

This script combines Tetris simulation images into an MP4 or GIF animation.
It can use simulated_iter, pre_execution, or post_execution images.

Requirements:
- pillow (for image processing and GIF creation)
- moviepy (optional, for MP4 creation)

Usage examples:
    # Create a GIF with default settings
    python create_tetris_animation.py --session session_20250308_020339 --type gif
    
    # Create an MP4 with custom settings (requires moviepy)
    python create_tetris_animation.py --session session_20250308_020339 --type mp4 --fps 2 --mode post
    
    # Options for mode: 
    # - sim: only simulated_iter images
    # - pre: only pre_execution images
    # - post: only post_execution images
    # - pre-post: alternating pre and post execution images
    # - all: all images in order
"""

import os
import re
import sys
import argparse
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional

# Check for optional dependencies
MOVIEPY_AVAILABLE = False
try:
    from moviepy.editor import ImageSequenceClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    print("Note: MoviePy not found. MP4 output will not be available.")
    print("To enable MP4 output, install MoviePy with:")
    print("pip install moviepy")
    print("Using Pillow for GIF creation only.\n")

# Default values
DEFAULT_FPS = 1  # Frames per second
DEFAULT_MODE = "sim"  # Default to simulated_iter images
DEFAULT_OUTPUT_TYPE = "gif"  # Default to GIF since it doesn't require moviepy
DEFAULT_OUTPUT_FOLDER = "animations"

def sort_by_iteration(filename: str) -> Tuple[int, int]:
    """
    Extract iteration number and timestamp for sorting.
    Returns (iteration number, timestamp) tuple.
    """
    # Extract iteration number
    iter_match = re.search(r'iter_(\d+)', filename)
    exec_match = re.search(r'execution_(\d+)', filename)
    
    if iter_match:
        iter_num = int(iter_match.group(1))
    elif exec_match:
        iter_num = int(exec_match.group(1))
    else:
        iter_num = 0
    
    # Extract timestamp for secondary sorting
    time_match = re.search(r'(\d{8})_(\d{6})', filename)
    if time_match:
        # Convert to an integer for comparison
        timestamp = int(time_match.group(1) + time_match.group(2))
    else:
        timestamp = 0
        
    return (iter_num, timestamp)

def find_images(session_dir: str, mode: str) -> List[str]:
    """
    Find relevant images based on the selected mode.
    
    Args:
        session_dir: Path to the session directory
        mode: Which images to use (sim, pre, post, pre-post, all)
    
    Returns:
        List of image paths sorted by iteration
    """
    screenshots_dir = os.path.join(session_dir, "screenshots")
    if not os.path.exists(screenshots_dir):
        raise FileNotFoundError(f"Screenshots directory not found: {screenshots_dir}")
    
    # Get all PNG files
    all_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
    
    # Filter based on mode
    if mode == "sim":
        files = [f for f in all_files if "simulated_iter" in f]
    elif mode == "pre":
        files = [f for f in all_files if "pre_execution" in f]
    elif mode == "post":
        files = [f for f in all_files if "post_execution" in f]
    elif mode == "pre-post":
        # Get pre and post pairs, sorted by iteration
        pre_files = [f for f in all_files if "pre_execution" in f]
        post_files = [f for f in all_files if "post_execution" in f]
        
        # Sort each list
        pre_files.sort(key=sort_by_iteration)
        post_files.sort(key=sort_by_iteration)
        
        # Create alternating list
        files = []
        for pre, post in zip(pre_files, post_files):
            files.append(pre)
            files.append(post)
    else:  # "all"
        files = all_files
    
    # Sort by iteration number
    files.sort(key=sort_by_iteration)
    
    # Return full paths
    return [os.path.join(screenshots_dir, f) for f in files]

def add_frame_labels(image_paths: List[str], temp_dir: str = None) -> List[str]:
    """
    Add frame number and type labels to each image.
    
    Args:
        image_paths: List of image paths
        temp_dir: Directory to save labeled images (creates one if None)
    
    Returns:
        List of paths to labeled images
    """
    # Create temp directory if needed
    if temp_dir is None:
        temp_dir = os.path.join(os.path.dirname(image_paths[0]), "temp_frames")
    
    os.makedirs(temp_dir, exist_ok=True)
    
    labeled_paths = []
    
    for i, img_path in enumerate(image_paths):
        # Get image type
        if "simulated_iter" in img_path:
            frame_type = "Simulated"
        elif "pre_execution" in img_path:
            frame_type = "Pre-Execution"
        elif "post_execution" in img_path:
            frame_type = "Post-Execution"
        else:
            frame_type = "Frame"
        
        # Extract iteration number
        iter_match = re.search(r'iter_(\d+)', img_path)
        exec_match = re.search(r'execution_(\d+)', img_path)
        
        if iter_match:
            iter_num = iter_match.group(1)
        elif exec_match:
            iter_num = exec_match.group(1)
        else:
            iter_num = str(i+1)
        
        # Open and add label
        img = Image.open(img_path)
        draw = ImageDraw.Draw(img)
        
        # Prepare font
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        # Draw label at the bottom
        label = f"Frame {i+1}: {frame_type} {iter_num}"
        
        # The textsize method was deprecated in Pillow 10.0.0
        # Try the new method first, then fall back to the old one
        try:
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            # Fall back to the old method for older Pillow versions
            text_width, text_height = draw.textsize(label, font=font) if hasattr(draw, 'textsize') else (150, 20)
        
        draw.rectangle(
            [(0, img.height - text_height - 10), (text_width + 10, img.height)],
            fill=(0, 0, 0, 180)
        )
        draw.text((5, img.height - text_height - 5), label, fill=(255, 255, 255), font=font)
        
        # Save labeled image
        output_path = os.path.join(temp_dir, f"frame_{i:03d}.png")
        img.save(output_path)
        labeled_paths.append(output_path)
    
    return labeled_paths

def create_gif_with_pillow(image_paths: List[str], output_path: str, fps: int = DEFAULT_FPS):
    """
    Create a GIF animation using Pillow.
    
    Args:
        image_paths: List of paths to frames
        output_path: Path to save the GIF
        fps: Frames per second
    """
    print(f"Creating GIF animation with Pillow ({len(image_paths)} frames)...")
    
    # Open all images
    images = [Image.open(img_path) for img_path in image_paths]
    
    # Calculate duration in milliseconds
    duration = int(1000 / fps)
    
    # Save as animated GIF
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        optimize=False,
        duration=duration,
        loop=0  # Loop forever
    )
    
    # Close all images
    for img in images:
        img.close()

def create_animation(image_paths: List[str], output_path: str, fps: int = DEFAULT_FPS):
    """
    Create an animation (MP4 or GIF) from the images.
    
    Args:
        image_paths: List of image paths
        output_path: Path to save the animation
        fps: Frames per second
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Check if we have images
    if not image_paths:
        print("No images found!")
        return
    
    print(f"Creating animation with {len(image_paths)} frames at {fps} fps...")
    
    # Create labeled frames
    labeled_frames = add_frame_labels(image_paths)
    
    # Create animation based on output type
    try:
        if output_path.endswith('.mp4'):
            if not MOVIEPY_AVAILABLE:
                print("Error: MoviePy is required for MP4 creation.")
                print("Please install it with: pip install moviepy")
                print("Converting to GIF instead...")
                output_path = output_path.replace('.mp4', '.gif')
            else:
                # Create animation with MoviePy
                clip = ImageSequenceClip(labeled_frames, fps=fps)
                clip.write_videofile(output_path, codec='libx264', fps=fps)
                print(f"MP4 animation saved to: {output_path}")
        
        if output_path.endswith('.gif'):
            # Create GIF with Pillow
            create_gif_with_pillow(labeled_frames, output_path, fps)
            print(f"GIF animation saved to: {output_path}")
    except Exception as e:
        print(f"Error creating animation: {e}")
        print("Files were not deleted due to error.")
        return
    
    # Clean up temp frames
    try:
        temp_dir = os.path.dirname(labeled_frames[0])
        for frame in labeled_frames:
            os.remove(frame)
        os.rmdir(temp_dir)
    except Exception as e:
        print(f"Warning: Could not clean up temporary files: {e}")

def main():
    """Main function to parse args and create the animation"""
    parser = argparse.ArgumentParser(description="Create an animation from Tetris simulation images")
    
    parser.add_argument("--session", required=True, help="Session directory name (e.g., session_20250308_020339)")
    parser.add_argument("--output", help="Output file path (default: auto-generated)")
    parser.add_argument("--type", choices=["mp4", "gif"], default=DEFAULT_OUTPUT_TYPE, help="Output file type")
    parser.add_argument("--fps", type=int, default=DEFAULT_FPS, help="Frames per second")
    parser.add_argument("--mode", choices=["sim", "pre", "post", "pre-post", "all"], default=DEFAULT_MODE, 
                        help="Which images to include: simulated_iter, pre_execution, post_execution, pre-post pairs, or all")
    
    args = parser.parse_args()
    
    # If MP4 is requested but MoviePy is not available, switch to GIF
    if args.type == "mp4" and not MOVIEPY_AVAILABLE:
        print("Warning: MP4 output requires MoviePy, which is not installed.")
        print("Switching to GIF output.")
        args.type = "gif"
    
    # Locate the game_logs directory based on where the script is run from
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try several potential locations
    potential_paths = [
        os.path.join(script_dir, "game_logs", args.session),
        os.path.join(script_dir, "..", "game_logs", args.session),
        os.path.join(script_dir, "claude_tetris_outputs", args.session),
        os.path.join("game_logs", args.session),
        os.path.join("claude_tetris_outputs", args.session),
        args.session
    ]
    
    session_dir = None
    for path in potential_paths:
        if os.path.exists(path):
            session_dir = path
            break
    
    if session_dir is None:
        print(f"Error: Session directory not found: {args.session}")
        print("Available sessions:")
        
        # Try to find available sessions
        for base_dir in ["game_logs", "claude_tetris_outputs"]:
            if os.path.exists(base_dir):
                sessions = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
                if sessions:
                    print(f"\nIn {base_dir}:")
                    for s in sessions:
                        print(f"  - {s}")
        
        sys.exit(1)
    
    # Find images
    try:
        image_paths = find_images(session_dir, args.mode)
    except Exception as e:
        print(f"Error finding images: {e}")
        sys.exit(1)
    
    if not image_paths:
        print(f"No images found in {session_dir} for mode '{args.mode}'")
        sys.exit(1)
        
    print(f"Found {len(image_paths)} images for animation")
    
    # Generate output path if not specified
    if not args.output:
        output_filename = f"tetris_{args.mode}_{Path(session_dir).name}.{args.type}"
        output_dir = os.path.join(script_dir, DEFAULT_OUTPUT_FOLDER)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
    else:
        output_path = args.output
        if not output_path.endswith(f'.{args.type}'):
            output_path += f'.{args.type}'
    
    # Create animation
    create_animation(image_paths, output_path, args.fps)

if __name__ == "__main__":
    main() 