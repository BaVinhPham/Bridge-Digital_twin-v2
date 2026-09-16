"""Local prototype model registry. Deploy behind authentication before public use."""
import hashlib
import json
import os
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

router = APIRouter()
STORE = Path(os.getenv('MODEL_STORE', str(Path(__file__).parent.parent / 'data/models')))
SEED = Path(__file__).parent / 'static/models'
MAX_BYTES = 100 * 1024 * 1024


def inspect_glb(path):
    size = path.stat().st_size
    with path.open('rb') as stream:
        header = stream.read(20)
        if len(header) != 20:
            raise ValueError('Incomplete GLB header')
        magic, version, total, length, chunk = struct.unpack('<4sIIII', header)
        if magic != b'glTF' or version != 2 or total != size or chunk != 0x4E4F534A:
            raise ValueError('Expected a complete GLB 2.0 file')
        if length > min(size - 20, 16 * 1024 * 1024) or length % 4:
            raise ValueError('Invalid GLB JSON chunk')
        document = json.loads(stream.read(length))
        if document.get('asset', {}).get('version') != '2.0':
            raise ValueError('Expected glTF 2.0 asset')
        if not document.get('meshes'):
            raise ValueError('Model contains no meshes')
        # Uploaded models must be self-contained; never fetch arbitrary URLs from assets.
        for group in ('buffers', 'images'):
            if any('uri' in item for item in document.get(group, [])):
                raise ValueError('Use a self-contained GLB with embedded buffers and textures')
        while stream.tell() < size:
            raw = stream.read(8)
            if len(raw) != 8:
                raise ValueError('Truncated GLB chunk')
            count, kind = struct.unpack('<II', raw)
            if count % 4 or stream.tell() + count > size:
                raise ValueError('Invalid GLB binary chunk')
            stream.seek(count, 1)
    return document


@router.get('/models')
def list_models():
    records = []
    for folder in (SEED, STORE):
        for path in sorted(folder.glob('*.json'), reverse=True):
            item = json.loads(path.read_text(encoding='utf-8'))
            item.pop('elements', None)
            records.append(item)
    return records


@router.get('/models/{model_id}/file')
def model_file(model_id: str):
    if len(model_id) != 32 or any(c not in '0123456789abcdef' for c in model_id):
        raise HTTPException(404, 'Model not found')
    path = STORE / (model_id + '.glb')
    if not path.exists() or not path.with_suffix('.json').exists():
        raise HTTPException(404, 'Model not found')
    return FileResponse(path, media_type='model/gltf-binary')


@router.post('/models', status_code=201)
async def upload_model(request: Request, name: str = Query(min_length=1, max_length=120)):
    if request.headers.get('content-type', '').split(';')[0] not in ('model/gltf-binary', 'application/octet-stream'):
        raise HTTPException(415, 'Upload a GLB file')
    STORE.mkdir(parents=True, exist_ok=True)
    model_id = uuid.uuid4().hex
    temp = STORE / (model_id + '.part')
    final = STORE / (model_id + '.glb')
    digest = hashlib.sha256()
    size = 0
    published = False
    try:
        with temp.open('wb') as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'Maximum model size is 100 MB')
                stream.write(chunk)
                digest.update(chunk)
        try:
            doc = inspect_glb(temp)
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        record = {'id':model_id, 'name':name.strip(), 'status':'preliminary',
                  'url':f'/models/{model_id}/file', 'bytes':size,
                  'created_at':datetime.now(timezone.utc).isoformat(),
                  'sha256':digest.hexdigest(), 'mesh_count':len(doc['meshes']),
                  'notes':'User GLB upload. Dimensions and element identifiers have not been verified. Sensor positions are not mapped.'}
        temp.replace(final)
        metadata = STORE / (model_id + '.json.part')
        metadata.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        metadata.replace(STORE / (model_id + '.json'))
        published = True
        return record
    finally:
        temp.unlink(missing_ok=True)
        if not published:
            final.unlink(missing_ok=True)
            (STORE / (model_id + '.json.part')).unlink(missing_ok=True)
