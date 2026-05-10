#!/usr/bin/env python3
"""Script to load all textbooks from the textbooks directory."""
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.pdf_parser import parse_pdf
from app.utils import clear_memory

TEXTBOOKS_DIR = Path(__file__).parent.parent / "textbooks"

def load_all_textbooks():
    """Load all textbooks from the textbooks directory."""
    # Clear memory storage
    clear_memory("parsed_textbooks")

    if not TEXTBOOKS_DIR.exists():
        print(f"Textbooks directory not found: {TEXTBOOKS_DIR}")
        return

    pdf_files = list(TEXTBOOKS_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")

    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        try:
            # Use filename as textbook_id
            textbook_id = f"book_{pdf_file.stem}"
            result = parse_pdf(str(pdf_file), textbook_id, original_filename=pdf_file.name)
            print(f"  - Title: {result['title']}")
            print(f"  - Pages: {result['total_pages']}")
            print(f"  - Chapters: {len(result['chapters'])}")
        except Exception as e:
            print(f"  - Error: {e}")

if __name__ == "__main__":
    load_all_textbooks()
