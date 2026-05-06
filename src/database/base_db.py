import pandas as pd
from src.utils import collapse_columns

from abc import ABC, abstractmethod
from typing import List
from src.models import Patient, Record


class BaseDB(ABC):
    @abstractmethod
    def get_patient(self, mrn: str) -> Patient:
        pass

    @abstractmethod
    def get_records(self, mrn: str) -> List[Record]:
        pass

    @abstractmethod
    def create_records(self, records: List[Record]) -> None:
        pass

    @abstractmethod
    def create_record(self, record: Record) -> None:
        pass

    @abstractmethod
    def create_patient(self, patient: Patient) -> None:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    def __len__(self) -> int:
        pass

    def create_records(self, records: List[Record]) -> None:
        records.sort()
        for record in records:
            self.create_record(record)

    def load_csv(self, path: str, drop_existing=False) -> None:
        if drop_existing:
            self.reset()
        elif len(self) > 0:
            raise ValueError("Database is not empty. Set drop_existing=True to drop existing data.")

        df = pd.read_csv(path)

        level_cols = [col for col in df.columns if "result" in col]
        date_cols = [col for col in df.columns if "date" in col]

        df = collapse_columns(df, level_cols, "creatinine")
        df = collapse_columns(df, date_cols, "dates")

        for _, row in df.iterrows():
            mrn = row["mrn"]

            records = []
            for creatinine, date in zip(row["creatinine"], row["dates"]):
                record = Record(mrn, pd.to_datetime(date), creatinine)
                records.append(record)

            self.create_records(records)
