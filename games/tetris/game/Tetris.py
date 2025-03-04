import pygame
import random
import logging
import os

# Get the logger
logger = logging.getLogger("TetrisAgent.Game")

"""
10 x 20 grid
play_height = 2 * play_width

tetriminos:
    0 - S - green
    1 - Z - red
    2 - I - cyan
    3 - O - yellow
    4 - J - blue
    5 - L - orange
    6 - T - purple
"""

pygame.font.init()

# global variables

col = 10  # 10 columns
row = 10  # 10 rows (changed from 20 to make the game faster)
s_width = 800  # window width
s_height = 550  # window height (reduced from 750 to account for shorter play area)
play_width = 300  # play window width; 300/10 = 30 width per block
play_height = 300  # play window height; 300/10 = 30 height per block (adjusted for 10 rows)
block_size = 30  # size of block

top_left_x = (s_width - play_width) // 2
top_left_y = s_height - play_height - 50

# Initialize global paths
filepath = "./highscore.txt"
fontpath = None  # Default to None - will use system font
# We'll use the same font for all purposes to simplify
fontpath_mario = None

# Helper function to safely get a font with fallback
def safe_font(size, font_path=None):
    """Get a font with proper fallback to system fonts if needed"""
    try:
        # Try the specified font path first (if provided)
        if font_path and os.path.exists(font_path):
            return pygame.font.Font(font_path, size)
        
        # If no font path or it doesn't exist, try the global fontpath
        elif fontpath and os.path.exists(fontpath):
            return pygame.font.Font(fontpath, size)
        
        # If all else fails, use system font
        else:
            return pygame.font.SysFont('comicsans', size)
    except Exception as e:
        # Log the error and use system font
        logger.warning(f"Font loading error: {e}")
        return pygame.font.SysFont('comicsans', size)

# shapes formats

S = [['.....',
      '.....',
      '..00.',
      '.00..',
      '.....'],
     ['.....',
      '..0..',
      '..00.',
      '...0.',
      '.....']]

Z = [['.....',
      '.....',
      '.00..',
      '..00.',
      '.....'],
     ['.....',
      '..0..',
      '.00..',
      '.0...',
      '.....']]

I = [['.....',
      '..0..',
      '..0..',
      '..0..',
      '..0..'],
     ['.....',
      '0000.',
      '.....',
      '.....',
      '.....']]

O = [['.....',
      '.....',
      '.00..',
      '.00..',
      '.....']]

J = [['.....',
      '.0...',
      '.000.',
      '.....',
      '.....'],
     ['.....',
      '..00.',
      '..0..',
      '..0..',
      '.....'],
     ['.....',
      '.....',
      '.000.',
      '...0.',
      '.....'],
     ['.....',
      '..0..',
      '..0..',
      '.00..',
      '.....']]

L = [['.....',
      '...0.',
      '.000.',
      '.....',
      '.....'],
     ['.....',
      '..0..',
      '..0..',
      '..00.',
      '.....'],
     ['.....',
      '.....',
      '.000.',
      '.0...',
      '.....'],
     ['.....',
      '.00..',
      '..0..',
      '..0..',
      '.....']]

T = [['.....',
      '..0..',
      '.000.',
      '.....',
      '.....'],
     ['.....',
      '..0..',
      '..00.',
      '..0..',
      '.....'],
     ['.....',
      '.....',
      '.000.',
      '..0..',
      '.....'],
     ['.....',
      '..0..',
      '.00..',
      '..0..',
      '.....']]

# index represents the shape
shapes = [S, Z, I, O, J, L, T]
shape_colors = [(0, 255, 0), (255, 0, 0), (0, 255, 255), (255, 255, 0), (255, 165, 0), (0, 0, 255), (128, 0, 128)]


# class to represent each of the pieces


class Piece(object):
    def __init__(self, x, y, shape):
        self.x = x
        self.y = y
        self.shape = shape
        self.color = shape_colors[shapes.index(shape)]  # choose color from the shape_color list
        self.rotation = 0  # chooses the rotation according to index


# initialise the grid
def create_grid(locked_pos={}):
    grid = [[(0, 0, 0) for x in range(col)] for y in range(row)]  # grid represented rgb tuples

    # locked_positions dictionary
    # (x,y):(r,g,b)
    for y in range(row):
        for x in range(col):
            if (x, y) in locked_pos:
                color = locked_pos[
                    (x, y)]  # get the value color (r,g,b) from the locked_positions dictionary using key (x,y)
                grid[y][x] = color  # set grid position to color

    return grid


def convert_shape_format(piece):
    positions = []
    shape_format = piece.shape[piece.rotation % len(piece.shape)]  # get the desired rotated shape from piece

    '''
    e.g.
       ['.....',
        '.....',
        '..00.',
        '.00..',
        '.....']
    '''
    for i, line in enumerate(shape_format):  # i gives index; line gives string
        row = list(line)  # makes a list of char from string
        for j, column in enumerate(row):  # j gives index of char; column gives char
            if column == '0':
                positions.append((piece.x + j, piece.y + i))

    for i, pos in enumerate(positions):
        positions[i] = (pos[0] - 2, pos[1] - 4)  # offset according to the input given with dot and zero

    return positions


# checks if current position of piece in grid is valid
def valid_space(piece, grid):
    # makes a 2D list of all the possible (x,y)
    accepted_pos = [[(x, y) for x in range(col) if grid[y][x] == (0, 0, 0)] for y in range(row)]
    # removes sub lists and puts (x,y) in one list; easier to search
    accepted_pos = [x for item in accepted_pos for x in item]

    formatted_shape = convert_shape_format(piece)

    for pos in formatted_shape:
        if pos not in accepted_pos:
            if pos[1] >= 0:
                return False
    return True


# check if piece is out of board
def check_lost(positions):
    for pos in positions:
        x, y = pos
        if y < 1:
            return True
    return False


# chooses a shape randomly from shapes list
def get_shape():
    return Piece(5, 0, random.choice(shapes))


# draws text in the middle
def draw_text_middle(text, size, color, surface):
    # Use our safe font helper
    font = safe_font(size)
    label = font.render(text, 1, color)
    
    surface.blit(label, (top_left_x + play_width/2 - (label.get_width() / 2), top_left_y + play_height/2 - label.get_height()/2))

    # draws the lines of the grid for the game
def draw_grid(surface):
    r = g = b = 0
    grid_color = (r, g, b)

    for i in range(row):
        # draw grey horizontal lines
        pygame.draw.line(surface, grid_color, (top_left_x, top_left_y + i * block_size),
                         (top_left_x + play_width, top_left_y + i * block_size))
        for j in range(col):
            # draw grey vertical lines
            pygame.draw.line(surface, grid_color, (top_left_x + j * block_size, top_left_y),
                             (top_left_x + j * block_size, top_left_y + play_height))


# clear a row when it is filled
def clear_rows(grid, locked):
    # need to check if row is clear then shift every other row above down one
    increment = 0
    for i in range(len(grid) - 1, -1, -1):      # start checking the grid backwards
        grid_row = grid[i]                      # get the last row
        if (0, 0, 0) not in grid_row:           # if there are no empty spaces (i.e. black blocks)
            increment += 1
            # add positions to remove from locked
            index = i                           # row index will be constant
            for j in range(len(grid_row)):
                try:
                    del locked[(j, i)]          # delete every locked element in the bottom row
                except ValueError:
                    continue

    # shift every row one step down
    # delete filled bottom row
    # add another empty row on the top
    # move down one step
    if increment > 0:
        # sort the locked list according to y value in (x,y) and then reverse
        # reversed because otherwise the ones on the top will overwrite the lower ones
        for key in sorted(list(locked), key=lambda a: a[1])[::-1]:
            x, y = key
            if y < index:                       # if the y value is above the removed index
                new_key = (x, y + increment)    # shift position to down
                locked[new_key] = locked.pop(key)

    return increment


# draws the upcoming piece
def draw_next_shape(piece, surface):
    font = pygame.font.Font(fontpath, 30)
    label = font.render('Next shape', 1, (255, 255, 255))

    start_x = top_left_x + play_width + 50
    start_y = top_left_y + (play_height / 2 - 100)

    shape_format = piece.shape[piece.rotation % len(piece.shape)]

    for i, line in enumerate(shape_format):
        row = list(line)
        for j, column in enumerate(row):
            if column == '0':
                pygame.draw.rect(surface, piece.color, (start_x + j*block_size, start_y + i*block_size, block_size, block_size), 0)

    surface.blit(label, (start_x, start_y - 30))

    # pygame.display.update()


# draws the content of the window
def draw_window(surface, grid, score=0, last_score=0):
    surface.fill((0, 0, 0))  # fill with black
    
    # Tetris Title
    pygame.font.init()  # initialise font
    font = safe_font(65)
    label = font.render('TETRIS', 1, (255, 255, 255))
    surface.blit(label, (top_left_x + play_width / 2 - (label.get_width() / 2), 30))
    
    # Current Score
    font = safe_font(30)
    label = font.render('Score: ' + str(score), 1, (255, 255, 255))
    
    sx = top_left_x + play_width + 50
    sy = top_left_y + play_height/2 - 100
    
    surface.blit(label, (sx + 20, sy + 160))
    
    # Last Score
    font = safe_font(30)
    label = font.render('High Score: ' + str(last_score), 1, (255, 255, 255))
    
    sx = top_left_x - 240
    sy = top_left_y + 200
    
    surface.blit(label, (sx + 20, sy + 160))

    # draw content of the grid
    for i in range(row):
        for j in range(col):
            # pygame.draw.rect()
            # draw a rectangle shape
            # rect(Surface, color, Rect, width=0) -> Rect
            pygame.draw.rect(surface, grid[i][j],
                             (top_left_x + j * block_size, top_left_y + i * block_size, block_size, block_size), 0)

    # draw vertical and horizontal grid lines
    draw_grid(surface)

    # draw rectangular border around play area
    border_color = (255, 255, 255)
    pygame.draw.rect(surface, border_color, (top_left_x, top_left_y, play_width, play_height), 4)

    # pygame.display.update()


# update the score txt file with high score
def update_score(new_score):
    score = get_max_score()

    with open(filepath, 'w') as file:
        if new_score > score:
            file.write(str(new_score))
        else:
            file.write(str(score))


# get the high score from the file
def get_max_score():
    with open(filepath, 'r') as file:
        lines = file.readlines()        # reads all the lines and puts in a list
        score = int(lines[0].strip())   # remove \n

    return score


def main(window):
    logger.info("Game initialization started")
    locked_positions = {}
    create_grid(locked_positions)

    change_piece = False
    run = True
    current_piece = get_shape()
    next_piece = get_shape()
    clock = pygame.time.Clock()
    fall_time = 0
    fall_speed = 0.75  # Fall speed in seconds
    level_time = 0
    score = 0
    last_score = get_max_score()
    logger.info(f"Initialization complete: fall_speed={fall_speed}, score={score}, last_score={last_score}")
    
    # For AI control, we need to return information about the game state
    # Return the current piece position, grid state, and next piece
    game_info = None
    
    # Debug variables to trace execution
    frame_count = 0
    last_debug = pygame.time.get_ticks()
    start_time = pygame.time.get_ticks()
    
    # Explicitly update the display and add a delay to ensure window visibility
    window.fill((0, 0, 0))
    font = safe_font(60)
    label = font.render('Tetris Starting...', 1, (255, 255, 255))
    window.blit(label, (top_left_x + play_width/2 - (label.get_width()/2), top_left_y + play_height/2 - label.get_height()/2))
    pygame.display.update()
    pygame.time.delay(2000)  # 2-second delay to ensure window is visible
    logger.info("Initial delay complete, starting main game loop")

    # Monitor for Q key at game level
    try:
        import keyboard
        def check_q_key():
            if keyboard.is_pressed('q'):
                logger.info("Q key pressed at system level - terminating game")
                return True
            return False
    except ImportError:
        logger.warning("Keyboard module not available for global key monitoring")
        def check_q_key():
            return False

    # Force wait for any key press to start dropping pieces
    logger.info("Ready to start game. Pieces will start dropping.")
    pygame.time.delay(1000)  # Add a 1-second delay before game starts

    # Game is initialized with pieces ready to drop but paused initially
    # Set paused flag to False to allow game to proceed immediately 
    paused = False
    game_lost = False
    
    # Track the last key press time to avoid processing duplicates
    last_key_press = {
        pygame.K_LEFT: 0,
        pygame.K_RIGHT: 0,
        pygame.K_UP: 0,
        pygame.K_DOWN: 0,
        pygame.K_q: 0,
        pygame.K_p: 0
    }
    key_cooldown = 100  # milliseconds between key presses

    while run:
        # Debug tracking
        frame_count += 1
        current_time = pygame.time.get_ticks()
        elapsed_time = (current_time - start_time) / 1000
        
        if current_time - last_debug > 5000:  # Log every 5 seconds
            logger.info(f"Game running: frame {frame_count}, elapsed time: {elapsed_time:.1f}s")
            last_debug = current_time
            
        # Check for Q key at system level
        if check_q_key():
            logger.info("Q key detected, exiting game")
            run = False
            break
        
        grid = create_grid(locked_positions)
        fall_time += clock.get_rawtime()
        level_time += clock.get_rawtime()
        # Clock tick updates
        clock.tick(30)  # Cap at 30 FPS
        
        # Game state update logic based on time
        if not paused and not game_lost:
            if level_time/1000 > 5:    # make the difficulty harder every 10 seconds
                level_time = 0
                if fall_speed > 0.15:   # until fall speed is 0.15
                    fall_speed -= 0.005
                    logger.debug(f"Speed updated: fall_speed={fall_speed}")

            if fall_time / 1000 > fall_speed:
                fall_time = 0
                current_piece.y += 1
                if not valid_space(current_piece, grid) and current_piece.y > 0:
                    current_piece.y -= 1
                    # since only checking for down - either reached bottom or hit another piece
                    # need to lock the piece position
                    # need to generate new piece
                    change_piece = True

        # Handle key states (for AI control that might not generate events)
        keys = pygame.key.get_pressed()
        if not paused:
            # Left key (with cooldown)
            if keys[pygame.K_LEFT] and (current_time - last_key_press[pygame.K_LEFT]) > key_cooldown:
                logger.debug("Tetris received LEFT key (from key state)")
                current_piece.x -= 1
                if not valid_space(current_piece, grid):
                    current_piece.x += 1
                last_key_press[pygame.K_LEFT] = current_time

            # Right key (with cooldown)
            if keys[pygame.K_RIGHT] and (current_time - last_key_press[pygame.K_RIGHT]) > key_cooldown:
                logger.debug("Tetris received RIGHT key (from key state)")
                current_piece.x += 1
                if not valid_space(current_piece, grid):
                    current_piece.x -= 1
                last_key_press[pygame.K_RIGHT] = current_time

            # Down key (with cooldown)
            if keys[pygame.K_DOWN] and (current_time - last_key_press[pygame.K_DOWN]) > key_cooldown:
                logger.debug("Tetris received DOWN key (from key state)")
                current_piece.y += 1
                if not valid_space(current_piece, grid):
                    current_piece.y -= 1
                last_key_press[pygame.K_DOWN] = current_time

            # Up key (with cooldown)
            if keys[pygame.K_UP] and (current_time - last_key_press[pygame.K_UP]) > key_cooldown:
                logger.debug("Tetris received UP key (from key state)")
                current_piece.rotation = (current_piece.rotation + 1) % len(current_piece.shape)
                if not valid_space(current_piece, grid):
                    current_piece.rotation = (current_piece.rotation - 1) % len(current_piece.shape)
                last_key_press[pygame.K_UP] = current_time

        for event in pygame.event.get():
            # Process events as they come
            if event.type == pygame.QUIT:
                logger.info('Received pygame.QUIT event, setting run to False')
                run = False
                # Don't quit pygame immediately, just exit the game loop
                # This allows the caller to handle cleanup
                break
                
            elif event.type == pygame.KEYDOWN:
                # Add Q key handling to quit game
                if event.key == pygame.K_q:
                    logger.info("Q key pressed - quitting game")
                    run = False
                    # Don't force exit, allow clean termination
                    # Return special "QUIT" signal
                    return "QUIT"
                
                # Handle pause with P key
                if event.key == pygame.K_p:
                    paused = not paused
                    logger.info(f"Game {'paused' if paused else 'resumed'}")
                    continue
                
                if paused:
                    continue  # Skip other key processing if paused
                
                # Only process a key if it's not on cooldown
                if event.key in last_key_press and (current_time - last_key_press[event.key]) <= key_cooldown:
                    continue  # Skip if key was recently pressed
                    
                if event.key == pygame.K_LEFT:
                    logger.debug("Tetris received LEFT key (from event)")
                    current_piece.x -= 1  # move x position left
                    if not valid_space(current_piece, grid):
                        current_piece.x += 1
                    last_key_press[pygame.K_LEFT] = current_time

                elif event.key == pygame.K_RIGHT:
                    logger.debug("Tetris received RIGHT key (from event)")
                    current_piece.x += 1  # move x position right
                    if not valid_space(current_piece, grid):
                        current_piece.x -= 1
                    last_key_press[pygame.K_RIGHT] = current_time

                elif event.key == pygame.K_DOWN:
                    logger.debug("Tetris received DOWN key (from event)")
                    # move shape down
                    current_piece.y += 1
                    if not valid_space(current_piece, grid):
                        current_piece.y -= 1
                    last_key_press[pygame.K_DOWN] = current_time

                elif event.key == pygame.K_UP:
                    logger.debug("Tetris received UP key (from event)")
                    # rotate shape
                    current_piece.rotation = (current_piece.rotation + 1) % len(current_piece.shape)
                    if not valid_space(current_piece, grid):
                        current_piece.rotation = (current_piece.rotation - 1) % len(current_piece.shape)
                    last_key_press[pygame.K_UP] = current_time

        if paused:
            # Display pause message
            draw_text_middle('Game Paused - Press P to continue', 30, (255, 255, 255), window)
            pygame.display.update()
            continue

        piece_pos = convert_shape_format(current_piece)

        # draw the piece on the grid by giving color in the piece locations
        for i in range(len(piece_pos)):
            x, y = piece_pos[i]
            if y >= 0:
                grid[y][x] = current_piece.color

        if change_piece:  # if the piece is locked
            for pos in piece_pos:
                p = (pos[0], pos[1])
                locked_positions[p] = current_piece.color       # add the key and value in the dictionary
            current_piece = next_piece
            next_piece = get_shape()
            change_piece = False
            
            # Getting score by calling clear_rows method and adding it to 'score'
            score += clear_rows(grid, locked_positions) * 10
            
            # Update the game info after rows are cleared and score is updated
            game_info = {
                'current_piece': {
                    'x': current_piece.x,
                    'y': current_piece.y,
                    'shape': current_piece.shape,
                    'rotation': current_piece.rotation,
                    'color': current_piece.color
                },
                'next_piece': {
                    'shape': next_piece.shape,
                    'color': next_piece.color
                },
                'grid': grid,
                'score': score
            }
            
            # Check if game is lost
            if check_lost(locked_positions):
                logger.info(f"Game over! Final score: {score}")
                draw_text_middle("Game Over! Score: " + str(score), 40, (255, 255, 255), window)
                pygame.display.update()
                pygame.time.delay(1500)
                game_lost = True
                
                # Update high score if needed
                if score > last_score:
                    update_score(score)
                    last_score = score
                    logger.info(f"New high score: {score}")
                
                # Don't quit immediately, wait for Q key
                draw_text_middle("Press Q to quit", 40, (255, 255, 255), window)
                pygame.display.update()
                continue

        # Drawing everything to window
        draw_window(window, grid, score, last_score)
        draw_next_shape(next_piece, window)
        pygame.display.update()

        # We'll never reach this if the game is lost because of the continue
        if game_lost:
            # Let the caller handle this, but set all the flags
            logger.info("Game is lost, exiting main loop")
            run = False

    # Update the game info one last time before returning
    game_info = {
        'current_piece': {
            'x': current_piece.x,
            'y': current_piece.y,
            'shape': current_piece.shape,
            'rotation': current_piece.rotation,
            'color': current_piece.color
        },
        'next_piece': {
            'shape': next_piece.shape,
            'color': next_piece.color
        },
        'grid': grid,
        'score': score
    }
    
    # Return the current game state to the agent
    return game_info


def main_menu(window):
    logger.info("Starting main menu")
    run = True
    while run:
        window.fill((0, 0, 0))
        
        # Use our safe font helper
        font = safe_font(60)
        label = font.render('Press any key to begin', 1, (255, 255, 255))
        
        window.blit(label, (top_left_x + play_width/2 - (label.get_width()/2), top_left_y + play_height/2 - label.get_height()/2))
        pygame.display.update()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                logger.info("Quit event received in main menu")
                run = False
                return None  # Return without quitting pygame
            
            if event.type == pygame.KEYDOWN:
                logger.info(f"Key pressed in main menu: {pygame.key.name(event.key)}")
                if event.key == pygame.K_q:
                    logger.info("Q key pressed in main menu - exiting")
                    return "QUIT"
                    
                logger.info("Starting main game from menu")
                result = main(window)
                logger.info(f"Main game returned: {result}")
                return result  # Pass the return value from main
        
    # Don't quit pygame here, let the caller handle it
    logger.info("Exiting main menu normally")
    return None


if __name__ == '__main__':
    # This is only used when running this file directly
    win = pygame.display.set_mode((s_width, s_height))
    pygame.display.set_caption('Tetris')

    main_menu(win)  # start game
    pygame.quit()   # Quit pygame only when running as standalone
