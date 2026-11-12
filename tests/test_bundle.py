import argparse
import importlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from render import Layout, make_files
from state import File, State
from manage import apt_guard, parser, resolve_options, render_all, validate, display_text

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name);self.layout=Layout(self.home)
    def tearDown(self): self.temp.cleanup()
    def options(self,*extra):
        return parser().parse_args(['install','--desktop','both','--profile','generic','--resolution','auto',*extra])
    def render(self,desktop='both',profile='generic',extra=()):
        args=parser().parse_args(['install','--desktop',desktop,'--profile',profile,'--resolution','auto',*extra])
        return render_all(self.layout,args)
    def test_controls_are_optional_and_use_local_display_file(self):
        fs=self.render(desktop='hyprland',extra=['--addons','controls'])['hyprland']
        conf=next(f.data for f in fs if f.path.name=='hyprland.conf')
        bar=json.loads(next(f.data for f in fs if f.path.name=='config.jsonc'))
        self.assertIn(b'XF86MonBrightnessDown',conf)
        self.assertIn(b'--min-value=1',conf)
        self.assertIn(str(self.layout.config/'hypr/monitors.conf'),bar['custom/displays']['on-click'])
        self.assertIn('backlight',bar['modules-right'])
        self.assertNotIn(b'gnome-control-center',conf)
        plain=self.render(desktop='hyprland',extra=['--addons','none'])['hyprland']
        self.assertNotIn('backlight',json.loads(next(f.data for f in plain if f.path.name=='config.jsonc'))['modules-right'])
    def test_controls_prefer_saved_standard_monitor_positions(self):
        managed=self.layout.config/'cyberpunk-desktop/hardware/hyprland-display.conf'
        managed.parent.mkdir(parents=True);managed.write_text('monitor = , preferred, auto, 1\n')
        standard=self.layout.config/'hypr/monitors.conf'
        standard.parent.mkdir(parents=True);standard.write_text('monitor=HDMI-A-1,1920x1080@60,0x0,1\nmonitor=eDP-1,1920x1080@120,1920x0,1\n')
        args=self.options('--desktop','hyprland','--addons','controls','--resolution','preserve')
        files=render_all(self.layout,args)['hyprland']
        conf=next(f.data for f in files if f.path.name=='hyprland.conf')
        self.assertIn(('source = '+str(standard)).encode(),conf)
        output=next(f.data for f in files if f.path==standard)
        self.assertIn(b'monitor=eDP-1,1920x1080@120,1920x0,1',output)
        self.assertNotIn(b'auto',output)
    def test_foot_launcher_shared_and_selects_current_session(self):
        groups=self.render()
        path=self.layout.data/'applications/foot.desktop'
        entries=[next(f.data for f in fs if f.path==path) for fs in groups.values()]
        self.assertEqual(entries[0],entries[1])
        self.assertIn(b'auto terminal',entries[0])
        import runpy
        from unittest.mock import patch
        with patch.object(sys,'argv',['runtime.py','auto','terminal']), patch.dict(os.environ,{'XDG_CURRENT_DESKTOP':'GNOME'}):
            with patch('os.execvp',side_effect=SystemExit) as execute:
                with self.assertRaises(SystemExit):runpy.run_path(str(ROOT/'scripts/runtime.py'),run_name='__main__')
                execute.assert_called_once_with('foot',['foot'])
    def test_controls_reject_niri(self):
        with self.assertRaises(ValueError):self.render(extra=['--addons','controls'])
    def test_generic_has_no_vmware_environment_or_monitor(self):
        for fs in self.render().values():
            text='\n'.join(f.data.decode(errors='ignore') for f in fs if f.path.suffix in ('.conf','.kdl') or '.local/bin' in str(f.path))
            self.assertNotIn('AQ_NO_ATOMIC',text)
            self.assertNotIn('Virtual-1',text)
    def test_legacy_workaround_only_in_vmware_hyprland_launcher(self):
        groups=self.render(profile='vmware',extra=['--vmware-legacy-drm'])
        for d,fs in groups.items():
            launcher=next(f for f in fs if f.path==self.home/'.local/bin'/('cyberpunk-'+d))
            self.assertEqual(b'export AQ_NO_ATOMIC=1' in launcher.data,d=='hyprland')
    def test_software_cursor_only_on_vmware_hyprland(self):
        for profile in ('generic','vmware'):
            groups=self.render(profile=profile)
            hardware=next(f for f in groups['hyprland'] if f.path.name==f'hyprland-{profile}.conf')
            self.assertEqual(b'no_hardware_cursors = 1' in hardware.data,profile=='vmware')
            niri=next(f for f in groups['niri'] if f.path.name=='config.kdl')
            self.assertNotIn(b'no_hardware_cursors',niri.data)
    def test_generic_rejects_vmware_workaround(self):
        with self.assertRaises(ValueError): resolve_options(self.options('--vmware-legacy-drm'))
    def test_niri_rejects_hyprland_workaround(self):
        args=parser().parse_args(['install','--desktop','niri','--profile','vmware','--vmware-legacy-drm'])
        with self.assertRaises(ValueError): resolve_options(args)
    def test_resolution_requires_machine_output(self):
        with self.assertRaises(ValueError): resolve_options(self.options('--resolution','1920x1080'))
    def test_explicit_resolution_for_both(self):
        groups=self.render(extra=['--resolution','1920x1080@60','--output','DP-2'])
        niri=next(f for f in groups['niri'] if f.path.name=='config.kdl').data
        hypr=next(f for f in groups['hyprland'] if f.path.name=='hyprland-display.conf').data
        self.assertIn(b'output "DP-2"',niri);self.assertIn(b'1920x1080@60',hypr)
    def test_preserve_drops_legacy_aq_from_screen_import(self):
        p=self.layout.config/'hypr/monitors.conf';p.parent.mkdir(parents=True)
        p.write_text('monitor = Virtual-1, 1920x1080, auto, 1\nenv = AQ_NO_ATOMIC,1\n')
        args=self.options('--resolution','preserve')
        text=display_text(self.layout,args,'hyprland')
        self.assertIn('1920x1080',text);self.assertNotIn('AQ_',text)
    def test_niri_preserves_its_local_display_fragment(self):
        p=self.layout.config/'cyberpunk-desktop/hardware/niri-display.conf';p.parent.mkdir(parents=True)
        p.write_text('output "DP-2" { mode "1920x1080@60"; }')
        args=self.options('--resolution','preserve')
        files=render_all(self.layout,args)['niri']
        self.assertIn(b'output "DP-2"',next(f for f in files if f.path.name=='config.kdl').data)
    def test_without_addons_no_office_or_broken_shortcuts(self):
        for desktop,fs in self.render(extra=['--addons','none']).items():
            conf=next(f for f in fs if f.path.name==('config.kdl' if desktop=='niri' else 'hyprland.conf')).data
            self.assertNotIn(b'SAL_USE_VCLPLUGIN',conf)
            self.assertNotIn(b'"clipboard"',conf)
            self.assertNotIn(b'"widgets"',conf)
            self.assertFalse(any(f.path.name=='dashboard.py' for f in fs))
    def test_paths_are_generated_for_each_home(self):
        for home in [self.home/'alice',self.home/'bob']:
            fs=render_all(Layout(home),self.options())
            for items in fs.values():
                for item in items:
                    self.assertNotIn(b'/home/ivan',item.data)
                    if item.path.suffix not in ('.png',):
                        tokens=set(re.findall(rb'@([A-Z_]+)@',item.data))
                        self.assertLessEqual(tokens,{b'DEFAULT_AUDIO_SINK',b'DEFAULT_AUDIO_SOURCE'})
    def test_apt_refuses_shared_dependency_removal(self):
        with self.assertRaises(RuntimeError): apt_guard('Purg hyprland [0.55]\nRemv libwayland-client0 [1]\n',['hyprland'])
    def test_apt_allows_only_selected_packages(self): apt_guard('Purg hyprland [0.55]\n',['hyprland'])
    def test_apt_refuses_side_effect_upgrade(self):
        with self.assertRaises(RuntimeError): apt_guard('Inst libc6 [2.41]\n',['hyprland'])
    def test_backup_restores_original_and_preserves_unrelated_file(self):
        dest=self.home/'config';dest.write_text('original')
        other=self.home/'document';other.write_text('personal')
        state=State(self.home/'state');state.write('niri',File(dest,b'managed'))
        state.write('niri',File(dest,b'updated'))
        self.assertTrue(state.restore('niri'));self.assertEqual(dest.read_text(),'original');self.assertEqual(other.read_text(),'personal')
    def test_local_edit_is_not_overwritten_or_deleted(self):
        state=State(self.home/'state');dest=self.home/'config'
        state.write('niri',File(dest,b'managed'));dest.write_text('my edit')
        with self.assertRaises(RuntimeError): state.write('niri',File(dest,b'updated'))
        self.assertFalse(state.restore('niri'));self.assertEqual(dest.read_text(),'my edit')
    def test_explicit_overwrite_keeps_initial_backup(self):
        dest=self.home/'config';dest.write_text('original');state=State(self.home/'state')
        state.write('niri',File(dest,b'managed'));dest.write_text('edit')
        item=File(dest,b'new');state.allow_overwrite('niri',item);state.write('niri',item)
        state.restore('niri');self.assertEqual(dest.read_text(),'original')
        self.assertEqual(len(list((self.home/'state/backups/niri/edits').iterdir())),1)
    def test_existing_symlink_is_restored_without_touching_target(self):
        target=self.home/'target';target.write_text('original');link=self.home/'link';link.symlink_to(target)
        state=State(self.home/'state');state.write('shared',File(link,link='/dev/null'))
        state.restore('shared');self.assertEqual(link.resolve(),target);self.assertEqual(target.read_text(),'original')
    def test_missing_dest_is_removed_on_restore(self):
        state=State(self.home/'state');dest=self.home/'config';state.write('niri',File(dest,b'data'))
        state.restore('niri');self.assertFalse(dest.exists())
    def test_render_is_read_only(self):
        render_all(self.layout,self.options())
        self.assertFalse(self.layout.state.exists());self.assertFalse(self.layout.root.exists())
    def test_plain_theme_does_not_force_transparency(self):
        files=self.render(extra=['--theme','plain'])['hyprland']
        conf=next(f for f in files if f.path.name=='appearance.conf').data
        self.assertIn(b'active_opacity = 1',conf);self.assertIn(b'enabled = false',conf)

if __name__=='__main__': unittest.main()
