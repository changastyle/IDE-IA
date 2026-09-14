/*
 * test-sample.java — Resumen del archivo.
 *
 * Lenguaje: Java
 *
 * Clases:
 *   - ScreenUtils   (línea 23)
 *       - ScreenUtils(int width, int height)   (línea 28)
 *       - area()   (línea 33)
 *       - largest(List<ScreenUtils> screens)   (línea 37)
 *       - validate()   (línea 47)
 *       - toString()   (línea 54)
 *
 * [generado por analyze_file]
 */



// Archivo de prueba para analyze_file
package tests;

import java.util.List;

public class ScreenUtils {

    private final int width;
    private final int height;

    public ScreenUtils(int width, int height) {
        this.width = width;
        this.height = height;
    }

    public int area() {
        return width * height;
    }

    public static ScreenUtils largest(List<ScreenUtils> screens) {
        ScreenUtils best = null;
        for (ScreenUtils s : screens) {
            if (best == null || s.area() > best.area()) {
                best = s;
            }
        }
        return best;
    }

    private void validate() throws IllegalStateException {
        if (width <= 0 || height <= 0) {
            throw new IllegalStateException("bad size");
        }
    }

    @Override
    public String toString() {
        return width + "x" + height;
    }
}
