from typing import List
from src.database import get_db
from src.models import Record


def get_records(mrn: str) -> List[Record]:
    db = get_db()
    return db.get_records(mrn)


def create_record(record: Record) -> None:
    db = get_db()
    db.create_record(record)
