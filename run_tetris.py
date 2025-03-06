#!/usr/bin/env python
"""
Tetris AI Agent启动器
提供一种简单的方式来启动Tetris AI代理

使用方法:
    python run_tetris.py [参数]

参数将被传递给tetris_agent.py
"""

import os
import sys
import subprocess
from pathlib import Path
import traceback


def main():
    # 获取当前脚本的目录
    script_dir = Path(__file__).parent.absolute()
    
    # 设置Tetris代理的路径
    tetris_agent_path = script_dir / "games" / "tetris" / "tetris_agent.py"
    simple_tetris_path = script_dir / "games" / "tetris" / "simple_tetris.py"
    
    if not tetris_agent_path.exists():
        print(f"错误：找不到Tetris代理脚本: {tetris_agent_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("Tetris AI Agent 启动器 (调试模式)")
    print("=" * 60)
    print(f"脚本路径: {tetris_agent_path}")
    print(f"简易Tetris路径: {simple_tetris_path}")
    print(f"Python路径: {sys.executable}")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"sys.path: {sys.path}")
    print("-" * 60)
    
    # 直接启动简易Tetris游戏进行测试
    should_run_simple_test = "--direct-game" in sys.argv
    if should_run_simple_test:
        print("直接启动简易Tetris游戏进行测试...")
        try:
            # 如果是直接测试游戏，则移除--direct-game参数
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
            traceback.print_exc()
            sys.exit(1)
    
    # 构建命令参数
    cmd = [sys.executable, str(tetris_agent_path)] + [arg for arg in sys.argv[1:] if arg != "--direct-game"]
    cmd_str = " ".join(cmd)
    print(f"运行命令: {cmd_str}")
    print("-" * 60)
    
    # 运行Tetris代理
    try:
        # 使用subprocess.run代替os.system以获得更好的控制
        process = subprocess.run(cmd, check=True)
        print("\nTetris代理已成功运行并退出。")
    except subprocess.CalledProcessError as e:
        print(f"\n错误：Tetris代理运行失败，退出代码: {e.returncode}")
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        print("\n用户中断，正在退出...")
        sys.exit(1)
    except Exception as e:
        print(f"\n未知错误：{e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 