import xxhash
import hashlib
from typing import Optional

CHUNK_SIZE = 1024 * 1024  # 1MB

def compute_xxhash(path: str) -> Optional[str]:
    try:
        h = xxhash.xxh64()
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def compute_md5(path: str) -> Optional[str]:
    try:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def compute_sha1(path: str) -> Optional[str]:
    try:
        h = hashlib.sha1()
        with open(path, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None
