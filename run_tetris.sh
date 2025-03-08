#!/bin/bash
echo "Setting up Tetris environment..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Python not found! Please make sure Python is installed."
    exit 1
fi

if [ "$1" = "animation" ]; then
    # Animation creator path
    if [ -z "$2" ]; then
        echo "Please provide a session directory name"
        echo "Usage: ./run_tetris.sh animation SESSION_NAME [--type gif/mp4] [OPTIONS]"
        exit 1
    fi
    
    # Determine animation type
    ANIMATION_TYPE="gif"
    if [ "$3" = "--type" ] && [ "$4" = "mp4" ]; then
        ANIMATION_TYPE="mp4"
    fi
    
    if [ "$ANIMATION_TYPE" = "mp4" ]; then
        echo "Setting up environment for MP4 animation creation..."
        echo "NOTE: This will temporarily install NumPy>=1.25.0 and MoviePy"
        echo "      This will make the Tetris simulator UNUSABLE until you reinstall NumPy 1.24.4"
        echo
        echo "Press Ctrl+C to cancel or Enter to continue..."
        read
        
        # Install MP4 dependencies
        pip install numpy>=1.25.0 moviepy
        if [ $? -ne 0 ]; then
            echo "Failed to install dependencies for MP4 creation!"
            exit 1
        fi
    else
        # Install GIF dependencies
        echo "Installing required dependencies for GIF creation..."
        pip install -r tetris_requirements.txt
        if [ $? -ne 0 ]; then
            echo "Failed to install dependencies!"
            exit 1
        fi
    fi
    
    echo "Dependencies installed successfully."
    echo ""
    
    echo "Creating $ANIMATION_TYPE animation from session $2..."
    # Handle arguments differently depending on animation type
    if [ "$ANIMATION_TYPE" = "mp4" ]; then
        # Skip the --type and mp4 parameters (args 3 and 4)
        python3 create_tetris_animation.py --session "$2" --type "$ANIMATION_TYPE" "${@:5}"
    else
        # For GIF, skip to argument 3 onwards
        python3 create_tetris_animation.py --session "$2" --type "$ANIMATION_TYPE" "${@:3}"
    fi
    
    if [ "$ANIMATION_TYPE" = "mp4" ]; then
        echo ""
        echo "IMPORTANT: The Tetris simulator will not work until you reinstall the correct NumPy version."
        echo "To fix this, run: pip install numpy==1.24.4"
    fi
else
    # Tetris simulator path
    echo "Installing required dependencies for Tetris simulator..."
    pip install -r tetris_requirements.txt
    if [ $? -ne 0 ]; then
        echo "Failed to install dependencies!"
        exit 1
    fi
    
    echo "Dependencies installed successfully."
    echo ""
    
    echo "Starting Tetris Claude Iterator..."
    python3 tetris_claude_iterator.py "$@"
fi

echo ""
echo "Done!" 