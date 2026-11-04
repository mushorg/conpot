import unittest
import filecmp
import os
import tempfile
import time
from tftpy import TftpClient, TftpException

import conpot
import conpot.core as conpot_core
from conpot.protocols.tftp.tftp_server import TftpServer
from conpot.utils.server_tasks import spawn_test_server, teardown_test_server


class TestTFTPServer(unittest.TestCase):
    def setUp(self):
        conpot_core.initialize_vfs()

        self.tftp_server, self.handle = spawn_test_server(
            TftpServer, template="default", protocol="tftp"
        )

        self.client = TftpClient(
            self.tftp_server.server.server_host, self.tftp_server.server.server_port
        )
        self._test_file = "/".join(
            conpot.__path__ + ["tests/data/test_data_fs/tftp/test.txt"]
        )

    def tearDown(self):
        teardown_test_server(self.tftp_server, self.handle)

    def _wait_uploaded(self, data_fs, needle="test-txt", timeout=3.0):
        # Handle runs in a thread-pool executor; context.end() copies to
        # data_fs after the client has already seen the final ACK.
        deadline = time.time() + timeout
        while time.time() < deadline:
            matches = [i for i in data_fs.listdir("./") if needle in i]
            if matches:
                return matches[0]
            time.sleep(0.05)
        self.fail("uploaded TFTP file matching %r not found" % needle)

    def test_tftp_upload(self):
        """Testing TFTP upload files."""
        self.client.upload("test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        _file = self._wait_uploaded(_data_fs)
        self.assertEqual(
            _data_fs.readtext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    def test_mkdir_upload(self):
        """Testing TFTP upload files - while recursively making directories as per the TFTP path."""
        self.client.upload("/dir/dir/test.txt", self._test_file)
        _, _data_fs = conpot_core.get_vfs("tftp")
        _file = self._wait_uploaded(_data_fs)
        self.assertEqual(
            _data_fs.readtext(_file),
            "This is just a test file for Conpot's TFTP server\n",
        )
        _data_fs.remove(_file)

    def test_tftp_download(self):
        _dst_path = "/".join(
            conpot.__path__ + ["tests/data/data_temp_fs/tftp/download"]
        )
        try:
            self.client.download("tftp_data.txt", _dst_path)
            self.assertTrue(filecmp.cmp(_dst_path, self._test_file))
        finally:
            _, _data_fs = conpot_core.get_vfs("tftp")
            _data_fs.remove("download")

    def test_tftp_filename_control_characters_are_escaped_in_logs(self):
        rrq_marker = "INJECTED_RRQ_LOG_LINE"
        wrq_marker = "INJECTED_WRQ_LOG_LINE"
        malicious_rrq = "missing\r\n" + rrq_marker
        malicious_wrq = "uploaded\r" + wrq_marker

        with tempfile.TemporaryDirectory() as temp_dir:
            missing_path = os.path.join(temp_dir, "missing")
            download_path = os.path.join(temp_dir, "downloaded")
            with self.assertLogs(level="INFO") as captured:
                with self.assertRaises(TftpException):
                    self.client.download(malicious_rrq, missing_path)
                self.client.upload(malicious_wrq, self._test_file)
                _, data_fs = conpot_core.get_vfs("tftp")
                uploaded_file = self._wait_uploaded(data_fs, needle="uploaded")
                self.client.download(malicious_wrq, download_path)

        conpot_logs = "\n".join(
            record.getMessage()
            for record in captured.records
            if record.name.startswith("conpot")
        )
        all_logs = "\n".join(captured.output)
        self.assertIn(rrq_marker, conpot_logs)
        self.assertIn(wrq_marker, conpot_logs)
        self.assertNotIn("\n" + rrq_marker, conpot_logs)
        self.assertNotIn("\r" + rrq_marker, conpot_logs)
        self.assertNotIn("\n" + wrq_marker, conpot_logs)
        self.assertNotIn("\r" + wrq_marker, conpot_logs)
        self.assertIn(r"\r\n" + rrq_marker, conpot_logs)
        self.assertIn(r"uploaded\r" + wrq_marker, conpot_logs)
        self.assertIn(r"Reached EOF on file 'uploaded\r" + wrq_marker + "'", all_logs)
        completion_log = next(
            line for line in all_logs.splitlines() if "data_fs writing" in line
        )
        self.assertIn("Opening '", completion_log)
        self.assertTrue(completion_log.endswith("for data_fs writing."))

        data_fs.remove(uploaded_file)
