"""Launcher de NG-STUDIO (alias de ui_app.py).

Uso: python ng-studio-app.py [--splash]
"""
import sys

import UI.main_window

if __name__ == "__main__":
    params = {"show_splash": "--splash" in sys.argv}
    UI.main_window.main(params)