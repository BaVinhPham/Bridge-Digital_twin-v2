import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app import models

def glb(document=None):
    doc = document if document is not None else {'asset':{'version':'2.0'},'meshes':[{'primitives':[]}]}
    data = json.dumps(doc).encode();data += b' ' * (-len(data) % 4)
    return struct.pack('<4sIIII',b'glTF',2,20+len(data),len(data),0x4E4F534A)+data

class ModelsTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patch=patch.object(models,'STORE',Path(self.temp.name));self.patch.start()
        app=FastAPI();app.include_router(models.router);self.client=TestClient(app)
    def tearDown(self):
        self.client.close();self.patch.stop();self.temp.cleanup()
    def upload(self,data):
        return self.client.post('/models?name=Version%205',content=data,headers={'Content-Type':'model/gltf-binary'})
    def test_upload_download_and_versions(self):
        a=self.upload(glb());b=self.upload(glb());self.assertEqual(a.status_code,201)
        self.assertNotEqual(a.json()['id'],b.json()['id'])
        self.assertEqual(self.client.get(a.json()['url']).content,glb())
        ids=[r['id'] for r in self.client.get('/models').json()]
        self.assertIn(a.json()['id'],ids);self.assertIn(b.json()['id'],ids)
    def test_reject_invalid_and_external_assets(self):
        for data in [b'bad',glb()[:-1],glb({'asset':{'version':'2.0'},'meshes':[{}],'buffers':[{'uri':'https://example.com/a.bin'}]}),glb([])]:
            self.assertEqual(self.upload(data).status_code,422)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    def test_reject_oversize_and_wrong_type(self):
        with patch.object(models,'MAX_BYTES',16):self.assertEqual(self.upload(glb()).status_code,413)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
        self.assertEqual(self.client.post('/models?name=A',content=b'bad').status_code,415)
    def test_unpublished_and_invalid_ids(self):
        self.assertEqual(self.client.get('/models/not-a-model/file').status_code,404)
        self.assertEqual(self.client.get('/models/'+'0'*32+'/file').status_code,404)
    def test_real_bridge_asset(self):
        doc=models.inspect_glb(models.SEED/'binh-loi-v5.glb')
        self.assertTrue(doc['meshes'])
        self.assertTrue(doc['nodes'])

if __name__=='__main__':unittest.main(verbosity=2)
