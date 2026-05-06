import json

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Patient:
    mrn: str
    name: str
    dob: datetime

    @property
    def age(self):
        return (datetime.now() - self.dob).days // 365
    
    def to_json(self):
        return json.dumps({
            "mrn": self.mrn,
            "name": self.name,
            "dob": self.dob.isoformat()
        })
    
    @classmethod
    def from_json(cls, data):
        if data is None:
            return None
        return cls(data["mrn"], data["name"], datetime.fromisoformat(data["dob"]))
