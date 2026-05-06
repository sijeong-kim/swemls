import unittest
import struct
import os
from src.communication.message_wal import MessageWal

ADT_A01 = [
    r"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401201630||ADT^A01|||2.5",
    r"PID|1||478237423||ELIZABETH HOLMES||19840203|F",
    r"NK1|1|SUNNY BALWANI|PARTNER"
]

ADT_A02 = [
    r"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401201630||ADT^A01|||2.5",
    r"PID|1||478237424||JOHN DOE||19840203|M",
    r"NK1|1|SUNNY BALWANI|PARTNER"
]

class TestMessageWal(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        """Called once after all tests in the class."""
        if os.path.exists(os.path.join(os.path.dirname(__file__), "test_data")):
            os.rmdir(os.path.join(os.path.dirname(__file__), "test_data"))

    def setUp(self):
        self.directory = os.path.join(os.path.dirname(__file__), "test_data")
        self.wal = MessageWal(self.directory)

    def tearDown(self):
        self.wal.hl7_wal.close()
        self.wal.pager_wal.close()

        if os.path.exists(self.directory):
            for filename in os.listdir(self.directory):
                file_path = os.path.join(self.directory, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

    def test_initialization(self):
        """Test that the WAL initializes directories and files correctly."""
        wal = MessageWal(self.directory)
        self.assertTrue(os.path.isdir(self.directory))
        self.assertTrue(os.path.exists(os.path.join(self.directory, "hl7.wal")))
        self.assertTrue(os.path.exists(os.path.join(self.directory, "hl7.ckpt")))
        self.assertTrue(os.path.exists(os.path.join(self.directory, "pager.wal")))
        self.assertTrue(os.path.exists(os.path.join(self.directory, "pager.ckpt")))
        self.assertEqual(wal.hl7_ckpt, 0)
        self.assertEqual(wal.pager_ckpt, 0)

        wal.hl7_wal.close()
        wal.pager_wal.close()

    def test_load_checkpoint(self):
        """Test loading a checkpoint from an existing file."""
        ckpt_file = os.path.join(self.directory, "hl7.ckpt")
        expected_pos = 123
        with open(ckpt_file, "wb") as f:
            f.write(struct.pack("Q", expected_pos))

        wal = MessageWal(self.directory)
        self.assertEqual(wal.hl7_ckpt, expected_pos)

    def test_update_checkpoint(self):
        """Test updating a checkpoint file."""
        ckpt_file = os.path.join(self.directory, "pager.ckpt")
        expected_pos = 123
        self.wal._update_checkpoint("pager.ckpt", expected_pos)
        with open(ckpt_file, "rb") as f:
            pos = struct.unpack("Q", f.read(8))[0]
            self.assertEqual(pos, expected_pos)

    def test_append_hl7_message(self):
        """Test appending a message to the HL7 WAL."""
        message = ("\r".join(ADT_A01) + "\r").encode('utf-8')
        pos = self.wal.append_hl7(message)
        self.assertEqual(pos, len(message) + 1) # include newline
        self.assertEqual(self.wal.hl7_ckpt, 0)
        with open(os.path.join(self.directory, "hl7.wal"), "rb") as f:
            content = f.read()
            self.assertEqual(content, message + b"\n")

    def test_append_pager_request(self):
        """Test appending a message to the pager WAL."""
        message = b"478237423,202401202243"
        pos = self.wal.append_pager_request(message)
        self.assertEqual(pos, len(message) + 1)
        self.assertEqual(self.wal.pager_ckpt, 0)
        with open(os.path.join(self.directory, "pager.wal"), "rb") as f:
            content = f.read()
            self.assertEqual(content, message + b"\n")

    def test_load_replay_without_checkpoints(self):
        """Test loading all messages when no checkpoints are set."""
        hl7_msgs = [("\r".join(ADT_A01) + "\r").encode('utf-8'), ("\r".join(ADT_A02) + "\r").encode('utf-8')]
        pager_msgs = [b"478237423,202401202243"]
        for msg in hl7_msgs:
            self.wal.append_hl7(msg)
        for msg in pager_msgs:
            self.wal.append_pager_request(msg)
        hl7_replay, pager_replay = self.wal.load_replay()
        self.assertEqual(hl7_replay, [(len(hl7_msgs[0])+1, hl7_msgs[0]),(len(hl7_msgs[0])+len(hl7_msgs[1])+2, hl7_msgs[1])])
        self.assertEqual(pager_replay, [(len(pager_msgs[0])+1, pager_msgs[0])])

    def test_mark_processed_and_replay(self):
        """Test marking a position and loading messages after that position."""
        hl7_msg1, hl7_msg2 = ("\r".join(ADT_A01) + "\r").encode('utf-8'), ("\r".join(ADT_A02) + "\r").encode('utf-8')
        pos1 = self.wal.append_hl7(hl7_msg1)
        self.wal.append_hl7(hl7_msg2)
        self.wal.mark_hl7_processed(pos1)
        self.assertEqual(self.wal.hl7_ckpt, pos1)

        pager_msg1, pager_msg2 = b"478237423,202401202243", b"478237424,202401202244"
        pos2 = self.wal.append_pager_request(pager_msg1)
        self.wal.append_pager_request(pager_msg2)
        self.wal.mark_pager_processed(pos2)
        self.assertEqual(self.wal.pager_ckpt, pos2)

        hl7_replay, pager_replay = self.wal.load_replay()
        self.assertEqual(hl7_replay, [(len(hl7_msg2)+1, hl7_msg2)])
        self.assertEqual(pager_replay, [(len(pager_msg2)+1, pager_msg2)])

    def test_compact_files(self):
        """Test compaction removes processed messages and resets checkpoints."""
        hl7_msg1, hl7_msg2 = ("\r".join(ADT_A01) + "\r").encode('utf-8'), ("\r".join(ADT_A02) + "\r").encode('utf-8')
        pos1 = self.wal.append_hl7(hl7_msg1)
        self.wal.append_hl7(hl7_msg2)
        self.wal.mark_hl7_processed(pos1)
        self.assertEqual(self.wal.hl7_ckpt, pos1)

        pager_msg1, pager_msg2 = b"478237423,202401202243", b"478237424,202401202244"
        pos2 = self.wal.append_pager_request(pager_msg1)
        self.wal.append_pager_request(pager_msg2)
        self.wal.mark_pager_processed(pos2)
        self.assertEqual(self.wal.pager_ckpt, pos2)

        self.wal.compact_files()
        self.wal.hl7_wal.seek(0)
        self.wal.pager_wal.seek(0)
        self.assertEqual(self.wal.hl7_wal.read(), hl7_msg2 + b"\n")
        self.assertEqual(self.wal.pager_wal.read(), pager_msg2 + b"\n")
        self.assertEqual(self.wal.hl7_ckpt, 0)
        self.assertEqual(self.wal.pager_ckpt, 0)

    def test_compact_empty_after_processing_all(self):
        """Test compaction results in empty WAL when all messages are processed."""
        hl7_msg1, hl7_msg2 = ("\r".join(ADT_A01) + "\r").encode('utf-8'), ("\r".join(ADT_A02) + "\r").encode('utf-8')
        pos1 = self.wal.append_hl7(hl7_msg1)
        self.wal.mark_hl7_processed(pos1)
        pos1 = self.wal.append_hl7(hl7_msg2)
        self.wal.mark_hl7_processed(pos1)
        self.assertEqual(self.wal.hl7_ckpt, pos1)

        pager_msg1, pager_msg2 = b"478237423,202401202243", b"478237424,202401202244"
        pos2 = self.wal.append_pager_request(pager_msg1)
        self.wal.mark_pager_processed(pos2)
        pos2 = self.wal.append_pager_request(pager_msg2)
        self.wal.mark_pager_processed(pos2)
        self.assertEqual(self.wal.pager_ckpt, pos2)

        with open(os.path.join(self.wal.base_path, "hl7.ckpt"), 'rb') as f:
            self.assertEqual(struct.unpack('Q', f.read(8))[0], pos1)

        with open(os.path.join(self.wal.base_path, "pager.ckpt"), 'rb') as f:
            self.assertEqual(struct.unpack('Q', f.read(8))[0], pos2)

        self.wal.compact_files()
        self.wal.hl7_wal.seek(0)
        self.wal.pager_wal.seek(0)
        self.assertEqual(self.wal.hl7_wal.read(), b"")
        self.assertEqual(self.wal.pager_wal.read(), b"")
        self.assertEqual(self.wal.hl7_ckpt, 0)
        self.assertEqual(self.wal.pager_ckpt, 0)