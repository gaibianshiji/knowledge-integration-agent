import os
import tempfile
from pathlib import Path

# In-memory storage for serverless environments
_memory_storage = {}

def get_data_dir(subdir: str) -> Path:
    """Get a writable data directory, falling back to /tmp if needed"""
    # Try project data directory first
    project_dir = Path(__file__).parent.parent / "data" / subdir
    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        # Test if writable
        test_file = project_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
        return project_dir
    except (OSError, PermissionError):
        # Fall back to /tmp for serverless environments
        tmp_dir = Path(tempfile.gettempdir()) / "knowledge_agent" / subdir
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir

def get_bundled_data_dir(subdir: str) -> Path:
    """Get the bundled data directory (read-only, for pre-loaded data)"""
    return Path(__file__).parent.parent / "data" / subdir

def get_memory_storage(key: str) -> dict:
    """Get in-memory storage for a given key"""
    if key not in _memory_storage:
        _memory_storage[key] = {}
    return _memory_storage[key]

def store_in_memory(key: str, item_id: str, data: dict):
    """Store data in memory"""
    storage = get_memory_storage(key)
    storage[item_id] = data

def get_from_memory(key: str, item_id: str) -> dict | None:
    """Get data from memory"""
    storage = get_memory_storage(key)
    return storage.get(item_id)

def list_from_memory(key: str) -> list:
    """List all items from memory storage"""
    storage = get_memory_storage(key)
    return list(storage.values())
