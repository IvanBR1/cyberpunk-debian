"""Archivos administrados, respaldo inicial y restauración con verificación de cambios."""
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

@dataclass
class File:
    path: Path
    data: bytes = b''
    mode: int = 0o644
    system: bool = False
    link: str | None = None

    @property
    def digest(self):
        return sha256(self.link.encode() if self.link is not None else self.data).hexdigest()

def fingerprint(path):
    if path.is_symlink(): return 'link', sha256(os.readlink(path).encode()).hexdigest()
    if path.is_file(): return 'file', sha256(path.read_bytes()).hexdigest()
    if path.exists(): return 'directory', ''
    return 'absent', ''

class State:
    def __init__(self, root): self.root=Path(root)
    def load(self, desktop):
        p=self.root/'manifests'/f'{desktop}.json'
        return json.loads(p.read_text()) if p.exists() else {'schema':1,'files':[]}
    def save(self, desktop, doc):
        p=self.root/'manifests'/f'{desktop}.json'
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd,name=tempfile.mkstemp(dir=p.parent)
        with os.fdopen(fd,'w') as handle: json.dump(doc,handle,indent=2);handle.write('\n')
        os.replace(name,p)
    def write(self, desktop, item):
        doc=self.load(desktop)
        existing=next((v for v in doc['files'] if v['path']==str(item.path)),None)
        typ, digest=fingerprint(item.path)
        if typ=='directory': raise RuntimeError(f'El destino es un directorio: {item.path}')
        desired_type='link' if item.link is not None else 'file'
        if existing and digest!=existing['digest']:
            raise RuntimeError(f'Hay cambios locales en {item.path}. Usa --overwrite para respaldarlos y reemplazarlos.')
        if not existing:
            original={'type':typ}
            backup=self.root/'backups'/desktop/sha256(str(item.path).encode()).hexdigest()
            if typ=='link': original['target']=os.readlink(item.path)
            elif typ=='file':
                backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                backup.write_bytes(item.path.read_bytes());backup.chmod(0o600)
                original.update(path=str(backup),mode=item.path.stat().st_mode & 0o777)
            existing={'path':str(item.path),'original':original,'system':item.system}
        if digest!=item.digest or typ!=desired_type:
            self.replace(item)
        existing.update(digest=item.digest,type=desired_type,system=item.system)
        doc['files']=[v for v in doc['files'] if v['path']!=str(item.path)]+[existing]
        self.save(desktop,doc)
    def allow_overwrite(self, desktop, item):
        doc=self.load(desktop)
        record=next((v for v in doc['files'] if v['path']==str(item.path)),None)
        if record and fingerprint(item.path)[1]!=record['digest']:
            # Conservar también la edición posterior al primer despliegue.
            folder=self.root/'backups'/desktop/'edits'
            folder.mkdir(parents=True,exist_ok=True)
            fd,name=tempfile.mkstemp(dir=folder)
            with os.fdopen(fd,'wb') as f:
                f.write(os.readlink(item.path).encode() if item.path.is_symlink() else item.path.read_bytes() if item.path.is_file() else b'')
            record['digest']=fingerprint(item.path)[1]
            self.save(desktop,doc)
    @staticmethod
    def replace(item):
        if item.system:
            if item.link is not None:
                subprocess.run(['sudo','ln','-sfn','--',item.link,str(item.path)],check=True)
                return
            fd,name=tempfile.mkstemp()
            try:
                with os.fdopen(fd,'wb') as f: f.write(item.data)
                subprocess.run(['sudo','install','-D','-m',f'{item.mode:o}',name,str(item.path)],check=True)
            finally: Path(name).unlink(missing_ok=True)
        else:
            item.path.parent.mkdir(parents=True,exist_ok=True)
            fd,name=tempfile.mkstemp(dir=item.path.parent)
            os.close(fd)
            try:
                if item.link is not None:
                    Path(name).unlink();os.symlink(item.link,name)
                else:
                    Path(name).write_bytes(item.data);os.chmod(name,item.mode)
                os.replace(name,item.path)
            finally: Path(name).unlink(missing_ok=True)
    def restore(self, desktop, force=False):
        doc=self.load(desktop);remaining=[]
        for record in reversed(doc['files']):
            path=Path(record['path']);typ,digest=fingerprint(path)
            if typ!='absent' and digest!=record['digest'] and not force:
                print(f'CONSERVADO por cambios locales: {path}');remaining.append(record);continue
            if typ=='directory': raise RuntimeError(f'El destino administrado se convirtió en directorio: {path}; se conserva.')
            original=record['original']
            if original['type']=='file':
                self.replace(File(path,Path(original['path']).read_bytes(),original['mode'],record['system']))
            elif original['type']=='link':
                self.replace(File(path,system=record['system'],link=original['target']))
            elif record['system']:
                subprocess.run(['sudo','rm','-f','--',str(path)],check=True)
            else: path.unlink(missing_ok=True)
        self.save(desktop,{'schema':1,'files':list(reversed(remaining))})
        return not remaining
