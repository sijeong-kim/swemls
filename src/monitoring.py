from prometheus_client import Counter, Histogram, start_http_server
import socket

MESSAGES_RECEIVED = Counter('messages_total', 'Total messages received')
BLOOD_TEST_RESULTS = Counter('blood_test_results_total', 'Total blood tests received')
POSITIVE_PREDICTIONS = Counter('positive_prediction_total', 'Total AKI positive prediction')
PREDICTION_ERRORS = Counter('prediction_errors_total', 'Total prediction errors')
HTTP_400_ERRORS = Counter('http_400_errors_total', '400 HTTP responses')
HTTP_500_ERRORS = Counter('http_500_errors_total', '500 HTTP responses')
HTTP_BAD_ERRORS = Counter('http_bad_errors_total', 'Bad HTTP responses')
MLLP_RECONNECTS = Counter('mllp_reconnects_total', 'MLLP reconnections')
MLLP_ERRORS = Counter('mllp_errors_total', 'MLLP read errors')
PAGER_ERRORS = Counter('pager_errors_total', 'Total Pager request failings')
COMPACT_FILE_ERRORS = Counter('compact_file_errors_total', 'Total compact file errors')
TERMINATE_SIGNALS = Counter('terminate_signals_total', 'Total terminate signals received')

def start_metrics_server(port):
    # Check if the port is in use
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            # Start the Prometheus HTTP server if the port is free
            start_http_server(port)
            print(f"Prometheus metrics server started on port {port}")
        except socket.error:
            print(f"Prometheus Port {port} is already in use.")
