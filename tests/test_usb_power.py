from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from usb_power import adapters,rules

class USBPowerTests(unittest.TestCase):
    def test_only_nearest_bluetooth_usb_parent_not_hub(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            hub=root/'devices/pci/usb1'
            dongle=hub/'1-10';interface=dongle/'1-10:1.0'
            interface.mkdir(parents=True)
            for folder,vendor,product in [(hub,'1d6b','0002'),(dongle,'0bda','c829')]:
                (folder/'power').mkdir();(folder/'power/control').write_text('auto\n')
                (folder/'idVendor').write_text(vendor);(folder/'idProduct').write_text(product)
            hci=root/'class/bluetooth/hci0';hci.mkdir(parents=True)
            (hci/'device').symlink_to(interface)
            found=adapters(root)
            self.assertEqual(found,{str(dongle/'power/control'):('0bda','c829')})
            text=rules(found)
            self.assertIn('ATTR{idVendor}=="0bda"',text)
            self.assertNotIn('1d6b',text)
            self.assertNotIn(str(root),text)
    def test_empty_machine_has_no_rules_for_all_usb(self):
        with tempfile.TemporaryDirectory() as name:self.assertEqual(adapters(Path(name)),{})
    def test_identical_models_generate_one_rule(self):
        text=rules({'a':('1234','5678'),'b':('1234','5678')})
        self.assertEqual(text.count('ACTION=='),1)
