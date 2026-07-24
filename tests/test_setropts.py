import tempfile
import unittest
from pathlib import Path

from mfpandas import SETROPTS


class SETROPTSTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.tempdir = Path(self._tempdir.name)

    def tearDown(self):
        self._tempdir.cleanup()

    def _extract(self, *kvpairs):
        path = self.tempdir / 'setropts.txt'
        path.write_text('\n'.join(kvpairs) + '\n')
        return SETROPTS(str(path))

    def test_single_entry_list_is_not_a_setting(self):
        # Exactly one RACLISTed class used to be parsed as a key/value setting,
        # which then blew up on the _setropts_fields lookup.
        s = self._extract(
            'RACLIST:FACILITY',
            'CLASSACT:FACILITY',
            'CLASSACT:TSOAUTH',
            'INTERVAL:180',
        )

        self.assertNotIn('RACLIST', list(s.fieldInfo['Setting']))
        facility = s.classInfo[s.classInfo['name'] == 'FACILITY'].iloc[0]
        self.assertEqual(facility['RACLIST'], 'YES')
        self.assertEqual(facility['CLASSACT'], 'YES')

    def test_multi_entry_list_still_parses(self):
        s = self._extract('RACLIST:FACILITY', 'RACLIST:TSOAUTH')

        raclisted = set(s.classInfo[s.classInfo['RACLIST'] == 'YES']['name'])
        self.assertEqual(raclisted, {'FACILITY', 'TSOAUTH'})

    def test_settings_are_still_key_value_pairs(self):
        s = self._extract('INTERVAL:180', 'MIXDCASE:TRUE')

        settings = s.fieldInfo.set_index('Setting')['Value']
        self.assertEqual(settings['INTERVAL'], 180)
        self.assertEqual(settings['MIXDCASE'], 'TRUE')


if __name__ == '__main__':
    unittest.main()
