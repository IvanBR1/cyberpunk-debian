"""Lecturas locales para los widgets; sin procesos ni conexiones de red."""
from pathlib import Path
import shutil
import time

class Telemetry:
    def __init__(self, proc=Path('/proc'), sys=Path('/sys'), clock=time.monotonic):
        self.proc,self.sys,self.clock=proc,sys,clock
        self.previous=None

    def sample(self):
        now=self.clock()
        cpu=list(map(int,(self.proc/'stat').read_text().splitlines()[0].split()[1:9]))
        total=sum(cpu);idle=sum(cpu[3:5])
        net=[0,0]
        for line in (self.proc/'net/dev').read_text().splitlines()[2:]:
            name,values=line.split(':',1)
            if name.strip()=='lo':continue
            fields=values.split();net[0]+=int(fields[0]);net[1]+=int(fields[8])
        usage=rx=tx=0.0
        if self.previous:
            stamp,old_total,old_idle,old_net=self.previous
            elapsed=max(now-stamp,0.001);delta=total-old_total
            if delta>0:usage=max(0,min(1,1-(idle-old_idle)/delta))
            rx=max(0,net[0]-old_net[0])/elapsed;tx=max(0,net[1]-old_net[1])/elapsed
        self.previous=(now,total,idle,net)
        mem={line.split(':')[0]:int(line.split()[1]) for line in (self.proc/'meminfo').read_text().splitlines()}
        used=mem['MemTotal']-mem['MemAvailable']
        disk=shutil.disk_usage(Path.home())
        battery=None
        for device in sorted((self.sys/'class/power_supply').glob('*')):
            try:
                if (device/'type').read_text().strip()=='Battery':
                    battery={'capacity':int((device/'capacity').read_text()),'status':(device/'status').read_text().strip()};break
            except (OSError,ValueError):continue
        temperatures=[]
        for sensor in (self.sys/'class/thermal').glob('thermal_zone*'):
            try:
                if (sensor/'type').read_text().strip() in ('x86_pkg_temp','cpu-thermal','acpitz'):
                    temperatures.append(int((sensor/'temp').read_text())/1000)
            except (OSError,ValueError):continue
        return {'cpu':usage,'ram':used/mem['MemTotal'],'used_gib':used/1048576,'total_gib':mem['MemTotal']/1048576,
                'rx':rx,'tx':tx,'disk':disk.used/disk.total,'free_gib':disk.free/1073741824,
                'battery':battery,'temperature':max(temperatures) if temperatures else None,
                'uptime':int(float((self.proc/'uptime').read_text().split()[0]))}

def rate(value):
    for unit in ('B/s','KiB/s','MiB/s','GiB/s'):
        if value<1024 or unit=='GiB/s':return f'{value:.1f} {unit}'
        value/=1024
