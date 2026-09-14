/*
 * test-sample.js — Resumen del archivo.
 *
 * Lenguaje: JavaScript
 *
 * Clases:
 *   - Monitor   (línea 26)
 *       - constructor(name, width, height)   (línea 27)
 *       - area()   (línea 33)
 *       - fromScreen(screen)   (línea 37)
 *       - describe(prefix)   (línea 41)
 *
 * Funciones:
 *   - pickLargest(monitors)   (línea 46)
 *   - fitWindow(win, mon)   (línea 50)
 *   - clamp(v, lo, hi)   (línea 55)
 *
 * [generado por analyze_file]
 */




// Archivo de prueba para analyze_file
const MAX = 10;

class Monitor {
  constructor(name, width, height) {
    this.name = name;
    this.width = width;
    this.height = height;
  }

  get area() {
    return this.width * this.height;
  }

  static async fromScreen(screen) {
    return new Monitor(screen.name, 1920, 1080);
  }

  describe(prefix) {
    return `${prefix}: ${this.name}`;
  }
}

export function pickLargest(monitors) {
  return monitors.reduce((a, b) => (a.area > b.area ? a : b));
}

const fitWindow = async (win, mon) => {
  win.moveTo(mon.x, mon.y);
};

const helpers = {
  clamp: function (v, lo, hi) {
    return Math.min(hi, Math.max(lo, v));
  },
};
