#!/bin/bash

echo "=================================="
echo "Tetris AI Agent 一键启动程序"
echo "=================================="

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

echo "启动Tetris AI代理..."
python run_tetris.py "$@"

echo -e "\n程序执行完毕。"
read -p "按Enter键退出..." x 