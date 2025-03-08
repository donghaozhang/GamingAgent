@echo off
echo Setting up Tetris environment...

:: Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python not found! Please make sure Python is installed and in your PATH.
    exit /b 1
)

if "%1"=="animation" (
    :: Animation creator path
    if "%2"=="" (
        echo Please provide a session directory name
        echo Usage: run_tetris.bat animation SESSION_NAME [--type gif/mp4] [OPTIONS]
        exit /b 1
    )
    
    set ANIMATION_TYPE=gif
    if not "%3"=="" if "%3"=="--type" if "%4"=="mp4" set ANIMATION_TYPE=mp4
    
    if "%ANIMATION_TYPE%"=="mp4" (
        echo Setting up environment for MP4 animation creation...
        echo NOTE: This will temporarily install NumPy>=1.25.0 and MoviePy
        echo       This will make the Tetris simulator UNUSABLE until you reinstall NumPy 1.24.4
        echo.
        echo Press Ctrl+C to cancel or any key to continue...
        pause >nul
        
        :: Install MP4 dependencies
        pip install numpy>=1.25.0 moviepy
        if %ERRORLEVEL% NEQ 0 (
            echo Failed to install dependencies for MP4 creation!
            exit /b 1
        )
    ) else (
        :: Install GIF dependencies
        echo Installing required dependencies for GIF creation...
        pip install -r tetris_requirements.txt
        if %ERRORLEVEL% NEQ 0 (
            echo Failed to install dependencies!
            exit /b 1
        )
    )
    
    echo Dependencies installed successfully.
    echo.
    
    echo Creating %ANIMATION_TYPE% animation from session %2...
    python create_tetris_animation.py --session %2 --type %ANIMATION_TYPE% %5 %6 %7 %8 %9
    
    if "%ANIMATION_TYPE%"=="mp4" (
        echo.
        echo IMPORTANT: The Tetris simulator will not work until you reinstall the correct NumPy version.
        echo To fix this, run: pip install numpy==1.24.4
    )
) else (
    :: Tetris simulator path
    echo Installing required dependencies for Tetris simulator...
    pip install -r tetris_requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install dependencies!
        exit /b 1
    )
    
    echo Dependencies installed successfully.
    echo.
    
    echo Starting Tetris Claude Iterator...
    python tetris_claude_iterator.py %*
)

echo.
echo Done! 