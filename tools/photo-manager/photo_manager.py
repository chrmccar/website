#!/usr/bin/env python3
"""Tasmania Through Time local photo manager. Python standard library only.
Run using START-MAC.command or START-WINDOWS.bat; binds exclusively to 127.0.0.1.
"""
from __future__ import annotations

import base64
import binascii
import json
import io
import zipfile
import mimetypes
import os
from pathlib import Path
import re
import shutil
import threading
import uuid
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, urlparse

BASE = Path(__file__).resolve().parent
SITE = BASE / 'tasmania-through-time'
CATALOGUE = BASE / 'LOCAL_COLLECTION.json'  # private; never upload
PUBLIC_CATALOGUE = SITE / 'photos.json'
PRIVATE_IMAGES = BASE / 'photo-assets'  # drafts stay private
IMAGES = SITE / 'images'
PORT = 8765
MAX_BODY = 27 * 1024 * 1024


def load_catalogue():
    if not CATALOGUE.is_file():
        return {'version': 1, 'photos': []}
    data = json.loads(CATALOGUE.read_text(encoding='utf-8'))
    if not isinstance(data.get('photos'), list):
        raise ValueError('Invalid catalogue structure')
    return data


def initialise_collection():
    """Seed a new private working folder from the bundled public collection only.

    Existing working catalogues are always left alone, including private drafts.
    The public starter download contains no private catalogue or source originals.
    """
    if CATALOGUE.exists():
        return
    data = json.loads(PUBLIC_CATALOGUE.read_text(encoding='utf-8'))
    paths = set()
    for photo in data['photos']:
        rights = photo.get('rights') or {}
        if not photo.get('published') or not rights.get('reviewed'):
            raise ValueError('The starter catalogue must contain only approved public photographs')
        for field in ('image', 'thumbnail'):
            name = photo.get(field, '')
            if not re.fullmatch(r'images/photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)', name):
                raise ValueError('Invalid starter photograph path')
            if not (SITE / name).is_file():
                raise ValueError('A starter photograph is missing; extract the entire ZIP first')
            paths.add(name)
    PRIVATE_IMAGES.mkdir(parents=True, exist_ok=True)
    for name in paths:
        target = PRIVATE_IMAGES / Path(name).name
        if not target.exists():
            shutil.copy2(SITE / name, target)
    atomic_catalogue(data)


def public_photos(data):
    live = []
    for photo in data['photos']:
        rights = photo.get('rights') or {}
        if not photo.get('published'):
            continue
        if not rights.get('reviewed') or rights.get('status') in ('', None, 'not_verified'):
            raise ValueError('Review the rights for every public photograph')
        if not (parse_point(photo.get('camera')) or parse_point(photo.get('subject'))):
            raise ValueError('Every public photograph needs a location')
        for field in ('image', 'thumbnail'):
            name = photo.get(field, '')
            if not re.fullmatch(r'images/photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)', name):
                raise ValueError('Invalid photograph image path')
            if not (PRIVATE_IMAGES / Path(name).name).is_file():
                raise ValueError('A photograph file is missing')
        live.append(photo)
    return live


def atomic_catalogue(data):
    # Validate before replacing either catalogue; drafts never enter the export.
    live = public_photos(data)
    IMAGES.mkdir(parents=True, exist_ok=True)
    permitted = set()
    for photo in live:
        for field in ('image', 'thumbnail'):
            name = Path(photo[field]).name
            permitted.add(name)
            shutil.copy2(PRIVATE_IMAGES / name, IMAGES / name)
    temp = CATALOGUE.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temp, CATALOGUE)
    public_tmp = PUBLIC_CATALOGUE.with_suffix('.json.tmp')
    public_tmp.write_text(json.dumps({'version': 1, 'photos': live}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(public_tmp, PUBLIC_CATALOGUE)
    for image in IMAGES.iterdir():
        if re.fullmatch(r'photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)', image.name) and image.name not in permitted:
            image.unlink()


def website_update():
    data = load_catalogue()
    live = public_photos(data)
    atomic_catalogue(data)
    # Explicit file list: never zip the private working directory.
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        # Photo uploads update data only, preserving improvements to the live map.
        for name in ('photos.json',):
            archive.write(SITE / name, 'tasmania-through-time/' + name)
        names = {p[field] for p in live for field in ('image', 'thumbnail')}
        for name in sorted(names):
            archive.write(SITE / name, 'tasmania-through-time/' + name)
    return output.getvalue()


def clean(value, maxlen=1000):
    return str(value or '').strip()[:maxlen]


def optional_year(value):
    if value in (None, ''):
        return None
    year = int(value)
    if not (1500 <= year <= 2200):
        raise ValueError('Year must be between 1500 and 2200')
    return year


def optional_float(value, min_value, max_value):
    if value in (None, ''):
        return None
    n = float(value)
    if not min_value <= n <= max_value:
        raise ValueError(f'Value must be between {min_value} and {max_value}')
    return n


def parse_point(raw, *, bearing=False):
    if not isinstance(raw, dict) or not raw:
        return None
    lat = optional_float(raw.get('lat'), -90, 90)
    lng = optional_float(raw.get('lng'), -180, 180)
    if lat is None and lng is None:
        return None
    if lat is None or lng is None:
        raise ValueError('Both latitude and longitude are required')
    point = {'lat': lat, 'lng': lng}
    if bearing:
        b = optional_float(raw.get('bearing'), 0, 360)
        if b is not None:
            point['bearing'] = round(b % 360, 2)
    return point


def image_from_data(raw, photo_id, suffix):
    if not raw:
        return None
    if not isinstance(raw, str) or not raw.startswith('data:image/'):
        raise ValueError('Unsupported image format')
    match = re.fullmatch(r'data:image/(webp|jpeg);base64,([A-Za-z0-9+/=]+)', raw)
    if not match:
        raise ValueError('Images must be JPEG or WebP')
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError):
        raise ValueError('Invalid image encoding')
    if len(content) > 12 * 1024 * 1024:
        raise ValueError('Image is too large (max 12 MB)')
    if match.group(1) == 'webp' and not content.startswith(b'RIFF'):
        raise ValueError('Invalid WebP image')
    if match.group(1) == 'jpeg' and not content.startswith(b'\xff\xd8'):
        raise ValueError('Invalid JPEG image')
    ext = 'webp' if match.group(1) == 'webp' else 'jpg'
    filename = f'{photo_id}{suffix}.{ext}'
    output = PRIVATE_IMAGES / filename
    output.write_bytes(content)
    return f'images/{filename}'


def save_photo(obj):
    data = load_catalogue()
    items = data['photos']
    incoming_id = clean(obj.get('id'), 120)
    existing = next((p for p in items if p.get('id') == incoming_id), None) if incoming_id else None
    photo_id = incoming_id if existing else f'photo-{uuid.uuid4().hex[:14]}'
    title = clean(obj.get('title'), 180)
    if not title:
        raise ValueError('A photograph title is required')
    years = (optional_year(obj.get('year_start')), optional_year(obj.get('year_end')))
    if years[0] is None and years[1] is not None:
        years = (years[1], years[1])
    if years[0] is not None and years[1] is None:
        years = (years[0], years[0])
    if years[0] is not None and years[1] < years[0]:
        raise ValueError('End year cannot be earlier than start year')
    camera = parse_point(obj.get('camera'), bearing=True)
    subject = parse_point(obj.get('subject'))
    image_type = clean(obj.get('image_type'), 40)
    if image_type not in ('ground', 'oblique_aerial', 'vertical_aerial'):
        image_type = 'ground'
    accuracy = clean(obj.get('location_accuracy'), 40)
    if accuracy not in ('known', 'estimated'):
        accuracy = 'estimated'
    rights_raw = obj.get('rights') or {}
    rights = {
        'creator': clean(rights_raw.get('creator'), 200),
        'source': clean(rights_raw.get('source'), 200),
        'source_url': clean(rights_raw.get('source_url'), 500),
        'archive_id': clean(rights_raw.get('archive_id'), 160),
        'status': clean(rights_raw.get('status'), 70),
        'licence_url': clean(rights_raw.get('licence_url'), 500),
        'statement': clean(rights_raw.get('statement'), 1500),
        'notes': clean(rights_raw.get('notes'), 1000),
        'reviewed': bool(rights_raw.get('reviewed')),
    }
    requested_publish = bool(obj.get('published'))
    if requested_publish and not rights['reviewed']:
        raise ValueError('Check the image rights before publishing')
    if requested_publish and rights['status'] in ('', 'not_verified'):
        raise ValueError('Choose a verified rights status before publishing')
    if requested_publish and not (camera or subject):
        raise ValueError('Place the camera or the subject on the map before publishing')
    image = existing.get('image') if existing else None
    thumbnail = existing.get('thumbnail') if existing else None
    incoming_image = obj.get('image_data')
    incoming_thumb = obj.get('thumb_data')
    if incoming_image:
        if not incoming_thumb:
            raise ValueError('Thumbnail is missing')
        image = image_from_data(incoming_image, photo_id, '')
        thumbnail = image_from_data(incoming_thumb, photo_id, '-thumb')
    if not image:
        raise ValueError('Select a photograph to save')
    photo = {
        'id': photo_id,
        'title': title,
        'description': clean(obj.get('description'), 2500),
        'place': clean(obj.get('place'), 150),
        'date_display': clean(obj.get('date_display'), 120),
        'year_start': years[0], 'year_end': years[1],
        'image_type': image_type,
        'image': image, 'thumbnail': thumbnail or image,
        'camera': camera, 'subject': subject,
        'location_accuracy': accuracy,
        'rights': rights,
        'published': requested_publish,
    }
    if existing:
        items[items.index(existing)] = photo
    else:
        items.append(photo)
    atomic_catalogue(data)
    return photo


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def log_message(self, fmt, *args):
        if not self.path.startswith('/api/'):
            super().log_message(fmt, *args)

    def respond(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/':
            self.send_response(302)
            self.send_header('Location', '/editor.html')
            self.end_headers()
            return
        if path == '/api/export':
            try:
                body = website_update()
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', 'attachment; filename="website-update.zip"')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            except (ValueError, OSError) as exc:
                self.respond(400, {'error': str(exc)})
            return
        if path == '/api/photos':
            try:
                self.respond(200, load_catalogue())
            except Exception as exc:
                self.respond(500, {'error': str(exc)})
            return
        if path == '/preview':
            self.send_response(302)
            self.send_header('Location', '/tasmania-through-time/')
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ('/api/save', '/api/delete'):
            return self.respond(404, {'error':'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= MAX_BODY:
                return self.respond(413, {'error':'Upload too large'})
            obj = json.loads(self.rfile.read(length))
            if not isinstance(obj,dict):
                raise ValueError('Invalid submission')
            if path == '/api/save':
                result=save_photo(obj)
                return self.respond(200, {'ok':True,'photo':result})
            photo_id=clean(obj.get('id'),120)
            data=load_catalogue()
            existing=next((p for p in data['photos'] if p['id']==photo_id),None)
            if existing is None:
                return self.respond(404, {'error':'Photograph not found'})
            data['photos'].remove(existing)
            atomic_catalogue(data)
            # Remove generated files only, never arbitrary external paths.
            for field in ('image','thumbnail'):
                filename=existing.get(field,'')
                if re.fullmatch(r'images/photo-[0-9a-f]{14}(?:-thumb)?\.(?:webp|jpg)', filename):
                    (PRIVATE_IMAGES / Path(filename).name).unlink(missing_ok=True)
            return self.respond(200, {'ok':True})
        except (ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
            return self.respond(400, {'error':str(exc)})
        except Exception as exc:
            return self.respond(500, {'error':f'Unable to save: {exc}'})


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    PRIVATE_IMAGES.mkdir(parents=True, exist_ok=True)
    try:
        initialise_collection()
    except (OSError, ValueError, KeyError) as exc:
        print(f'Unable to open the collection: {exc}\nExtract the entire download before starting the manager.')
        return
    try:
        server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    except OSError as exc:
        print(f'Unable to start on port {PORT}: {exc}\nClose any other Photo Manager window and retry.')
        return
    url=f'http://127.0.0.1:{PORT}/editor.html'
    print('\n' + '='*56)
    print(' TASMANIA THROUGH TIME — PHOTO MANAGER')
    print('='*56)
    print(f'Opening {url}')
    print('Your entries are saved automatically to the site folder.')
    print('Keep this window open while editing. Ctrl+C stops it.')
    print('='*56 + '\n')
    if os.environ.get('PHOTO_MANAGER_NO_BROWSER') != '1':
        threading.Timer(0.65, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nPhoto Manager stopped. All saved photographs remain on disk.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
