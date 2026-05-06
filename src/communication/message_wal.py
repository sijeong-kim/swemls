import os
import threading
import struct

class MessageWal:
    def __init__(self, base_path):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
        
        # HL7 storage
        self.hl7_wal = open(os.path.join(base_path, 'hl7.wal'), 'ab+')
        self.hl7_ckpt = self._load_checkpoint('hl7.ckpt')
        
        # Pager response storage
        self.pager_wal = open(os.path.join(base_path, 'pager.wal'), 'ab+')
        self.pager_ckpt = self._load_checkpoint('pager.ckpt')
        
        self.lock = threading.Lock()

    def __del__(self):
        if hasattr(self, 'hl7_wal') and not self.hl7_wal.closed:
            self.hl7_wal.close()
        if hasattr(self, 'pager_wal') and not self.pager_wal.closed:
            self.pager_wal.close()
    
    def _load_checkpoint(self, ckpt_file):
        path = os.path.join(self.base_path, ckpt_file)
        if os.path.exists(path):
            with open(path, 'rb') as f:
                # Read the binary content and unpack it into an integer (position)
                return struct.unpack('Q', f.read(8))[0]  # 'Q' is for unsigned long long (8 bytes)
        else:
            with open(path, 'wb') as f:
                f.write(struct.pack('Q', 0))
        return 0
    
    def _update_checkpoint(self, ckpt_file, position):
        path = os.path.join(self.base_path, ckpt_file)
        with open(path, 'wb') as f:
            # Pack the position into 8 bytes (64-bit unsigned integer) and write it to the file
            f.write(struct.pack('Q', position))  # 'Q' is for unsigned long long (8 bytes)
    
    def append_hl7(self, message):
        with self.lock:
            self.hl7_wal.write(message + b"\n")
            self.hl7_wal.flush()
            return self.hl7_wal.tell()
    
    def append_pager_request(self, message):
        with self.lock:
            self.pager_wal.write(message + b"\n")
            self.pager_wal.flush()
            return self.pager_wal.tell()

    def load_replay(self):
        with self.lock:
            # Load unprocessed HL7 messages
            cumulative_length = 0
            self.hl7_wal.seek(self.hl7_ckpt)
            hl7_messages = []
            for msg in self.hl7_wal.read().split(b"\n"):
                if msg:
                    cumulative_length += len(msg) + 1
                    hl7_messages.append((cumulative_length, msg))
            
            # Load pending pager requests
            cumulative_length = 0
            self.pager_wal.seek(self.pager_ckpt)
            pager_requests = []
            for msg in self.pager_wal.read().split(b"\n"):
                if msg:
                    cumulative_length += len(msg) + 1
                    pager_requests.append((cumulative_length, msg))
            
            return hl7_messages, pager_requests
    
    def mark_hl7_processed(self, position):
        with self.lock:
            self._update_checkpoint('hl7.ckpt', position)
        self.hl7_ckpt = position
    
    def mark_pager_processed(self, position):
        with self.lock:
            self._update_checkpoint('pager.ckpt', position)
        self.pager_ckpt = position
    
    def compact_files(self):
        with self.lock:
            # Compact HL7 WAL
            self._compact_file('hl7.wal', self.hl7_ckpt, self.hl7_wal)
            self.hl7_wal = open(os.path.join(self.base_path, 'hl7.wal'), 'ab+')
            self._update_checkpoint('hl7.ckpt', 0)
            self.hl7_ckpt = 0

            # Compact Pager WAL
            self._compact_file('pager.wal', self.pager_ckpt, self.pager_wal)
            self.pager_wal = open(os.path.join(self.base_path, 'pager.wal'), 'ab+')
            self._update_checkpoint('pager.ckpt', 0)
            self.pager_ckpt = 0
    
    def _compact_file(self, filename, ckpt_pos, source):
        temp_path = os.path.join(self.base_path, f'{filename}.tmp')
        source.seek(ckpt_pos)
        with open(temp_path, 'wb') as new_file:
            new_file.write(source.read())
        
        source.close()
        os.replace(temp_path, source.name)
