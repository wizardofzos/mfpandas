import tempfile
import unittest
from pathlib import Path

from mfpandas import SETROPTS
from mfpandas.setropts_list import convert


# A trimmed but realistically ordered SETROPTS LIST capture: general options and
# password options first, class lists last (wrapped-header lists must be the
# final indented block so continuation joining does not swallow later lines).
SETROPTS_LIST = """\
READY
  SETROPTS LIST
  ATTRIBUTES = INITSTATS NOCMDVIOL SAUDIT OPERAUDIT
  PASSWORD PROCESSING OPTIONS:
    PASSWORD CHANGE INTERVAL IS  180 DAYS.
    PASSWORD MINIMUM CHANGE INTERVAL IS   0 DAYS.
    MIXED CASE PASSWORD SUPPORT IS IN EFFECT.
     8 GENERATIONS OF PREVIOUS PASSWORDS BEING MAINTAINED.
    AFTER   5 CONSECUTIVE UNSUCCESSFUL PASSWORD ATTEMPTS, A USERID WILL BE REVOKED.
  ERASE-ON-SCRATCH IS INACTIVE
  ACTIVE CLASSES  =  DATASET USER GROUP FACILITY TSOAUTH
  GENERIC PROFILE CLASSES  =  DATASET FACILITY
  SETR RACLIST CLASSES  =  FACILITY
READY
"""


class ConvertTests(unittest.TestCase):
    def test_emits_expected_key_value_pairs(self):
        lines = convert(SETROPTS_LIST)

        self.assertIn('INITSTAT:TRUE', lines)
        self.assertIn('CMDVIOL:FALSE', lines)
        self.assertIn('INTERVAL:180', lines)
        self.assertIn('HISTORY:008', lines)
        self.assertIn('REVOKE:005', lines)
        self.assertIn('ERASE:FALSE', lines)
        # Class membership is emitted as one record per class.
        self.assertIn('CLASSACT:FACILITY', lines)
        self.assertIn('GENERIC:DATASET', lines)
        self.assertIn('RACLIST:FACILITY', lines)

    def test_rejects_non_setropts_input(self):
        with self.assertRaises(ValueError):
            convert('READY\n  LISTGRP SYS1\nREADY\n')


class FromSetroptsListTests(unittest.TestCase):
    def test_from_text_builds_dataframes(self):
        s = SETROPTS.from_setropts_list(SETROPTS_LIST)

        settings = s.fieldInfo.set_index('Setting')['Value']
        self.assertEqual(settings['INTERVAL'], 180)
        self.assertEqual(settings['INITSTAT'], 'TRUE')
        self.assertEqual(settings['ERASE'], 'FALSE')

        facility = s.classInfo[s.classInfo['name'] == 'FACILITY'].iloc[0]
        self.assertEqual(facility['CLASSACT'], 'YES')
        self.assertEqual(facility['GENERIC'], 'YES')
        self.assertEqual(facility['RACLIST'], 'YES')

    def test_from_file_matches_from_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'setropts-list.txt'
            path.write_text(SETROPTS_LIST)
            from_file = SETROPTS.from_setropts_list(str(path))

        from_text = SETROPTS.from_setropts_list(SETROPTS_LIST)
        self.assertTrue(from_file.fieldInfo.equals(from_text.fieldInfo))


if __name__ == '__main__':
    unittest.main()
