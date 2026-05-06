#!/usr/bin/env python3
import argparse
import os
import time
import signal
import dotenv

from src.database import get_db
from src.communication.message_broker import MessageBroker

def main():
    # Load environment variables
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="Healthcare Inference System")
    parser.add_argument(
        "--mllp-address",
        default=os.getenv("MLLP_ADDRESS", "localhost:8440"),
        help="MLLP server address in 'host:port' format",
    )
    parser.add_argument(
        "--pager-endpoint",
        default=os.getenv("PAGER_ADDRESS", "localhost:8441"),
        help="Pager system HTTP endpoint",
    )
    parser.add_argument(
        "--wal-path",
        default="wal",
        help="WAL storage directory")
    parser.add_argument(
        "--clean-storage",
        default=False,
        action="store_true",
        help="Clean up storage before for full reset")
    parser.add_argument(
        "--metric-port",
        default=9090,
        help="Prometheus metrics port")
    parser.add_argument(
        "--history",
        default="data/history.csv",
        help="history.csv",
    )
    args = parser.parse_args()

    if args.clean_storage:
        print("Cleaning up storage...")
        if os.path.exists(args.wal_path):
            for file in os.listdir(args.wal_path):
                os.remove(os.path.join(args.wal_path, file))
        print("Storage cleaned up")

    try:
        # Populate db
        print("Populating db...")
        db = get_db()
        db.load_csv(args.history, args.clean_storage)
    except ValueError as e:
        print(e)

    print("Starting message broker...")
    broker = MessageBroker(args.mllp_address, args.pager_endpoint, args.wal_path, args.metric_port)
    
    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        broker.shutdown()
        time.sleep(4) # Allow time for threads to finish
        exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    broker.start()
    # Keep the main thread running
    while True:
        time.sleep(300)

if __name__ == "__main__":
    main()
