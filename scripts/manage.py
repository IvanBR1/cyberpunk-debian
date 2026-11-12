#!/usr/bin/env python3
"""Orquestador portable. Plan primero; mutaciones solo con --apply."""
import argparse
from datetime import datetime
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from render import Layout, make_files, load_packages
from state import File, State, fingerprint

ROOT=Path(__file__).resolve().parents[1]
EXCLUSIVE={'niri':['niri'], 'hyprland':['hyprland','hyprland-guiutils','xdg-desktop-portal-hyprland']}

def call(args, **kwargs): return subprocess.run([str(v) for v in args],check=True,**kwargs)
def installed(package):
    if not shutil.which('dpkg-query'): return False
    r=subprocess.run(['dpkg-query','-W','-f=${db:Status-Status}',package],capture_output=True,text=True)
    return r.returncode==0 and r.stdout=='installed'
def detect_profile():
    r=subprocess.run(['systemd-detect-virt'],capture_output=True,text=True) if shutil.which('systemd-detect-virt') else None
    return 'vmware' if r and r.stdout.strip()=='vmware' else 'generic'
def desktops(value): return ['niri','hyprland'] if value=='both' else [value]
def os_release():
    return dict(line.split('=',1) for line in Path('/etc/os-release').read_text().replace('"','').splitlines() if '=' in line)
def read_versions(): return json.loads((ROOT/'versions.json').read_text())
def resolve_options(args):
    profile=detect_profile() if args.profile=='auto' else args.profile
    metadata=json.loads((ROOT/'hardware'/profile/'profile.json').read_text())
    if args.vmware_legacy_drm and (not metadata['supports_legacy_drm'] or args.desktop=='niri'):
        raise ValueError('--vmware-legacy-drm solo es válido para Hyprland en el perfil vmware.')
    if not re.fullmatch(r'[a-zA-Z0-9_,+-]+',args.keyboard): raise ValueError('Distribución de teclado inválida.')
    if args.resolution not in ('preserve','auto'):
        if not re.fullmatch(r'[1-9]\d{2,4}x[1-9]\d{2,4}(?:@\d+(?:\.\d+)?)?',args.resolution): raise ValueError('Resolución inválida.')
        if not args.output or not re.fullmatch(r'[a-zA-Z0-9_.-]+',args.output): raise ValueError('Indica --output con el nombre del monitor de esta máquina.')
    addons=[] if args.addons=='none' else list(dict.fromkeys(args.addons.split(',')))
    if set(addons)-{'office','widgets','clipboard','controls'}: raise ValueError('Complemento desconocido.')
    if 'controls' in addons and args.desktop!='hyprland':
        raise ValueError('El complemento controls requiere --desktop hyprland.')
    return profile,addons

def display_text(layout,args,desktop):
    if args.resolution!='preserve': return None
    if desktop=='niri':
        path=layout.config/'cyberpunk-desktop/hardware/niri-display.conf'
        return path.read_text() if path.exists() else None
    # Importar solo reglas monitor, nunca variables AQ_* ni hacks del equipo anterior.
    paths=[layout.config/'cyberpunk-desktop/hardware/hyprland-display.conf',layout.config/'hypr/monitors.conf']
    if 'controls' in args.addons.split(','):paths.reverse()
    for path in paths:
        if path.exists():
            lines=[line for line in path.read_text().splitlines() if re.match(r'^\s*monitor\s*=',line)]
            if lines: return '# Reglas locales conservadas, separadas del tema.\n'+'\n'.join(lines)+'\n'
    return None

def niri_binary(layout,args):
    own=layout.root/'niri/bin/niri'
    if args.niri_source=='build': return str(own)
    return shutil.which('niri') or (str(own) if own.exists() else str(own))

def render_all(layout,args):
    profile,addons=resolve_options(args)
    return {d:make_files(ROOT,layout,d,profile,args.theme,addons,args.keyboard,args.resolution,args.output,
                         args.vmware_legacy_drm and d=='hyprland',display_text(layout,args,d),niri_binary(layout,args))
            for d in desktops(args.desktop)}

def validate(files, require=False):
    # Referenciar archivos temporales durante el análisis, sin instalar nada.
    unique={str(f.path):f for group in files.values() for f in group}
    with tempfile.TemporaryDirectory(prefix='cyberpunk-check-') as name:
        folder=Path(name); mapping={dest:str(folder/str(i)) for i,dest in enumerate(unique)}
        for dest,item in unique.items():
            data=item.data
            try:
                text=data.decode()
                for old,new in sorted(mapping.items(),key=lambda x:-len(x[0])): text=text.replace(old,new)
                data=text.encode()
            except UnicodeDecodeError: pass
            Path(mapping[dest]).write_bytes(data)
        for desktop,items in files.items():
            config=next(f for f in items if f.path.name==('config.kdl' if desktop=='niri' else 'hyprland.conf'))
            binary=shutil.which('niri' if desktop=='niri' else 'Hyprland')
            if desktop=='niri' and not binary:
                candidate=next(f for f in items if f.path.name=='cyberpunk-niri.service')
                match=re.search(r'^ExecStart=(.+?) --session',candidate.data.decode(),re.M)
                if match and Path(match[1]).is_file(): binary=match[1]
            if not binary:
                if require: raise RuntimeError(f'Falta {desktop} para validar. Instala paquetes o usa el modo de instalación completo.')
                print(f'Validación {desktop}: pendiente (compositor ausente).');continue
            if desktop=='hyprland':
                version=subprocess.run([binary,'--version'],capture_output=True,text=True).stdout
                series=read_versions()['hyprland']['config_series']
                if not re.search(r'Hyprland '+re.escape(series)+r'\.',version):
                    raise RuntimeError(f'La plantilla Hyprland está validada para {series}.x; no se aplicará a otra serie sin revisión.')
            cmd=[binary,'validate','-c',mapping[str(config.path)]] if desktop=='niri' else [binary,'--verify-config','-c',mapping[str(config.path)]]
            r=subprocess.run(cmd,capture_output=True,text=True)
            if r.returncode: raise RuntimeError(f'Configuración {desktop} inválida:\n'+r.stdout+r.stderr)
            print(f'Validación {desktop}: correcta.')

def stable_and_backports(args,profile,addons):
    stable=load_packages(ROOT,['packages/common.txt',f'hardware/{profile}/packages.txt']+[f'addons/{x}.txt' for x in addons])
    backports=[]
    for d in desktops(args.desktop):
        pkgs=load_packages(ROOT,[f'environments/{d}/packages.txt'])
        if d=='hyprland': backports+=pkgs
        else:
            stable+=pkgs
            if args.niri_source=='build' or not shutil.which('niri'):
                stable+=load_packages(ROOT,['environments/niri/build-packages.txt'])
    if args.login_manager=='greetd': stable+=['greetd','tuigreet']
    return list(dict.fromkeys(stable)),list(dict.fromkeys(backports))

def ensure_backports():
    r=call(['apt-cache','policy'],capture_output=True,text=True)
    if 'trixie-backports' not in r.stdout:
        # Conservar repositorios previos; no editar sources.list.
        dest=Path('/etc/apt/sources.list.d/cyberpunk-desktop-backports.list')
        if dest.exists() and dest.read_text().strip()!='deb https://deb.debian.org/debian trixie-backports main':
            raise RuntimeError(f'Repositorio personalizado en {dest}; se conserva. Revísalo manualmente.')
        State.replace(File(dest,b'deb https://deb.debian.org/debian trixie-backports main\n',system=True))

def install_packages(args,profile,addons):
    release=os_release()
    if release.get('ID')!='debian' or release.get('VERSION_ID')!='13':
        raise RuntimeError('Instalación de paquetes disponible para Debian 13. En otra distribución usa --configure-only con las dependencias instaladas.')
    stable,backports=stable_and_backports(args,profile,addons)
    call(['sudo','-v'])
    if backports: ensure_backports()
    call(['sudo','apt-get','update'])
    if backports:
        policy=call(['apt-cache','-o','APT::Default-Release=trixie-backports','policy','hyprland'],capture_output=True,text=True,env={**os.environ,'LC_ALL':'C'}).stdout
        candidate=re.search(r'Candidate:\s+(\S+)',policy)
        series=read_versions()['hyprland']['config_series']
        if not candidate or not re.match(r'(?:\d+:)?'+re.escape(series)+r'\.',candidate.group(1)):
            raise RuntimeError('La versión candidata de Hyprland no coincide con la serie validada; revisa versions.json y las plantillas antes de instalar.')
    call(['sudo','apt-get','--no-remove','install','-y',*stable])
    if backports: call(['sudo','apt-get','--no-remove','install','-y','-t','trixie-backports',*backports])


def build_niri(layout,args):
    if 'niri' not in desktops(args.desktop): return None
    binary=Path(niri_binary(layout,args))
    if binary.exists() and args.niri_source!='build': return None
    if args.configure_only: raise RuntimeError('Niri no está instalado; --configure-only no lo compila.')
    info=read_versions()['niri']; cache=Path.home()/'.cache/cyberpunk-desktop'
    source=cache/('niri-'+info['tag']);cache.mkdir(parents=True,exist_ok=True)
    if not source.exists(): call(['git','clone','--depth','1','--branch',info['tag'],info['url'],source])
    commit=call(['git','-C',source,'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
    if commit!=info['commit']: raise RuntimeError('La revisión Niri no coincide con versions.json.')
    if call(['git','-C',source,'status','--porcelain'],capture_output=True,text=True).stdout.strip():
        raise RuntimeError('El árbol fuente de Niri tiene cambios locales; no se compila automáticamente.')
    # Independiente de la cantidad de RAM: no inferir optimizaciones solo por GB.
    # --build-jobs permite limitar la compilación en máquinas pequeñas.
    call(['/usr/bin/cargo','build','--locked','--release','--bin','niri','--jobs',str(args.build_jobs)],cwd=source)
    return File(layout.root/'niri/bin/niri',(source/'target/release/niri').read_bytes(),0o755)

def font_files(layout):
    info=read_versions()['font']; cache=Path.home()/'.cache/cyberpunk-desktop';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/f'Hack-{info["version"]}.zip'
    if not archive.exists() or sha256(archive.read_bytes()).hexdigest()!=info['sha256']:
        partial=archive.with_suffix('.part')
        call(['curl','--fail','--location','--retry','3','--connect-timeout','20',info['url'],'-o',partial])
        if sha256(partial.read_bytes()).hexdigest()!=info['sha256']: raise RuntimeError('SHA256 de Hack Nerd Font incorrecto.')
        partial.replace(archive)
    files=[]
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.endswith('.ttf') or Path(name).name in ('LICENSE.md','LICENSE.txt','OFL.txt'):
                files.append(File(layout.data/'fonts/cyberpunk-desktop/Hack'/Path(name).name,z.read(name)))
    return files

def preflight(args):
    # Evitar detener o reemplazar el gestor de inicio de sesión actual.
    if args.login_manager=='greetd':
        manager=Path('/etc/systemd/system/display-manager.service')
        if manager.exists() and manager.resolve().name!='greetd.service':
            raise RuntimeError('Ya hay otro gestor de acceso. Usa --login-manager keep; no se reemplaza automáticamente.')

def install(args):
    layout=Layout();profile,addons=resolve_options(args)
    preflight(args)
    groups=render_all(layout,args)
    print(f'Entornos: {args.desktop}; hardware: {profile}; tema: {args.theme}; complementos: {addons}')
    if args.vmware_legacy_drm: print('Workaround DRM VMware solicitado explícitamente; requiere sesión nueva. No se considera verificado universalmente.')
    stable,backports=stable_and_backports(args,profile,addons)
    print('Paquetes estables:',', '.join(stable))
    print('Paquetes backports:',', '.join(backports) or '(ninguno)')
    for desktop,items in groups.items():
        print(f'Archivos {desktop}:')
        for item in items: print('  '+str(item.path))
    state=State(layout.state)
    for desktop,items in groups.items():
        for item in items:
            owner='shared' if item.path in {layout.runtime,layout.config/'systemd/user/waybar.service',layout.data/'applications/foot.desktop'} else desktop
            record=next((v for v in state.load(owner)['files'] if v['path']==str(item.path)),None)
            if record and fingerprint(item.path)[1]!=record['digest'] and not args.overwrite:
                raise RuntimeError(f'Hay cambios locales en {item.path}; revisa el plan o usa --overwrite para respaldarlos.')
    validate(groups)
    if not args.apply:
        print('PLAN: no se instaló ni reemplazó ningún archivo. Añade --apply para ejecutar.')
        return
    if not args.configure_only: install_packages(args,profile,addons)
    elif any(f.system and fingerprint(f.path)[1]!=f.digest for fs in groups.values() for f in fs): call(['sudo','-v'])
    binary=build_niri(layout,args)
    # Validar Niri recién compilado sin instalarlo previamente.
    if binary:
        with tempfile.TemporaryDirectory() as tmp:
            candidate=Path(tmp)/'niri';candidate.write_bytes(binary.data);candidate.chmod(0o755)
            niri_config=next(f for f in groups['niri'] if f.path.name=='config.kdl')
            conf=Path(tmp)/'config.kdl';conf.write_bytes(niri_config.data)
            call([candidate,'validate','-c',conf])
        # validate() debe encontrar la compilación en su ruta final; validar los demás ahora.
        validate({k:v for k,v in groups.items() if k!='niri'},require=True)
    else: validate(groups,require=True)
    state=State(layout.state)
    shared_paths={layout.runtime,layout.config/'systemd/user/waybar.service',layout.data/'applications/foot.desktop'}
    if args.theme=='cyberpunk' and not args.configure_only:
        for item in font_files(layout):
            if args.overwrite: state.allow_overwrite('shared',item)
            state.write('shared',item)
        call(['fc-cache','-f',layout.data/'fonts/cyberpunk-desktop'])
    if binary:
        if args.overwrite: state.allow_overwrite('niri',binary)
        state.write('niri',binary)
    for desktop,items in groups.items():
        for item in items:
            owner='shared' if item.path in shared_paths else desktop
            if args.overwrite: state.allow_overwrite(owner,item)
            state.write(owner,item)
        doc=state.load(desktop);doc['settings']={'profile':profile,'theme':args.theme,'addons':addons};state.save(desktop,doc)
    call(['systemctl','--user','daemon-reload'])
    # Los paquetes de audio usan socket activation; no sustituir servidores de audio existentes.
    if not args.configure_only:
        call(['systemctl','--user','enable','pipewire.socket','pipewire-pulse.socket','wireplumber.service'])
    if profile=='vmware' and not args.configure_only: call(['sudo','systemctl','enable','open-vm-tools.service'])
    if args.login_manager=='greetd':
        conf=b'[terminal]\nvt = 1\n[default_session]\ncommand = "/usr/bin/tuigreet --time --sessions /usr/share/wayland-sessions"\nuser = "_greetd"\n'
        item=File(Path('/etc/greetd/config.toml'),conf,system=True)
        if args.overwrite: state.allow_overwrite('shared',item)
        state.write('shared',item)
        call(['sudo','systemctl','enable','greetd.service'])
    print(f'Aplicado. Manifiestos y respaldos: {layout.state}')
    print('No se reinició ni se cerró la sesión. En el próximo acceso selecciona el entorno (Cyberpunk).')
    if args.configure_only: print('Modo configuración: no se instalaron paquetes ni fuentes; verifica dependencias con doctor.sh.')


def apt_guard(text,allowed):
    removed={m.group(1).split(':')[0] for m in re.finditer(r'^(?:Remv|Purg)\s+(\S+)',text,re.M)}
    if removed-set(allowed): raise RuntimeError('APT quitaría paquetes ajenos: '+', '.join(sorted(removed-set(allowed))))
    if re.search(r'^Inst\s+',text,re.M): raise RuntimeError('APT propone instalar/actualizar paquetes durante la purga.')

def uninstall(args):
    layout=Layout();state=State(layout.state);chosen=desktops(args.desktop)
    packages=[p for d in chosen for p in EXCLUSIVE[d] if installed(p)] if args.purge_packages else []
    docs={d:state.load(d) for d in chosen}
    for d,doc in docs.items():
        print(d+':')
        if not doc['files']: print('  Sin manifiesto: no se borrarán archivos ajenos. Para instalaciones antiguas usa scripts/legacy-uninstall.sh.')
        for f in doc['files']: print('  Restaurar original o quitar: '+f['path'])
        if args.delete_backups: print('  Borrar respaldos administrados de '+d+' después de restaurar.')
    last=not any(state.load(d)['files'] for d in ('niri','hyprland') if d not in chosen)
    if args.remove_shared and not last: raise RuntimeError('El otro entorno sigue instalado; sus componentes compartidos se conservan.')
    if args.remove_shared:
        for f in state.load('shared')['files']: print('  Compartido administrado: '+f['path'])
    if packages:
        r=call(['apt-get','-s','-o','APT::Get::AutomaticRemove=false','purge',*packages],capture_output=True,text=True,env={**os.environ,'LC_ALL':'C'})
        apt_guard(r.stdout,packages);print('APT: '+', '.join(packages)+'; sin autoremove.')
    if not args.apply:
        print('PLAN de desinstalación: no se borró nada. Añade --apply.');return
    # Si el ejecutable está activo en otra TTY, tampoco se elimina.
    for d in chosen:
        if subprocess.run(['pgrep','-u',str(os.getuid()),'-x','Hyprland' if d=='hyprland' else 'niri'],stdout=subprocess.DEVNULL).returncode==0:
            raise RuntimeError(f'Cierra la sesión {d} y entra en GNOME o una TTY antes de desinstalar.')
    if args.remove_shared:
        greet=Path('/etc/greetd/config.toml')
        if greet.exists() and 'cyberpunk-' in greet.read_text(): raise RuntimeError('Revisa primero el acceso greetd que utiliza estas sesiones.')
    call(['sudo','-v'])
    if packages:
        r=call(['sudo','apt-get','-s','-o','APT::Get::AutomaticRemove=false','purge',*packages],capture_output=True,text=True,env={**os.environ,'LC_ALL':'C'})
        apt_guard(r.stdout,packages)
        call(['sudo','apt-get','-o','APT::Get::AutomaticRemove=false','purge',*packages])
    for d in chosen:
        complete=state.restore(d,force=args.force)
        if args.delete_backups and complete:
            folder=layout.state/'backups'/d
            if folder.exists(): shutil.rmtree(folder)
            (layout.state/'manifests'/f'{d}.json').unlink(missing_ok=True)
        elif args.delete_backups: print(f'Respaldos de {d} conservados: hay archivos modificados sin restaurar.')
    if args.remove_shared and all(not state.load(d)['files'] for d in ('niri','hyprland')):
        complete=state.restore('shared',force=args.force)
        if args.delete_backups and complete:
            shutil.rmtree(layout.state/'backups/shared',ignore_errors=True)
            (layout.state/'manifests/shared.json').unlink(missing_ok=True)
    if args.purge_cache and last:
        shutil.rmtree(layout.home/'.cache/cyberpunk-desktop',ignore_errors=True)
    call(['systemctl','--user','daemon-reload'])
    print('Limpieza terminada. Wayland, Xwayland, audio, LibreOffice y paquetes comunes se conservan.')


def doctor(_args):
    print('Sistema:',os_release().get('PRETTY_NAME'));print('Perfil detectado:',detect_profile())
    mem=next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))
    print(mem,'(no se infieren ajustes solo por GB)')
    for binary in ['niri','Hyprland','waybar','mako','foot','fuzzel','swaylock','swayidle','wl-paste','pipewire','wpctl','vmtoolsd']:
        print(binary+':',shutil.which(binary) or 'no encontrado en PATH')
    for package in ['libreoffice-gtk3','hyprland-guiutils','open-vm-tools-desktop']:
        print(package+':', 'instalado' if installed(package) else 'ausente/no Debian')
    font=subprocess.run(['fc-match','-f','%{family}\n','Hack Nerd Font'],capture_output=True,text=True) if shutil.which('fc-match') else None
    print('Fuente resuelta:',font.stdout.strip() if font else 'fontconfig ausente')
    if shutil.which('hyprctl'):
        for args in [['hyprctl','configerrors'],['hyprctl','monitors']]:
            r=subprocess.run(args,capture_output=True,text=True);print(r.stdout.strip() or r.stderr.strip())
    print('Diagnóstico de lectura: no se cambió ningún ajuste ni se registraron contraseñas.')


def export(args):
    dest=Path(args.output).expanduser() if args.output else ROOT/'dist/cyberpunk-portable-1.0.tar.gz'
    dest=dest.resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    excluded={'dist','__pycache__','.git','.cache','backups','downloads','sources','state'}
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.name!='SHA256SUMS' and not p.is_symlink() and not set(p.relative_to(ROOT).parts)&excluded and p.resolve()!=dest]
    sums=''.join(f'{sha256(p.read_bytes()).hexdigest()}  {p.relative_to(ROOT).as_posix()}\n' for p in sorted(files))
    with tarfile.open(dest,'w:gz') as archive:
        for p in sorted(files): archive.add(p,arcname='cyberpunk-portable/'+p.relative_to(ROOT).as_posix(),recursive=False)
        info=tarfile.TarInfo('cyberpunk-portable/SHA256SUMS');data=sums.encode();info.size=len(data);info.mode=0o644
        archive.addfile(info,io.BytesIO(data))
    print(f'Exportado: {dest}\nSHA256: {sha256(dest.read_bytes()).hexdigest()}\nSin respaldos, cachés, fuentes compiladas ni archivos personales.')


def parser():
    p=argparse.ArgumentParser(description='Cyberpunk Desktop: entornos, hardware y tema independientes. Plan por defecto.')
    subs=p.add_subparsers(dest='command',required=True)
    i=subs.add_parser('install');i.add_argument('--desktop',choices=['niri','hyprland','both'],required=True)
    i.add_argument('--profile',choices=['auto','generic','vmware'],default='auto')
    i.add_argument('--theme',choices=['cyberpunk','plain'],default='cyberpunk')
    i.add_argument('--addons',default='office,widgets,clipboard',help='office,widgets,clipboard,controls o none')
    i.add_argument('--keyboard',default='latam');i.add_argument('--resolution',default='preserve')
    i.add_argument('--output',help='Nombre real de salida; obligatorio con resolución explícita')
    i.add_argument('--vmware-legacy-drm',action='store_true',help='Workaround opcional AQ_NO_ATOMIC=1; solo Hyprland+vmware')
    i.add_argument('--login-manager',choices=['keep','greetd'],default='keep')
    i.add_argument('--configure-only',action='store_true');i.add_argument('--niri-source',choices=['auto','build'],default='auto')
    i.add_argument('--build-jobs',type=int,default=2,help='Trabajos Cargo; ajustable según recursos, no tuning de RAM del sistema')
    i.add_argument('--apply',action='store_true');i.add_argument('--overwrite',action='store_true',help='Respaldar y reemplazar ediciones posteriores al primer despliegue')
    u=subs.add_parser('uninstall');u.add_argument('--desktop',choices=['niri','hyprland','both'],required=True)
    for opt in ['apply','purge-packages','delete-backups','remove-shared','purge-cache','force']: u.add_argument('--'+opt,action='store_true')
    usb=subs.add_parser('usb-power',help='Control optativo de suspensión USB de adaptadores Bluetooth')
    for opt in ['apply','persistent','restore']:usb.add_argument('--'+opt,action='store_true')
    subs.add_parser('doctor');e=subs.add_parser('export');e.add_argument('--output')
    return p

def usb_power(args):
    import usb_power as module
    if args.restore and args.persistent:raise ValueError('--restore y --persistent son excluyentes.')
    module.manage(args)

def main():
    args=parser().parse_args()
    if os.geteuid()==0 and args.command in ('install','uninstall','usb-power'): raise SystemExit('Ejecuta como tu usuario, sin sudo. El script lo solicita cuando hace falta.')
    if getattr(args,'build_jobs',1)<1: raise SystemExit('--build-jobs debe ser positivo.')
    try: globals()[args.command.replace('-','_')](args)
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit('ERROR: '+str(exc)) from exc
if __name__=='__main__': main()
