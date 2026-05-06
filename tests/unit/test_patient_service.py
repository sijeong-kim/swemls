from unittest import TestCase
from unittest.mock import patch, MagicMock
from datetime import date
from src.service.patient_service import get_patient, create_patient
from src.models import Patient


class TestPatientService(TestCase):
    @patch("src.service.patient_service.get_db")
    def test_get_patient(self, mock_get_db):
        mock_db = MagicMock()
        mock_patient = Patient(mrn="12345", name="John Doe", dob=date(1980, 1, 1))
        mock_db.get_patient.return_value = mock_patient
        mock_get_db.return_value = mock_db

        result = get_patient("12345")

        mock_get_db.assert_called_once()
        mock_db.get_patient.assert_called_once_with("12345")
        self.assertEqual(result, mock_patient)

    @patch("src.service.patient_service.get_db")
    def test_create_patient(self, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_patient = Patient(mrn="12345", name="John Doe", dob=date(1980, 1, 1))

        create_patient(mock_patient)

        mock_get_db.assert_called_once()
        mock_db.create_patient.assert_called_once_with(mock_patient)
