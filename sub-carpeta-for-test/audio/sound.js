/* Snake Game - Efectos de sonido generados con Web Audio API (sin archivos externos) */
(function () {
'use strict';

// Este módulo está pensado para el navegador. Si se ejecuta en Node
// (p. ej. `node sound.js`), no hay window/document: salimos sin error.
if (typeof window === 'undefined' || typeof document === 'undefined') return;

let audioCtx = null;

function getCtx() {
    if (!audioCtx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        audioCtx = new AC();
    }
    if (audioCtx.state === 'suspended') audioCtx.resume();
    return audioCtx;
}

/** Reproduce un tono con envolvente simple */
function tone(freq, duration, type, volume, when) {
    const ctx = getCtx();
    if (!ctx) return;
    const t0 = ctx.currentTime + (when || 0);
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type || 'square';
    osc.frequency.setValueAtTime(freq, t0);
    gain.gain.setValueAtTime(volume || 0.15, t0);
    gain.gain.exponentialRampToValueAtTime(0.001, t0 + duration);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t0);
    osc.stop(t0 + duration + 0.05);
}

/** Sonido al comer comida normal: blip corto ascendente */
function playEat() {
    tone(440, 0.08, 'square', 0.12);
    tone(660, 0.10, 'square', 0.12, 0.06);
}

/** Sonido al comer comida dorada: arpegio brillante */
function playGold() {
    tone(523, 0.09, 'triangle', 0.15);
    tone(659, 0.09, 'triangle', 0.15, 0.07);
    tone(784, 0.09, 'triangle', 0.15, 0.14);
    tone(1047, 0.15, 'triangle', 0.15, 0.21);
}

/** Sonido de Game Over: descenso grave */
function playGameOver() {
    tone(330, 0.18, 'sawtooth', 0.12);
    tone(262, 0.18, 'sawtooth', 0.12, 0.15);
    tone(196, 0.30, 'sawtooth', 0.12, 0.30);
}

/** Sonido al subir de nivel */
function playLevelUp() {
    tone(523, 0.08, 'sine', 0.15);
    tone(784, 0.12, 'sine', 0.15, 0.08);
}

window.SnakeSound = {
    eat: playEat,
    gold: playGold,
    gameOver: playGameOver,
    levelUp: playLevelUp,
};

// Desbloqueo del audio: los navegadores requieren un gesto del usuario
// para crear/reanudar el AudioContext. Lo hacemos en la primera interacción.
function unlock() {
    getCtx();
    document.removeEventListener('keydown', unlock);
    document.removeEventListener('pointerdown', unlock);
    document.removeEventListener('touchstart', unlock);
}
document.addEventListener('keydown', unlock);
document.addEventListener('pointerdown', unlock);
document.addEventListener('touchstart', unlock);
})();
