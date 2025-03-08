@echo off
echo Setting up Tetris environment...

:: Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python not found! Please make sure Python is installed and in your PATH.
    exit /b 1
)

:: Install dependencies from the requirements file
echo Installing required dependencies...
pip install -r tetris_requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo Failed to install dependencies!
    exit /b 1
)

echo Dependencies installed successfully.
echo.

if "%1"=="animation" (
    :: Run the animation creator
    if "%2"=="" (
        echo Please provide a session directory name
        echo Usage: run_tetris.bat animation SESSION_NAME [OPTIONS]
        exit /b 1
    )
    
    echo Creating animation from session %2...
    python create_tetris_animation.py --session %2 %3 %4 %5 %6 %7 %8 %9
) else (
    :: Run the Tetris simulator
    echo Starting Tetris Claude Iterator...
    python tetris_claude_iterator.py %*
)

echo.
echo Done! 