import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from drift_profile import profile_files, staged_files, ensure_safe
from state import State


class DriftProfileTests(unittest.TestCase):
    def test_profile_restores_previous_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            directory = home/'config/driftwm'
            directory.mkdir(parents=True)
            original = directory/'config.toml'
            original.write_text('autostart = ["personal"]\n')
            state = State(home/'state')
            with patch.dict(os.environ,{'XDG_CONFIG_HOME':str(home/'config')}):
                files = profile_files()
            ensure_safe(state,files,False)
            for item in files: state.write('driftwm',item)
            self.assertTrue(state.restore('driftwm'))
            self.assertEqual(original.read_text(),'autostart = ["personal"]\n')
            self.assertFalse((directory/'cyberpunk-waybar.json').exists())

    def test_stage_maps_only_install_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root/'usr/local/bin/driftwm'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'binary')
            binary.chmod(0o755)
            files = staged_files(root)
            self.assertEqual([(f.path,f.mode) for f in files],[(Path('/usr/local/bin/driftwm'),0o755)])


if __name__ == '__main__': unittest.main()
