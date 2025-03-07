import re

# 读取文件
with open('games/tetris/tetris_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 使用正则表达式修复缩进
content = content.replace('    \nexcept KeyboardInterrupt:', '    \n    except KeyboardInterrupt:')
content = content.replace('\nexcept KeyboardInterrupt:', '\n    except KeyboardInterrupt:')

# 写回文件
with open('games/tetris/tetris_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Successfully fixed indentation in tetris_agent.py') 