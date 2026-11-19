#!/usr/bin/env python3
"""Widgets GTK3 sobre Wayland: sin servicios externos ni consultas de red."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import re
import time
from metrics import Telemetry, rate
from media import parse_metadata, settle_metadata
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
gi.require_foreign('cairo')
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
window.set_default_size(340, -1)
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
#panel { background: rgba(9,13,27,0.88); border: 1px solid rgba(0,157,255,0.5); border-radius: 22px; padding: 20px; }
#brand { color: #009dff; font-size: 10px; letter-spacing: 3px; }
#time { font-size: 48px; font-weight: bold; color: #e6e0ff; }
#date { color: #ff66dd; font-size: 11px; }
#subtitle { color: #7b82a2; font-size: 9px; letter-spacing: 2px; margin-top: 9px; }
#cpu-metric { color: #80cfff; font-size: 11px; }
#ram-metric { color: #ff66dd; font-size: 11px; }
#metric { color: #bac5df; font-size: 11px; }
#muted { color: #7b82a2; font-size: 10px; }
#track { color: #e6e0ff; font-size: 13px; font-weight: bold; }
progressbar trough, scale trough { min-height: 4px; background: #20243c; border: none; border-radius: 4px; }
progressbar progress, scale highlight { min-height: 4px; background: linear-gradient(to right, #009dff, #ff00cc); border: none; border-radius: 4px; }
scale { padding: 3px 0; }
scale slider { min-width: 10px; min-height: 10px; background: #80cfff; border: none; border-radius: 8px; }
button { background: rgba(0,157,255,0.08); border: 1px solid #273759; border-radius: 10px; color: #b8dfff; padding: 7px; box-shadow: none; }
button:hover { background: rgba(255,0,204,0.16); border-color: #ff00cc; }
calendar { color: #bac5df; font-size: 10px; padding: 4px; }
calendar:selected { background: #009dff; color: #0b0914; }
''')
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=7);box.set_name('panel')
# Mantener acceso a todos los controles en pantallas de poca altura.
scroll=Gtk.ScrolledWindow();scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
scroll.set_propagate_natural_height(True)
monitor=window.get_display().get_primary_monitor() or window.get_display().get_monitor(0)
scroll.set_max_content_height(max(360,monitor.get_geometry().height-200) if monitor else 900)
scroll.add(box);window.add(scroll)

def label(text='',name='metric',parent=box):
    obj=Gtk.Label(label=text);obj.set_xalign(0);obj.set_name(name)
    parent.pack_start(obj,False,False,0);return obj

def run(args):
    try:subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    except OSError:pass

class Chart(Gtk.DrawingArea):
    def __init__(self,colors,dynamic=False,height=48):
        super().__init__();self.colors=colors;self.dynamic=dynamic
        self.series=[deque(maxlen=60) for _ in colors]
        self.set_size_request(280,height);self.connect('draw',self.draw_chart)
    def push(self,*values):
        for series,value in zip(self.series,values):series.append(max(0,value))
        self.queue_draw()
    def draw_chart(self,widget,ctx):
        w=self.get_allocated_width();h=self.get_allocated_height()
        ctx.set_source_rgba(0.3,0.4,0.65,0.16);ctx.set_line_width(1)
        for y in (h*.25,h*.5,h*.75):ctx.move_to(0,y);ctx.line_to(w,y)
        ctx.stroke()
        maximum=max(1024,max((max(s,default=0) for s in self.series),default=0)*1.15) if self.dynamic else 1
        for series,color in zip(self.series,self.colors):
            if len(series)<2:continue
            points=[(w-(len(series)-1-i)*w/59,h-3-min(1,value/maximum)*(h-6)) for i,value in enumerate(series)]
            ctx.move_to(points[0][0],h)
            for x,y in points:ctx.line_to(x,y)
            ctx.line_to(points[-1][0],h);ctx.close_path();ctx.set_source_rgba(*color,.10);ctx.fill()
            ctx.move_to(*points[0])
            for point in points[1:]:ctx.line_to(*point)
            ctx.set_source_rgba(*color,.95);ctx.set_line_width(1.7);ctx.stroke()
        return False

label('NEON // SYSTEMS','brand')
clock=label('','time');date=label('','date')
label('RECURSOS  /  120 s','subtitle')
cpu=label(name="cpu-metric");ram=label(name="ram-metric")
resources=Chart([(0,.62,1),(1,0,.8)],height=62);box.pack_start(resources,False,False,0)
health=label('','muted')
label('RED  /  TRÁFICO EN TIEMPO REAL','subtitle')
network=label();netchart=Chart([(0,.62,1),(1,0,.8)],dynamic=True,height=48)
box.pack_start(netchart,False,False,0)
label('ALMACENAMIENTO Y ENERGÍA','subtitle')
disk=label();diskbar=Gtk.ProgressBar();box.pack_start(diskbar,False,False,0)
power=label()
label('CONTROLES','subtitle')
volume_text=label();volume=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,0,100,1)
volume.set_draw_value(False);box.pack_start(volume,False,False,0)
backlights=sorted(Path('/sys/class/backlight').glob('*'))
brightness_text=label();brightness=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,1,100,1)
brightness.set_draw_value(False);box.pack_start(brightness,False,False,0)
if not backlights:brightness_text.set_no_show_all(True);brightness.set_no_show_all(True)

def buttons(items):
    row=Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=7);result=[]
    for title,tip,command in items:
        button=Gtk.Button(label=title);button.set_tooltip_text(tip)
        button.connect('clicked',lambda _b,cmd=command:cmd() if callable(cmd) else run(cmd))
        row.pack_start(button,True,True,0);result.append(button)
    box.pack_start(row,False,False,2);return result

label('REPRODUCCIÓN','subtitle')
track=label('Sin reproducción','track');track.set_max_width_chars(29);track.set_ellipsize(3)
artist=label('','muted');artist.set_max_width_chars(34);artist.set_ellipsize(3)
playback=Gtk.ProgressBar();box.pack_start(playback,False,False,0)
media_time=label('','muted')
media_buttons=buttons([('󰒮','Anterior',lambda:media_action('previous')),('󰐊','Reproducir / Pausar',lambda:media_action('play-pause')),('󰒭','Siguiente',lambda:media_action('next'))])
expander=Gtk.Expander(label='Calendario');cal=Gtk.Calendar();expander.add(cal);box.pack_start(expander,False,False,0)

telemetry=Telemetry();syncing=False;pending={};executor=ThreadPoolExecutor(max_workers=1);poll_future=None;last_poll=0
media_raw='';media_status=None;media_revision=0;media_busy=False

def schedule_control(key,args):
    if syncing:return
    if key in pending:GLib.source_remove(pending[key])
    def apply():
        pending.pop(key,None);run(args);return False
    pending[key]=GLib.timeout_add(180,apply)

volume.connect('value-changed',lambda scale:schedule_control('volume',['wpctl','set-volume','-l','1','@DEFAULT_AUDIO_SINK@',f'{scale.get_value()/100:.2f}']))
brightness.connect('value-changed',lambda scale:schedule_control('brightness',['brightnessctl','-c','backlight','set',f'{scale.get_value():.0f}%']))

def query(args):
    try:return subprocess.run(args,capture_output=True,text=True,timeout=.7).stdout.strip()
    except (OSError,subprocess.TimeoutExpired):return ''

def control(args):
    try:return subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=.7).returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def media_metadata():
    return query(['playerctl','metadata','--format','{{title}}\x1f{{artist}}\x1f{{status}}\x1f{{position}}\x1f{{mpris:length}}'])

def poll_controls(revision):
    return (revision,query(['wpctl','get-volume','@DEFAULT_AUDIO_SINK@']),media_metadata())

def apply_media(metadata):
    global media_raw,media_status
    state=parse_metadata(metadata);media_raw=metadata
    active=state is not None
    for button in media_buttons:button.set_sensitive(active)
    if active:
        media_status=state['status'];track.set_text(state['title']);artist.set_text(state['artist'] or 'Reproductor multimedia')
        media_buttons[1].set_label('󰏤' if media_status=='Playing' else '󰐊')
        current,duration=state['current'],state['duration']
        if current is not None and duration is not None:
            playback.set_fraction(max(0,min(1,current/duration)) if duration>0 else 0)
            media_time.set_text(f'{int(current)//60}:{int(current)%60:02d}  /  {int(duration)//60}:{int(duration)%60:02d}')
        else:playback.set_fraction(0);media_time.set_text(media_status)
    else:
        media_status=None;track.set_text('Sin reproducción');artist.set_text('');media_time.set_text('');playback.set_fraction(0)

def finish_media_action(future,revision):
    global media_busy
    if revision==media_revision:
        media_busy=False
        try:apply_media(future.result())
        except Exception:pass
    return False

def media_action(action):
    global media_revision,media_status,media_busy
    if media_status is None:return
    media_revision+=1;revision=media_revision;before=media_raw;media_busy=True
    if action=='play-pause':
        media_status='Paused' if media_status=='Playing' else 'Playing'
        media_buttons[1].set_label('󰏤' if media_status=='Playing' else '󰐊')
    def work():
        return settle_metadata(action,before,lambda:control(['playerctl',action]),media_metadata)
    future=executor.submit(work)
    future.add_done_callback(lambda done:GLib.idle_add(finish_media_action,done,revision))

def apply_controls(values):
    global syncing
    revision,vol,metadata=values;syncing=True
    if 'volume' not in pending and not volume.has_grab():
        match=re.search(r'Volume: ([\d.]+)',vol)
        if match:
            value=float(match[1])*100;volume.set_value(min(100,value))
            volume_text.set_text('Volumen · silenciado' if 'MUTED' in vol else f'Volumen                              {value:.0f}%')
    if revision==media_revision:apply_media(metadata)
    syncing=False

def update():
    global syncing,poll_future,last_poll
    now=datetime.now();clock.set_text(now.strftime('%H:%M'));date.set_text(now.strftime('%A · %d %B').upper())
    try:
        data=telemetry.sample()
        cpu.set_text(f'CPU  {data["cpu"]*100:3.0f}%');ram.set_text(f'RAM  {data["used_gib"]:.1f} / {data["total_gib"]:.1f} GiB')
        resources.push(data['cpu'],data['ram'])
        seconds=data['uptime'];temp=f' · {data["temperature"]:.0f} °C' if data['temperature'] is not None else ''
        health.set_text(f'Activo {seconds//3600}h {seconds//60%60:02d}m'+temp)
        network.set_text(f'↓ {rate(data["rx"])}     ↑ {rate(data["tx"])}');netchart.push(data['rx'],data['tx'])
        disk.set_text(f'Disco  {data["disk"]*100:.0f}% · {data["free_gib"]:.1f} GiB libres');diskbar.set_fraction(data['disk'])
        battery=data['battery']
        states={'Charging':'cargando','Discharging':'en batería','Full':'carga completa','Not charging':'conectada'}
        power.set_text(f'Batería  {battery["capacity"]}% · {states.get(battery["status"],battery["status"])}' if battery else 'Alimentación sin batería')
        if backlights and 'brightness' not in pending and not brightness.has_grab():
            light=backlights[0];percent=int((light/'brightness').read_text())/max(1,int((light/'max_brightness').read_text()))*100
            syncing=True;brightness.set_value(percent);syncing=False
            brightness_text.set_text(f'Brillo del panel                     {percent:.0f}%')
    except (OSError,ValueError,KeyError):health.set_text('Telemetría no disponible')
    if poll_future is not None and poll_future.done():
        try:apply_controls(poll_future.result())
        except Exception:pass
        poll_future=None
    if poll_future is None and not media_busy and time.monotonic()-last_poll>=4:
        last_poll=time.monotonic();poll_future=executor.submit(poll_controls,media_revision)
    return True

front=False

def receive(_source,_condition):
    global front
    try:
        conn,_=server.accept();conn.settimeout(.1)
        with conn:data=conn.recv(32)
    except (BlockingIOError,socket.timeout):return True
    if data==b'quit':Gtk.main_quit()
    elif data==b'toggle':front=not front;layer_call('set_layer',3 if front else 1)
    return True

GLib.io_add_watch(server.fileno(),GLib.IO_IN,receive)
GLib.timeout_add_seconds(2,update)
update();window.show_all()
try:Gtk.main()
finally:
    executor.shutdown(wait=False,cancel_futures=True)
    server.close();SOCKET.unlink(missing_ok=True)
