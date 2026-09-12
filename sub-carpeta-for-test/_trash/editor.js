/* Editor de niveles para Snake Game */
(function () {
'use strict';

const canvas = document.getElementById('editorCanvas');
const ctx = canvas.getContext('2d');
const levelNameInput = document.getElementById('levelName');
const saveBtn = document.getElementById('saveBtn');
const clearBtn = document.getElementById('clearBtn');
const levelList = document.getElementById('level-list');
const playClassicBtn = document.getElementById('playClassicBtn');

const gridSize = 20;
const tileCount = 20;

let walls = new Set();
let painting = false;
let paintValue = true; // true = añadir muro, false = quitar

function key(x, y) { return x + ',' + y; }

function draw() {
    ctx.fillStyle = '#0f0f1a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // cuadrícula
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
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

    // muros
    ctx.fillStyle = '#8a8aa8';
    for (const k of walls) {
        const [x, y] = k.split(',').map(Number);
        ctx.fillRect(x * gridSize + 1, y * gridSize + 1, gridSize - 2, gridSize - 2);
    }
}

function cellFromEvent(e) {
    const rect = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - rect.left) / (rect.width / tileCount));
    const y = Math.floor((e.clientY - rect.top) / (rect.height / tileCount));
    if (x < 0 || x >= tileCount || y < 0 || y >= tileCount) return null;
    return { x, y };
}

function paintAt(e) {
    const cell = cellFromEvent(e);
    if (!cell) return;
    if (paintValue) walls.add(key(cell.x, cell.y));
    else walls.delete(key(cell.x, cell.y));
    draw();
}

canvas.addEventListener('pointerdown', function (e) {
    painting = true;
    // si la primera celda ya tenía muro, este trazo borra; si no, pinta
    const cell = cellFromEvent(e);
    paintValue = !(cell && walls.has(key(cell.x, cell.y)));
    paintAt(e);
});
canvas.addEventListener('pointermove', function (e) {
    if (painting) paintAt(e);
});
window.addEventListener('pointerup', function () { painting = false; });
canvas.addEventListener('contextmenu', function (e) {
    e.preventDefault();
    const cell = cellFromEvent(e);
    if (cell) { walls.delete(key(cell.x, cell.y)); draw(); }
});

saveBtn.addEventListener('click', function () {
    let n = parseInt(levelNameInput.value, 10);
    if (!n || n < 2) n = 2;
    const data = Array.from(walls).map(k => k.split(',').map(Number));
    localStorage.setItem('snake_custom_level_' + n, JSON.stringify(data));
    refreshList();
    saveBtn.textContent = '✅ Guardado';
    setTimeout(function () { saveBtn.textContent = '💾 Guardar nivel'; }, 1200);
});

clearBtn.addEventListener('click', function () {
    walls.clear();
    draw();
});

playClassicBtn.addEventListener('click', function () {
    localStorage.setItem('snake_selected_level', 'classic');
    window.location.href = 'index.html';
});

function refreshList() {
    levelList.innerHTML = '';
    const names = ['classic'];
    for (let i = 2; i <= 20; i++) {
        if (localStorage.getItem('snake_custom_level_' + i)) names.push(String(i));
        else if (i > 2 && !localStorage.getItem('snake_custom_level_' + (i - 1))) break;
    }
    for (const name of names) {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'level-chip';
        chip.textContent = name === 'classic' ? 'Clásico' : 'Nivel ' + name;
        chip.addEventListener('click', function () {
            localStorage.setItem('snake_selected_level', name);
            window.location.href = 'index.html';
        });
        const del = document.createElement('button');
        del.type = 'button';
        del.className = 'level-chip delete';
        del.textContent = '✕';
        del.title = 'Borrar nivel';
        del.addEventListener('click', function (ev) {
            ev.stopPropagation();
            localStorage.removeItem('snake_custom_level_' + name);
            refreshList();
        });
        const wrap = document.createElement('span');
        wrap.className = 'level-chip-wrap';
        wrap.appendChild(chip);
        wrap.appendChild(del);
        levelList.appendChild(wrap);
    }
}

// cargar un nivel existente en el editor si se llega con ?level=N
const params = new URLSearchParams(window.location.search);
const editLevel = params.get('level');
if (editLevel) {
    const raw = localStorage.getItem('snake_custom_level_' + editLevel);
    if (raw) {
        walls = new Set(JSON.parse(raw).map(c => key(c[0], c[1])));
        levelNameInput.value = editLevel;
    }
    history.replaceState(null, '', 'editor.html');
}

draw();
refreshList();
})();
