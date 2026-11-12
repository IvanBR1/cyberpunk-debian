"""Ahorro USB de adaptadores Bluetooth, basado en corregir-audio-bluetooth.sh."""
from pathlib import Path
import re
import subprocess
from state import File, State
from render import Layout

RULE=Path('/etc/udev/rules.d/99-cyberpunk-bluetooth-usb-power.rules')

def adapters(sysroot=Path('/sys')):
    result={}
    for hci in (sysroot/'class/bluetooth').glob('hci*'):
        device=(hci/'device').resolve()
        for parent in (device,*device.parents):
            if not parent.is_relative_to(sysroot/'devices'):break
            if (parent/'idVendor').is_file() and (parent/'power/control').is_file():
                vendor=(parent/'idVendor').read_text().strip()
                product=(parent/'idProduct').read_text().strip()
                if not re.fullmatch('[0-9a-fA-F]{4}',vendor) or not re.fullmatch('[0-9a-fA-F]{4}',product):
                    raise RuntimeError('Identificador USB inválido.')
                result[str(parent/'power/control')]=(vendor,product)
                break
    return result

def rules(devices):
    lines=['# Terminales Cyberpunk: solo modelos USB de los adaptadores Bluetooth seleccionados.']
    for vendor,product in sorted(set(devices.values())):
        lines.append('ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="'+vendor+'", ATTR{idProduct}=="'+product+'", TEST=="power/control", ATTR{power/control}="on"')
    return '\n'.join(lines)+'\n'

def write_control(path,value):
    subprocess.run(['sudo','tee',str(path)],input=value+'\n',text=True,stdout=subprocess.DEVNULL,check=True)

def manage(args):
    state=State(Layout().state);doc=state.load('usb-power')
    if args.restore:
        entries=doc.get('controls',{})
        for path,value in entries.items():print('Restaurar:',path,'→',value)
        for item in doc['files']:print('Restaurar regla:',item['path'])
        if not args.apply:print('PLAN: añade --apply para restaurar.');return
        if doc['files'] or entries:subprocess.run(['sudo','-v'],check=True)
        # No restaurar rutas arbitrarias procedentes de un estado editado.
        current=adapters()
        for path,value in list(entries.items()):
            if path not in current:
                print('Adaptador ausente; no se escribe en su ruta antigua:',path)
                continue
            if value not in ('auto','on'):raise RuntimeError('Valor de respaldo inválido.')
            if Path(path).read_text().strip()!='on':
                print('CONSERVADO por cambios locales:',path);continue
            write_control(path,value);del entries[path]
        doc['controls']=entries;state.save('usb-power',doc)
        state.restore('usb-power')
        # State.restore solo conserva archivos; mantener respaldos de dispositivos ausentes.
        updated=state.load('usb-power');updated['controls']=entries;state.save('usb-power',updated)
        subprocess.run(['sudo','udevadm','control','--reload-rules'],check=True)
        print('Restauración terminada. Los dispositivos ausentes conservan su respaldo.')
        return
    devices=adapters()
    if not devices:raise RuntimeError('No se encontró adaptador Bluetooth USB; no se modifica nada.')
    for path,ids in devices.items():print('Bluetooth USB',':'.join(ids),path,'=',Path(path).read_text().strip(),'→ on')
    if args.persistent:print('Persistencia optativa:',RULE,'(por fabricante/producto detectados en este equipo).')
    else:print('Temporal: se pierde al reiniciar o reconectar el adaptador.')
    if not args.apply:print('PLAN: añade --apply.');return
    subprocess.run(['sudo','-v'],check=True)
    controls=doc.setdefault('controls',{})
    for path in devices:
        value=Path(path).read_text().strip()
        if value not in ('auto','on'):raise RuntimeError('Estado USB inesperado: '+value)
        controls.setdefault(path,value);state.save('usb-power',doc)
        write_control(path,'on')
        if Path(path).read_text().strip()!='on':raise RuntimeError('No se confirmó el cambio USB.')
    if args.persistent:
        state.write('usb-power',File(RULE,rules(devices).encode(),system=True))
        subprocess.run(['sudo','udevadm','control','--reload-rules'],check=True)
    print('Aplicado sin reiniciar Bluetooth ni modificar emparejamientos. Puede aumentar el consumo.')
