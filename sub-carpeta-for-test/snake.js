/* Snake Game - funciona con index.html y snake.html */
(function () {
'use strict';

const canvas = document.getElementById('gameCanvas');
if (!canvas) {
    console.error('No se encontró el elemento #gameCanvas');
    return;
}
const ctx = canvas.getContext('2d');
if (!ctx) {
    console.error('Tu navegador no soporta canvas 2D');
    return;
}

const scoreEl = document.getElementById('score');
const bestEl = document.getElementById('best');
const levelEl = document.getElementById('level');
const overlay = document.getElementById('overlay');
const overlayTitle = document.getElementById('overlayTitle');
const overlayMsg = document.getElementById('overlayMsg');
const restartBtn = document.getElementById('restartBtn');

const gridSize = 20;
const tileCount = 20;
const BASE_STEP_MS = 110;

let snake, food, goldFood, dir, nextDir, score, best, level, running, paused, lastStep, rafId, particles;

best = parseInt(localStorage.getItem('snake_best') || '0', 10) || 0;

function init() {
    canvas.width = tileCount * gridSize;
    canvas.height = tileCount * gridSize;
    snake = [{ x: 10, y: 10 }];
    dir = { x: 1, y: 0 };
    nextDir = { x: 1, y: 0 };
    score = 0;
    level = 1;
    running = true;
    paused = false;
    lastStep = 0;
    particles = [];
    placeFood();
    goldFood = null;
    hideOverlay();
    updateHud();
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(loop);
}

function stepInterval() {
    return Math.max(50, BASE_STEP_MS - (level - 1) * 8);
}

function loop(ts) {
    if (!running) return;
    rafId = requestAnimationFrame(loop);
    if (paused) { draw(); return; }
    if (!lastStep) lastStep = ts;
    if (ts - lastStep >= stepInterval()) {
        tick();
        lastStep = ts;
    }
    updateParticles();
    draw();
}

function tick() {
    dir = nextDir;
    const head = { x: snake[0].x + dir.x, y: snake[0].y + dir.y };

    if (head.x < 0 || head.x >= tileCount || head.y < 0 || head.y >= tileCount) {
        gameOver();
        return;
    }
    for (let i = 0; i < snake.length; i++) {
        if (snake[i].x === head.x && snake[i].y === head.y) {
            gameOver();
            return;
        }
    }

    snake.unshift(head);

    if (goldFood && head.x === goldFood.x && head.y === goldFood.y) {
        score += 50;
        spawnParticles(goldFood.x, goldFood.y, '#ffd166');
        if (window.SnakeSound) SnakeSound.gold();
        goldFood = null;
        checkLevel();
    } else if (head.x === food.x && head.y === food.y) {
        score += 10;
        spawnParticles(food.x, food.y, '#ff4444');
        if (window.SnakeSound) SnakeSound.eat();
        placeFood();
        checkLevel();
        if (score % 100 === 0 && !goldFood && Math.random() < 0.5) {
            placeGoldFood();
        }
    } else {
        snake.pop();
    }

    updateHud();
}

function checkLevel() {
    const newLevel = Math.floor(score / 50) + 1;
    if (newLevel > level) {
        level = newLevel;
        if (window.SnakeSound) SnakeSound.levelUp();
    }
}

function draw() {
    ctx.fillStyle = '#0f0f1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= tileCount; i++) {
        ctx.beginPath();
        ctx.moveTo(i * gridSize, 0);
        ctx.lineTo(i * gridSize, canvas.height);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(0, i * gridSize);
        ctx.lineTo(canvas.width, i * gridSize);
        ctx.stroke();
    }

    if (food) {
        ctx.fillStyle = '#ff4444';
        roundRect(food.x * gridSize + 2, food.y * gridSize + 2, gridSize - 4, gridSize - 4, 4);
        ctx.fill();
    }
    if (goldFood) {
        ctx.fillStyle = '#ffd166';
        ctx.shadowColor = '#ffd166';
        ctx.shadowBlur = 8;
        roundRect(goldFood.x * gridSize + 2, goldFood.y * gridSize + 2, gridSize - 4, gridSize - 4, 4);
        ctx.fill();
        ctx.shadowBlur = 0;
    }

    for (let i = 0; i < snake.length; i++) {
        const s = snake[i];
        ctx.fillStyle = i === 0 ? '#7CFF6B' : '#00cc66';
        roundRect(s.x * gridSize + 1, s.y * gridSize + 1, gridSize - 2, gridSize - 2, 5);
        ctx.fill();
    }

    drawParticles();

    if (paused) {
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 28px Segoe UI, Arial';
        ctx.textAlign = 'center';
        ctx.fillText('⏸ Pausa', canvas.width / 2, canvas.height / 2);
        ctx.textAlign = 'left';
    }
}

function roundRect(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
}

function placeFood() {
    let attempts = 0;
    do {
        food = { x: Math.floor(Math.random() * tileCount), y: Math.floor(Math.random() * tileCount) };
        attempts++;
    } while (snake.some(s => s.x === food.x && s.y === food.y) && attempts < 100);
}

function placeGoldFood() {
    let attempts = 0;
    do {
        goldFood = { x: Math.floor(Math.random() * tileCount), y: Math.floor(Math.random() * tileCount) };
        attempts++;
    } while ((snake.some(s => s.x === goldFood.x && s.y === goldFood.y) ||
             (food && goldFood.x === food.x && goldFood.y === food.y)) && attempts < 100);
}

function spawnParticles(gx, gy, color) {
    const cx = gx * gridSize + gridSize / 2;
    const cy = gy * gridSize + gridSize / 2;
    for (let i = 0; i < 8; i++) {
        particles.push({
            x: cx, y: cy,
            vx: (Math.random() - 0.5) * 4,
            vy: (Math.random() - 0.5) * 4,
            life: 1.0,
            color: color,
        });
    }
}

function updateParticles() {
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        p.life -= 0.05;
        if (p.life <= 0) particles.splice(i, 1);
    }
}

function drawParticles() {
    for (const p of particles) {
        ctx.globalAlpha = p.life;
        ctx.fillStyle = p.color;
        ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    }
    ctx.globalAlpha = 1;
}

function gameOver() {
    running = false;
    cancelAnimationFrame(rafId);
    if (window.SnakeSound) SnakeSound.gameOver();
    const isRecord = score > best;
    if (isRecord) {
        best = score;
        localStorage.setItem('snake_best', String(best));
    }
    updateHud();
    showOverlay('Game Over',
        `Puntuación: ${score} · Nivel ${level}` + (isRecord ? ' · ¡Nuevo récord!' : ''));
}

function updateHud() {
    if (scoreEl) scoreEl.textContent = 'Puntuación: ' + score;
    if (levelEl) levelEl.textContent = 'Nivel: ' + level;
    if (bestEl) bestEl.textContent = 'Récord: ' + best;
}

function showOverlay(title, msg) {
    if (overlay) overlay.classList.remove('hidden');
    if (overlayTitle) overlayTitle.textContent = title;
    if (overlayMsg) overlayMsg.textContent = msg;
}

function hideOverlay() {
    if (overlay) overlay.classList.add('hidden');
}

function setDirection(key) {
    const dirs = {
        'ArrowUp': { x: 0, y: -1 }, 'ArrowDown': { x: 0, y: 1 },
        'ArrowLeft': { x: -1, y: 0 }, 'ArrowRight': { x: 1, y: 0 },
        'w': { x: 0, y: -1 }, 's': { x: 0, y: 1 },
        'a': { x: -1, y: 0 }, 'd': { x: 1, y: 0 },
    };
    const nd = dirs[key];
    if (!nd) return;
    if (!running) { init(); return; }
    if (nd.x === -dir.x && nd.y === -dir.y) return;
    nextDir = nd;
}

document.addEventListener('keydown', function (e) {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) {
        e.preventDefault();
    }
    if (e.key === ' ' || e.key === 'p' || e.key === 'P') {
        if (running) { paused = !paused; if (!paused) lastStep = 0; }
        return;
    }
    setDirection(e.key);
});

if (restartBtn) {
    restartBtn.addEventListener('click', function () { init(); });
}

let touchStartX = 0, touchStartY = 0;
canvas.addEventListener('touchstart', function (e) {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
}, { passive: true });

canvas.addEventListener('touchend', function (e) {
    const dx = e.changedTouches[0].clientX - touchStartX;
    const dy = e.changedTouches[0].clientY - touchStartY;
    if (Math.abs(dx) < 20 && Math.abs(dy) < 20) return;
    if (Math.abs(dx) > Math.abs(dy)) {
        setDirection(dx > 0 ? 'ArrowRight' : 'ArrowLeft');
    } else {
        setDirection(dy > 0 ? 'ArrowDown' : 'ArrowUp');
    }
}, { passive: true });

init();
})();
