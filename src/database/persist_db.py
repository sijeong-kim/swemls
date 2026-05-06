import redis
import json
import time
from .base_db import BaseDB
from src.models import Patient, Record
from typing import List

class PersistDB(BaseDB):
    def __init__(self, record_limit=100, **config):
        self.record_limit = record_limit
        self.delay = 2
        self.config = config
        self._connect_to_redis()

    def _connect_to_redis(self):
        while True:
            try:
                self.conn = redis.Redis(**self.config)
                # Test connection
                self.conn.ping()
                break  # Exit loop if connection is successful
            except redis.ConnectionError as e:
                print(f"Failed to connect to Redis: {e}")
                time.sleep(self.delay)

    def get_patient(self, mrn: str) -> Patient:
        result = self.conn.get(f'patient:{mrn}')
        if not result:
            return None
        return Patient.from_json(json.loads(result))
    
    def get_records(self, mrn: str) -> List[Record]:
        records = self.conn.lrange(f'records:{mrn}', 0, -1)
        return [Record.from_json(json.loads(r)) for r in records]

    
    def create_record(self, record: Record) -> None:
        self.conn.rpush(f'records:{record.mrn}', record.to_json())
        self.conn.ltrim(f'records:{record.mrn}', -self.record_limit, -1)
        
    def create_patient(self, patient: Patient) -> None:
        self.conn.set(f'patient:{patient.mrn}', patient.to_json())

    def reset(self):
        self.conn.flushdb()

    def __len__(self):
        return self.conn.dbsize()
