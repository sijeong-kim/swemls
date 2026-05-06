import json

from datetime import datetime
from dataclasses import dataclass


@dataclass
class Record:
    mrn: str
    timestamp: datetime
    creatinine: float

    def to_json(self):
        return json.dumps({
            "mrn": self.mrn,
            "timestamp": self.timestamp.isoformat(),
            "creatinine": self.creatinine
        })
    
    @classmethod
    def from_json(cls, data):
        if data is None:
            return None
        return cls(data["mrn"], datetime.fromisoformat(data["timestamp"]), data["creatinine"])
    
    def __lt__(self, other: 'Record'):
        return self.timestamp < other.timestamp
