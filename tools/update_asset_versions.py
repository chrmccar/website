"""Refresh content-based asset URLs after changing map or editor JavaScript/CSS."""
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
for directory, document, names in (
    (ROOT/'tasmania-through-time', 'index.html', ('app.js', 'style.css')),
    (ROOT/'tools/photo-manager', 'editor.html', ('editor.js', 'editor.css')),
):
    html = (directory/document).read_text()
    for name in names:
        version = hashlib.sha256((directory/name).read_bytes()).hexdigest()[:12]
        html = re.sub(r'\./' + re.escape(name) + r'(?:\?v=[a-zA-Z0-9_-]+)?',
                      f'./{name}?v={version}', html)
    (directory/document).write_text(html)
