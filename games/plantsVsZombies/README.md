# Plants vs Zombies HTML Game

A simplified Plants vs Zombies clone implemented using HTML, CSS, and JavaScript.

## Game Overview

This is a browser-based version of the popular Plants vs Zombies tower defense game. Plant different types of defensive plants to protect your lawn from incoming zombies.

## How to Play

### Running the Game (Easy Method)

1. **Windows**: Double-click the `run_game.bat` file
2. **Mac/Linux**: In terminal, navigate to the game directory and run `chmod +x run_game.sh && ./run_game.sh`

The game will automatically start a local web server and open in your default browser.

### Running the Game (Manual Method)

1. Open `index.html` in your web browser
   - For best results, use a local web server: `python -m http.server` and then visit `http://localhost:8000`
2. Wait for the loading screen to finish as SVG assets are converted to PNG
3. Click the "Start Game" button to begin
4. Select plants from the plant selection bar (costs sun)
5. Click on a lawn tile to place the selected plant
6. Defend your lawn against the zombies!

## Game Features

- **3 Types of Plants:**
  - **Peashooter** - Shoots peas at zombies
  - **Sunflower** - Generates sun over time
  - **Wallnut** - Acts as a defensive barrier

- **2 Types of Zombies:**
  - **Regular Zombie** - Basic zombie with moderate health
  - **Cone Zombie** - Tougher zombie with a traffic cone for protection

- **Resource Management:**
  - Collect sun that falls from the sky
  - Generate additional sun from sunflowers
  - Use sun to purchase and place plants

## Controls

- **Mouse Click** - Select plants and place them on the lawn
- **Start Button** - Begin the game
- **Reset Button** - Reset the game

## Technical Implementation

The game is built using standard web technologies:
- HTML for structure
- CSS for styling
- JavaScript for game logic

No external libraries or frameworks are used, making it easy to run in any modern browser.

### SVG to PNG Conversion

This game uses SVG graphics that are automatically converted to PNG format on load:
- Original SVG assets are in the `assets/` folder
- The game dynamically converts these to PNG for display
- No manual conversion is needed - just wait for the loading screen to complete

## Troubleshooting

If you encounter any issues:

1. **Images not loading**: The game automatically converts SVG to PNG on startup. Make sure to wait for the loading screen to complete.
2. **Game doesn't start**: Try using a modern browser like Chrome, Firefox, or Edge.
3. **Performance issues**: Reduce other applications running in the background.

## Future Enhancements

Potential features for future development:
- More plant types
- Additional zombie varieties
- Level progression
- Sound effects and music
- Mobile touch support

## License

This project is created for educational purposes as part of the GamingAgent project. 