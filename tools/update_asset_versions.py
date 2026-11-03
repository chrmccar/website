"""Refresh content-based asset URLs after changing the map's JavaScript or CSS."""
import hashlib
from pathlib import Path
import re

SITE = Path(__file__).resolve().parents[1] / 'tasmania-through-time'
html = (SITE / 'index.html').read_text()
for name in ('app.js', 'style.css'):
    version = hashlib.sha256((SITE / name).read_bytes()).hexdigest()[:12]
    html = re.sub(r'\./' + re.escape(name) + r'(?:\?v=[a-zA-Z0-9_-]+)?',
                  f'./{name}?v={version}', html)
(SITE / 'index.html').write_text(html)
