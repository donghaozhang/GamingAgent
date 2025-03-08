#!/usr/bin/env python
"""
Tetris Animation Creator

This script creates animations from Tetris screenshots.
It can create GIFs or video files from a series of screenshots.

Usage:
    python create_tetris_animation.py --session SESSION_DIR [--output OUTPUT_FILE] [--type gif|mp4] [--fps FPS] [--mode all|before|after]

Requirements:
    - PIL (Pillow)
    - moviepy (optional, for video creation)
"""

import os
import sys
import argparse
import glob
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# Optional import for video creation
try:
    import moviepy.editor as mpy
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False

def find_images(session_dir, mode="all"):
    """
    Find all screenshot images in the session directory.
    
    Args:
        session_dir: Path to the session directory
        mode: 'all', 'before', or 'after' to filter which images to include
        
    Returns:
        List of image paths sorted by timestamp
    """
    # Ensure screenshots directory exists
    screenshots_dir = os.path.join(session_dir, "screenshots")
    if not os.path.exists(screenshots_dir):
        screenshots_dir = session_dir  # Try the session dir itself if no screenshots subdir
        
    # Find all PNG files
    if mode == "all":
        pattern = os.path.join(screenshots_dir, "*.png")
    elif mode == "before":
        pattern = os.path.join(screenshots_dir, "screenshot_*.png")
    elif mode == "after":
        pattern = os.path.join(screenshots_dir, "post_execution_*.png")
    else:
        raise ValueError(f"Invalid mode: {mode}")
        
    # Get all matching files and sort them
    image_paths = glob.glob(pattern)
    
    # Sort by iteration number (embedded in filename)
    def get_iteration(path):
        filename = os.path.basename(path)
        parts = filename.split('_')
        # Try to extract iteration number
        try:
            if 'post' in filename:
                return int(parts[2])  # post_execution_NUMBER_timestamp.png
            else:
                return int(parts[1])  # screenshot_NUMBER_timestamp.png
        except (IndexError, ValueError):
            # If can't extract iteration, sort by full path (fallback)
            return float('inf')  # Put at end if we can't extract iteration
    
    return sorted(image_paths, key=get_iteration)

def add_frame_labels(image_paths):
    """
    Add labels to frames to indicate iteration number and type.
    
    Args:
        image_paths: List of paths to images
    
    Returns:
        List of PIL Image objects with labels
    """
    frames = []
    
    for i, path in enumerate(image_paths):
        try:
            # Open the image
            img = Image.open(path)
            
            # Create a copy for drawing
            draw_img = img.copy()
            draw = ImageDraw.Draw(draw_img)
            
            # Get iteration number from filename
            filename = os.path.basename(path)
            parts = filename.split('_')
            
            # Determine if this is a 'before' or 'after' screenshot
            is_post = 'post' in filename
            
            # Try to extract iteration number
            try:
                if is_post:
                    iter_num = int(parts[2])  # post_execution_NUMBER_timestamp.png
                else:
                    iter_num = int(parts[1])  # screenshot_NUMBER_timestamp.png
            except (IndexError, ValueError):
                iter_num = i + 1  # Use position in sequence as fallback
            
            # Add label with frame number and type
            label = f"Iteration {iter_num}: {'After Move' if is_post else 'Before Move'}"
            
            # Try to load font, fall back to default if needed
            try:
                font = ImageFont.truetype("arial.ttf", 16)
            except:
                font = ImageFont.load_default()
            
            # Add semi-transparent background for text
            text_width = len(label) * 8  # Approximate width
            text_height = 20
            draw.rectangle([(10, 10), (10 + text_width, 10 + text_height)], fill=(0, 0, 0, 128))
            
            # Draw text
            draw.text((15, 12), label, fill=(255, 255, 255), font=font)
            
            # Add to frames
            frames.append(draw_img)
            
        except Exception as e:
            print(f"Error processing {path}: {e}")
            # If there's an error, try to add the original image without modification
            try:
                frames.append(Image.open(path))
            except:
                pass
    
    return frames

def create_gif(frames, output_path, fps=2):
    """
    Create a GIF from frames.
    
    Args:
        frames: List of PIL Image objects
        output_path: Path to save the GIF
        fps: Frames per second
    """
    # Determine frame duration in milliseconds
    duration = int(1000 / fps)
    
    # Save as GIF
    if frames:
        # Get the size of the first frame
        size = frames[0].size
        
        # Ensure all frames are the same size
        uniform_frames = []
        for frame in frames:
            if frame.size != size:
                # Resize if needed
                frame = frame.resize(size, Image.LANCZOS)
            uniform_frames.append(frame)
        
        # Save animated GIF
        uniform_frames[0].save(
            output_path,
            save_all=True,
            append_images=uniform_frames[1:],
            optimize=True,
            duration=duration,
            loop=0  # Loop forever
        )
        return True
    else:
        print("No frames to create GIF")
        return False

def create_video(frames, output_path, fps=5):
    """
    Create a video from frames using moviepy (if available).
    
    Args:
        frames: List of PIL Image objects
        output_path: Path to save the video
        fps: Frames per second
    """
    if not MOVIEPY_AVAILABLE:
        print("Error: moviepy not installed. Cannot create video.")
        return False
    
    if not frames:
        print("No frames to create video")
        return False
    
    # Convert PIL images to numpy arrays
    import numpy as np
    frame_arrays = [np.array(frame) for frame in frames]
    
    try:
        # Create video clip
        clip = mpy.ImageSequenceClip(frame_arrays, fps=fps)
        
        # Write to file
        clip.write_videofile(output_path, fps=fps, codec='libx264')
        return True
    except Exception as e:
        print(f"Error creating video: {e}")
        return False

def create_animation(image_paths, output_path, fps=2, animation_type="gif"):
    """
    Create an animation from a list of image paths.
    
    Args:
        image_paths: List of paths to images
        output_path: Path to save the animation
        fps: Frames per second
        animation_type: 'gif' or 'mp4'
    
    Returns:
        True if successful, False otherwise
    """
    # Create list of frames with labels
    frames = add_frame_labels(image_paths)
    
    if not frames:
        print("No frames to process")
        return False
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create animation based on type
    if animation_type.lower() == "gif":
        return create_gif(frames, output_path, fps)
    elif animation_type.lower() == "mp4":
        if not MOVIEPY_AVAILABLE:
            print("Warning: moviepy not available, creating GIF instead")
            # Change extension to .gif
            output_path = os.path.splitext(output_path)[0] + ".gif"
            return create_gif(frames, output_path, fps)
        else:
            return create_video(frames, output_path, fps)
    else:
        print(f"Unsupported animation type: {animation_type}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Create an animation from Tetris screenshots")
    parser.add_argument("--session", required=True, help="Path to the session directory")
    parser.add_argument("--output", help="Path to save the animation")
    parser.add_argument("--type", default="gif", choices=["gif", "mp4"], help="Animation type (gif or mp4)")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second")
    parser.add_argument("--mode", default="all", choices=["all", "before", "after"], 
                        help="Which screenshots to include: all, before moves only, after moves only")
    
    args = parser.parse_args()
    
    # Default output path if not specified
    if not args.output:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        extension = ".gif" if args.type == "gif" else ".mp4"
        args.output = f"tetris_animation_{timestamp}{extension}"
    
    # Find images
    image_paths = find_images(args.session, args.mode)
    
    if not image_paths:
        print(f"No {args.mode} screenshots found in {args.session}")
        return
    
    print(f"Found {len(image_paths)} screenshots")
    
    # Create animation
    success = create_animation(image_paths, args.output, args.fps, args.type)
    
    if success:
        print(f"Animation saved to: {args.output}")
    else:
        print("Failed to create animation")

if __name__ == "__main__":
    main() 