import unittest
import tempfile
import threading
import time
import socket
import shutil
import os
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler, http
from src.communication.message_broker import MessageBroker
from src.communication.message_wal import MessageWal
from unittest.mock import MagicMock
from src.communication.message_helper import (
    MLLP_START_OF_BLOCK,
    MLLP_END_OF_BLOCK,
    MLLP_CARRIAGE_RETURN,
    create_mllp_ack
)

ADT_A01 = [
    r"MSH|^~\&|SIMULATION|SOUTH RIVERSIDE|||202401201630||ADT^A01|||2.5",
    r"PID|1||478237423||ELIZABETH HOLMES||19840203|F",
    r"NK1|1|SUNNY BALWANI|PARTNER"
]

def to_mllp(segments):
    m = bytes([MLLP_START_OF_BLOCK])
    m += b"\r".join([segment.encode("ascii") for segment in segments]) + b"\r"
    m += bytes([MLLP_END_OF_BLOCK, MLLP_CARRIAGE_RETURN])
    return m

TEST_MLLP_PORT = 18440
TEST_PAGER_PORT = 18441
TEST_METRIC_PORT = 19090

class TestMessageBroker(unittest.TestCase):
    def setUp(self):
        os.environ["DB_TYPE"] = "memory"
        self.wal_dir = tempfile.mkdtemp()
        self.broker = MessageBroker(
            mllp_address=f"localhost:{TEST_MLLP_PORT}",
            pager_endpoint=f"localhost:{TEST_PAGER_PORT}",
            wal_path=self.wal_dir,
            metric_port=TEST_METRIC_PORT
        )
        self.broker.compactor = MagicMock()
        self.mllp_thread = None
        self.pager_thread = None
        self.broker_thread = None

    def tearDown(self):
        if self.mllp_thread and self.mllp_thread.is_alive():
            self.mllp_thread.join()
        if self.pager_thread and self.pager_thread.is_alive():
            self.pager_thread.join()
        if self.broker_thread and self.broker_thread.is_alive():
            self.broker.shutdown()
            self.broker_thread.join()
        time.sleep(4)
        shutil.rmtree(self.wal_dir)

    def test_receive_hl7_message(self):
        server_ready = threading.Event()
        ack_received = threading.Event()
        # Mock MLLP server to send message
        def mllp_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("localhost", TEST_MLLP_PORT))
                s.listen(1)
                server_ready.set()
                conn, _ = s.accept()
                with conn:
                    print("Server connection accepted")
                    conn.sendall(to_mllp(ADT_A01))
                    ack = conn.recv(1024)
                    if ack:
                        print("ACK received: ", ack)
                        ack_received.set()

        self.mllp_thread = threading.Thread(target=mllp_server)
        
        # mock functions
        self.broker._handle_prediction = MagicMock()
        self.broker._send_to_pager = MagicMock()

        # Start services
        self.mllp_thread.start()

        self.broker_thread = threading.Thread(target=self.broker.start)
        self.broker_thread.start()

        ack_received.wait(timeout=2)
        self.assertTrue(ack_received.is_set())

    def test_prediction_processing_sends_ack(self):
        # Mock MLLP server to send message and capture ACK
        ack_received = threading.Event()
        ack_data = []

        def mllp_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("localhost", TEST_MLLP_PORT))
                s.listen(1)
                conn, addr = s.accept()
                with conn:
                    conn.sendall(to_mllp(ADT_A01))
                    data = conn.recv(1024)
                    if data:
                        ack_data.append(data)
                        ack_received.set()

        mllp_thread = threading.Thread(target=mllp_server)
        mllp_thread.start()

        self.broker._send_to_pager = MagicMock()

        # Start broker and prediction
        self.broker_thread = threading.Thread(target=self.broker.start)
        self.broker_thread.start()

        # Wait for ACK
        ack_received.wait(timeout=2)
        self.assertTrue(ack_received.is_set(), "ACK was not received within the timeout period")
        expected_ack = create_mllp_ack()
        self.assertEqual(ack_data[0], expected_ack, "Received ACK does not match the expected ACK")

    def test_pager_retry_on_failure(self):
        # Setup mock pager server
        class PagerHandler(BaseHTTPRequestHandler):
            request_count = 0
            def do_POST(self):
                if self.path == "/page":
                    PagerHandler.request_count += 1
                    if PagerHandler.request_count == 1:
                        self.send_response(http.HTTPStatus.INTERNAL_SERVER_ERROR)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                    else:
                        self.send_response(http.HTTPStatus.OK)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                else:
                    print("pager: bad request: not /page")
                    self.send_response(http.HTTPStatus.BAD_REQUEST)
                    self.end_headers()

        # Start the mock pager server
        pager_server = ThreadingHTTPServer(("localhost", TEST_PAGER_PORT), PagerHandler)
        self.pager_thread = threading.Thread(target=pager_server.serve_forever)
        self.pager_thread.start()

        self.broker._receive_messages = MagicMock()
        self.broker._handle_prediction = MagicMock()

        try:
            # Start broker
            self.broker_thread = threading.Thread(target=self.broker.start)
            self.broker_thread.start()

            # Add pager request to queue
            pager_data = b"478237423,202401202243"
            position = self.broker.wal.append_pager_request(pager_data)
            self.broker.pager_queue.append((position, pager_data))

            # Wait for retries and success
            self.wait_for_condition(lambda: PagerHandler.request_count >= 2 and len(self.broker.pager_queue) == 0, 
                                    "Pager request not processed after retries", timeout=15)

            # Verify request count and queue state
            self.assertEqual(PagerHandler.request_count, 2)
            self.assertEqual(len(self.broker.pager_queue), 0)
        finally:
            pager_server.shutdown()
            pager_server.server_close()

    def test_wal_replay(self):
        # Mock MessageWal and its load_replay function
        hl7_msg = ("\r".join(ADT_A01) + "\r").encode("utf-8")
        pager_msg = b"478237423,202401202243"
        wal = MagicMock(spec=MessageWal)
        wal.load_replay.return_value = (
            [(len(hl7_msg) + 1, hl7_msg)],  # HL7 messages
            [(len(pager_msg) + 1, pager_msg)]  # Pager requests
        )

        # Replace the broker's wal with the mock
        self.broker.wal = wal

        # Mock functions
        self.broker._receive_messages = MagicMock()
        self.broker._handle_prediction = MagicMock()
        self.broker._send_to_pager = MagicMock()

        # Start broker
        self.broker_thread = threading.Thread(target=self.broker.start)
        self.broker_thread.start()

        wal.load_replay.assert_called_once()

        # Check thread queues
        self.assertEqual(len(self.broker.hl7_queue), 1)
        self.assertEqual(self.broker.hl7_queue[0], (len(hl7_msg) + 1, hl7_msg))
        self.assertEqual(len(self.broker.pager_queue), 1)
        self.assertEqual(self.broker.pager_queue[0], (len(pager_msg) + 1, pager_msg))

    def wait_for_condition(self, condition, timeout_msg, timeout=3):
        for _ in range(timeout):
            if condition():
                return
            time.sleep(1)
        self.fail(timeout_msg)

if __name__ == "__main__":
    unittest.main()