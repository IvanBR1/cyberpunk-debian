from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'themes/cyberpunk/common/widgets'))
from metrics import Telemetry,rate

class TelemetryTests(unittest.TestCase):
    def test_counter_deltas_memory_and_missing_battery(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);proc=root/'proc';(proc/'net').mkdir(parents=True)
            (proc/'stat').write_text('cpu 10 0 10 80 0 0 0 0\n')
            (proc/'meminfo').write_text('MemTotal: 1000 kB\nMemAvailable: 400 kB\n')
            (proc/'uptime').write_text('120.0 0\n')
            net=proc/'net/dev';net.write_text('head\nhead\n eth0: 100 0 0 0 0 0 0 0 200\n lo: 999 0 0 0 0 0 0 0 999\n')
            times=iter((10,12,14));metrics=Telemetry(proc,root/'sys',lambda:next(times))
            first=metrics.sample();self.assertEqual(first['cpu'],0);self.assertIsNone(first['battery'])
            (proc/'stat').write_text('cpu 20 0 10 90 0 0 0 0\n')
            net.write_text('head\nhead\n eth0: 300 0 0 0 0 0 0 0 600\n')
            value=metrics.sample();self.assertEqual(value['cpu'],.5);self.assertEqual(value['ram'],.6)
            self.assertEqual((value['rx'],value['tx']),(100,200))
            net.write_text('head\nhead\n eth0: 0 0 0 0 0 0 0 0 0\n')
            self.assertEqual(metrics.sample()['rx'],0)
    def test_rate_units(self):
        self.assertEqual(rate(1024),'1.0 KiB/s')
        self.assertEqual(rate(1048576),'1.0 MiB/s')
