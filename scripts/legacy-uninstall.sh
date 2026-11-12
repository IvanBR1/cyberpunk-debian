#!/usr/bin/env bash
# Copia idéntica en ambos proyectos. Por defecto SOLO muestra el plan.
# Ejemplo: ./uninstall.sh both --apply --purge-packages
# --delete-projects borra también estas carpetas y los propios scripts.
set -Eeuo pipefail
[[ $EUID != 0 ]] || { echo 'Ejecuta como tu usuario, sin sudo.' >&2; exit 1; }
python3 - "$@" <<'PY'
import argparse, os, re, shutil, subprocess
from pathlib import Path
p=argparse.ArgumentParser(description='Quitar configuraciones Cyberpunk y sus respaldos. Sin --apply solo muestra el plan.')
p.add_argument('target',choices=['niri','hyprland','both'])
p.add_argument('--apply',action='store_true',help='Ejecutar el borrado definitivo, incluidos respaldos del entorno elegido')
p.add_argument('--purge-packages',action='store_true',help='Purgar paquetes instalados del entorno elegido; conserva dependencias compartidas')
p.add_argument('--delete-projects',action='store_true',help='Borrar también las carpetas del proyecto y estos scripts')
a=p.parse_args()
h=Path.home()
niri=a.target in ('niri','both')
hypr=a.target in ('hyprland','both')
paths=[]
projects=[]
packages=[]
def installed(package):
    result=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',package],capture_output=True,text=True)
    return result.returncode==0 and result.stdout=='installed'
niri_installed=installed('niri') or Path('/usr/local/bin/niri').exists() or shutil.which('niri') is not None
hypr_installed=installed('hyprland') or shutil.which('Hyprland') is not None
print(f'Detectado: Niri={niri_installed}; Hyprland={hypr_installed}',flush=True)
if niri and a.purge_packages and installed('niri'):
    packages.append('niri')
if niri:
    projects.append(h/'cyberpunk-niri-legacy')
    paths += [h/'.config/niri',h/'.config/xdg-desktop-portal/niri-portals.conf',
        Path('/usr/local/bin/niri'),Path('/usr/local/bin/niri-session'),
        Path('/etc/systemd/user/niri.service'),Path('/etc/systemd/user/niri-shutdown.target'),
        Path('/usr/local/share/wayland-sessions/niri.desktop'),Path('/usr/share/wayland-sessions/niri.desktop')]
    # foot/fuzzel/mako/waybar/swaylock son herramientas compartidas.
    # Sus configuraciones globales se conservan aunque se quite Niri.
if hypr:
    projects.append(h/'cyberpunk-hyprland-legacy')
    paths += [h/'.config/hypr/hyprland.conf',h/'.config/hypr/monitors.conf',h/'.config/hypr/cyberpunk',
        h/'.config/xdg-desktop-portal/hyprland-portals.conf']
    paths.extend((h/'.config/hypr').glob('hyprland.conf.bak.*'))
    if a.purge_packages:
        packages += [x for x in ('hyprland','hyprland-guiutils','xdg-desktop-portal-hyprland') if installed(x)]
# Hack Nerd Font y la máscara de Waybar se conservan: pueden servir a otras sesiones.
# No borrar manualmente archivos que pertenezcan a paquetes Debian.
# Si se solicita purgar, dpkg/apt se encargan de sus archivos.
def package_owned(path):
    if not str(path).startswith(('/usr/', '/etc/')):
        return False
    return subprocess.run(['dpkg-query','-S',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
paths=[x for x in paths if not package_owned(x)]
for project in projects:
    if a.delete_projects:
        paths.append(project)
    else:
        paths.extend(project/x for x in ('backups','sources','downloads','.verify'))
# No seguir enlaces: rm elimina el enlace, no su destino.
paths=list(dict.fromkeys(str(x) for x in paths if x.exists() or x.is_symlink()))
print('BORRADO DEFINITIVO previsto (incluye configuraciones modificadas y respaldos):',flush=True)
for x in paths: print('  '+x,flush=True)
if packages: print('Paquetes a purgar: '+', '.join(packages),flush=True)
print('Se conservan Wayland, Xwayland, portales comunes, fuentes, configuraciones globales de herramientas, documentos, audio, red y GNOME.',flush=True)
print('Se conservan PAM, el gestor de acceso y la fuente APT de backports; pueden ser usados por otros componentes.',flush=True)
# Revisar el plan de APT incluso en simulación. Abortamos si quiere quitar
# cualquier paquete fuera de la lista exclusiva elegida, sin usar autoremove.
def check_apt_plan(privileged=False):
    command=(['sudo'] if privileged else [])+['apt-get','-s','-o','APT::Get::AutomaticRemove=false','purge',*packages]
    result=subprocess.run(command,capture_output=True,text=True,env={**os.environ,'LC_ALL':'C'})
    if result.returncode:
        raise SystemExit('APT no pudo resolver el plan; no se borró nada.\n'+result.stdout+result.stderr)
    removed={match.group(1).split(':')[0] for match in re.finditer(r'^(?:Remv|Purg)\s+(\S+)',result.stdout,re.M)}
    unexpected=removed-set(packages)
    if unexpected:
        raise SystemExit('Se cancela: APT también quitaría paquetes protegidos o ajenos: '+', '.join(sorted(unexpected)))
    # Una purga no debe instalar o actualizar paquetes como efecto colateral.
    if re.search(r'^Inst\s+',result.stdout,re.M):
        raise SystemExit('Se cancela: APT propone instalar o actualizar paquetes. Requiere revisión manual.')
    print('Plan APT verificado: solo paquetes exclusivos seleccionados.',flush=True)
if packages:
    check_apt_plan()
if not a.apply:
    print('Simulación: no se borró nada. Añade --apply para ejecutar este plan.')
    raise SystemExit(0)
# No romper una sesión actualmente en ejecución, aunque estés en otra TTY.
for selected,process in ((niri,'niri'),(hypr,'Hyprland')):
    if selected and subprocess.run(['pgrep','-u',str(os.getuid()),'-x',process],stdout=subprocess.DEVNULL).returncode==0:
        raise SystemExit('Cierra la sesión de '+process+' y ejecuta desde GNOME o una TTY antes de quitarlo.')
# Si greetd tiene una sesión fija de Niri, hay que seleccionar otro acceso primero.
if niri:
    greet=Path('/etc/greetd/config.toml')
    if greet.exists() and 'niri-session' in greet.read_text():
        if subprocess.run(['systemctl','is-enabled','--quiet','greetd.service']).returncode==0:
            raise SystemExit('greetd está habilitado con una sesión Niri fija. Configura primero otro acceso (por ejemplo GDM).')
subprocess.run(['sudo','-v'],check=True)
if packages:
    # Volver a comprobar justo antes de purgar. APT muestra su confirmación normal.
    check_apt_plan(privileged=True)
    subprocess.run(['sudo','apt-get','-o','APT::Get::AutomaticRemove=false','purge',*packages],check=True)
if paths:
    subprocess.run(['sudo','rm','-rf','--one-file-system','--',*paths],check=True)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
print('Limpieza completada. No se ejecutó autoremove ni se vació la caché global de APT.')
PY
