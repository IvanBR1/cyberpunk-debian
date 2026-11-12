#!/usr/bin/env python3
"""Servicios de sesión por entorno; rutas locales, locks y una instancia por rol."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

def paths(desktop):
    if desktop not in ('niri', 'hyprland'):
        raise SystemExit('Entorno desconocido')
    return ROOT/desktop, json.loads((ROOT/desktop/'session.json').read_text())

def commands(desktop):
    asset, settings = paths(desktop)
    runtime = str(Path(__file__).resolve())
    lock = shlex.join(['python3',runtime,desktop,'lock'])
    result = {
        'bar': ['waybar','-c',str(asset/'waybar/config.jsonc'),'-s',str(asset/'waybar/style.css')],
        'notifications': ['mako','--config',str(asset/'mako/config')],
        'idle': ['swayidle','-w','timeout','600',lock,'before-sleep',lock],
    }
    if desktop=='hyprland': result['polkit']=['lxpolkit']
    if settings['theme']=='cyberpunk':
        result['wallpaper']=['swaybg','-i',str(asset/'wallpapers/neon-grid.png'),'-m','fill']
    if 'widgets' in settings['addons']:
        result['widgets']=['python3',str(asset/'widgets/dashboard.py')]
    if 'clipboard' in settings['addons']:
        result['clipboard']=['wl-paste','--type','text','--watch','cliphist','store']
    return result

def daemon(desktop, role):
    runtime=Path(os.environ['XDG_RUNTIME_DIR'])
    with (runtime/f'cyberpunk-{desktop}-{role}.lock').open('w') as guard:
        try: fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return
        env={**os.environ,'CYBERPUNK_DESKTOP':desktop}
        child=subprocess.Popen(commands(desktop)[role],env=env)
        def stop(_sig,_frame):
            if child.poll() is None: child.terminate()
        signal.signal(signal.SIGTERM,stop)
        signal.signal(signal.SIGINT,stop)
        child.wait()

def main():
    desktop, action = sys.argv[1:3]
    if desktop=='auto' and action=='terminal':
        current=os.environ.get('XDG_CURRENT_DESKTOP','').lower().split(':')
        desktop=next((d for d in ('hyprland','niri') if d in current and (ROOT/d/'session.json').is_file()),None)
        if desktop is None:
            os.execvp('foot',['foot',*sys.argv[3:]])
    asset, settings=paths(desktop)
    if action=='daemon': return daemon(desktop,sys.argv[3])
    if action=='start':
        subprocess.run(['dbus-update-activation-environment','--systemd','WAYLAND_DISPLAY','XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE'],check=False)
        subprocess.run(['systemctl','--user','start',f'cyberpunk-{desktop}.target'],check=True)
        return
    if action=='terminal': cmd=['foot','-c',str(asset/'foot/foot.ini'),*sys.argv[3:]]
    elif action=='launcher': cmd=['fuzzel','--config',str(asset/'fuzzel/fuzzel.ini')]
    elif action=='lock': cmd=['swaylock','-f','-C',str(asset/'swaylock/config')]
    elif action=='widgets':
        if 'widgets' not in settings['addons']: raise SystemExit('Widgets desactivados en este perfil.')
        cmd=['python3',str(asset/'widgets/dashboard.py'),'--toggle']
    elif action=='clipboard':
        if 'clipboard' not in settings['addons']: raise SystemExit('Historial desactivado en este perfil.')
        listing=subprocess.run(['cliphist','list'],capture_output=True,check=True)
        pick=subprocess.run(['fuzzel','--config',str(asset/'fuzzel/fuzzel.ini'),'--dmenu'],input=listing.stdout,capture_output=True)
        if pick.returncode or not pick.stdout.strip(): return
        decoded=subprocess.run(['cliphist','decode'],input=pick.stdout,capture_output=True,check=True)
        subprocess.run(['wl-copy'],input=decoded.stdout,check=True)
        return
    else: raise SystemExit('Acción desconocida')
    os.environ['CYBERPUNK_DESKTOP']=desktop
    os.execvp(cmd[0],cmd)

if __name__=='__main__': main()
