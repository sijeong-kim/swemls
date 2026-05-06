import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.service.record_service import get_records, create_record
from src.models import Record


class TestRecordService(unittest.TestCase):
    @patch("src.service.record_service.get_db")
    def test_get_records(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_records = mock_db = MagicMock()
        mock_records = [
            Record(mrn="12345", timestamp=datetime(2020, 1, 1), creatinine=109.2),
            Record(mrn="12345", timestamp=datetime(2020, 1, 2), creatinine=110.2),
        ]
        mock_db.get_records.return_value = mock_records
        mock_get_db.return_value = mock_db

        result = get_records("12345")

        mock_get_db.assert_called_once()
        mock_db.get_records.assert_called_once_with("12345")
        self.assertEqual(result, mock_records)

    @patch("src.service.record_service.get_db")
    def test_create_record(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        record = Record(mrn="123", timestamp=datetime(2020, 1, 1), creatinine=109.2)

        create_record(record)

        mock_get_db.assert_called_once()
        mock_db.create_record.assert_called_once_with(record)


if __name__ == "__main__":
    unittest.main()
