from src.models import Patient
from src.database import get_db


def get_patient(mrn: str) -> Patient:
    return get_db().get_patient(mrn)


def create_patient(patient: Patient) -> None:
    get_db().create_patient(patient)
