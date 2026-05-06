import unittest
from unittest.mock import patch, MagicMock
import socket
import time
import os
import tempfile
import threading
import shutil
from src.communication.message_broker import MessageBroker

TEST_MLLP_PORT = 18440
TEST_PAGER_PORT = 18441
TEST_METRIC_PORT = 19090

class TestMessageBroker(unittest.TestCase):
    def setUp(self):
        os.environ["DB_TYPE"] = "memory"
        self.wal_dir = tempfile.mkdtemp()
        # Mock start_metrics_server to do nothing
        self.broker = MessageBroker(
            mllp_address=f"localhost:{TEST_MLLP_PORT}",
            pager_endpoint=f"localhost:{TEST_PAGER_PORT}",
            wal_path=self.wal_dir,
            metric_port=TEST_METRIC_PORT
        )  
        self.broker.wal = MagicMock()
        self.broker.compactor = MagicMock()

    def tearDown(self):
        shutil.rmtree(self.wal_dir)

    @patch('socket.socket')
    def test_receive_messages_connection_phase_success(self, mock_socket):
        # Simulate successful connection
        mock_socket_instance = mock_socket.return_value

        self.broker._receive_messages()

        mock_socket_instance.connect.assert_called_with(("localhost", TEST_MLLP_PORT))
        mock_socket_instance.settimeout.assert_called_with(2)
        self.assertIsNotNone(self.broker.mllp_connection)

    @patch('socket.socket')
    def test_receive_messages_connection_phase_failure(self, mock_socket):
        # Simulate connection failure
        mock_socket_instance = mock_socket.return_value
        mock_socket_instance.fileno.return_value = -1
        mock_socket_instance.connect.side_effect = Exception("Connection error")

        with patch('time.sleep', return_value=None):
            self.broker._receive_messages()

        mock_socket_instance.connect.assert_called_with(("localhost", TEST_MLLP_PORT))
        self.assertIsNone(self.broker.mllp_connection)

    def test_receive_messages_data_processing_phase_empty_data(self):
        shutdown_event = threading.Event()
        def mllp_server():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("localhost", TEST_MLLP_PORT))
                s.listen(1)
                conn, addr = s.accept()
                with conn:
                    conn.sendall(b'')
                    time.sleep(1)
                    shutdown_event.set()

        mllp_thread = threading.Thread(target=mllp_server)
        mllp_thread.start()

        # first call establishes connection
        self.broker._receive_messages()
        self.assertIsNotNone(self.broker.mllp_connection)
        shutdown_event.wait()
        # second call should close connection since server sent empty data
        self.broker._receive_messages()
        self.assertIsNone(self.broker.mllp_connection)

if __name__ == '__main__':
    unittest.main()