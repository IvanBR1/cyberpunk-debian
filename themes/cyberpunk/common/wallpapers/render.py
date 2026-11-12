#!/usr/bin/env python3
"""Dibujo vectorial original, rasterizado con el cargador SVG de GdkPixbuf."""
from pathlib import Path
import gi

gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
root = Path(__file__).resolve().parent.parent / 'wallpapers'
svg = root / 'neon-grid.svg'
GdkPixbuf.Pixbuf.new_from_file(str(svg)).savev(str(root/'neon-grid.png'), 'png', [], [])
