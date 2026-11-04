"""Private alignment drafts. Old camera/subject coordinates are never changed here."""
import copy
import hashlib
import json
import math
from pathlib import Path
import uuid
import re
from datetime import datetime, timezone


def number(value, lower, upper):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
        raise ValueError('Invalid alignment number')
    return value


def image_hash(base, photo):
    name = Path(photo['image']).name
    return hashlib.sha256((base / 'photo-assets' / name).read_bytes()).hexdigest()


def terrain_record(base):
    path = base / 'terrain/data/manifest.json'
    raw = path.read_bytes()
    manifest = json.loads(raw)
    if manifest.get('kind') != 'list' or manifest.get('encoding') != 'terrarium' or manifest.get('exaggeration') != 1:
        raise ValueError('A real LIST terrain pack is required to save an alignment')
    return manifest, hashlib.sha256(raw).hexdigest()


def pose(raw):
    if not isinstance(raw, dict):
        raise ValueError('Missing camera pose')
    return {'version': 1,
            'lat': number(raw.get('lat'), -85, 85), 'lng': number(raw.get('lng'), -180, 180),
            'elevation_m': number(raw.get('elevation_m'), -1000, 10000),
            'bearing': number(raw.get('bearing'), 0, 360) % 360,
            'pitch': number(raw.get('pitch'), 0, 89.9),
            'vertical_fov': number(raw.get('vertical_fov'), 10, 100)}


def public_pose(photo, base):
    """No notes, drafts, original positions or undo history may leave the manager."""
    state = photo.get('alignment') or {}
    accepted = state.get('accepted')
    if not accepted or accepted.get('image_sha256') != image_hash(base, photo):
        return None
    result = pose(accepted['pose'])
    result.update({k: accepted[k] for k in ('terrain_id', 'vertical_datum', 'confidence')})
    result['method'] = 'manual-terrain-alignment'
    return result


def import_public_pose(photo, base):
    """Retain an already approved pose when seeding from a public-only starter."""
    raw = photo.get('camera_pose')
    if not raw or photo.get('alignment'):
        return
    candidate = pose(raw)
    if not re.fullmatch(r'[0-9a-f]{64}', str(raw.get('terrain_id', ''))) or raw.get('confidence') not in ('low', 'medium', 'high'):
        raise ValueError('Invalid approved camera pose in starter collection')
    datum = raw.get('vertical_datum')
    if not isinstance(datum, str) or not 1 <= len(datum) <= 500:
        raise ValueError('Missing height datum in approved camera pose')
    accepted = {'pose': candidate, 'terrain_id': raw['terrain_id'], 'vertical_datum': datum,
                'confidence': raw['confidence'], 'image_sha256': image_hash(base, photo),
                'notes': '', 'opacity': 50, 'saved_at': 'imported-already-public'}
    photo['alignment'] = {'draft': copy.deepcopy(accepted), 'accepted': accepted,
                          'revision': uuid.uuid4().hex,
                          'original_camera': copy.deepcopy(photo.get('camera')),
                          'original_subject': copy.deepcopy(photo.get('subject'))}


def update(data, obj, base, action):
    photo = next((p for p in data['photos'] if p['id'] == obj.get('id')), None)
    if photo is None:
        raise ValueError('Save the photograph in Photo Manager first')
    state = copy.deepcopy(photo.get('alignment') or {})
    if obj.get('revision') != state.get('revision'):
        raise ValueError('This photograph changed in another window. Reload it before saving.')
    state.setdefault('original_camera', copy.deepcopy(photo.get('camera')))
    state.setdefault('original_subject', copy.deepcopy(photo.get('subject')))
    if action == 'save':
        manifest, terrain_id = terrain_record(base)
        candidate = pose(obj.get('pose'))
        z = manifest['maxzoom']; n = 2 ** z
        x = math.floor((candidate['lng'] + 180) / 360 * n)
        y = math.floor((1 - math.asinh(math.tan(math.radians(candidate['lat']))) / math.pi) / 2 * n)
        if f'{z}/{x}/{y}' not in manifest['tiles']:
            raise ValueError('The camera is outside this terrain pack')
        confidence = obj.get('confidence')
        if confidence not in ('low', 'medium', 'high'):
            raise ValueError('Choose an alignment confidence')
        previous = state.get('draft')
        if previous:
            state['history'] = (state.get('history', []) + [previous])[-30:]
        state['draft'] = {'pose': candidate, 'terrain_id': terrain_id,
                          'vertical_datum': manifest['vertical_datum'], 'confidence': confidence,
                          'notes': str(obj.get('notes') or '')[:4000],
                          'opacity': number(obj.get('opacity'), 0, 100),
                          'image_sha256': image_hash(base, photo),
                          'saved_at': datetime.now(timezone.utc).isoformat()}
    elif action == 'accept':
        if not state.get('draft'):
            raise ValueError('Save an alignment draft first')
        if state['draft']['image_sha256'] != image_hash(base, photo):
            raise ValueError('The image changed. Align and save a new draft first.')
        _, terrain_id = terrain_record(base)
        if state['draft']['terrain_id'] != terrain_id:
            raise ValueError('The terrain changed. Check and save the alignment again.')
        if not photo.get('rights', {}).get('reviewed') or photo.get('rights', {}).get('status') in ('', None, 'not_verified'):
            raise ValueError('Review this photograph’s rights in Photo Manager first')
        state['accepted'] = copy.deepcopy(state['draft'])
    elif action == 'withdraw':
        state.pop('accepted', None)
    elif action == 'undo':
        history = state.get('history') or []
        if not history:
            raise ValueError('There is no earlier saved draft')
        state['draft'] = history.pop()
        state['history'] = history
    else:
        raise ValueError('Unknown alignment action')
    state['revision'] = uuid.uuid4().hex
    photo['alignment'] = state
    return photo
