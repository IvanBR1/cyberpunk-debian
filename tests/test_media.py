from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'themes/cyberpunk/common/widgets'))
from media import parse_metadata,settle_metadata


def metadata(title='Tema',status='Playing'):
    return f'{title}\x1fArtista\x1f{status}\x1f1000000\x1f9000000'


class MediaTests(unittest.TestCase):
    def test_parses_metadata_and_times(self):
        state=parse_metadata(metadata())
        self.assertEqual((state['title'],state['current'],state['duration']),('Tema',1,9))
        self.assertIsNone(parse_metadata(''))

    def test_toggle_waits_for_changed_status(self):
        values=iter((metadata(status='Playing'),metadata(status='Paused')));calls=[];delays=[]
        result=settle_metadata('play-pause',metadata(),lambda:(calls.append('toggle') or True),lambda:next(values),delays.append)
        self.assertEqual(parse_metadata(result)['status'],'Paused')
        self.assertEqual(calls,['toggle']);self.assertEqual(delays,[.12])

    def test_next_waits_for_new_metadata(self):
        old=metadata();values=iter((old,metadata('Siguiente')))
        result=settle_metadata('next',old,lambda:True,lambda:next(values),lambda _:None)
        self.assertEqual(parse_metadata(result)['title'],'Siguiente')

    def test_failed_command_preserves_previous_state(self):
        old=metadata()
        self.assertEqual(settle_metadata('next',old,lambda:False,lambda:'',lambda _:None),old)
