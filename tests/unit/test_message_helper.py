import unittest
from datetime import datetime
from src.communication.message_helper import (
    MLLP_START_OF_BLOCK,
    MLLP_END_OF_BLOCK,
    MLLP_CARRIAGE_RETURN,
    create_mllp_ack,
    parse_mllp_frames,
    parse_one_raw_hl7_message,
)


class TestCreateMllpAck(unittest.TestCase):
    def test_ack_structure(self):
        ack = create_mllp_ack()

        # Check the ACK starts with MLLP_START_OF_BLOCK
        self.assertEqual(ack[0], MLLP_START_OF_BLOCK)

        # Check the ACK ends with MLLP_END_OF_BLOCK followed by MLLP_CARRIAGE_RETURN
        self.assertEqual(ack[-2], MLLP_END_OF_BLOCK)
        self.assertEqual(ack[-1], MLLP_CARRIAGE_RETURN)

        # Extract content between start and end blocks
        content = ack[1:-2]  # Exclude start, end, and trailing CR
        segments = content.split(b"\r")

        # Verify MSH and MSA segments exist
        self.assertGreaterEqual(len(segments), 2)
        self.assertTrue(segments[0].startswith(b"MSH|"))
        self.assertTrue(segments[1].startswith(b"MSA|AA"))


class TestParseMllpFrames(unittest.TestCase):
    def test_empty_data(self):
        data = b""
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [])
        self.assertEqual(remaining, data)

    def test_single_complete_frame(self):
        frame = (
            bytes([MLLP_START_OF_BLOCK])
            + b"TestMessage"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        messages, remaining = parse_mllp_frames(frame)
        self.assertEqual(messages, [b"TestMessage"])
        self.assertEqual(remaining, b"")

    def test_start_without_end(self):
        data = bytes([MLLP_START_OF_BLOCK, 0x41, 0x42, 0x43])  # 'ABC'
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [])
        self.assertEqual(remaining, data)

    def test_multiple_complete_frames(self):
        frame1 = (
            bytes([MLLP_START_OF_BLOCK])
            + b"Frame1"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        frame2 = (
            bytes([MLLP_START_OF_BLOCK])
            + b"Frame2"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        data = frame1 + frame2
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [b"Frame1", b"Frame2"])
        self.assertEqual(remaining, b"")

    def test_garbage_before_frame(self):
        garbage = b"Garbage" + bytes([MLLP_END_OF_BLOCK])
        frame = (
            bytes([MLLP_START_OF_BLOCK])
            + b"ValidMessage"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        data = garbage + frame
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [b"ValidMessage"])
        self.assertEqual(remaining, b"")

    def test_data_after_frame(self):
        frame = (
            bytes([MLLP_START_OF_BLOCK])
            + b"Message"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        extra_data = b"ExtraData"
        data = frame + extra_data
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [b"Message"])
        self.assertEqual(remaining, extra_data)

    def test_multiple_end_blocks(self):
        data = (
            bytes([MLLP_START_OF_BLOCK])
            + b"Data"
            + bytes([MLLP_END_OF_BLOCK])
            + b"Extra"
            + bytes([MLLP_END_OF_BLOCK])
        )
        messages, remaining = parse_mllp_frames(data)
        # Here is a invalid MLLP message, so the parser should ignore the message
        self.assertEqual(messages, [])
        self.assertEqual(remaining, data)

    def test_zero_length_message(self):
        data = bytes([MLLP_START_OF_BLOCK, MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [b""])
        self.assertEqual(remaining, b"")

    def test_split_across_calls(self):
        # Simulate receiving data in two chunks
        chunk1 = bytes([MLLP_START_OF_BLOCK]) + b"Partial"
        chunk2 = b"Message" + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])

        # First parse
        messages1, remaining1 = parse_mllp_frames(chunk1)
        self.assertEqual(messages1, [])
        self.assertEqual(remaining1, chunk1)

        # Second parse with combined data
        combined = remaining1 + chunk2
        messages2, remaining2 = parse_mllp_frames(combined)
        self.assertEqual(messages2, [b"PartialMessage"])
        self.assertEqual(remaining2, b"")

    def test_internal_start_block(self):
        internal_data = bytes([MLLP_START_OF_BLOCK, 0x41, 0x42])
        data = (
            bytes([MLLP_START_OF_BLOCK])
            + internal_data
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [internal_data])
        self.assertEqual(remaining, b"")

    def test_end_before_start(self):
        data = (
            bytes([MLLP_END_OF_BLOCK])
            + b"Ignored"
            + bytes([MLLP_START_OF_BLOCK])
            + b"Valid"
            + bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
        )
        messages, remaining = parse_mllp_frames(data)
        self.assertEqual(messages, [b"Valid"])
        self.assertEqual(remaining, b"")


class TestHL7Parser(unittest.TestCase):
    def test_parse_one_raw_hl7_message(self):
        adt_a01_message = b"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401201630||ADT^A01|||2.5\rPID|1||478237423||ELIZABETH HOLMES||19840203|F\rNK1|1|SUNNY BALWANI|PARTNER\r"
        adt_a03_message = b"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401221000||ADT^A03|||2.5\rPID|1||478237423\r"
        oru_r01_message = b"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401201800||ORU^R01|||2.5\rPID|1||478237423\rOBR|1||||||202401202243\rOBX|1|SN|CREATININE||103.4\r"

        expected_adt_a01 = {
            "message_type": "ADT A01",
            "mrn": "478237423",
            "name": "ELIZABETH HOLMES",
            "dob": datetime(1984, 2, 3),
            "sex": "F",
        }
        expected_adt_a03 = {"message_type": "ADT A03", "mrn": "478237423"}
        expected_oru_r01 = {
            "message_type": "ORU R01",
            "mrn": "478237423",
            "blood_test_time": datetime(2024, 1, 20, 22, 43),
            "blood_test_type": "CREATININE",
            "blood_test_result": 103.4,
        }

        self.assertEqual(parse_one_raw_hl7_message(adt_a01_message), expected_adt_a01)
        self.assertEqual(parse_one_raw_hl7_message(adt_a03_message), expected_adt_a03)
        self.assertEqual(parse_one_raw_hl7_message(oru_r01_message), expected_oru_r01)


if __name__ == "__main__":
    unittest.main()
