with open('games/tetris/tetris_agent.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复第508行的缩进问题
if 'except KeyboardInterrupt:' in lines[507]:
    lines[507] = '    except KeyboardInterrupt:\n'

with open('games/tetris/tetris_agent.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Successfully fixed indentation in tetris_agent.py') 