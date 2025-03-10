// Game elements
const gameBoard = document.querySelector('.game-board');
const startButton = document.getElementById('start-button');
const resetButton = document.getElementById('reset-button');
const scoreElement = document.getElementById('score');
const sunCountElement = document.getElementById('sun-count');
const plantCards = document.querySelectorAll('.plant-card');
const gameOverScreen = document.getElementById('game-over');
const finalScoreElement = document.getElementById('final-score');
const playAgainButton = document.getElementById('play-again');

// Game state
let gameActive = false;
let selectedPlant = null;
let score = 0;
let sunCount = 50;
let zombieInterval;
let sunInterval;
let gameGrid = [];
let zombies = [];
let projectiles = [];
let assetsLoaded = false;

// Grid dimensions
const ROWS = 5;
const COLS = 9;

// Plant types and their properties
const PLANTS = {
    peashooter: {
        cost: 100,
        health: 100,
        image: 'assets/peashooter.png',
        svgImage: 'assets/peashooter.svg',
        attackRate: 2000, // milliseconds
        attackDamage: 20,
        range: 'row',
    },
    sunflower: {
        cost: 50,
        health: 50,
        image: 'assets/sunflower.png',
        svgImage: 'assets/sunflower.svg',
        produceRate: 5000, // milliseconds
        produceAmount: 25,
    },
    wallnut: {
        cost: 50,
        health: 400,
        image: 'assets/wallnut.png',
        svgImage: 'assets/wallnut.svg',
    }
};

// Zombie types and their properties
const ZOMBIES = {
    regular: {
        health: 100,
        damage: 10,
        speed: 1, // cells per second
        image: 'assets/zombie.png',
        svgImage: 'assets/zombie.svg',
        points: 10,
    },
    cone: {
        health: 200,
        damage: 10,
        speed: 0.8,
        image: 'assets/cone-zombie.png',
        svgImage: 'assets/cone-zombie.svg',
        points: 20,
    },
    yi: {  // Adding/fixing the Yi zombie type that was moving too fast
        health: 150,
        damage: 15,
        speed: 0.7,  // Reduced from a higher value to fix the too-fast movement
        image: 'assets/zombie.png',  // Using regular zombie image as fallback
        svgImage: 'assets/zombie.svg',  // Using regular zombie SVG as fallback
        points: 15,
    }
};

// Asset files to convert
const assetsToConvert = [
    { name: 'peashooter', svgPath: 'assets/peashooter.svg', pngPath: 'assets/peashooter.png' },
    { name: 'sunflower', svgPath: 'assets/sunflower.svg', pngPath: 'assets/sunflower.png' },
    { name: 'wallnut', svgPath: 'assets/wallnut.svg', pngPath: 'assets/wallnut.png' },
    { name: 'zombie', svgPath: 'assets/zombie.svg', pngPath: 'assets/zombie.png' },
    { name: 'cone-zombie', svgPath: 'assets/cone-zombie.svg', pngPath: 'assets/cone-zombie.png' },
    { name: 'sun', svgPath: 'assets/sun.svg', pngPath: 'assets/sun.png' },
    { name: 'lawn', svgPath: 'assets/lawn.svg', pngPath: 'assets/lawn.png', width: 900, height: 400 }
];

// Function to convert SVG to PNG
function convertSvgToPng(asset) {
    return new Promise((resolve, reject) => {
        const svgURL = asset.svgPath;
        fetch(svgURL)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed to fetch ${svgURL}: ${response.status} ${response.statusText}`);
                }
                return response.text();
            })
            .then(svgText => {
                // Create a temporary container
                const container = document.createElement('div');
                container.innerHTML = svgText;
                document.body.appendChild(container);
                
                // Get the SVG element
                const svg = container.querySelector('svg');
                if (!svg) {
                    document.body.removeChild(container);
                    reject(new Error(`SVG not found in ${svgURL}`));
                    return;
                }
                
                // Convert to a data URL
                const svgData = new XMLSerializer().serializeToString(svg);
                const width = asset.width || 100;
                const height = asset.height || 100;
                
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                
                const img = new Image();
                const blob = new Blob([svgData], {type: 'image/svg+xml'});
                const url = URL.createObjectURL(blob);
                
                img.onload = function() {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    URL.revokeObjectURL(url);
                    document.body.removeChild(container);
                    
                    // Create a data URL and store it
                    const dataURL = canvas.toDataURL('image/png');
                    
                    // Store the converted image URL
                    asset.dataURL = dataURL;
                    
                    resolve(asset);
                };
                
                img.onerror = function(err) {
                    document.body.removeChild(container);
                    URL.revokeObjectURL(url);
                    console.error("Error loading SVG image:", err);
                    reject(new Error(`Failed to load SVG from ${svgURL}`));
                };
                
                img.src = url;
            })
            .catch(error => {
                console.error(`Error processing ${svgURL}:`, error);
                reject(error);
            });
    });
}

// Update all images with their converted versions
function updateImages() {
    // Update plant cards
    document.querySelectorAll('img[data-img-src]').forEach(img => {
        const imgSrc = img.getAttribute('data-img-src');
        const asset = assetsToConvert.find(a => a.pngPath === imgSrc);
        if (asset && asset.dataURL) {
            img.src = asset.dataURL;
        } else {
            console.warn(`No converted image found for ${imgSrc}`);
        }
    });
}

// Initialize game
function initGame() {
    // Make sure the Game Over screen is hidden
    gameOverScreen.classList.add('hidden');
    
    // Don't recreate everything if assets are still loading
    if (!assetsLoaded) {
        return;
    }
    
    createGameBoard();
    updateSunCount(50);
    score = 0;
    updateScore(0);
    
    plantCards.forEach(card => {
        card.addEventListener('click', () => selectPlant(card));
        updatePlantCardAvailability(card);
    });
    
    startButton.addEventListener('click', startGame);
    resetButton.addEventListener('click', resetGame);
    playAgainButton.addEventListener('click', resetGame);
}

// Create the game board grid
function createGameBoard() {
    gameBoard.innerHTML = '';
    gameGrid = [];
    
    // Set the background image
    const lawnAsset = assetsToConvert.find(a => a.name === 'lawn');
    if (lawnAsset && lawnAsset.dataURL) {
        gameBoard.style.backgroundImage = `url(${lawnAsset.dataURL})`;
    } else {
        // Fallback to a solid color
        gameBoard.style.backgroundColor = "#2E8B57";
    }
    
    for (let row = 0; row < ROWS; row++) {
        gameGrid[row] = [];
        for (let col = 0; col < COLS; col++) {
            const cell = document.createElement('div');
            cell.className = 'cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            
            cell.addEventListener('click', () => {
                if (gameActive && selectedPlant) {
                    placePlant(row, col);
                }
            });
            
            gameBoard.appendChild(cell);
            gameGrid[row][col] = {
                element: cell,
                plant: null,
                zombies: []
            };
        }
    }
}

// Load assets function
function loadAssets() {
    console.log("Loading game assets...");
    const loadingScreen = document.getElementById('loading-screen');
    const loadingProgress = document.getElementById('loading-progress');
    
    // Track progress
    let totalAssets = assetsToConvert.length;
    let loadedAssets = 0;
    
    // Function to update progress
    const updateProgress = () => {
        loadedAssets++;
        const percentage = Math.round((loadedAssets / totalAssets) * 100);
        loadingProgress.textContent = `${percentage}%`;
    };
    
    // Use Promise.all to load all assets in parallel
    const loadPromises = assetsToConvert.map(asset => 
        convertSvgToPng(asset)
            .then((asset) => {
                updateProgress();
                return asset.name;
            })
            .catch(error => {
                console.error(`Failed to load ${asset.name}:`, error);
                updateProgress();
                return null;
            })
    );
    
    Promise.all(loadPromises)
        .then(results => {
            console.log("All assets loaded:", results.filter(Boolean));
            
            // Update all images with their converted versions
            updateImages();
            
            // Hide loading screen
            setTimeout(() => {
                loadingScreen.style.opacity = "0";
                loadingScreen.style.transition = "opacity 0.5s";
                setTimeout(() => {
                    loadingScreen.style.display = "none";
                }, 500);
            }, 500); // Show 100% for a moment
            
            // Update game
            assetsLoaded = true;
            initGame();
        })
        .catch(error => {
            console.error("Error in asset loading:", error);
            // Hide loading screen even on error
            loadingScreen.style.display = "none";
            
            // Try to initialize with fallback graphics
            assetsLoaded = true;
            initGame();
        });
}

// Start the game when the page loads
window.addEventListener('load', () => {
    // First load assets, then initialize
    loadAssets();
});

// Update sun count display
function updateSunCount(amount) {
    sunCount = amount;
    sunCountElement.textContent = sunCount;
    
    // Update plant card availability
    plantCards.forEach(updatePlantCardAvailability);
}

// Update plant card availability based on sun count
function updatePlantCardAvailability(card) {
    const cost = parseInt(card.dataset.cost);
    if (cost > sunCount) {
        card.classList.add('disabled');
    } else {
        card.classList.remove('disabled');
    }
}

// Update game score
function updateScore(amount) {
    score = amount;
    scoreElement.textContent = score;
}

// Select a plant for placement
function selectPlant(card) {
    if (gameActive && !card.classList.contains('disabled')) {
        plantCards.forEach(p => p.classList.remove('selected'));
        card.classList.add('selected');
        selectedPlant = card.dataset.plant;
    }
}

// Place a plant on the game board
function placePlant(row, col) {
    const cell = gameGrid[row][col];
    
    // Check if cell is empty
    if (cell.plant !== null) return;
    
    const plantType = selectedPlant;
    const plantData = PLANTS[plantType];
    
    // Check if enough sun
    if (sunCount < plantData.cost) return;
    
    // Deduct sun cost
    updateSunCount(sunCount - plantData.cost);
    
    // Find the converted image
    const plantAsset = assetsToConvert.find(a => a.name === plantType);
    
    // Create plant element
    const plantElement = document.createElement('div');
    plantElement.className = 'plant';
    
    if (plantAsset && plantAsset.dataURL) {
        plantElement.style.backgroundImage = `url(${plantAsset.dataURL})`;
    } else {
        // Fallback to SVG directly
        plantElement.style.backgroundImage = `url(${plantData.svgImage})`;
    }
    
    // Add to cell
    cell.element.appendChild(plantElement);
    
    // Update game state
    cell.plant = {
        type: plantType,
        health: plantData.health,
        element: plantElement,
        lastAttack: 0,
        lastProduce: 0
    };
    
    // Deselect plant
    plantCards.forEach(p => p.classList.remove('selected'));
    selectedPlant = null;
}

// Spawn a zombie
function spawnZombie() {
    if (!gameActive) return;
    
    // Randomly choose a row
    const row = Math.floor(Math.random() * ROWS);
    
    // Randomly choose a zombie type
    const zombieTypes = Object.keys(ZOMBIES);
    const type = zombieTypes[Math.floor(Math.random() * zombieTypes.length)];
    const zombieData = ZOMBIES[type];
    
    // Find the converted image
    const zombieAsset = assetsToConvert.find(a => a.name === (type === 'cone' ? 'cone-zombie' : 'zombie'));
    
    // Create zombie element
    const zombieElement = document.createElement('div');
    zombieElement.className = 'zombie';
    
    if (zombieAsset && zombieAsset.dataURL) {
        zombieElement.style.backgroundImage = `url(${zombieAsset.dataURL})`;
    } else {
        // Fallback to SVG directly
        zombieElement.style.backgroundImage = `url(${zombieData.svgImage})`;
    }
    
    // Position zombie at far right of the row
    const lastCell = gameGrid[row][COLS - 1];
    lastCell.element.appendChild(zombieElement);
    
    // Add to game state
    const zombie = {
        type,
        row,
        col: COLS - 1,
        position: 0, // 0 = right edge of cell, 1 = left edge
        health: zombieData.health,
        element: zombieElement,
        speed: zombieData.speed
    };
    
    zombies.push(zombie);
    lastCell.zombies.push(zombie);
}

// Create a sun drop
function spawnSun() {
    if (!gameActive) return;
    
    // Find the converted sun image
    const sunAsset = assetsToConvert.find(a => a.name === 'sun');
    
    // Create sun element
    const sun = document.createElement('div');
    sun.className = 'sun';
    
    // Set the background image
    if (sunAsset && sunAsset.dataURL) {
        sun.style.backgroundImage = `url(${sunAsset.dataURL})`;
    } else {
        // Fallback to SVG directly
        sun.style.backgroundImage = `url(assets/sun.svg)`;
    }
    
    // Random column position
    const left = Math.random() * (gameBoard.offsetWidth - 40);
    sun.style.left = `${left}px`;
    
    // Add click handler to collect sun
    sun.addEventListener('click', () => {
        collectSun(sun);
    });
    
    // Add to game board
    gameBoard.appendChild(sun);
    
    // Remove after animation ends
    setTimeout(() => {
        if (sun.parentElement) {
            sun.parentElement.removeChild(sun);
        }
    }, 10000);
}

// Collect sun when clicked
function collectSun(sunElement) {
    // Add sun to count
    updateSunCount(sunCount + 25);
    
    // Remove from board
    if (sunElement.parentElement) {
        sunElement.parentElement.removeChild(sunElement);
    }
}

// Generate sun from sunflowers
function produceSunFromSunflowers() {
    if (!gameActive) return;
    
    const now = Date.now();
    // Find the converted sun image
    const sunAsset = assetsToConvert.find(a => a.name === 'sun');
    
    // Check all sunflowers
    for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
            const cell = gameGrid[row][col];
            if (cell.plant && cell.plant.type === 'sunflower') {
                const sunflower = cell.plant;
                const produceRate = PLANTS.sunflower.produceRate;
                
                // Check if it's time to produce sun
                if (now - sunflower.lastProduce >= produceRate) {
                    // Create a sun above the sunflower
                    const sun = document.createElement('div');
                    sun.className = 'sun';
                    
                    // Set the background image
                    if (sunAsset && sunAsset.dataURL) {
                        sun.style.backgroundImage = `url(${sunAsset.dataURL})`;
                    } else {
                        // Fallback to SVG directly
                        sun.style.backgroundImage = `url(assets/sun.svg)`;
                    }
                    
                    // Position above sunflower
                    const rect = cell.element.getBoundingClientRect();
                    const boardRect = gameBoard.getBoundingClientRect();
                    sun.style.left = `${rect.left - boardRect.left + 10}px`;
                    sun.style.top = `${rect.top - boardRect.top - 20}px`;
                    sun.style.animation = 'none';
                    
                    // Add click handler
                    sun.addEventListener('click', () => {
                        collectSun(sun);
                    });
                    
                    // Add to game board
                    gameBoard.appendChild(sun);
                    
                    // Remove after 5 seconds if not collected
                    setTimeout(() => {
                        if (sun.parentElement) {
                            sun.parentElement.removeChild(sun);
                        }
                    }, 5000);
                    
                    // Update last produce time
                    sunflower.lastProduce = now;
                }
            }
        }
    }
}

// Move zombies
function moveZombies() {
    if (!gameActive) return;
    
    const cellWidth = gameGrid[0][0].element.offsetWidth;
    const step = 0.05; // movement increment
    
    zombies.forEach((zombie, index) => {
        // Movement calculation
        zombie.position += step * zombie.speed;
        
        // Check if moving to previous cell
        if (zombie.position >= 1 && zombie.col > 0) {
            // Remove from current cell
            const currentCell = gameGrid[zombie.row][zombie.col];
            currentCell.zombies = currentCell.zombies.filter(z => z !== zombie);
            
            // Move to previous cell
            zombie.col--;
            zombie.position = 0;
            
            // Add to new cell
            const newCell = gameGrid[zombie.row][zombie.col];
            newCell.zombies.push(zombie);
            newCell.element.appendChild(zombie.element);
            
            // Check if reached leftmost column
            if (zombie.col === 0 && zombie.position > 0.5) {
                gameOver();
                return;
            }
        }
        
        // Update visual position
        zombie.element.style.right = `${(1 - zombie.position) * cellWidth}px`;
        
        // Check for plant collision
        const cell = gameGrid[zombie.row][zombie.col];
        if (cell.plant && zombie.position > 0.5) {
            // Stop zombie movement
            zombie.element.style.right = `${(1 - 0.5) * cellWidth}px`;
            
            // Damage plant
            damageEntity(cell.plant, ZOMBIES[zombie.type].damage / 10);
            
            // Check if plant destroyed
            if (cell.plant.health <= 0) {
                // Remove plant
                cell.element.removeChild(cell.plant.element);
                cell.plant = null;
                
                // Continue zombie movement
                zombie.position = 0.5;
            }
        }
    });
}

// Create projectiles from peashooters
function shootProjectiles() {
    if (!gameActive) return;
    
    const now = Date.now();
    
    // Check all peashooters
    for (let row = 0; row < ROWS; row++) {
        for (let col = 0; col < COLS; col++) {
            const cell = gameGrid[row][col];
            if (cell.plant && cell.plant.type === 'peashooter') {
                const peashooter = cell.plant;
                const attackRate = PLANTS.peashooter.attackRate;
                
                // Check if it's time to shoot
                if (now - peashooter.lastAttack >= attackRate) {
                    // Check if zombies in same row
                    let zombiesInRow = false;
                    for (let c = col + 1; c < COLS; c++) {
                        if (gameGrid[row][c].zombies.length > 0) {
                            zombiesInRow = true;
                            break;
                        }
                    }
                    
                    if (zombiesInRow) {
                        // Create a projectile
                        const projectile = document.createElement('div');
                        projectile.className = 'pea';
                        
                        // Add to cell
                        cell.element.appendChild(projectile);
                        
                        // Add to game state
                        projectiles.push({
                            row,
                            col,
                            element: projectile,
                            damage: PLANTS.peashooter.attackDamage
                        });
                        
                        // Update last attack time
                        peashooter.lastAttack = now;
                    }
                }
            }
        }
    }
}

// Move projectiles
function moveProjectiles() {
    if (!gameActive) return;
    
    const cellWidth = gameGrid[0][0].element.offsetWidth;
    
    projectiles.forEach((projectile, index) => {
        // Get current position
        const style = window.getComputedStyle(projectile.element);
        let left = parseInt(style.left);
        
        // If no left position set, use default
        if (isNaN(left)) {
            left = 40;
        }
        
        // Move right
        left += 5;
        projectile.element.style.left = `${left}px`;
        
        // Check if hit a zombie or went off screen
        let hit = false;
        
        // Check for collision with zombies in same row
        if (left > cellWidth) {
            // Moved to next cell
            projectile.col++;
            
            // Reset position
            projectile.element.style.left = '10px';
            
            // Check if gone off board
            if (projectile.col >= COLS) {
                hit = true;
            } else {
                // Move to new cell
                const currentCell = gameGrid[projectile.row][projectile.col - 1];
                const nextCell = gameGrid[projectile.row][projectile.col];
                
                // Check if hit a zombie
                if (nextCell.zombies.length > 0) {
                    // Damage first zombie
                    const zombie = nextCell.zombies[0];
                    damageEntity(zombie, projectile.damage);
                    
                    // Check if zombie killed
                    if (zombie.health <= 0) {
                        // Remove from cell
                        nextCell.zombies = nextCell.zombies.filter(z => z !== zombie);
                        
                        // Remove from board
                        if (zombie.element.parentElement) {
                            zombie.element.parentElement.removeChild(zombie.element);
                        }
                        
                        // Remove from game state
                        zombies = zombies.filter(z => z !== zombie);
                        
                        // Add score
                        updateScore(score + ZOMBIES[zombie.type].points);
                    }
                    
                    hit = true;
                }
                
                // Move projectile to new cell
                if (!hit) {
                    currentCell.element.removeChild(projectile.element);
                    nextCell.element.appendChild(projectile.element);
                }
            }
        }
        
        // Remove projectile if hit or off screen
        if (hit) {
            if (projectile.element.parentElement) {
                projectile.element.parentElement.removeChild(projectile.element);
            }
            projectiles.splice(index, 1);
        }
    });
}

// Damage an entity (plant or zombie)
function damageEntity(entity, damage) {
    entity.health -= damage;
}

// Start the game
function startGame() {
    if (gameActive) return;
    
    gameActive = true;
    startButton.disabled = true;
    
    // Spawn zombies every 5-10 seconds
    zombieInterval = setInterval(() => {
        spawnZombie();
    }, Math.random() * 5000 + 5000);
    
    // Spawn sun every 10 seconds
    sunInterval = setInterval(() => {
        spawnSun();
    }, 10000);
    
    // Start game loop
    gameLoop();
}

// Game loop
function gameLoop() {
    if (!gameActive) return;
    
    // Update game state
    moveZombies();
    moveProjectiles();
    shootProjectiles();
    produceSunFromSunflowers();
    
    // Continue loop
    requestAnimationFrame(gameLoop);
}

// Game over
function gameOver() {
    gameActive = false;
    clearInterval(zombieInterval);
    clearInterval(sunInterval);
    
    // Show game over screen
    finalScoreElement.textContent = score;
    gameOverScreen.classList.remove('hidden');
}

// Reset the game
function resetGame() {
    gameActive = false;
    clearInterval(zombieInterval);
    clearInterval(sunInterval);
    
    // Reset game state
    zombies = [];
    projectiles = [];
    selectedPlant = null;
    
    // Hide game over screen
    gameOverScreen.classList.add('hidden');
    
    // Reset the board
    initGame();
    
    // Enable start button
    startButton.disabled = false;
} 