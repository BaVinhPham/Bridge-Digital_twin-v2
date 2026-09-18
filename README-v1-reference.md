# Bridge Digital Twin Data Platform — Prototype v1

This first prototype implements:

Simulated Sensors → MQTT → Ingestion → PostgreSQL/TimescaleDB → FastAPI

## 1. Requirements
- Docker Desktop

## 2. Start the platform
From this folder:

```bash
docker compose up --build
```

Wait until the API, MQTT broker, and database are running.

The compose stack includes a restartable simulator, which publishes data every
two seconds for:
- ACC_01
- SG_01
- TEMP_01
- DISP_01

## 3. Test the API
Open:

- http://localhost:8000/
- http://localhost:8000/docs
- http://localhost:8000/sensors
- http://localhost:8000/sensors/ACC_01/latest
- http://localhost:8000/sensors/ACC_01/history?limit=20

## Architecture

```text
Simulated Sensors
      ↓
     MQTT
      ↓
Python ingestion subscriber
      ↓
PostgreSQL + TimescaleDB
      ↓
FastAPI
      ↓
Dashboard / Digital Twin (next stage)
```

## What this version teaches
1. Sensor data generation
2. MQTT publishing
3. Data ingestion
4. Time-series storage
5. API access

## Imported bridge model (Version 4)

Open **http://localhost:8000/model** for the imported bridge, or the sensor
dashboard to see it alongside simulated readings. The viewer includes orbit,
zoom, pan, object inspection, site visibility, and two-point measurement.
Colours are presentation colours, not verified Revit material appearances.

The included 15.5 MB GLB was converted from
`output/revit/Binh Loi Bridge _final version.fbx` using Blender 5.2.
It contains 215 mesh objects. The FBX timestamp precedes the latest Version 4
RVT save by six minutes, so changes after that export are not represented.
The RVT and FBX originals are unchanged. Conversion provenance and element names
are recorded in `app/static/models/binh-loi-v5.json`.

To regenerate the browser asset from that FBX:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python output/revit/convert_fbx.py
docker compose up -d --build
```

To add later versions, use **Add a model version** in the model workspace.
It accepts a self-contained GLB up to 100 MB, preserves previous versions, and
stores uploads in the persistent `model_data` Docker volume. `GET /models`
lists versions; `POST /models?name=...` accepts the raw GLB body with
`Content-Type: model/gltf-binary`. This is a local prototype without user
authentication; add access control before making it publicly accessible.

Export names are retained for inspection, but are not verified persistent Revit
UniqueIds. Sensor positions and object-to-sensor links are deliberately not
assigned. Confirm these before connecting measurements to specific components.
GLB distances are in metres; verify known dimensions against structural drawings.
This version follows the available **RVT → FBX → GLB** path, not IFC property
transfer. An IFC/UniqueId workflow is still needed for full BIM metadata.

Viewer dependencies are pinned to Three.js 0.180.0 and served locally with its
MIT license in `app/static/vendor/three/LICENSE`; no external CDN is required.

Model API tests (requires `httpx` in the test environment):

```bash
python -m unittest discover -s tests -p test_models.py -v
```

## Next version
- validation rules
- processed results table
- RMS / peak / FFT processing
- alert rules
- dashboard
- mapping sensors to BIM/FEM bridge components

## Live dashboard demo

Readiness is available at http://localhost:8000/health. It checks database access
and the MQTT subscription, not sensor freshness. Docker waits for readiness before
starting the demo simulator. Database interruptions return HTTP 503 to data requests.

Start the platform with continuous simulated readings (this is also the default
when deploying with `docker compose up`):

```bash
docker compose up -d --build
```

Open http://localhost:8000/dashboard. The four sensor cards refresh every two
seconds. Choose 20–200 readings per chart or pause/resume the display. Statistics
cover the displayed samples. Data is simulated, not a bridge safety assessment.

The bridge schematic maps the four sensors to approximate component locations.
Select a numbered marker or a named sensor button to see its current reading and
highlight its card. The chart link jumps to that sensor's history. These controls
also work with the keyboard. The schematic is illustrative; actual geometry and
surveyed sensor positions are needed before connecting a real 3D bridge model.

The dashboard now uses a dark control-room layout. Its bridge workspace is an
interactive 3D-style drawing: drag to rotate and use the mouse wheel to zoom.
It is an illustrative browser model, not an imported Revit or certified
engineering model. A Revit export plus surveyed coordinates are needed before
using an accurate 3D twin.

Stop only the simulator (the dashboard remains available):

```bash
docker compose stop simulator
```

After ten seconds without a fresh reading, cards show “No recent data”. Restart
with `docker compose start simulator`. Stop all services with
`docker compose stop`; stored measurements remain in the database.
