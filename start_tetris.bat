@echo off
echo ==================================
echo Tetris AI Agent 一键启动程序
echo ==================================

REM 检查conda是否可用
where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Conda未安装或不在PATH中，尝试直接启动...
    python run_tetris.py %*
    goto :end
)

REM 获取当前激活的conda环境
for /f "tokens=*" %%i in ('conda info --envs ^| findstr "*"') do (
    set env_line=%%i
)
set conda_env=%env_line:~1,10%
echo 当前conda环境: %conda_env%

REM 如果当前是game_cua环境，则直接运行
if "%conda_env%"=="game_cua" (
    echo 已在game_cua环境中，直接启动...
    python run_tetris.py %*
    goto :end
)

REM 否则尝试激活game_cua环境并运行
echo 尝试激活game_cua环境...
call conda activate game_cua
if %ERRORLEVEL% neq 0 (
    echo 无法激活game_cua环境，尝试使用当前环境运行...
) else (
    echo 已激活game_cua环境
)

echo 启动Tetris AI代理...
python run_tetris.py %*

:end
echo.
echo 程序执行完毕。
pause 