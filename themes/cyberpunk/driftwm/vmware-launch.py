"""Launch Workstation on a private nested X display if driftwm has none."""
import os
import shutil
from pathlib import Path
import secrets
import select
import struct
import subprocess
import sys
import tempfile


def main():
    compat = Path.home()/'.local/bin/vmware-compatible'
    command = [str(compat) if os.access(compat, os.X_OK) else '/usr/bin/vmware', *sys.argv[1:]]
    desktops = os.environ.get('XDG_CURRENT_DESKTOP','').lower().split(':')
    display = os.environ.get('DISPLAY')
    if 'niri' in desktops and not shutil.which('xwayland-satellite') and display and shutil.which('xdpyinfo'):
        try:
            display = subprocess.run(['xdpyinfo'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2).returncode == 0
        except subprocess.TimeoutExpired:
            display = False
    if not {'driftwm','niri'}.intersection(desktops) or display or not os.environ.get('WAYLAND_DISPLAY'):
        os.execv(command[0], command)
    with tempfile.TemporaryDirectory(prefix='cyber-vmware-') as directory:
        auth = Path(directory)/'authority'
        # FamilyWild and an empty display number match the display allocated by Xwayland.
        fields = (b'', b'', b'MIT-MAGIC-COOKIE-1', secrets.token_bytes(16))
        auth.write_bytes(b'\xff\xff' + b''.join(struct.pack('>H',len(f))+f for f in fields))
        read_fd, write_fd = os.pipe()
        try:
            server = subprocess.Popen(['Xwayland','-displayfd',str(write_fd),'-auth',str(auth),
                                       '-nolisten','tcp','-terminate','-geometry','1280x800'],
                                      pass_fds=(write_fd,))
        finally:
            os.close(write_fd)
        with os.fdopen(read_fd,'rb') as ready:
            try:
                if not select.select([ready],[],[],10)[0]:
                    raise SystemExit('Xwayland tardó demasiado en iniciar.')
                number = ready.readline().strip()
                if not number.isdigit():
                    raise SystemExit('Xwayland no pudo abrir una ventana en Wayland.')
                env = dict(os.environ, DISPLAY=':'+number.decode(), XAUTHORITY=str(auth), GDK_BACKEND='x11')
                result = subprocess.run(command,env=env)
                if result.returncode:
                    return result.returncode
                server.wait()
            finally:
                if server.poll() is None:
                    server.terminate()
                    server.wait()
    return 0


if __name__=='__main__':
    sys.exit(main())
