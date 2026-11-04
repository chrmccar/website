#!/usr/bin/env python3
"""Package a local program + derived terrain update. Never read a private collection."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PROGRAM = ROOT / 'tools/photo-manager'
PILOT = ROOT / 'pilots/terrain'


def package(data, output):
    data = Path(data).resolve()
    manifest = json.loads((data / 'manifest.json').read_text())
    if manifest.get('kind') != 'list' or manifest.get('exaggeration') != 1:
        raise ValueError('Only real, true-scale LIST terrain may enter this update')
    files = [(PROGRAM / name, name) for name in
             ('photo_manager.py', 'alignment.py', 'editor.html', 'editor.js', 'editor.css',
              'START-WINDOWS.bat', 'START-MAC.command')]
    files += [(PILOT / name, 'terrain/' + name) for name in ('index.html', 'pilot.js', 'pilot.css', 'cc-by.jpg')]
    # Explicit list. Do not ship raw source, arbitrary local files or an image catalogue.
    files += [(data / name, 'terrain/data/' + name) for name in
              ('manifest.json', 'tilejson.json', 'coverage.geojson', 'nodata-mask.geojson')]
    for key, info in manifest['tiles'].items():
        if len(key.split('/')) != 3 or not all(x.isdigit() for x in key.split('/')):
            raise ValueError('Invalid tile path')
        source = data / 'tiles' / (key + '.png')
        if hashlib.sha256(source.read_bytes()).hexdigest() != info['sha256']:
            raise ValueError('Tile checksum mismatch')
        files.append((source, 'terrain/data/tiles/' + key + '.png'))
    # PNG is the supported local delivery. The separately measured PMTiles archive
    # is deliberately excluded: the Photo Manager does not need a range server.
    files.append((ROOT / 'docs/PHOTO-ALIGNMENT-START.txt', 'PHOTO-ALIGNMENT-START.txt'))
    output = Path(output);output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for source, name in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            archive.writestr(info, source.read_bytes())
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--output', default=str(ROOT / 'downloads/Photo-Manager-Terrain-Update.zip'))
    args = parser.parse_args()
    print(package(args.data, args.output))
