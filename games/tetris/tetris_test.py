"""
简单的Pygame测试程序，用于验证Pygame是否能正常工作
"""
import pygame
import sys
import time

def main():
    # 初始化Pygame
    pygame.init()
    
    # 打印Pygame版本信息
    print(f"Pygame version: {pygame.version.ver}")
    print(f"SDL version: {pygame.version.SDL}")
    
    # 创建窗口
    width, height = 400, 400
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Pygame Test")
    
    # 设置颜色
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    
    # 主循环
    running = True
    clock = pygame.time.Clock()
    start_time = time.time()
    
    try:
        while running and time.time() - start_time < 30:  # 最多运行30秒
            # 处理事件
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                # 按ESC键退出
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
            
            # 清屏
            screen.fill(BLACK)
            
            # 绘制一些内容
            # 1. 绘制矩形
            pygame.draw.rect(screen, RED, (50, 50, 100, 100))
            
            # 2. 绘制圆形
            pygame.draw.circle(screen, GREEN, (250, 100), 50)
            
            # 3. 绘制线条
            pygame.draw.line(screen, BLUE, (50, 200), (350, 200), 5)
            
            # 4. 绘制文本
            font = pygame.font.SysFont(None, 36)
            text = font.render("Pygame Test", True, WHITE)
            screen.blit(text, (width // 2 - text.get_width() // 2, 300))
            
            # 显示剩余时间
            seconds_left = int(30 - (time.time() - start_time))
            time_text = font.render(f"Closing in: {seconds_left}s", True, WHITE)
            screen.blit(time_text, (width // 2 - time_text.get_width() // 2, 350))
            
            # 更新屏幕
            pygame.display.flip()
            
            # 控制帧率
            clock.tick(60)
    
    except Exception as e:
        print(f"Error during pygame execution: {e}")
    finally:
        pygame.quit()
        print("Pygame test completed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Failed to run pygame: {e}")
        sys.exit(1) 