"""Composición de entorno + hardware + apariencia. No escribe en la máquina."""
import json
import os
from pathlib import Path
import shlex
from state import File

class Layout:
    def __init__(self, home=None):
        self.home=Path(home or Path.home())
        self.config=self.home/'.config'
        self.data=self.home/'.local/share'
        self.state=self.home/'.local/state/cyberpunk-desktop'
        self.root=self.data/'cyberpunk-desktop'
        self.runtime=self.root/'bin/runtime.py'

def load_packages(root, names):
    packages=[]
    for name in names:
        for line in (root/name).read_text().splitlines():
            line=line.split('#',1)[0].strip()
            if line and line not in packages: packages.append(line)
    return packages

def replace(text, values):
    for key,value in values.items(): text=text.replace('@'+key+'@',str(value))
    return text

def make_files(root, layout, desktop, profile, theme, addons, keyboard, resolution, output,
               legacy_drm=False, display_text=None, niri_binary=None):
    asset=layout.root/desktop
    display=layout.config/'cyberpunk-desktop/hardware'/f'{desktop}-display.conf'
    if desktop=='hyprland' and 'controls' in addons:
        display=layout.config/'hypr/monitors.conf'
    hardware=layout.config/'cyberpunk-desktop/hardware'/f'{desktop}-{profile}.conf'
    appearance=asset/'appearance.conf'
    values={'ASSETS':asset,'RUNTIME':layout.runtime,'RUNTIME_KDL':json.dumps(str(layout.runtime)),
            'DESKTOP':desktop,'DISPLAY':display,'HARDWARE':hardware,'APPEARANCE':appearance,'KEYBOARD':keyboard}
    files=[]
    def add(path, data, mode=0o644, system=False):
        files.append(File(Path(path),data.encode() if isinstance(data,str) else data,mode,system))
    add(layout.runtime,(root/'scripts/runtime.py').read_bytes(),0o755)
    # La entrada local de Foot usa el perfil del entorno actual; fuera del kit conserva Foot normal.
    add(layout.data/'applications/foot.desktop', '[Desktop Entry]\nType=Application\nName=Foot\nGenericName=Terminal\nExec=python3 '+json.dumps(str(layout.runtime))+' auto terminal\nIcon=foot\nTerminal=false\nCategories=System;TerminalEmulator;\nKeywords=shell;prompt;command;commandline;\n')
    settings={'desktop':desktop,'profile':profile,'theme':theme,'addons':addons,'keyboard':keyboard,'legacy_drm':legacy_drm}
    # Servicios ligados a la sesión, sin habilitación global de barras duplicadas.
    roles=['bar','notifications','idle']
    if desktop=='hyprland': roles.append('polkit')
    if theme=='cyberpunk': roles.append('wallpaper')
    if 'widgets' in addons: roles.append('widgets')
    if 'clipboard' in addons: roles.append('clipboard')
    unitroot=layout.config/'systemd/user'
    target=f'cyberpunk-{desktop}.target'
    units=[f'cyberpunk-{desktop}-{role}.service' for role in roles]
    add(unitroot/target,'[Unit]\nDescription=Cyberpunk '+desktop+' session\nPartOf=graphical-session.target\nWants='+' '.join(units)+'\n')
    for role,unit in zip(roles,units):
        add(unitroot/unit,'[Unit]\nDescription=Cyberpunk '+desktop+' '+role+'\nPartOf='+target+' graphical-session.target\nAfter=graphical-session-pre.target\n[Service]\nType=simple\nExecStart=/usr/bin/python3 '+json.dumps(str(layout.runtime))+' '+desktop+' daemon '+role+'\n')

    add(asset/'session.json',json.dumps(settings,indent=2)+'\n')
    for group in ['common',desktop]:
        for source in sorted((root/'themes/cyberpunk'/group).rglob('*')):
            if not source.is_file(): continue
            rel=source.relative_to(root/'themes/cyberpunk'/group)
            if rel.parts[0]=='widgets' and 'widgets' not in addons: continue
            if rel.parts[0]=='wallpapers' and theme!='cyberpunk': continue
            data=source.read_bytes()
            if source.suffix not in ('.png','.ttf'):
                data=replace(data.decode(),values).replace('@HOME@',str(layout.home)).encode()
            add(asset/rel,data,0o755 if source.suffix in ('.py','.sh') else 0o644)
    # Terminal de las aplicaciones lanzadas por fuzzel: ruta resuelta para esta máquina.
    fuzzel=next(f for f in files if f.path==asset/'fuzzel/fuzzel.ini')
    fuzzel.data=fuzzel.data.replace(b'foot -c '+str(layout.home).encode()+b'/.config/hypr/cyberpunk/foot/foot.ini',
                                    ('python3 '+shlex.quote(str(layout.runtime))+' '+desktop+' terminal').encode())
    if theme=='plain':
        # La base funcional no impone transparencias, papel tapiz ni ornamentación neón.
        for item in files:
            if item.path==asset/'foot/foot.ini':
                item.data=b'[main]\nfont=monospace:size=11\n[colors]\nalpha=1.0\n'
            if item.path==asset/'waybar/style.css':
                item.data=b'* { font-family: monospace; }\nwindow#waybar { background: #202020; color: #eeeeee; }\n'
            if item.path==asset/'fuzzel/fuzzel.ini':
                item.data=('[main]\nfont=monospace:size=11\nterminal=python3 '+str(layout.runtime)+' '+desktop+' terminal\n').encode()
        for item in files:
            if item.path==asset/'mako/config':
                item.data=b'background-color=#202020\ntext-color=#eeeeee\nborder-color=#777777\n'
            if item.path==asset/'swaylock/config':
                item.data=b'color=202020\nindicator-idle-visible\nshow-keyboard-layout\nindicator-caps-lock\nignore-empty-password\n'
            if item.path==asset/'widgets/dashboard.py':
                text=item.data.decode().replace('Hack Nerd Font','monospace')
                for neon in ('#009dff','#ff00cc','#ff66dd'):
                    text=text.replace(neon,'#aaaaaa')
                for glyph,word in [('󰒮','Prev'),('󰐊','Play'),('󰒭','Next'),('󰕾','Audio'),('󰈹','Web'),('󰉋','Files')]:
                    text=text.replace(glyph,word)
                item.data=text.encode()
        # Quitar el acceso a widgets cuando se omite ese complemento.
    bar=next(f for f in files if f.path==asset/'waybar/config.jsonc')
    data=json.loads(bar.data)
    if 'widgets' not in addons:
        data['modules-right']=[v for v in data['modules-right'] if v!='custom/dashboard']
        data.pop('custom/dashboard',None)
    if theme=='plain':
        data['custom/launcher']['format']='Apps'
        if 'custom/dashboard' in data: data['custom/dashboard']['format']='Panel'
    if 'controls' in addons:
        data['modules-right'].insert(0,'custom/displays')
        data['modules-right'].insert(1,'backlight')
        data['custom/displays']={'format':'DISP','tooltip-format':'Ordenar pantallas · Super+P','on-click':'nwg-displays -m '+shlex.quote(str(display))}
        data['backlight']={'format':'BRI {percent}%','tooltip-format':'Brillo del panel interno: {percent}% · rueda para ajustar','on-scroll-up':'brightnessctl -c backlight set +5%','on-scroll-down':'brightnessctl -c backlight --min-value=1 set 5%-'}
        data['pulseaudio'].update({'format-muted':'VOL mute','scroll-step':5,'max-volume':100,'on-click-right':'wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle'})
    bar.data=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
    portals=layout.config/'xdg-desktop-portal'/f'{desktop}-portals.conf'
    add(portals,(root/'environments'/desktop/'portals.conf').read_bytes())
    if desktop=='hyprland':
        if display_text is None:
            display_text='monitor = , preferred, auto, 1\n'
        if resolution not in ('preserve','auto'):
            display_text=f'monitor = , preferred, auto, 1\nmonitor = {output}, {resolution}, auto, 1\n'
        elif resolution=='auto': display_text='monitor = , preferred, auto, 1\n'
        add(display,display_text)
        # El workaround se exporta en el launcher ANTES de inicializar Aquamarine.
        add(hardware,(root/'hardware'/profile/'hyprland.conf.in').read_text().replace('@LEGACY_DRM@',str(legacy_drm)))
        if theme=='plain':
            item=next(f for f in files if f.path==appearance)
            item.data=b'decoration {\n    active_opacity = 1\n    inactive_opacity = 1\n    blur {\n        enabled = false\n    }\n    shadow {\n        enabled = false\n    }\n}\n'
        config=replace((root/'environments/hyprland/hyprland.conf.in').read_text(),values)
        if 'controls' in addons:
            config+='\n# Controles opcionales: hardware estándar, sin demonio adicional.\nbindel = , XF86MonBrightnessUp, exec, brightnessctl -c backlight set +5%\nbindel = , XF86MonBrightnessDown, exec, brightnessctl -c backlight --min-value=1 set 5%-\nbindl = , XF86AudioMicMute, exec, wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle\nbind = $mainMod, P, exec, nwg-displays -m '+shlex.quote(str(display))+'\nbind = $mainMod, S, exec, pavucontrol\n'
        config+='\nexec-shutdown = systemctl --user stop cyberpunk-hyprland.target\n'
        if 'office' in addons: config='env = SAL_USE_VCLPLUGIN,gtk3\n'+config
        add(layout.config/'hypr/hyprland.conf',config)
        command=shlex.quote('/usr/bin/start-hyprland')
        launcher='#!/usr/bin/env bash\nset -euo pipefail\n'
        if legacy_drm: launcher+='export AQ_NO_ATOMIC=1\n'
        launcher+=f'exec {command}\n'
    else:
        niri_display=display_text or '// Modo de pantalla automático; sin nombres de monitor de otra máquina.'
        if resolution=='auto': niri_display='// Modo de pantalla automático.'
        if resolution not in ('preserve','auto'):
            niri_display='output '+json.dumps(output)+' { mode '+json.dumps(resolution)+'; scale 1; }'
        add(display,niri_display+'\n')
        add(hardware,(root/'hardware'/profile/'niri.kdl.in').read_text())
        # En Niri 25.08 se inserta el bloque validado: no requiere soporte de include.
        values['NIRI_DISPLAY']=niri_display
        values['NIRI_LAYOUT']=(root/'themes/cyberpunk/niri/layout.kdl').read_text()
        config=replace((root/'environments/niri/config.kdl.in').read_text(),values)
        if 'office' not in addons:
            config=config.replace('environment {\n    SAL_USE_VCLPLUGIN "gtk3"\n}\n','')
        if theme=='plain':
            config=config.replace('active-color "#00e5ff"','active-color "#dddddd"').replace('active-color "#ff2a9d"','active-color "#aaaaaa"')
        else:
            config=config.replace('#00e5ff','#009dff').replace('#ff2a9d','#ff00cc')
        add(layout.config/'niri/config.kdl',config)
        binary=niri_binary or str(asset/'bin/niri')
        session=(root/'environments/niri/niri-session').read_text()
        session=session.replace('niri.service','cyberpunk-niri.service').replace('niri-shutdown.target','cyberpunk-niri-shutdown.target')
        session=session.replace('exec niri --session','exec '+shlex.quote(binary)+' --session')
        add(asset/'bin/niri-session',session,0o755)
        service=(root/'environments/niri/niri.service').read_text().replace('/usr/bin/niri',binary)
        add(layout.config/'systemd/user/cyberpunk-niri.service',service)
        add(layout.config/'systemd/user/cyberpunk-niri-shutdown.target',(root/'environments/niri/niri-shutdown.target').read_bytes())
        launcher='#!/usr/bin/env bash\nset -euo pipefail\nexec '+shlex.quote(str(asset/'bin/niri-session'))+' "$@"\n'
    if 'widgets' not in addons:
        # Los atajos no instalados no deben mostrar errores al pulsarlos.
        for item in files:
            if item.path in (layout.config/'hypr/hyprland.conf',layout.config/'niri/config.kdl'):
                item.data=b'\n'.join(line for line in item.data.split(b'\n') if not (b'widgets' in line and (b'bind =' in line or b'Mod+A ' in line)))
    if 'clipboard' not in addons:
        for item in files:
            if item.path in (layout.config/'hypr/hyprland.conf',layout.config/'niri/config.kdl'):
                item.data=b'\n'.join(line for line in item.data.split(b'\n') if not (b'clipboard' in line and (b'bind =' in line or b'Mod+V ' in line)))
    executable=layout.home/'.local/bin'/f'cyberpunk-{desktop}'
    add(executable,launcher,0o755)
    add(Path('/usr/share/wayland-sessions')/f'cyberpunk-{desktop}.desktop',
        '[Desktop Entry]\nName='+desktop.capitalize()+' (Cyberpunk)\nExec='+str(executable)+'\nType=Application\nDesktopNames='+('Hyprland' if desktop=='hyprland' else 'niri')+'\n',system=True)
    files.append(File(layout.config/'systemd/user/waybar.service',link='/dev/null'))
    return files
