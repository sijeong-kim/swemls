import unittest
import os
import pandas as pd

from datetime import date, datetime

from src.models import Patient, Record
from src.database import create_db, DBType


class TestLoadCSV(unittest.TestCase):
    def setUp(self):
        self.db = create_db(DBType.MEMORY)

    def test_load_csv(self):
        path = os.path.join(os.path.dirname(__file__), "data/history.csv")
        df = pd.read_csv(path)
        self.db.load_csv(path)

        self.assertTrue(os.path.exists(path))
        self.assertEqual(len(self.db), len(df))


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db = create_db(DBType.MEMORY)

    def test_create_patient(self):
        patient = Patient(mrn="123", name="Alice", dob=date(1988, 1, 1))
        self.db.create_patient(patient)
        self.assertEqual(self.db.get_patient("123").mrn, patient.mrn)
        self.assertEqual(self.db.get_patient("123").name, patient.name)
        self.assertEqual(self.db.get_patient("123").dob, patient.dob)

    def test_create_record(self):
        record = Record(mrn="123", timestamp=datetime(2020, 1, 1), creatinine=109.2)
        self.db.create_record(record)
        self.assertEqual(self.db.get_records("123")[0].mrn, record.mrn)
        self.assertEqual(self.db.get_records("123")[0].creatinine, record.creatinine)
        self.assertEqual(self.db.get_records("123")[0].timestamp, record.timestamp)


if __name__ == "__main__":
    unittest.main()
