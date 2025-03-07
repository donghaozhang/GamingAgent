#!/bin/bash

echo "=================================="
echo "     Tetris AI Agent 启动程序"
echo "=================================="
echo

# 显示菜单选项
echo "请选择启动模式:"
echo "1. 同时启动游戏和AI代理 (推荐)"
echo "2. 仅启动游戏，不启动AI代理"
echo "3. 仅启动AI代理，不启动游戏 (假设游戏已经运行)"
echo
read -p "请输入选项 (1-3, 默认为1): " choice

# 设置默认值
if [ -z "$choice" ]; then
    choice=1
fi

# 根据选择设置参数
case $choice in
    1)
        launch_params=""
        ;;
    2)
        launch_params="--direct-game"
        ;;
    3)
        launch_params="--only-agent"
        ;;
    *)
        echo "无效选项，使用默认选项1"
        launch_params=""
        ;;
esac

# 检查conda是否可用
if command -v conda &> /dev/null; then
    # 获取当前激活的conda环境
    CONDA_ENV=$(conda info | grep "active environment" | cut -d ":" -f 2 | xargs)
    echo "当前conda环境: $CONDA_ENV"
    
    # 如果当前不是game_cua环境，则尝试激活它
    if [ "$CONDA_ENV" != "game_cua" ]; then
        echo "尝试激活game_cua环境..."
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate game_cua
        if [ $? -ne 0 ]; then
            echo "无法激活game_cua环境，尝试使用当前环境运行..."
        else
            echo "已激活game_cua环境"
        fi
    else
        echo "已在game_cua环境中，直接启动..."
    fi
else
    echo "Conda未安装或不在PATH中，尝试直接启动..."
fi

echo "启动Tetris程序..."
python run_tetris.py $launch_params "$@"

echo -e "\n程序执行完毕。"
read -p "按Enter键退出..." x 