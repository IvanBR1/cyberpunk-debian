#!/usr/bin/env python3
"""Widgets GTK3 sobre Wayland: sin servicios externos ni consultas de red."""
import calendar
import ctypes
import ctypes.util
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib

RUNTIME = Path(GLib.get_user_runtime_dir())
DESKTOP = os.environ.get('CYBERPUNK_DESKTOP', 'hyprland')
if DESKTOP not in ('niri','hyprland'): raise SystemExit('Entorno inválido')
SOCKET = RUNTIME / f'cyberpunk-{DESKTOP}-widgets.sock'
command = 'toggle' if '--toggle' in sys.argv else 'quit' if '--quit' in sys.argv else None
if command:
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.connect(str(SOCKET)); client.sendall(command.encode())
    except (FileNotFoundError, ConnectionRefusedError):
        if command == 'toggle':
            subprocess.Popen([sys.executable, str(Path(__file__).resolve())], start_new_session=True)
    raise SystemExit(0)
# Un socket por usuario, protegido por el directorio runtime privado.
server = socket.socket(socket.AF_UNIX)
try:
    server.bind(str(SOCKET))
except OSError:
    try:
        with socket.socket(socket.AF_UNIX) as probe:
            probe.connect(str(SOCKET))
        raise SystemExit(0)
    except (FileNotFoundError, ConnectionRefusedError):
        SOCKET.unlink(missing_ok=True); server.bind(str(SOCKET))
server.listen(4)
server.setblocking(False)
os.chmod(SOCKET, 0o600)

# Usar la API C instalada también por Waybar. GtkLayerShell no necesita su typelib.
# hash(objeto GI) expone el puntero GObject nativo.
layer = ctypes.CDLL(ctypes.util.find_library('gtk-layer-shell') or 'libgtk-layer-shell.so.0')
for name, args in {
    'init_for_window': [ctypes.c_void_p],
    'set_namespace': [ctypes.c_void_p, ctypes.c_char_p],
    'set_layer': [ctypes.c_void_p, ctypes.c_int],
    'set_anchor': [ctypes.c_void_p, ctypes.c_int, ctypes.c_int],
    'set_margin': [ctypes.c_void_p, ctypes.c_int, ctypes.c_int],
    'set_keyboard_mode': [ctypes.c_void_p, ctypes.c_int],
    'set_exclusive_zone': [ctypes.c_void_p, ctypes.c_int],
}.items():
    func = getattr(layer, 'gtk_layer_'+name)
    func.argtypes = args
    func.restype = None

def layer_call(name, *args):
    getattr(layer, 'gtk_layer_'+name)(hash(window), *args)

window = Gtk.Window(title='Cyberpunk Widgets')
window.set_default_size(296, -1)
window.set_resizable(False)
window.set_app_paintable(True)
visual = window.get_screen().get_rgba_visual()
if visual: window.set_visual(visual)
layer_call('init_for_window')
layer_call('set_namespace', b'cyberpunk-widgets')
# BOTTOM=1; RIGHT=1, TOP=2; no espacio reservado ni foco de teclado.
layer_call('set_layer', 1)
layer_call('set_anchor', 1, 1)
layer_call('set_anchor', 2, 1)
layer_call('set_margin', 1, 24)
layer_call('set_margin', 2, 86)
layer_call('set_keyboard_mode', 0)
layer_call('set_exclusive_zone', 0)
provider = Gtk.CssProvider()
provider.load_from_data(b'''
window { background: transparent; font-family: "Hack Nerd Font"; color: #e6e0ff; }
#panel { background: rgba(9,13,27,0.83); border: 1px solid rgba(0,157,255,0.5); border-radius: 22px; padding: 22px; }
#brand { color: #009dff; font-size: 10px; letter-spacing: 3px; }
#time { font-size: 52px; font-weight: bold; color: #e6e0ff; }
#date { color: #ff66dd; font-size: 11px; }
#subtitle { color: #7b82a2; font-size: 9px; letter-spacing: 2px; margin-top: 12px; }
#metric { color: #bac5df; font-size: 11px; margin-top: 8px; }
#calendar { font-family: "Hack Nerd Font Mono"; font-size: 11px; color: #9cabc8; padding: 12px 0; }
progressbar trough { min-height: 4px; background: #20243c; border: none; border-radius: 4px; }
progressbar progress { min-height: 4px; background: linear-gradient(to right, #009dff, #ff00cc); border: none; border-radius: 4px; }
button { background: rgba(0,157,255,0.08); border: 1px solid #273759; border-radius: 10px; color: #b8dfff; padding: 8px; box-shadow: none; }
button:hover { background: rgba(255,0,204,0.16); border-color: #ff00cc; }
''')
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
box.set_name('panel'); window.add(box)

def label(text='', name='', align=0):
    obj=Gtk.Label(label=text); obj.set_xalign(align); obj.set_name(name)
    box.pack_start(obj, False, False, 0)
    return obj

label('NEON // SYSTEMS', 'brand')
clock = label('', 'time')
date = label('', 'date')
label('SYSTEM TELEMETRY', 'subtitle')
cpu_text = label('', 'metric'); cpu_bar = Gtk.ProgressBar(); box.pack_start(cpu_bar,False,False,0)
ram_text = label('', 'metric'); ram_bar = Gtk.ProgressBar(); box.pack_start(ram_bar,False,False,0)
uptime = label('', 'metric')
cal = label('', 'calendar'); cal.set_justify(Gtk.Justification.CENTER)
label('NOW PLAYING', 'subtitle')
media = label('Sin reproducción', 'metric'); media.set_max_width_chars(26); media.set_ellipsize(3)

def run(args):
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)

def buttons(items):
    row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=8)
    for title,tip,cmd in items:
        b=Gtk.Button(label=title); b.set_tooltip_text(tip)
        b.connect('clicked', lambda _button, command=cmd: run(command))
        row.pack_start(b,True,True,0)
    box.pack_start(row,False,False,3)

buttons([('󰒮','Anterior',['playerctl','previous']),('󰐊','Reproducir / Pausar',['playerctl','play-pause']),('󰒭','Siguiente',['playerctl','next'])])
buttons([('󰕾','Sonido',['pavucontrol']),('󰈹','Navegador',['firefox-esr']),('󰉋','Archivos',['thunar'])])
label('SUPER+A  //  ABRIR / CERRAR PANEL', 'subtitle')
prev_total = prev_idle = 0
last_media = 0

def update():
    global prev_total, prev_idle, last_media
    now = datetime.now()
    clock.set_text(now.strftime('%H:%M'))
    date.set_text(now.strftime('%A · %d %B').upper())
    values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    total=sum(values); idle=values[3]+values[4]
    fraction=0 if total==prev_total else 1-(idle-prev_idle)/(total-prev_total)
    prev_total,prev_idle=total,idle
    cpu_bar.set_fraction(max(0,min(1,fraction)))
    cpu_text.set_text(f'CPU                              {fraction*100:3.0f}%')
    mem={line.split(':')[0]:int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()}
    used=mem['MemTotal']-mem['MemAvailable']; ram_bar.set_fraction(used/mem['MemTotal'])
    ram_text.set_text(f'RAM                    {used/1048576:.1f} / {mem["MemTotal"]/1048576:.1f} GiB')
    seconds=int(float(Path('/proc/uptime').read_text().split()[0]))
    uptime.set_text(f'UPTIME                     {seconds//3600:02d}h {seconds//60%60:02d}m')
    cal.set_text(calendar.TextCalendar(firstweekday=0).formatmonth(now.year,now.month).strip())
    # Sondeo espaciado para evitar despertar procesos constantemente.
    if now.timestamp()-last_media>=10:
        last_media=now.timestamp()
        try:
            result=subprocess.run(['playerctl','metadata','--format','{{artist}} — {{title}}'],capture_output=True,text=True,timeout=0.5)
            media.set_text(result.stdout.strip() or 'Sin reproducción')
        except (OSError,subprocess.TimeoutExpired): media.set_text('Sin reproducción')
    return True

front=False

def receive(_source, _condition):
    global front
    try:
        conn,_=server.accept()
        conn.settimeout(0.1)
        with conn: data=conn.recv(32)
    except (BlockingIOError,socket.timeout): return True
    if data==b'quit': Gtk.main_quit()
    elif data==b'toggle':
        front=not front
        layer_call('set_layer',3 if front else 1)
    return True

GLib.io_add_watch(server.fileno(),GLib.IO_IN,receive)
GLib.timeout_add_seconds(2,update)
update(); window.show_all()
try: Gtk.main()
finally: server.close(); SOCKET.unlink(missing_ok=True)
