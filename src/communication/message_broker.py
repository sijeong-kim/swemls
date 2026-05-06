import argparse
import socket
import threading
import time
import httpx
from collections import deque
from .message_helper import (
    create_mllp_ack,
    parse_mllp_frames,
    parse_one_raw_hl7_message,
)
from .message_wal import MessageWal
from src.service.prediction_service import process_message
from src.monitoring import *

"""
The code for communication between the Integration Engine and Pager System.
We will view messaging part and the prediction part as a single entity to reduce latency for communication.
"""

MAX_QUEUE_SIZE = 1000
SHUTDOWN_POLL_INTERVAL_SECONDS = 2
MESSAGE_BUFFER_SIZE = 1024
RETRY_INTERVAL = 1  # Seconds
COMPACT_WAL_INTERVAL = 21600  # Seconds, 6 hours

class MessageBroker:
    def __init__(self, mllp_address, pager_endpoint, wal_path, metric_port):
        self._shutdown_event = threading.Event()

        # initialising WAL
        self.wal = MessageWal(wal_path)
        
        if not pager_endpoint.startswith(("http://", "https://")):
            self.pager_url = f"http://{pager_endpoint}/page"  # Default to HTTP
        else:
            self.pager_url = f"{pager_endpoint}/page"
        
        # in-memory queues
        self.hl7_queue = deque()
        self.pager_queue = deque()

        # read buffer for messages
        self.read_buffer = b""
        self.ack_send = False
        
        self.mllp_connection = None
        self.mllp_host, self.mllp_port = mllp_address.split(":")
        self.mllp_port = int(self.mllp_port)
        
        self.compactor = threading.Thread(
            target=self._compact_wals,
            daemon=True
        )

        # Prometheus metrics
        start_metrics_server(metric_port)

    def start(self):
        # replay message from persisent storage
        self.load_replay()
        self.compactor.start()

        print("Inference Operational")
        while not self._shutdown_event.is_set():
            self._receive_messages()
            self._handle_prediction()
            self._send_to_pager()

    def shutdown(self):
        print("\nInitiating graceful shutdown...")
        self._shutdown_event.set()

        # close on shutdown
        if self.mllp_connection and self.mllp_connection.fileno() != -1:
            self.mllp_connection.close()

        # Clean up WAL resources
        self.wal.compact_files()
        del self.wal

        TERMINATE_SIGNALS.inc()
        print("Shutdown complete")

    def _receive_messages(self):
        """Connect to MLLP server and receive HL7 messages"""
        # connection phase
        if not self.mllp_connection or self.mllp_connection.fileno() == -1:
            try:
                self.mllp_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.mllp_connection.connect((self.mllp_host, self.mllp_port))
                self.mllp_connection.settimeout(SHUTDOWN_POLL_INTERVAL_SECONDS)
                print(f"mllp: Connected at {self.mllp_host}:{self.mllp_port}")
            except Exception as e:
                print(f"Connection error: {e}, retrying after delay...")
                if self.mllp_connection:
                    self.mllp_connection.close()
                self.mllp_connection = None
                MLLP_RECONNECTS.inc()
                time.sleep(RETRY_INTERVAL)
        else:
            # data processing phase
            try:
                data = self.mllp_connection.recv(MESSAGE_BUFFER_SIZE)
                if data:
                    self.read_buffer += data
                    messages, self.read_buffer = parse_mllp_frames(self.read_buffer)
                    for msg in messages:
                        # append to queue for processing
                        hl7_position = self.wal.append_hl7(msg)
                        self.hl7_queue.append((hl7_position, msg))

                        MESSAGES_RECEIVED.inc()

                        # request more message into the queue
                        if len(self.hl7_queue) < MAX_QUEUE_SIZE:
                            self.mllp_connection.sendall(create_mllp_ack())
                            self.ack_send = True
                        else:
                            self.ack_send = False
                elif data == b'':
                    print("Connection closed by server")
                    self.mllp_connection.close()
                    self.mllp_connection = None
            except socket.timeout:
                pass  # normal for shutdown checks
            except Exception as e:
                print(f"Error receiving messages: {e}")
                self.mllp_connection.close()
                self.mllp_connection = None
                MLLP_ERRORS.inc()
                time.sleep(RETRY_INTERVAL)

    def _handle_prediction(self):
        """Handle processing message on prediction system"""
        if self.hl7_queue:
            hl7_position, message = self.hl7_queue.popleft()

            try:
                parsed_data = parse_one_raw_hl7_message(message)

                if parsed_data["message_type"] == "ORU R01":
                    BLOOD_TEST_RESULTS.inc()

                response_message = process_message(parsed_data)
                if response_message:
                    # append to pager queue for sending to pager
                    pager_position = self.wal.append_pager_request(response_message.encode())
                    self.pager_queue.append((pager_position, response_message))
                    POSITIVE_PREDICTIONS.inc()

                # mark HL7 message as processed
                self.wal.mark_hl7_processed(hl7_position)

                # request more HL7 message since queue is free up
                if not self.ack_send and self.mllp_connection and self.mllp_connection.fileno() != -1:
                    self.mllp_connection.sendall(create_mllp_ack())
            except Exception as e:
                self.hl7_queue.appendleft((hl7_position, message))
                PREDICTION_ERRORS.inc()
                print(f"Prediction error: {str(e)}")        

    def _send_to_pager(self):
        """Send pager requests to the pager system"""
        if self.pager_queue:
            pager_position, message = self.pager_queue.popleft()

            try:
                response = httpx.post(
                    self.pager_url, content=message, headers={"Content-Type": "text/plain"}
                )
                if response.status_code == 200:
                    self.wal.mark_pager_processed(pager_position)
                    print("Page at: ", message)
                elif response.status_code == 400:
                    HTTP_400_ERRORS.inc()
                    print(f"Permanent failure (400) for message: Invalid request format")
                elif response.status_code == 500:
                    HTTP_500_ERRORS.inc()
                    print(f"Temporary failure (500) for message, response: {response.read()}")
                    # retry sending this message
                    self.pager_queue.appendleft((pager_position, message))
                    time.sleep(RETRY_INTERVAL)
                else:
                    HTTP_BAD_ERRORS.inc()
                    print(f"Unexpected status {response.status} for message: {message}, no retry")
            except Exception as e:
                self.pager_queue.appendleft((pager_position, message))
                PAGER_ERRORS.inc()
                print(f"Pager error: {str(e)}") 
            
    def _compact_wals(self):
        """Periodically compact WAL files"""
        while not self._shutdown_event.is_set():
            for _ in range(COMPACT_WAL_INTERVAL // 60):
                if self._shutdown_event.is_set():
                    break
                time.sleep(60)
            else:
                try:
                    print("Compacting WAL files...")
                    self.wal.compact_files()
                    print("WAL files compacted successfully.")
                except Exception as e:
                    COMPACT_FILE_ERRORS.inc()
                    print(f"Error compacting WAL files: {e}")

    def load_replay(self):
        # load replay from WAL if message broker crashed and restarted
        hl7_messages, pager_requests = self.wal.load_replay()
        self.hl7_queue.extend(hl7_messages)
        self.pager_queue.extend(pager_requests)
