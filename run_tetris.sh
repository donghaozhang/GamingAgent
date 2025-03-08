#!/bin/bash
echo "Setting up Tetris environment..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Python not found! Please make sure Python is installed."
    exit 1
fi

# Install dependencies from the requirements file
echo "Installing required dependencies..."
pip install -r tetris_requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies!"
    exit 1
fi

echo "Dependencies installed successfully."
echo ""

if [ "$1" = "animation" ]; then
    # Run the animation creator
    if [ -z "$2" ]; then
        echo "Please provide a session directory name"
        echo "Usage: ./run_tetris.sh animation SESSION_NAME [OPTIONS]"
        exit 1
    fi
    
    echo "Creating animation from session $2..."
    python3 create_tetris_animation.py --session "$2" "${@:3}"
else
    # Run the Tetris simulator
    echo "Starting Tetris Claude Iterator..."
    python3 tetris_claude_iterator.py "$@"
fi

echo ""
echo "Done!" 