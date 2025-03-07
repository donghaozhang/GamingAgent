"""
简化版Tetris游戏，专为AI控制设计
- 更加健壮的错误处理
- 简化的游戏逻辑
- 游戏自动启动，无需按键
- 提供状态信息，便于AI读取
"""
import pygame
import random
import sys
import time
import os
import threading

# 确保总是使用图形界面模式
# 注释掉原来的终端检测代码
# if os.environ.get('TERM') or os.environ.get('PROMPT'):
#     os.environ['SDL_VIDEODRIVER'] = 'dummy'  # 无图形界面模式
# else:
#     os.environ['SDL_VIDEO_CENTERED'] = '1'  # 居中显示窗口

# 强制使用图形界面模式
os.environ['SDL_VIDEO_CENTERED'] = '1'  # 居中显示窗口

# 增加调试输出
print("Starting Simple Tetris game...")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 游戏常量
BLOCK_SIZE = 30
GRID_WIDTH = 10
GRID_HEIGHT = 20
PREVIEW_SIZE = 4

# 计算窗口尺寸
SCREEN_WIDTH = BLOCK_SIZE * (GRID_WIDTH + 6)  # 额外空间用于显示下一个方块和分数
SCREEN_HEIGHT = BLOCK_SIZE * GRID_HEIGHT

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)

# 方块形状定义
SHAPES = [
    [[1, 1, 1, 1]],                                # I
    [[1, 1], [1, 1]],                              # O
    [[0, 1, 0], [1, 1, 1]],                        # T
    [[0, 1, 1], [1, 1, 0]],                        # S
    [[1, 1, 0], [0, 1, 1]],                        # Z
    [[1, 0, 0], [1, 1, 1]],                        # J
    [[0, 0, 1], [1, 1, 1]]                         # L
]

# 方块颜色
SHAPE_COLORS = [CYAN, YELLOW, MAGENTA, GREEN, RED, BLUE, ORANGE]

# 游戏状态
class GameState:
    def __init__(self):
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.grid = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.current_piece = None
        self.next_piece = None
        self.piece_x = 0
        self.piece_y = 0
        self.fall_speed = 2.0  # 减慢下落速度（秒/格），原来为0.5
        self.last_fall_time = 0
        self.moves_made = []
        self.ai_control = True  # 默认AI控制
        self.paused = False  # 添加暂停状态
        self.auto_fall = False  # 禁用自动下落功能
        
    def generate_new_piece(self):
        # 随机选择一个方块
        shape_idx = random.randint(0, len(SHAPES) - 1)
        return {
            'shape': SHAPES[shape_idx],
            'color': SHAPE_COLORS[shape_idx],
            'rotation': 0
        }
    
    def spawn_piece(self):
        if self.next_piece is None:
            self.next_piece = self.generate_new_piece()
        
        self.current_piece = self.next_piece
        self.next_piece = self.generate_new_piece()
        
        # 设置初始位置（居中）
        shape = self.current_piece['shape']
        self.piece_x = GRID_WIDTH // 2 - len(shape[0]) // 2
        self.piece_y = 0
        
        # 检查游戏是否结束
        if not self.is_valid_position():
            self.game_over = True
    
    def rotate_piece(self):
        if not self.current_piece:
            return False
            
        # 保存当前状态
        original_rotation = self.current_piece['rotation']
        
        # 旋转
        shape = self.current_piece['shape']
        rows = len(shape)
        cols = len(shape[0])
        
        # 计算新的旋转状态
        self.current_piece['rotation'] = (self.current_piece['rotation'] + 1) % 4
        
        # 根据旋转状态重新计算形状
        if self.current_piece['rotation'] == 0:
            # 原始形状
            pass
        elif self.current_piece['rotation'] == 1:
            # 旋转90度
            self.current_piece['shape'] = [[shape[rows-1-j][i] for j in range(rows)] for i in range(cols)]
        elif self.current_piece['rotation'] == 2:
            # 旋转180度
            self.current_piece['shape'] = [[shape[rows-1-i][cols-1-j] for j in range(cols)] for i in range(rows)]
        elif self.current_piece['rotation'] == 3:
            # 旋转270度
            self.current_piece['shape'] = [[shape[j][cols-1-i] for j in range(rows)] for i in range(cols)]
        
        # 检查旋转后是否有效
        if not self.is_valid_position():
            # 恢复原状态
            self.current_piece['rotation'] = original_rotation
            self.current_piece['shape'] = shape
            return False
        
        return True
    
    def move_left(self):
        if not self.current_piece:
            return False
            
        self.piece_x -= 1
        if not self.is_valid_position():
            self.piece_x += 1
            return False
        return True
    
    def move_right(self):
        if not self.current_piece:
            return False
            
        self.piece_x += 1
        if not self.is_valid_position():
            self.piece_x -= 1
            return False
        return True
    
    def move_down(self):
        if not self.current_piece:
            return False
            
        self.piece_y += 1
        if not self.is_valid_position():
            self.piece_y -= 1
            self.lock_piece()
            return False
        return True
    
    def drop_piece(self):
        if not self.current_piece:
            return
            
        while self.move_down():
            pass
    
    def is_valid_position(self):
        if not self.current_piece:
            return False
            
        shape = self.current_piece['shape']
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    # 计算在网格中的实际位置
                    grid_x = self.piece_x + x
                    grid_y = self.piece_y + y
                    
                    # 检查是否超出边界
                    if (grid_x < 0 or grid_x >= GRID_WIDTH or
                        grid_y < 0 or grid_y >= GRID_HEIGHT):
                        return False
                    
                    # 检查是否与已有方块重叠
                    if grid_y >= 0 and self.grid[grid_y][grid_x]:
                        return False
        return True
    
    def lock_piece(self):
        if not self.current_piece:
            return
            
        shape = self.current_piece['shape']
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    # 计算在网格中的实际位置
                    grid_x = self.piece_x + x
                    grid_y = self.piece_y + y
                    
                    # 确保在有效范围内
                    if 0 <= grid_y < GRID_HEIGHT and 0 <= grid_x < GRID_WIDTH:
                        self.grid[grid_y][grid_x] = self.current_piece['color']
        
        # 清除完整的行
        self.clear_lines()
        
        # 生成新的方块
        self.spawn_piece()
    
    def clear_lines(self):
        lines_to_clear = []
        for y in range(GRID_HEIGHT):
            if all(self.grid[y]):
                lines_to_clear.append(y)
        
        # 清除行并计算分数
        if lines_to_clear:
            for y in lines_to_clear:
                # 将上面的行向下移动
                for y2 in range(y, 0, -1):
                    self.grid[y2] = self.grid[y2 - 1].copy()
                # 清空最上面的行
                self.grid[0] = [0 for _ in range(GRID_WIDTH)]
            
            # 更新分数和等级
            self.lines_cleared += len(lines_to_clear)
            self.score += len(lines_to_clear) * 100 * self.level
            self.level = self.lines_cleared // 10 + 1
            
            # 更新下落速度
            self.fall_speed = max(0.1, 0.5 - (self.level - 1) * 0.05)
            # self.fall_speed = 20
    
    def update(self, current_time):
        if self.game_over or not self.current_piece or self.paused:
            return
            
        # 只有在auto_fall为True时才自动下落
        if self.auto_fall and current_time - self.last_fall_time > self.fall_speed:
            self.last_fall_time = current_time
            self.move_down()
    
    def get_state_for_ai(self):
        """返回当前游戏状态的简洁表示，供AI分析"""
        state = {
            'score': self.score,
            'level': self.level,
            'lines_cleared': self.lines_cleared,
            'game_over': self.game_over,
            'grid': self.grid.copy(),
            'current_piece': {
                'shape': self.current_piece['shape'] if self.current_piece else None,
                'x': self.piece_x,
                'y': self.piece_y
            },
            'next_piece': {
                'shape': self.next_piece['shape'] if self.next_piece else None
            }
        }
        return state

# 游戏渲染器
class GameRenderer:
    def __init__(self, game_state):
        self.game_state = game_state
        self.font = None
        
    def initialize(self):
        try:
            pygame.init()
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
            pygame.display.set_caption("Simple Tetris")
            self.font = pygame.font.SysFont(None, 24)
            return True
        except Exception as e:
            print(f"Failed to initialize renderer: {e}")
            return False
    
    def draw_grid(self):
        # 绘制网格背景
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                pygame.draw.rect(
                    self.screen, 
                    GRAY,
                    (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE),
                    1
                )
        
        # 绘制已放置的方块
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if self.game_state.grid[y][x]:
                    pygame.draw.rect(
                        self.screen,
                        self.game_state.grid[y][x],
                        (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE)
                    )
    
    def draw_current_piece(self):
        if not self.game_state.current_piece:
            return
            
        piece = self.game_state.current_piece
        shape = piece['shape']
        
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(
                        self.screen,
                        piece['color'],
                        ((self.game_state.piece_x + x) * BLOCK_SIZE, 
                         (self.game_state.piece_y + y) * BLOCK_SIZE,
                         BLOCK_SIZE, BLOCK_SIZE)
                    )
    
    def draw_next_piece(self):
        if not self.game_state.next_piece:
            return
            
        piece = self.game_state.next_piece
        shape = piece['shape']
        
        # 预览区域位置
        preview_x = GRID_WIDTH * BLOCK_SIZE + 20
        preview_y = 100
        
        # 绘制预览标题
        text = self.font.render("Next:", True, WHITE)
        self.screen.blit(text, (preview_x, preview_y - 30))
        
        # 绘制预览方块
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(
                        self.screen,
                        piece['color'],
                        (preview_x + x * BLOCK_SIZE, 
                         preview_y + y * BLOCK_SIZE,
                         BLOCK_SIZE, BLOCK_SIZE)
                    )
    
    def draw_score(self):
        score_x = GRID_WIDTH * BLOCK_SIZE + 20
        score_y = 250
        
        # 分数
        score_text = self.font.render(f"Score: {self.game_state.score}", True, WHITE)
        self.screen.blit(score_text, (score_x, score_y))
        
        # 等级
        level_text = self.font.render(f"Level: {self.game_state.level}", True, WHITE)
        self.screen.blit(level_text, (score_x, score_y + 30))
        
        # 行数
        lines_text = self.font.render(f"Lines: {self.game_state.lines_cleared}", True, WHITE)
        self.screen.blit(lines_text, (score_x, score_y + 60))
    
    def draw_game_over(self):
        if not self.game_state.game_over:
            return
            
        # 半透明覆盖层
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.screen.blit(overlay, (0, 0))
        
        # 游戏结束文本
        font = pygame.font.SysFont(None, 48)
        text = font.render("Game Over", True, RED)
        text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50))
        self.screen.blit(text, text_rect)
        
        # 分数
        score_text = self.font.render(f"Final Score: {self.game_state.score}", True, WHITE)
        score_rect = score_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(score_text, score_rect)
        
        # 重新开始提示
        restart_text = self.font.render("Press R to restart", True, WHITE)
        restart_rect = restart_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(restart_text, restart_rect)
    
    def draw_ai_status(self):
        """绘制AI状态信息"""
        # 创建状态文本
        ai_status = "AI: ON" if self.game_state.ai_control else "AI: OFF"
        auto_fall = "Auto Fall: ON" if self.game_state.auto_fall else "Auto Fall: OFF"
        
        # 绘制AI状态
        ai_text = self.font.render(ai_status, True, WHITE)
        ai_rect = ai_text.get_rect()
        ai_rect.topleft = (10, 10)
        self.screen.blit(ai_text, ai_rect)
        
        # 绘制自动下落状态
        fall_text = self.font.render(auto_fall, True, WHITE)
        fall_rect = fall_text.get_rect()
        fall_rect.topleft = (10, 40)
        self.screen.blit(fall_text, fall_rect)
        
        # 如果游戏暂停，显示暂停状态
        if self.game_state.paused:
            pause_text = self.font.render("PAUSED", True, YELLOW)
            pause_rect = pause_text.get_rect()
            pause_rect.center = (SCREEN_WIDTH // 2, 50)
            self.screen.blit(pause_text, pause_rect)
    
    def render(self):
        try:
            # 清屏
            self.screen.fill(BLACK)
            
            # 绘制游戏元素
            self.draw_grid()
            self.draw_current_piece()
            self.draw_next_piece()
            self.draw_score()
            self.draw_ai_status()
            self.draw_game_over()
            
            # 更新屏幕
            pygame.display.flip()
        except Exception as e:
            print(f"Render error: {e}")

# AI控制类
class AIController:
    def __init__(self, game_state):
        self.game_state = game_state
        self.last_move_time = 0
        self.move_delay = 0.05  # 减少AI移动间隔时间（秒），原来为0.1
        self.command_queue = []  # 添加命令队列
        self.last_piece_move_time = 0  # 跟踪当前方块上次移动时间
        self.move_count_for_current_piece = 0  # 当前方块操作计数
        self.idle_time_threshold = 2.0  # 如果某个方块超过2秒无操作，考虑强制drop
    
    def update(self, current_time):
        if (not self.game_state.ai_control or 
            self.game_state.game_over or
            self.game_state.paused or  # 考虑暂停状态
            current_time - self.last_move_time < self.move_delay):
            return
        
        # 更新最后移动时间
        self.last_move_time = current_time
        
        # 如果当前方块长时间未操作且不是自动下落模式，强制下落
        if (not self.game_state.auto_fall and 
            current_time - self.last_piece_move_time > self.idle_time_threshold and 
            self.move_count_for_current_piece > 0):
            print("方块长时间未操作，强制下落")
            if self.execute_action("drop"):
                self.move_count_for_current_piece = 0  # 重置计数器
                self.last_piece_move_time = current_time
                return
        
        # 检查是否需要强制下落
        # 如果当前位置可以下移但没有自动下落，适时移动一格
        if not self.game_state.auto_fall:
            # 保存当前位置
            current_x, current_y = self.game_state.piece_x, self.game_state.piece_y
            # 尝试下移一格
            self.game_state.piece_y += 1
            # 如果不是有效位置，恢复原位置
            if not self.game_state.is_valid_position():
                self.game_state.piece_y = current_y
                # 如果无法下移，可能需要锁定方块
                if random.random() < 0.1:  # 10%的概率触发drop操作
                    self.execute_action("drop")
                    self.move_count_for_current_piece = 0  # 重置计数器
                    self.last_piece_move_time = current_time
                    return
            else:
                # 如果可以下移，恢复原位置（让AI决定是否要移动）
                self.game_state.piece_y = current_y
        
        # 如果有命令队列，优先执行队列中的命令
        if self.command_queue:
            action = self.command_queue.pop(0)
            success = self.execute_action(action)
            # 打印执行的命令
            if success:
                print(f"AI executed command: {action}")
                self.last_piece_move_time = current_time
                self.move_count_for_current_piece += 1
                
                # 如果是drop命令，重置计数器
                if action == "drop" or action.endswith("_drop"):
                    self.move_count_for_current_piece = 0
                return
        
        # 简单AI：随机选择动作
        # 在实际应用中，这里可以由Claude等AI模型替代
        actions = ["left", "right", "rotate", "drop"]
        weights = [0.3, 0.3, 0.3, 0.1]  # 权重决定选择不同动作的概率
        action = random.choices(actions, weights=weights, k=1)[0]
        
        # 执行选择的动作
        success = self.execute_action(action)
        
        # 记录移动
        if success:
            self.game_state.moves_made.append(action)
            if len(self.game_state.moves_made) > 10:
                self.game_state.moves_made.pop(0)  # 保持最近10次移动的记录
                
            # 更新方块操作计数
            self.last_piece_move_time = time.time()
            self.move_count_for_current_piece += 1
            
            # 如果是drop命令，重置计数器
            if action == "drop" or action.endswith("_drop"):
                self.move_count_for_current_piece = 0
    
    def execute_action(self, action):
        """执行指定的动作并返回是否成功"""
        success = False
        
        if action == "left":
            success = self.game_state.move_left()
        elif action == "right":
            success = self.game_state.move_right()
        elif action == "down":
            success = self.game_state.move_down()
        elif action == "rotate":
            success = self.game_state.rotate_piece()
        elif action == "drop":
            self.game_state.drop_piece()
            success = True
        # 添加多步组合动作
        elif action == "left_drop":
            self.game_state.move_left()
            self.game_state.drop_piece()
            success = True
        elif action == "right_drop":
            self.game_state.move_right()
            self.game_state.drop_piece()
            success = True
        elif action == "rotate_drop":
            self.game_state.rotate_piece()
            self.game_state.drop_piece()
            success = True
        
        return success
    
    def add_commands(self, commands):
        """添加一系列命令到队列中"""
        self.command_queue.extend(commands)
        print(f"Added {len(commands)} commands to AI queue")

# 主游戏类
class SimpleTetris:
    def __init__(self):
        self.game_state = GameState()
        self.renderer = GameRenderer(self.game_state)
        self.ai = AIController(self.game_state)
        self.clock = pygame.time.Clock()
        self.running = False
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                print("QUIT event received. Closing the game.")
            elif event.type == pygame.KEYDOWN:
                print(f"Key pressed: {pygame.key.name(event.key)}")
                if event.key == pygame.K_r and self.game_state.game_over:
                    # 重新开始游戏
                    self.game_state = GameState()
                    self.renderer.game_state = self.game_state
                    self.ai.game_state = self.game_state
                    self.game_state.spawn_piece()
                
                elif event.key == pygame.K_a:
                    # 切换AI控制
                    self.game_state.ai_control = not self.game_state.ai_control
                    print(f"AI control: {self.game_state.ai_control}")
                
                # 切换自动下落功能
                elif event.key == pygame.K_f:
                    self.game_state.auto_fall = not self.game_state.auto_fall
                    print(f"Auto fall: {self.game_state.auto_fall}")
                
                # 暂停/继续游戏
                elif event.key == pygame.K_p:
                    self.game_state.paused = not self.game_state.paused
                    print(f"Game paused: {self.game_state.paused}")
                
                # 控制下落速度
                elif event.key == pygame.K_PLUS or event.key == pygame.K_KP_PLUS:
                    self.game_state.fall_speed = max(0.1, self.game_state.fall_speed - 0.1)
                    print(f"Fall speed: {self.game_state.fall_speed:.1f}s/grid")
                elif event.key == pygame.K_MINUS or event.key == pygame.K_KP_MINUS:
                    self.game_state.fall_speed += 0.1
                    print(f"Fall speed: {self.game_state.fall_speed:.1f}s/grid")
                
                # 退出游戏
                elif event.key == pygame.K_ESCAPE:
                    self.running = False
                    print("ESC key pressed. Closing the game.")
                
                # 只有在玩家控制模式下才处理这些键
                elif not self.game_state.ai_control and not self.game_state.game_over:
                    if event.key == pygame.K_LEFT:
                        self.game_state.move_left()
                    elif event.key == pygame.K_RIGHT:
                        self.game_state.move_right()
                    elif event.key == pygame.K_DOWN:
                        self.game_state.move_down()
                    elif event.key == pygame.K_UP:
                        self.game_state.rotate_piece()
                    elif event.key == pygame.K_SPACE:
                        self.game_state.drop_piece()
    
    def run(self):
        print("Initializing SimpleTetris game...")
        
        # 初始化Pygame
        try:
            pygame.init()
            print("Pygame initialized successfully")
        except Exception as e:
            print(f"Error initializing Pygame: {e}")
            return
        
        # 初始化渲染器
        if not self.renderer.initialize():
            print("Failed to initialize game renderer. Exiting.")
            pygame.quit()
            return
        
        # 初始化游戏
        try:
            self.game_state.spawn_piece()
            print("Game state initialized successfully")
        except Exception as e:
            print(f"Error initializing game state: {e}")
            pygame.quit()
            return
            
        self.running = True
        print("Game running... Press ESC to quit, A to toggle AI control")
        
        # 主游戏循环
        frame_count = 0
        start_time = time.time()
        
        try:
            while self.running:
                # 处理事件
                self.handle_events()
                
                # 获取当前时间
                current_time = time.time()
                
                # 更新游戏状态
                self.game_state.update(current_time)
                
                # AI控制
                self.ai.update(current_time)
                
                # 渲染游戏
                self.renderer.render()
                
                # 控制帧率
                self.clock.tick(60)
                
                # 计算帧率
                frame_count += 1
                if frame_count % 100 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"FPS: {fps:.1f}, Frames: {frame_count}, Time: {elapsed:.1f}s")
                    
        except Exception as e:
            print(f"Game error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            pygame.quit()
            print("Game exited")

    def send_ai_commands(self, commands):
        """向AI控制器发送一系列命令

        Args:
            commands (list): 要执行的命令列表，如["left", "rotate", "right", "drop"]
        
        Returns:
            bool: 命令是否已添加到队列
        """
        if not self.game_state.ai_control:
            print("Warning: AI control is OFF. Commands won't be executed unless AI mode is enabled.")
            return False
            
        # 确保命令有效
        valid_commands = ["left", "right", "down", "rotate", "drop", 
                         "left_drop", "right_drop", "rotate_drop"]
        filtered_commands = [cmd for cmd in commands if cmd in valid_commands]
        
        if len(filtered_commands) != len(commands):
            invalid = set(commands) - set(valid_commands)
            print(f"Warning: Invalid commands removed: {invalid}")
        
        if not filtered_commands:
            print("No valid commands provided")
            return False
            
        # 添加命令到AI队列
        self.ai.add_commands(filtered_commands)
        print(f"Added {len(filtered_commands)} commands to AI queue: {filtered_commands}")
        
        # 确保游戏未暂停
        if self.game_state.paused:
            print("Warning: Game is paused. Commands will execute when resumed.")
            
        return True

# 启动游戏
if __name__ == "__main__":
    print("\n---- Simple Tetris Game ----")
    print("Controls:")
    print("  Arrow keys - Move/rotate piece")
    print("  Space - Drop piece")
    print("  A - Toggle AI control")
    print("  F - Toggle auto fall (default: OFF)")
    print("  P - Pause/Resume game")
    print("  +/- - Increase/Decrease fall speed")
    print("  R - Restart (when game over)")
    print("  ESC - Quit")
    print("\nAI Mode Features:")
    print("  - AI can control pieces with commands: left, right, down, rotate, drop")
    print("  - Also supports combo moves: left_drop, right_drop, rotate_drop")
    print("  - When auto fall is OFF, pieces only move by AI/player commands")
    print("----------------------------\n")
    
    # 尝试启动游戏
    try:
        # 检查Pygame是否支持图形界面
        if "dummy" in os.environ.get("SDL_VIDEODRIVER", ""):
            print("Warning: Running in dummy video mode. No window will be shown.")
        
        print("Creating game instance...")
        game = SimpleTetris()
        print("Starting game...")
        game.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 