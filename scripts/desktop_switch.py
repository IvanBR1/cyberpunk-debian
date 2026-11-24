"""Administrar perfiles instalados y respaldar la configuración del usuario."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from render import Layout
from state import File, State, fingerprint

DESKTOPS = ('niri', 'hyprland', 'driftwm')
ROOT = Path(__file__).resolve().parents[1]


def snapshot(state, name, apply):
    records = state.load(name)['files']
    if not records:
        raise ValueError(f'{name} no tiene un perfil instalado.')
    if not apply:
        print(f'Respaldar {len(records)} archivos administrados de {name}')
        return
    folder = state.root/'snapshots'/name
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as tmp:
        entries = []
        for record in records:
            path = Path(record['path'])
            kind, digest = fingerprint(path)
            entry = dict(path=str(path), kind=kind)
            if kind == 'file':
                blob = folder/digest
                if not blob.exists():
                    candidate = Path(tmp)/'blob'
                    shutil.copyfile(path, candidate)
                    candidate.chmod(0o600)
                    candidate.replace(blob)
                entry.update(blob=digest, mode=path.stat().st_mode & 0o777)
            elif kind == 'link':
                entry['target'] = os.readlink(path)
            else:
                raise ValueError(f'Falta un archivo del perfil o cambió de tipo: {path}')
            entries.append(entry)
        index = Path(tmp)/'index'
        index.write_text(json.dumps(entries))
        index.replace(folder/'index.json')


def restore(state, name, apply):
    folder = state.root/'snapshots'/name
    records = {r['path']:r for r in state.load(name)['files']}
    entries = json.loads((folder/'index.json').read_text())
    if not records.keys() == {e['path'] for e in entries}:
        raise ValueError('El respaldo corresponde a otra instalación del perfil.')
    items = []
    for entry in entries:
        path = Path(entry['path'])
        system = records[str(path)]['system']
        if entry['kind'] == 'link':
            item = File(path, system=system, link=entry['target'])
        else:
            item = File(path, (folder/entry['blob']).read_bytes(), entry['mode'], system)
            if item.digest != entry['blob']:
                raise ValueError(f'Respaldo dañado: {path}')
        if fingerprint(path) != (entry['kind'],item.digest) or (
                entry['kind']=='file' and path.stat().st_mode & 0o777 != item.mode):
            items.append(item)
    for item in items:
        print('Restaurar',item.path)
        if apply:
            if item.path.is_dir() and not item.path.is_symlink():
                raise ValueError(f'El destino es un directorio: {item.path}')
            state.replace(item)
            doc = state.load(name)
            for record in doc['files']:
                if record['path']==str(item.path):
                    record['digest']=item.digest
                    record['type']='link' if item.link is not None else 'file'
            state.save(name,doc)
    if apply and items:
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action',required=True)
    sub.add_parser('status')
    for command in ('switch','backup','restore'):
        p = sub.add_parser(command)
        p.add_argument('desktop', choices=DESKTOPS)
        p.add_argument('--apply', action='store_true')
        if command=='switch':
            p.add_argument('--keep', action='store_true')
    import sys
    argv = ['--keep' if word=='keep' else word for word in sys.argv[1:]]
    args = parser.parse_args(argv)
    layout = Layout()
    state = State(layout.state)
    installed = [name for name in DESKTOPS if state.load(name)['files']]
    if args.action=='status':
        print('Perfiles administrados:', ', '.join(installed) or 'ninguno')
        return
    if args.apply and os.geteuid()==0:
        parser.error('Ejecuta como usuario de escritorio.')
    name=args.desktop
    if args.action=='backup':
        return snapshot(state,name,args.apply)
    if args.action=='restore':
        return restore(state,name,args.apply)
    remove=[] if args.keep else [d for d in installed if d!=name]
    print('Destino:',name,'· Retirar:',', '.join(remove) or 'ninguno',flush=True)
    for other in remove:
        binary='Hyprland' if other=='hyprland' else other
        if args.apply and subprocess.run(['pgrep','-u',str(os.getuid()),'-x',binary],
                                         stdout=subprocess.DEVNULL).returncode==0:
            raise ValueError(f'Cierra la sesión {other} y ejecuta desde una TTY.')
        for record in state.load(other)['files']:
            kind,digest=fingerprint(Path(record['path']))
            if kind!='absent' and digest!=record['digest']:
                raise ValueError(f"Edición local en {record['path']}. Revisa el archivo antes de retirar el perfil.")
    if name not in installed:
        subprocess.run([ROOT/'setup.sh','--desktop',name]+(['--apply'] if args.apply else []),check=True)
    if not args.apply:
        return
    for other in remove:
        if other=='driftwm':
            subprocess.run([ROOT/'uninstall.sh','--desktop','driftwm','--apply'],check=True)
            continue
        subprocess.run([ROOT/'uninstall.sh','--desktop',other,'--apply'],check=True)
    if remove:
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)


if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))
