import os

from enum import Enum
from .in_memory_db import MemoryDB
from .base_db import BaseDB
from .persist_db import PersistDB

_db = None


class DBType(Enum):
    MEMORY = 0
    PERSIST = 1

    @classmethod
    def from_str(cls, s: str):
        if s == "memory":
            return cls.MEMORY
        elif s == "persist":
            return cls.PERSIST
        else:
            raise ValueError(f"Invalid database type: {s}")

def get_db(type: DBType = None) -> BaseDB:
    global _db

    if _db is None:
        if type is None:
            type = DBType.from_str(os.getenv("DB_TYPE", "persist"))

        if type == DBType.MEMORY:
            _db = MemoryDB()
        elif type == DBType.PERSIST:
            config = get_db_config(type)           
            _db = PersistDB(**config)
        else:
            raise NotImplementedError(f"Database type {type} not implemented")

    return _db


def get_db_config(type: DBType = DBType.MEMORY) -> dict:
    if type == DBType.PERSIST:        
        return {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", 6379)),
            "db": int(os.getenv("REDIS_DB", 0)),
            "record_limit": int(os.getenv("RECORD_LIMIT", 100)),
            "decode_responses": True,
            "charset": "utf-8"
        }
    return None


def create_db(type: DBType = DBType.MEMORY, **kwargs) -> BaseDB:
    if type == DBType.MEMORY:
        return MemoryDB()
    elif type == DBType.PERSIST:
        return PersistDB(**kwargs)
    else:
        raise NotImplementedError(f"Database type {type} not implemented")
