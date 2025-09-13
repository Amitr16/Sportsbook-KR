# JSON streaming utilities to reduce memory usage
from typing import Iterator, Dict, Any
import json
import os

def iter_json_lines(path: str) -> Iterator[Dict]:
    """Iterate over JSON Lines file (one JSON object per line)"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as e:
                        print(f"Warning: Invalid JSON on line {line_num}: {e}")
                        continue
    except FileNotFoundError:
        print(f"Warning: File not found: {path}")
        return

def iter_large_json_array(path: str, array_key: str = 'matches', item_key: str = 'item') -> Iterator[Dict]:
    """Stream large JSON arrays without loading everything into memory"""
    try:
        with open(path, 'rb') as f:
            import ijson
            prefix = f'{array_key}.{item_key}' if item_key else array_key
            for obj in ijson.items(f, prefix):
                yield obj
    except ImportError:
        print("Warning: ijson not available, falling back to full load")
        # Fallback to regular json.load if ijson not available
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if array_key in data and isinstance(data[array_key], list):
                for item in data[array_key]:
                    yield item
    except FileNotFoundError:
        print(f"Warning: File not found: {path}")
        return

def stream_filtered_events(json_file: str, sport_name: str, filters: Dict[str, Any] = None, limit: int = 500) -> Iterator[Dict]:
    """Stream and filter events from large JSON files"""
    if not os.path.exists(json_file):
        return
    
    count = 0
    filters = filters or {}
    
    try:
        # Try to use ijson for streaming
        for match in iter_large_json_array(json_file, 'matches', 'item'):
            # Apply filters
            if filters.get('league') and match.get('league') != filters['league']:
                continue
            if filters.get('date') and match.get('date') != filters['date']:
                continue
            if filters.get('status') and match.get('status') != filters['status']:
                continue
                
            yield match
            count += 1
            if count >= limit:
                break
                
    except Exception as e:
        print(f"Error streaming {json_file}: {e}")
        return
