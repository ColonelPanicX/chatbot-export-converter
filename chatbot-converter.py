#!/usr/bin/env python3
"""
ChatGPT Export Converter — run directly without installing.

Usage:
    python3 chatbot-converter.py
    python3 chatbot-converter.py --input export.zip --output ./chats
"""

import os
import sys

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from chatbot_export_converter.converter import main

if __name__ == "__main__":
    raise SystemExit(main())
