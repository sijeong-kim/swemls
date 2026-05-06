import torch
import os
from .patient_service import get_patient, create_patient
from .record_service import create_record
from src.models import Patient, Record
from src.database import get_db
from src.ml.model import AKIModel
from src.ml.dataset import AKINormalizer
from src.ml.inference import infer

_model_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "checkpoints", "best_model.pth"
)
_model = AKIModel()
_model.load_state_dict(torch.load(_model_path))

_normalizer_path = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "normalizers.config"
)
_normalizer = AKINormalizer.load(_normalizer_path)


def diagnose(mrn: str) -> int:
    db = get_db()
    patient = db.get_patient(mrn)
    records = db.get_records(mrn)
    if not patient or not records:
        return None

    creatinine = [record.creatinine for record in records]
    dates = [record.timestamp for record in records]

    return infer(_model, _normalizer, patient.age, creatinine, dates)

def process_message(data: dict) -> str:
    message_type = data["message_type"]
    mrn = data.get("mrn")

    if message_type == "ADT A01" and get_patient(mrn) is None:  # Admission
        create_patient(Patient(mrn=mrn, name=data.get("name"), dob=data.get("dob")))

    elif message_type == "ORU R01" and data["blood_test_type"].upper() == "CREATININE":
        # Save record to db
        timestamp = data.get("blood_test_time")
        record = Record(mrn=mrn, timestamp=timestamp, creatinine=data.get("blood_test_result"))
        create_record(record)

        # Predict for AKI
        if diagnose(mrn):
            return f"{mrn},{timestamp.strftime('%Y%m%d%H%M%S')}"

    return None
