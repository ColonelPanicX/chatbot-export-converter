#!/usr/bin/env python3
"""
ChatGPT Export Converter — run directly without installing.

Usage:
    python3 chatgpt-converter.py
    python3 chatgpt-converter.py --input export.zip --output ./chats
"""
import sys
import os

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from chatgpt_export_converter.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
