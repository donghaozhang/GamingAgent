# Tetris AI 代理说明文档

这是一个能够自动玩Tetris（俄罗斯方块）游戏的AI代理系统。该系统使用AI模型来控制游戏，实现自动游玩。

## 一键启动方法

我们提供了几种简单的启动方式：

### Windows用户

直接双击运行：
```
start_tetris.bat
```

这个批处理文件会自动：
1. 检测并尝试激活game_cua环境（如果存在）
2. 启动Tetris AI代理

### Linux/Mac用户

在终端中运行：
```bash
# 先添加执行权限
chmod +x start_tetris.sh
# 然后运行
./start_tetris.sh
```

### 通过Python直接运行

如果您已经激活了正确的环境，也可以直接运行：
```bash
# 在GamingAgent目录下运行
python run_tetris.py
```

## 高级启动选项

您可以添加这些命令行参数来自定义行为：

```bash
# 显示详细的AI输出
python run_tetris.py --verbose_output

# 保存AI响应到文件
python run_tetris.py --save_responses

# 手动指定游戏窗口位置（如果自动检测有问题）
python run_tetris.py --manual_window --window_left 100 --window_top 100 --window_width 800 --window_height 700

# 使用不同的API提供商
python run_tetris.py --api_provider openai --model_name gpt-4o

# 查看所有可用选项
python run_tetris.py --help
```

## 游戏控制

游戏运行时：
- 按 `q` 键停止所有线程和游戏
- 在游戏窗口中按 `A` 键切换AI/玩家控制
- 在游戏窗口中按 `ESC` 键退出游戏
- 在游戏窗口中按 `R` 键重新开始游戏（游戏结束时）

## 故障排除

1. **游戏窗口不显示**
   - 确保您的系统支持Pygame图形界面
   - 检查是否已安装所有依赖项：`pip install -r requirements.txt`

2. **找不到模块错误**
   - 请确保您在正确的目录（GamingAgent）下运行程序
   - 确保已激活正确的conda环境：`conda activate game_cua`

3. **游戏窗口无法自动检测**
   - 使用手动窗口参数启动：`python run_tetris.py --manual_window` 