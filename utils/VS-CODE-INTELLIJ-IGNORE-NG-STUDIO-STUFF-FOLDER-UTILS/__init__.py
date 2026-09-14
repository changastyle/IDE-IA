# -*- coding: utf-8 -*-
"""Marca ng-studio-stuff/ como no-indexable para IDEs y buscadores."""
import importlib as _il

_m = _il.import_module(
    __name__ + ".VS-CODE-INTELLIJ-IGNORE-NG-STUDIO-STUFF-FOLDER-UTILS")

STUFF_DIR = _m.STUFF_DIR
mark_no_index = _m.mark_no_index
ensure_stuff_dir = _m.ensure_stuff_dir

__all__ = ["STUFF_DIR", "mark_no_index", "ensure_stuff_dir"]
