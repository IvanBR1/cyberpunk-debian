"""Instalación administrada de driftwm y del perfil Cyberpunk."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile

from state import File, State, fingerprint
from manage import installed, installed_packages, apt_guard

ROOT = Path(__file__).resolve().parents[1]
DEPS = ('build-essential', 'git', 'pkg-config', 'libseat-dev', 'libdisplay-info-dev',
        'libinput-dev', 'libudev-dev', 'libgbm-dev', 'libxkbcommon-dev', 'libwayland-dev')
MATCHING_DEV = {'libxkbcommon-dev':'libxkbcommon0', 'libgbm-dev':'libgbm1',
                'libwayland-dev':'libwayland-client0'}


def run(*command, **kwargs):
    return subprocess.run([str(x) for x in command], check=True, **kwargs)


def dependency_packages():
    packages = []
    for package in DEPS:
        runtime = MATCHING_DEV.get(package)
        if runtime:
            result = subprocess.run(['dpkg-query','-W','-f=${Version}',runtime],
                                    capture_output=True,text=True)
            if result.returncode == 0:
                package += '=' + result.stdout
        packages.append(package)
    return packages


def profile_files():
    config = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')
    directory = config/'driftwm'
    bar = directory/'cyberpunk-waybar.json'
    style = directory/'cyberpunk.css'
    command = shlex.join(['waybar', '-c', str(bar), '-s', str(style)])
    widgets = ROOT/'themes/cyberpunk/common/widgets'
    panel = shlex.join(['env','CYBERPUNK_DESKTOP=driftwm','/usr/bin/python3',str(directory/'widgets/dashboard.py')])
    profile = 'autostart = ' + json.dumps([command,panel], ensure_ascii=False) + '\n'
    assets = ROOT/'themes/cyberpunk/driftwm'
    shader = directory/'skyline.glsl'
    profile += '\n[background]\ntype = "shader"\npath = ' + json.dumps(str(shader),ensure_ascii=False) + '\n'
    profile += '\n[input.keyboard]\nlayout = "latam"\n'
    foot_config = directory/'foot.ini'
    terminal = directory/'bin/foot'
    profile += '\n[env]\nSAL_USE_VCLPLUGIN = "gtk3"\n'
    profile += 'TERMINAL = ' + json.dumps(str(terminal),ensure_ascii=False) + '\n'
    profile += 'XDG_CONFIG_DIRS = ' + json.dumps(os.pathsep.join([str(directory/'defaults'),os.environ.get('XDG_CONFIG_DIRS') or '/etc/xdg']),ensure_ascii=False) + '\n'
    profile += '\n[session]\nrestore_windows = false\n'
    profile += '\n[decorations]\nbg_color = "#08090e"\nfg_color = "#66bdff"\n'
    profile += '\n[[window_rules]]\napp_id = "foot"\ndecoration = "server"\n'
    hyprbar = ROOT/'themes/cyberpunk/hyprland/waybar'
    modules = json.loads((hyprbar/'config.jsonc').read_text())
    modules['modules-left'].remove('hyprland/workspaces')
    del modules['hyprland/workspaces']
    modules['custom/launcher'].update(format='󰣇  CYBER // DRIFTWM', **{'on-click':'fuzzel'})
    modules['custom/dashboard']['on-click'] = panel+' --toggle'
    vmware_files = []
    original = Path('/usr/share/applications/vmware-workstation.desktop')
    if original.is_file() and Path('/usr/bin/vmware').is_file():
        launcher = directory/'vmware-launch.py'
        entry = original.read_text().replace('Exec=/usr/bin/vmware ', 'Exec=/usr/bin/python3 '+json.dumps(str(launcher))+' ',1)
        data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')
        vmware_files = [File(launcher,(assets/'vmware-launch.py').read_bytes()),
                        File(data_home/'applications/vmware-workstation.desktop',entry.encode())]
    return [*vmware_files,*[File(directory/'widgets'/name,(widgets/name).read_bytes())
              for name in ('dashboard.py','metrics.py','media.py')],
            File(bar,json.dumps(modules,indent=2).encode()),
            File(foot_config,(ROOT/'themes/cyberpunk/common/foot/foot.ini').read_bytes()),
            File(directory/'defaults/foot/foot.ini',link=str(foot_config)),
            File(terminal,('#!/bin/sh\nexec /usr/bin/foot -c '+shlex.quote(str(foot_config))+' "$@"\n').encode(),0o755),
            File(style,(hyprbar/'style.css').read_bytes()),
            File(shader,(assets/'skyline.glsl').read_bytes()),
            File(directory/'config.toml',profile.encode())]


def staged_files(stage):
    """Usar el manifiesto del Makefile upstream sin ejecutar su uninstall destructivo."""
    root = Path(stage)/'usr/local'
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_file():
            files.append(File(Path('/usr/local')/path.relative_to(root), path.read_bytes(),
                              path.stat().st_mode & 0o777, True))
    reference = Path(stage)/'etc/driftwm/config.reference.toml'
    if reference.is_file():
        files.append(File(Path('/etc/driftwm/config.reference.toml'), reference.read_bytes(), system=True))
    if not any(item.path == Path('/usr/local/bin/driftwm') for item in files):
        raise RuntimeError('La compilación no produjo driftwm.')
    return files


def ensure_safe(state, files, overwrite):
    records = {r['path']:r for r in state.load('driftwm')['files']}
    for item in files:
        typ, digest = fingerprint(item.path)
        if typ == 'directory':
            raise RuntimeError(f'El destino es un directorio: {item.path}')
        record = records.get(str(item.path))
        if record and typ != 'absent' and digest != record['digest'] and not overwrite:
            raise RuntimeError(f'Cambios locales en {item.path}; usa --overwrite para respaldarlos.')
        if not record and typ != 'absent' and item.system:
            raise RuntimeError(f'Instalación ajena en {item.path}; desinstálala antes de usar este instalador.')


def install(args, state):
    files = profile_files()
    print('Perfil:', *(str(f.path) for f in files), sep='\n  ')
    print('Compositor: compilación oficial desde código fuente; archivos de /usr/local y referencia de /etc administrados.')
    print('Dependencias Debian:', ', '.join(DEPS), '; Rust y Cargo desde trixie-backports; waybar.')
    ensure_safe(state, files, args.overwrite)
    if not args.apply:
        print('PLAN: añade --apply para instalar.'); return
    if args.configure_only:
        if not shutil.which('driftwm'):
            raise RuntimeError('--configure-only requiere driftwm ya instalado.')
        if not shutil.which('waybar'):
            raise RuntimeError('--configure-only requiere waybar.')
        binary = shutil.which('driftwm')
        system_files = []
    else:
        release = Path('/etc/os-release').read_text()
        if 'ID=debian' not in release or 'VERSION_ID="13"' not in release and 'VERSION_ID=13' not in release:
            raise RuntimeError('La compilación automática requiere Debian 13; usa --configure-only con driftwm instalado.')
        policy = subprocess.run(['apt-cache','policy'],capture_output=True,text=True,check=True).stdout
        backports = None
        if 'trixie-backports' not in policy:
            backports = File(Path('/etc/apt/sources.list.d/cyberpunk-driftwm-backports.list'),
                             b'deb https://deb.debian.org/debian trixie-backports main\n',system=True)
            ensure_safe(state,[backports],args.overwrite)
        run('sudo','-v')
        if backports:
            state.write('driftwm',backports)
        before = installed_packages()
        run('sudo','apt-get','update')
        packages = dependency_packages()
        widget_packages = [p for p in (ROOT/'addons/widgets.txt').read_text().splitlines() if p and not p.startswith('#')]
        office_packages = [p for p in (ROOT/'addons/office.txt').read_text().splitlines() if p and not p.startswith('#')]
        run('sudo','apt-get','--no-remove','install','-y',*packages,'foot','waybar','fuzzel','playerctl','pavucontrol','wireplumber','brightnessctl',*widget_packages,*office_packages)
        run('sudo','apt-get','--no-remove','install','-y','-t','trixie-backports','rustc','cargo')
        doc = state.load('driftwm')
        doc['packages'] = sorted(set(doc.get('packages',[])) | (installed_packages()-before))
        state.save('driftwm',doc)
        with tempfile.TemporaryDirectory(prefix='cyberpunk-drift-') as tmp:
            source = Path(tmp)/'source'
            run('git','clone','--depth','1','https://github.com/malbiruk/driftwm.git',source)
            run('make','build',cwd=source,env={**os.environ,'CARGO_BUILD_JOBS':str(args.build_jobs)})
            stage = Path(tmp)/'stage'
            run('make','install',f'DESTDIR={stage}',cwd=source)
            system_files = staged_files(stage)
            ensure_safe(state, system_files + files, args.overwrite)
            candidate = stage/'usr/local/bin/driftwm'
            binary = str(candidate)
            validate(binary, files[-1])
            for item in system_files:
                if args.overwrite: state.allow_overwrite('driftwm',item)
                state.write('driftwm',item)
    if args.configure_only: validate(binary, files[-1])
    for item in files:
        if args.overwrite: state.allow_overwrite('driftwm',item)
        state.write('driftwm',item)
    if system_files:
        run('systemctl','--user','daemon-reload')
    print('DriftWM y perfil instalados. Selecciona driftwm al iniciar sesión.')


def validate(binary, config):
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)/'driftwm'
        directory.mkdir()
        (directory/'config.toml').write_bytes(config.data)
        run(binary,'--check-config',env={**os.environ,'XDG_CONFIG_HOME':tmp})


def uninstall(args, state):
    records = state.load('driftwm')['files']
    packages = [p for p in state.load('driftwm').get('packages',[]) if installed(p)] if args.purge_packages else []
    if packages:
        result = subprocess.run(['apt-get','-s','-o','APT::Get::AutomaticRemove=false','purge',*packages],
                                capture_output=True,text=True,check=True,env={**os.environ,'LC_ALL':'C'})
        apt_guard(result.stdout,packages)
        print('Paquetes APT:',', '.join(packages))
    for record in records: print('Restaurar original o quitar:',record['path'])
    if not records: print('No hay archivos administrados de driftwm.')
    if not args.apply:
        print('PLAN: añade --apply para desinstalar.'); return
    if subprocess.run(['pgrep','-u',str(os.getuid()),'-x','driftwm'],stdout=subprocess.DEVNULL).returncode == 0:
        raise RuntimeError('Cierra la sesión driftwm y entra desde otra sesión o TTY.')
    if packages or any(r['system'] for r in records): run('sudo','-v')
    if packages:
        result = subprocess.run(['sudo','apt-get','-s','-o','APT::Get::AutomaticRemove=false','purge',*packages],
                                capture_output=True,text=True,check=True,env={**os.environ,'LC_ALL':'C'})
        apt_guard(result.stdout,packages)
        run('sudo','apt-get','-o','APT::Get::AutomaticRemove=false','purge',*packages)
    complete = state.restore('driftwm',force=args.force)
    if complete and args.purge_packages:
        doc=state.load('driftwm');doc['packages']=[];state.save('driftwm',doc)
    if args.delete_backups and complete:
        shutil.rmtree(state.root/'backups/driftwm',ignore_errors=True)
        (state.root/'manifests/driftwm.json').unlink(missing_ok=True)
    elif args.delete_backups:
        print('Respaldos conservados: hay archivos modificados sin restaurar.')
    run('systemctl','--user','daemon-reload')
    print('Desinstalación terminada.' if complete else 'Se conservaron archivos con cambios locales.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install','uninstall'])
    parser.add_argument('--desktop', choices=['driftwm'], required=True)
    for flag in ('apply','overwrite','configure-only','force','delete-backups','purge-packages'):
        parser.add_argument('--'+flag, action='store_true')
    parser.add_argument('--build-jobs',type=int,default=2)
    args = parser.parse_args()
    if os.geteuid()==0: parser.error('Ejecuta como usuario normal; sudo se solicitará cuando haga falta.')
    if args.build_jobs < 1: parser.error('--build-jobs debe ser positivo.')
    state = State(Path.home()/'.local/state/cyberpunk-desktop')
    try:
        (install if args.action=='install' else uninstall)(args,state)
    except (OSError,RuntimeError,ValueError,subprocess.CalledProcessError) as exc:
        raise SystemExit('ERROR: '+str(exc)) from exc


if __name__ == '__main__': main()
