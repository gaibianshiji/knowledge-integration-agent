import json
from pathlib import Path
from app.utils import get_data_dir, get_bundled_data_dir

GRAPH_DIR = get_data_dir("graphs")
BUNDLED_GRAPH_DIR = get_bundled_data_dir("graphs")

_graph_cache = {}

def preload_graphs():
    """Load pre-built graph data from disk into memory at startup."""
    global _graph_cache
    try:
        for path in BUNDLED_GRAPH_DIR.glob("*_graph.json"):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _graph_cache[data["textbook_id"]] = data
        print(f"Preloaded {len(_graph_cache)} graphs from {BUNDLED_GRAPH_DIR}")
    except Exception as e:
        print(f"Failed to preload graphs: {e}")

def get_graph(textbook_id: str) -> dict | None:
    if textbook_id in _graph_cache:
        return _graph_cache[textbook_id]
    path = GRAPH_DIR / f"{textbook_id}_graph.json"
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            _graph_cache[textbook_id] = data
            return data
    return None
