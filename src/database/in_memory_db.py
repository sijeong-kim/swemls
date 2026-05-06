import pandas as pd

from .base_db import BaseDB
from src.models import Patient, Record
from src.utils import collapse_columns
from typing import List


class MemoryDB(BaseDB):
    def __init__(self):
        self.patients = {}
        self.records = {}

    def get_patient(self, mrn: str) -> Patient:
        return self.patients.get(mrn)

    def get_records(self, mrn: str) -> List[Record]:
        return self.records.get(mrn, [])

    def create_record(self, record: Record) -> None:
        if record.mrn not in self.records:
            self.records[record.mrn] = []
        self.records[record.mrn].append(record)
        self.records[record.mrn].sort(key=lambda x: x.timestamp)

    def create_patient(self, patient: Patient) -> None:
        self.patients[patient.mrn] = patient
        self.records[patient.mrn] = []

    def reset(self):
        self.patients = {}
        self.records = {}

    def __len__(self):
        return len(self.records)
