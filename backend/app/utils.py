import os
import tempfile
from pathlib import Path

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
