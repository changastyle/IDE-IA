# -*- coding: utf-8 -*-
"""Check-Monitor-Resolution — detección de monitores y sus resoluciones.

Pensado para el arranque de la app: saber el tamaño de cada monitor
conectado y elegir el más grande para ajustar la ventana principal.

El nombre del archivo lleva guiones (convención del proyecto), así que
no se puede importar con `import` normal — usar importlib:

    import importlib
    mon = importlib.import_module("UTILS.Check-Monitor-Resolution")
    screen = mon.largest_screen()

O por ruta de archivo:

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "check_monitor_resolution",
        r"C:\\path\\to\\UTILS\\Check-Monitor-Resolution.py")
    mon = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mon)

Uso standalone (imprime un reporte de los monitores):

    python UTILS/Check-Monitor-Resolution.py
"""

import sys


def _screens():
    """Lista de QScreen de los monitores conectados.

    Reutiliza la QApplication activa si existe; si no, crea una
    temporal (modo standalone / tests).
    """
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv[:1] or ["check-monitor-resolution"])
    return app.screens()


def list_monitors():
    """Info de cada monitor conectado.

    Devuelve una lista de dicts:
        name          nombre del monitor (ej: "Mi Monitor")
        primary       True si es el monitor principal
        width/height  resolución total en píxeles
        avail_width/  área disponible (sin barra de tareas ni docks)
        avail_height
        x/y           origen del área disponible en coordenadas virtuales
    """
    from PySide6.QtWidgets import QApplication
    screens = _screens()  # asegura la QApplication antes de primaryScreen()
    primary = QApplication.primaryScreen()
    monitors = []
    for s in screens:
        geo = s.geometry()
        avail = s.availableGeometry()
        monitors.append({
            "name": s.name(),
            "primary": s is primary,
            "width": geo.width(),
            "height": geo.height(),
            "avail_width": avail.width(),
            "avail_height": avail.height(),
            "x": avail.x(),
            "y": avail.y(),
        })
    return monitors


def largest_screen():
    """QScreen del monitor con mayor área disponible.

    Con varios monitores gana el de mayor avail_width × avail_height.
    Devuelve None si no hay pantallas.
    """
    screens = _screens()
    if not screens:
        return None
    return max(
        screens,
        key=lambda s: (s.availableGeometry().width()
                       * s.availableGeometry().height()))


def check_monitor_resolution():
    """(ancho, alto) disponibles del monitor más grande.

    Es la función principal: la app la usa al arrancar para ajustar la
    ventana al ancho/alto máximos del monitor en cuestión.
    Devuelve None si no hay pantallas.
    """
    screen = largest_screen()
    if screen is None:
        return None
    geo = screen.availableGeometry()
    return geo.width(), geo.height()


def fit_window_to_largest(window):
    """Mueve `window` al monitor más grande y la maximiza.

    Equivale a ocupar el ancho y alto máximos disponibles de ese
    monitor (respeta la barra de tareas). No hace nada si no hay
    pantallas.
    """
    screen = largest_screen()
    if screen is None:
        return
    window.move(screen.availableGeometry().topLeft())
    window.showMaximized()


if __name__ == "__main__":
    monitors = list_monitors()
    if not monitors:
        print("No se detectaron monitores.")
        sys.exit(1)
    for m in monitors:
        tag = " [primary]" if m["primary"] else ""
        print(f"{m['name']}{tag}: {m['width']}x{m['height']} "
              f"(disponible {m['avail_width']}x{m['avail_height']} "
              f"en {m['x']},{m['y']})")
    biggest = check_monitor_resolution()
    print(f"Monitor mas grande: {biggest[0]}x{biggest[1]}")
