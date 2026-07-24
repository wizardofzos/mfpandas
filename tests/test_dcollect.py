import tempfile
import time
import unittest
from pathlib import Path

from mfpandas import DCOLLECT
from mfpandas.dcollect import UsageError


def _record(record_type, length=470):
    data = bytearray(length)
    data[0:2] = length.to_bytes(2, "big")
    data[4:6] = record_type.ljust(2).encode("cp500")
    return data


class DCOLLECTTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.tempdir = Path(self._tempdir.name)

    def tearDown(self):
        self._tempdir.cleanup()

    def test_zero_dataset_dates_are_missing(self):
        record = _record("D")
        record[24:68] = "TEST.DATA".ljust(44).encode("cp500")
        record[78:84] = "VOL001".encode("cp500")
        record[386:388] = bytes.fromhex("FFFF")
        path = self.tempdir / "dcollect.bin"
        path.write_bytes(record)

        parsed = DCOLLECT(str(path))

        self.assertTrue(parsed.parse_t())
        self.assertEqual(parsed.status["status"], "Ready")
        self.assertEqual(parsed.datasets.iloc[0]["DCDDSNAM"], "TEST.DATA")
        self.assertIsNone(parsed.datasets.iloc[0]["DCDCREDT"])
        self.assertEqual(parsed.datasets.iloc[0]["DCDATYPE"], "FFFF")
        self.assertEqual(parsed.datasets.iloc[0]["DCDAKLBL"], "")

    def test_encrypted_dataset_exposes_key_label(self):
        record = _record("D")
        record[24:68] = "SECRET.DATA".ljust(44).encode("cp500")
        record[386:388] = bytes.fromhex("0100")
        record[388:452] = "KEY.LABEL.ONE".ljust(64).encode("cp500")
        path = self.tempdir / "encrypted.bin"
        path.write_bytes(record)

        parsed = DCOLLECT(str(path))

        self.assertTrue(parsed.parse_t())
        self.assertEqual(parsed.datasets.iloc[0]["DCDATYPE"], "0100")
        self.assertEqual(parsed.datasets.iloc[0]["DCDAKLBL"], "KEY.LABEL.ONE")

    def test_short_dataset_record_has_no_encryption_fields(self):
        # D-records predating APAR OA51067 stop before DCDAENCR.
        record = _record("D", length=300)
        record[24:68] = "OLD.DATA".ljust(44).encode("cp500")
        path = self.tempdir / "short.bin"
        path.write_bytes(record)

        parsed = DCOLLECT(str(path))

        self.assertTrue(parsed.parse_t())
        self.assertEqual(parsed.datasets.iloc[0]["DCDATYPE"], "")
        self.assertEqual(parsed.datasets.iloc[0]["DCDAKLBL"], "")

    def test_background_parse_reports_malformed_record(self):
        path = self.tempdir / "bad-dcollect.bin"
        path.write_bytes(b"\x00\x00")
        parsed = DCOLLECT(str(path))

        parsed.parse()
        for _ in range(100):
            if parsed.status["status"] == "Error":
                break
            time.sleep(0.01)

        self.assertEqual(parsed.status["status"], "Error")
        self.assertIn("Invalid DCOLLECT record length", parsed.status["error"])

    def test_failed_parse_surfaces_error_on_dataframes(self):
        path = self.tempdir / "bad-dcollect.bin"
        path.write_bytes(b"\x00\x00")
        parsed = DCOLLECT(str(path))

        self.assertFalse(parsed.parse_t())
        with self.assertRaises(UsageError) as raised:
            parsed.datasets
        self.assertIn("Invalid DCOLLECT record length", str(raised.exception))

    def test_truncated_association_record_is_reported(self):
        record = _record("A", length=100)
        path = self.tempdir / "short-association.bin"
        path.write_bytes(record)

        parsed = DCOLLECT(str(path))

        self.assertFalse(parsed.parse_t())
        self.assertIn("Truncated DCOLLECT A-record", parsed.status["error"])

    def test_vsam_association_records_are_exposed(self):
        record = _record("A", length=204)
        record[24:68] = "APP.INDEX".ljust(44).encode("cp500")
        record[68:112] = "APP.CLUSTER".ljust(44).encode("cp500")
        record[112] = 0b10000000
        path = self.tempdir / "associations.bin"
        path.write_bytes(record)

        parsed = DCOLLECT(str(path))

        self.assertTrue(parsed.parse_t())
        row = parsed.associations.iloc[0]
        self.assertEqual(row["DCADSNAM"], "APP.INDEX")
        self.assertEqual(row["DCAASSOC"], "APP.CLUSTER")
        self.assertTrue(bool(row["DCAKSDS"]))

    def test_counters_are_not_shared_between_instances(self):
        record = _record("D")
        record[24:68] = "TEST.DATA".ljust(44).encode("cp500")
        path = self.tempdir / "dcollect.bin"
        path.write_bytes(record)

        first = DCOLLECT(str(path))
        first.parse_t()
        second = DCOLLECT(str(path))
        second.parse_t()

        self.assertEqual(first.records_seen["D"], 1)
        self.assertEqual(second.records_seen["D"], 1)


if __name__ == "__main__":
    unittest.main()
