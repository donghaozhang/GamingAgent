#!/usr/bin/env python
"""
Tetris AI Agent启动器
提供一种简单的方式来启动Tetris AI代理

使用方法:
    python run_tetris.py [参数]
    
    --direct-game: 仅启动游戏，不启动AI代理
    --only-agent: 仅启动AI代理，不启动游戏
    
其他参数将被传递给tetris_agent.py
"""

import os
import sys
import subprocess
import time
from pathlib import Path


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
    print("Tetris AI Agent 启动器 (调试模式)")
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
        print(f"运行代理命令: {cmd_str}")
        
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