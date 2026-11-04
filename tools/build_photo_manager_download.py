"""Build a reproducible public-only starter. Never read a private working folder."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/photo-manager'
SITE = ROOT / 'tasmania-through-time'
OUTPUT = ROOT / 'downloads/Tasmania-Photo-Manager.zip'
SOURCES = ('photo_manager.py', 'alignment.py', 'editor.html', 'editor.js', 'editor.css',
           'START-MAC.command', 'START-WINDOWS.bat', 'START-HERE.txt')

def build():
    data = json.loads((SITE / 'photos.json').read_text())
    places = json.loads((SITE/'places.json').read_text())['places']
    for place in places:
        location=place.get('location') or {}
        if not place.get('published') or not place.get('title') or type(place.get('year_start')) is not int:
            raise ValueError('Refusing to distribute draft or undated places')
        if not (-90<=location.get('lat',999)<=90 and -180<=location.get('lng',999)<=180):
            raise ValueError('Invalid public place location')
        if place.get('year_end') is not None and place['year_end']<place['year_start']:
            raise ValueError('Invalid public place dates')
    images = set()
    for photo in data['photos']:
        if not photo.get('published') or not photo.get('rights', {}).get('reviewed'):
            raise ValueError('Refusing to distribute unpublished or unreviewed records')
        for field in ('image', 'thumbnail'):
            name = photo[field]
            import re
            if not re.fullmatch(r'images/photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)', name):
                raise ValueError('Invalid public image path')
            images.add(name)
    files = [(SOURCE / name, name) for name in SOURCES]
    files += [(SITE / name, 'tasmania-through-time/' + name)
              for name in ('index.html', 'app.js', 'style.css', 'photos.json', 'places.json', *sorted(images))]
    OUTPUT.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(OUTPUT, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in files:
            info = zipfile.ZipInfo('Tasmania-Photo-Manager/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100755 if name.endswith('.command') else 0o100644) << 16
            archive.writestr(info, path.read_bytes())
    update = ROOT / 'downloads/Photo-Manager-Update.zip'
    with zipfile.ZipFile(update, 'w', zipfile.ZIP_DEFLATED) as archive:
        files = [(SOURCE/name, name) for name in ('photo_manager.py','alignment.py','editor.html','editor.js','editor.css','UPDATE-INSTRUCTIONS.txt')]
        files += [(SITE/name,'tasmania-through-time/'+name) for name in ('index.html','app.js','style.css')]
        for path,name in files:
            info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16;archive.writestr(info,path.read_bytes())
    return OUTPUT

if __name__ == '__main__':
    print(build())
