#!/usr/bin/env python
"""
Tetris AI Agent增强版启动器
提供一种简单的方式来启动Tetris AI代理，启用增强的日志和截图功能

使用方法:
    python run_tetris_enhanced.py [参数]
    
    --screenshot-interval=N: 每N秒自动截图一次(默认为5秒)
    --no-enhanced-logging: 禁用增强日志
    --no-save-all-states: 禁用保存所有游戏状态截图
    
    其他参数将被传递给tetris_agent.py
"""

import os
import sys
import subprocess
import time
import re
from pathlib import Path
from datetime import datetime


def parse_custom_args(args):
    """解析自定义参数"""
    # 默认值
    screenshot_interval = 5
    enhanced_logging = True
    save_all_states = True
    plan_seconds = 60
    execution_mode = 'adaptive'
    piece_limit = 0
    
    # 需要移除的参数
    to_remove = []
    
    # 处理自定义参数
    for i, arg in enumerate(args):
        if arg.startswith("--screenshot-interval="):
            match = re.match(r"--screenshot-interval=(\d+)", arg)
            if match:
                screenshot_interval = int(match.group(1))
            to_remove.append(arg)
        elif arg == "--no-enhanced-logging":
            enhanced_logging = False
            to_remove.append(arg)
        elif arg == "--no-save-all-states":
            save_all_states = False
            to_remove.append(arg)
        elif arg.startswith("--plan-seconds="):
            match = re.match(r"--plan-seconds=(\d+)", arg)
            if match:
                plan_seconds = int(match.group(1))
            to_remove.append(arg)
        elif arg.startswith("--execution-mode="):
            match = re.match(r"--execution-mode=(\w+)", arg)
            if match:
                mode = match.group(1)
                if mode in ['adaptive', 'fast', 'slow']:
                    execution_mode = mode
            to_remove.append(arg)
        elif arg.startswith("--piece-limit="):
            match = re.match(r"--piece-limit=(\d+)", arg)
            if match:
                piece_limit = int(match.group(1))
            to_remove.append(arg)
    
    # 移除我们处理的参数
    filtered_args = [arg for arg in args if arg not in to_remove]
    
    # 添加我们处理的参数对应的tetris_agent.py参数
    if screenshot_interval > 0:
        filtered_args.append(f"--screenshot_interval={screenshot_interval}")
    if enhanced_logging:
        filtered_args.append("--enhanced_logging")
    if save_all_states:
        filtered_args.append("--save_all_states")
    
    # 添加新的参数
    filtered_args.append(f"--plan_seconds={plan_seconds}")
    filtered_args.append(f"--execution_mode={execution_mode}")
    if piece_limit > 0:
        filtered_args.append(f"--piece_limit={piece_limit}")
    
    # 创建带有时间戳的日志文件夹名称
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_folder = f"game_logs/session_{timestamp}"
    filtered_args.append(f"--log_folder={log_folder}")
    
    return filtered_args


def main():
    # 获取当前脚本的目录
    script_dir = Path(__file__).parent.absolute()
    
    # 设置Tetris代理和游戏的路径
    tetris_agent_path = script_dir / "games" / "tetris" / "tetris_agent.py"
    simple_tetris_path = script_dir / "games" / "tetris" / "simple_tetris.py"
    
    if not tetris_agent_path.exists():
        print(f"错误：找不到Tetris代理脚本: {tetris_agent_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("Tetris AI Agent 增强版启动器")
    print("=" * 60)
    print(f"代理脚本路径: {tetris_agent_path}")
    print(f"游戏脚本路径: {simple_tetris_path}")
    print(f"Python路径: {sys.executable}")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print("-" * 60)
    
    # 解析参数
    args = sys.argv[1:]
    direct_game = "--direct-game" in args
    only_agent = "--only-agent" in args
    
    # 移除我们处理的参数
    filtered_args = [arg for arg in args if arg not in ["--direct-game", "--only-agent"]]
    
    # 处理自定义参数
    filtered_args = parse_custom_args(filtered_args)
    
    # 直接启动简易Tetris游戏进行测试
    if direct_game:
        print("直接启动简易Tetris游戏进行测试...")
        try:
            test_cmd = [sys.executable, str(simple_tetris_path)]
            print(f"运行测试命令: {' '.join(test_cmd)}")
            process = subprocess.run(test_cmd, check=True)
            print("\n简易Tetris游戏测试完成，退出代码:", process.returncode)
            return
        except subprocess.CalledProcessError as e:
            print(f"\n错误：简易Tetris游戏测试失败，退出代码: {e.returncode}")
            sys.exit(e.returncode)
        except Exception as e:
            print(f"\n未知错误：{e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 只启动代理，不启动游戏
    if only_agent:
        print("仅启动AI代理，不启动游戏...")
        filtered_args.append("--no_launch_game")
    
    # 同时启动游戏和代理（默认行为）
    # 1. 先直接启动游戏进程
    game_process = None
    if not only_agent:
        try:
            print("启动简易Tetris游戏...")
            game_cmd = [sys.executable, str(simple_tetris_path)]
            print(f"运行游戏命令: {' '.join(game_cmd)}")
            # 使用subprocess.Popen而不是run，这样可以在后台运行
            game_process = subprocess.Popen(game_cmd)
            print(f"游戏进程已启动，PID: {game_process.pid}")
            # 等待一段时间让游戏窗口显示
            time.sleep(2)
        except Exception as e:
            print(f"启动游戏时出错: {e}")
            import traceback
            traceback.print_exc()
    
    # 2. 然后启动代理
    try:
        # 构建命令参数
        cmd = [sys.executable, str(tetris_agent_path)] + filtered_args
        
        # 如果我们已经启动了游戏，告诉代理不要再次启动游戏
        if game_process is not None and game_process.poll() is None:
            if "--no_launch_game" not in cmd:
                cmd.append("--no_launch_game")
                print("添加--no_launch_game参数，防止代理再次启动游戏")
        
        cmd_str = " ".join(cmd)
        print(f"运行增强版代理命令: {cmd_str}")
        
        # 运行Tetris代理
        process = subprocess.run(cmd, check=True)
        print("\nTetris代理已成功运行并退出。")
    except subprocess.CalledProcessError as e:
        print(f"\n错误：Tetris代理运行失败，退出代码: {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n用户中断，正在退出...")
    except Exception as e:
        print(f"\n未知错误：{e}")
        import traceback
        traceback.print_exc()
    finally:
        # 如果游戏进程还在运行，尝试结束它
        if game_process and game_process.poll() is None:
            print(f"游戏进程 (PID: {game_process.pid}) 仍在运行，尝试终止...")
            try:
                game_process.terminate()
                game_process.wait(timeout=3)
                print("游戏进程已终止")
            except Exception as e:
                print(f"终止游戏进程时出错: {e}")
                try:
                    game_process.kill()
                    print("已强制结束游戏进程")
                except:
                    print("无法结束游戏进程")


if __name__ == "__main__":
    main() 