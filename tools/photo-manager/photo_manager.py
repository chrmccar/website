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
import importlib.util

# Load beside this program, including when a test imports it by absolute path.
_alignment_spec = importlib.util.spec_from_file_location('photo_manager_alignment', Path(__file__).with_name('alignment.py'))
alignment = importlib.util.module_from_spec(_alignment_spec)
_alignment_spec.loader.exec_module(alignment)

BASE = Path(__file__).resolve().parent
SITE = BASE / 'tasmania-through-time'
CATALOGUE = BASE / 'LOCAL_COLLECTION.json'  # private; never upload
PUBLIC_CATALOGUE = SITE / 'photos.json'
PUBLIC_PLACES = SITE / 'places.json'
PRIVATE_IMAGES = BASE / 'photo-assets'  # drafts stay private
IMAGES = SITE / 'images'
PORT = 8765
MAX_BODY = 27 * 1024 * 1024
MUTATION_LOCK = threading.RLock()


def load_catalogue():
    if not CATALOGUE.is_file():
        return {'version': 1, 'photos': []}
    data = json.loads(CATALOGUE.read_text(encoding='utf-8'))
    if not isinstance(data.get('photos'), list):
        raise ValueError('Invalid catalogue structure')
    if not isinstance(data.get('places', []), list):
        raise ValueError('Invalid places structure')
    return data


def initialise_collection():
    """Seed a new private working folder from the bundled public collection only.

    Existing working catalogues are always left alone, including private drafts.
    The public starter download contains no private catalogue or source originals.
    """
    if CATALOGUE.exists():
        return
    data = json.loads(PUBLIC_CATALOGUE.read_text(encoding='utf-8'))
    if PUBLIC_PLACES.is_file():
        places = json.loads(PUBLIC_PLACES.read_text(encoding='utf-8')).get('places', [])
        if places:
            data['places'] = places
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
    for photo in data['photos']:
        alignment.import_public_pose(photo, BASE)
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
        public = dict(photo)
        public.pop('alignment', None)
        # A draft is private even when the photograph itself is already public.
        public.pop('camera_pose', None)
        approved_pose = alignment.public_pose(photo, BASE)
        if approved_pose:
            public['camera_pose'] = approved_pose
        live.append(public)
    return live


def atomic_catalogue(data):
    # Validate before replacing either catalogue; drafts never enter the export.
    live = public_photos(data)
    places = public_places(data)
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
    places_tmp = PUBLIC_PLACES.with_suffix('.json.tmp')
    places_tmp.write_text(json.dumps({'version': 1, 'places': places}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(places_tmp, PUBLIC_PLACES)
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
        for name in ('photos.json', 'places.json'):
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
    photo = dict(existing or {})
    photo.update({
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
    })
    # Invalidate any alignment window that opened before this photo edit, even
    # when it had not saved its first draft yet (for example, an image replacement).
    photo['alignment'] = dict(photo.get('alignment') or {})
    photo['alignment']['revision'] = uuid.uuid4().hex
    if existing:
        items[items.index(existing)] = photo
    else:
        items.append(photo)
    atomic_catalogue(data)
    return photo


def clean_place(obj, place_id):
    title = clean(obj.get('title'), 180)
    if not title:
        raise ValueError('A place name is required')
    start = optional_year(obj.get('year_start'))
    end = optional_year(obj.get('year_end'))
    if start is not None and end is not None and end < start:
        raise ValueError('The last year present cannot be before the first year')
    location = parse_point(obj.get('location'))
    published = bool(obj.get('published'))
    if published and (location is None or start is None):
        raise ValueError('A public place needs a location and its first year of existence')
    return {'id': place_id, 'title': title, 'description': clean(obj.get('description'), 2500),
            'location': location, 'year_start': start, 'year_end': end,
            'source_url': clean(obj.get('source_url'), 500), 'published': published}


def public_places(data):
    return [clean_place(p, p['id']) for p in data.get('places', []) if p.get('published')]


def save_place(obj):
    data = load_catalogue()
    items = data.setdefault('places', [])
    existing = next((p for p in items if p.get('id') == obj.get('id')), None)
    place_id = existing['id'] if existing else f'place-{uuid.uuid4().hex[:14]}'
    place = clean_place(obj, place_id)
    if existing:
        items[items.index(existing)] = place
    else:
        items.append(place)
    atomic_catalogue(data)
    return place


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE), **kwargs)

    def end_headers(self):
        path=urlparse(self.path).path
        if path.endswith(('.html', '.js', '.css', '/')):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

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
                with MUTATION_LOCK:
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
            self.send_header('Location', f'/tasmania-through-time/?session={uuid.uuid4().hex[:12]}')
            self.end_headers()
            return
        # Program updates can preserve ZIP timestamps: never return stale HTML/JS.
        if path.endswith(('.html', '.js', '.css', '/')) and 'If-Modified-Since' in self.headers:
            del self.headers['If-Modified-Since']
        super().do_GET()

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.respond(403, {'error': 'Save from the local Photo Manager window only'})
        with MUTATION_LOCK:
            return self._post()

    def _post(self):
        path = urlparse(self.path).path
        if path not in ('/api/save', '/api/delete', '/api/place/save', '/api/place/delete', '/api/alignment'):
            return self.respond(404, {'error':'Not found'})
        try:
            length = int(self.headers.get('Content-Length', '-1'))
            if not 0 <= length <= MAX_BODY:
                return self.respond(413, {'error':'Upload too large'})
            obj = json.loads(self.rfile.read(length))
            if not isinstance(obj,dict):
                raise ValueError('Invalid submission')
            if path == '/api/alignment':
                data = load_catalogue()
                photo = alignment.update(data, obj, BASE, obj.get('action'))
                # Lossless private snapshot before changing alignment metadata.
                backups = BASE / 'alignment-backups'
                backups.mkdir(exist_ok=True)
                shutil.copy2(CATALOGUE, backups / f'{uuid.uuid4().hex}.json')
                atomic_catalogue(data)
                return self.respond(200, {'ok': True, 'photo': photo})
            if path == '/api/place/save':
                return self.respond(200, {'ok': True, 'place': save_place(obj)})
            if path == '/api/place/delete':
                data = load_catalogue()
                items = data.get('places', [])
                existing = next((p for p in items if p['id'] == obj.get('id')), None)
                if existing is None:
                    return self.respond(404, {'error': 'Place not found'})
                items.remove(existing)
                atomic_catalogue(data)
                return self.respond(200, {'ok': True})
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
    url=f'http://127.0.0.1:{PORT}/editor.html?session={uuid.uuid4().hex[:12]}'
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
