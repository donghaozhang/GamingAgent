@echo off
echo ==================================
echo      Tetris AI Agent 启动程序
echo ==================================
echo.

REM 显示菜单选项
echo 请选择启动模式:
echo 1. 同时启动游戏和AI代理 (推荐)
echo 2. 仅启动游戏，不启动AI代理
echo 3. 仅启动AI代理，不启动游戏 (假设游戏已经运行)
echo.
set /p choice="请输入选项 (1-3, 默认为1): "

if "%choice%"=="" set choice=1

REM 根据选择设置参数
if "%choice%"=="1" (
    set launch_params=
) else if "%choice%"=="2" (
    set launch_params=--direct-game
) else if "%choice%"=="3" (
    set launch_params=--only-agent
) else (
    echo 无效选项，使用默认选项1
    set launch_params=
)

REM 检查conda是否可用
where conda >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Conda未安装或不在PATH中，尝试直接启动...
    python run_tetris.py %launch_params% %*
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
    python run_tetris.py %launch_params% %*
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

echo 启动Tetris程序...
python run_tetris.py %launch_params% %*

:end
echo.
echo 程序执行完毕。
pause 