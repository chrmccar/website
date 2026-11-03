#!/bin/bash
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 photo_manager.py
else
  echo "Python 3 was not found. Install Python 3, then run this launcher again."
  read -r -p "Press Enter to exit."
fi
