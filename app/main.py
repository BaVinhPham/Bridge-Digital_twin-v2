import json
import math
import os
import queue
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import psycopg2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from app.models import router as models_router

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://bridge:bridgepass@localhost:5432/bridge")
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

app = FastAPI(title="Bridge Digital Twin Data Platform", version="0.1.0")
app.include_router(models_router)
app.mount("/static", StaticFiles(directory=Path(__file__).with_name("static")), name="static")
mqtt_ready = threading.Event()
measurement_queue = queue.Queue()


@app.exception_handler(psycopg2.OperationalError)
async def database_unavailable(request, exc):
    return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})


@app.get("/health")
def health():
    database_ok = False
    try:
        with get_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT sensor_id FROM sensors LIMIT 1")
                database_ok = True
    except psycopg2.Error:
        pass
    ready = database_ok and mqtt_ready.is_set()
    return JSONResponse(status_code=200 if ready else 503, content={
        "status": "ready" if ready else "unavailable",
        "database": database_ok, "mqtt": mqtt_ready.is_set(),
    })


def get_conn():
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def measurement_row(payload: dict):
    required = {"sensor_id", "timestamp", "value"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise ValueError("sensor_id, timestamp and value are required")
    if not isinstance(payload["sensor_id"], str) or not payload["sensor_id"].strip():
        raise ValueError("sensor_id must be a non-empty string")
    if isinstance(payload["value"], bool):
        raise ValueError("value must be a finite number")
    value = float(payload["value"])
    if not math.isfinite(value):
        raise ValueError("value must be a finite number")

    ts = payload["timestamp"]
    if not isinstance(ts, str):
        raise ValueError("timestamp must be an ISO date-time string")
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return (dt, payload["sensor_id"], value, payload.get("quality", "GOOD"))


def store_measurements(rows):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO measurements(time, sensor_id, value, quality)
                VALUES (%s, %s, %s, %s)
                """,
                rows,
            )


def measurement_writer():
    """Persist MQTT readings in batches so a large sensor set cannot block the listener."""
    while True:
        first_row = measurement_queue.get()
        rows = [first_row]
        while len(rows) < 500:
            try:
                rows.append(measurement_queue.get_nowait())
            except queue.Empty:
                break
        try:
            store_measurements(rows)
        except Exception as exc:
            print("Measurement batch rejected:", exc)


def on_connect(client, userdata, flags, reason_code, properties=None):
    mqtt_ready.clear()
    if not reason_code.is_failure:
        client.subscribe("bridge/sensors/+/data")


def on_subscribe(client, userdata, mid, reason_codes, properties=None):
    if reason_codes and all(not code.is_failure for code in reason_codes):
        mqtt_ready.set()


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    mqtt_ready.clear()


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("sensor_id") != msg.topic.split("/")[2]:
            raise ValueError("sensor_id must match the MQTT topic")
        measurement_queue.put(measurement_row(payload))
    except Exception as exc:
        print("Message rejected:", exc)


def mqtt_worker():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, 60)
    client.loop_forever(retry_first_connection=True)


@app.on_event("startup")
def start_mqtt_listener():
    threading.Thread(target=measurement_writer, daemon=True).start()
    threading.Thread(target=mqtt_worker, daemon=True).start()


@app.get("/")
def root():
    return {"platform": "Bridge Digital Twin Data Platform", "status": "running"}


@app.get("/sensors")
def list_sensors():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT sensor_id, sensor_type, location, unit FROM sensors ORDER BY sensor_id")
            rows = cur.fetchall()
    return [
        {"sensor_id": r[0], "sensor_type": r[1], "location": r[2], "unit": r[3]}
        for r in rows
    ]


@app.get("/sensors/summary")
def sensor_summary():
    """Latest reading for every registered sensor in one dashboard-friendly query."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.sensor_id, s.sensor_type, s.location, s.unit,
                       m.time, m.value, m.quality
                FROM sensors s
                LEFT JOIN LATERAL (
                    SELECT time, value, quality
                    FROM measurements
                    WHERE sensor_id = s.sensor_id
                    ORDER BY time DESC
                    LIMIT 1
                ) m ON TRUE
                ORDER BY s.sensor_id
                """
            )
            rows = cur.fetchall()
    return [
        {
            "sensor_id": row[0], "sensor_type": row[1],
            "location": row[2], "unit": row[3],
            "timestamp": row[4].isoformat() if row[4] else None,
            "value": row[5], "quality": row[6],
        }
        for row in rows
    ]


@app.get("/sensors/{sensor_id}/latest")
def latest(sensor_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.time, m.sensor_id, m.value, s.unit, m.quality
                FROM measurements m
                JOIN sensors s ON s.sensor_id = m.sensor_id
                WHERE m.sensor_id = %s
                ORDER BY m.time DESC
                LIMIT 1
                """,
                (sensor_id,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No measurement found")
    return {
        "timestamp": row[0].isoformat(),
        "sensor_id": row[1],
        "value": row[2],
        "unit": row[3],
        "quality": row[4],
    }


@app.get("/sensors/{sensor_id}/history")
def history(sensor_id: str, limit: int = Query(20, ge=1, le=1000), minutes: int | None = Query(None, ge=1, le=10080)):

    with get_conn() as conn:
        with conn.cursor() as cur:

            if minutes is None:
                cur.execute(
                    """
                    SELECT time, value, quality
                    FROM measurements
                    WHERE sensor_id = %s
                    ORDER BY time DESC
                    LIMIT %s
                    """,
                    (sensor_id, limit),
                )

            else:
                cur.execute(
                    """
                    SELECT time, value, quality
                    FROM measurements
                    WHERE sensor_id = %s
                    AND time >= NOW() - (%s * INTERVAL '1 minute')
                    ORDER BY time DESC
                    LIMIT %s
                    """,
                    (sensor_id, minutes, limit),
                )

            rows = cur.fetchall()

    return [
        {
            "timestamp": row[0],
            "value": row[1],
            "quality": row[2]
        }
        for row in rows
    ]
@app.get("/sensors/{sensor_id}/stats")
def stats(sensor_id: str, minutes: int | None = Query(None, ge=1, le=10080)):

    with get_conn() as conn:
        with conn.cursor() as cur:

            if minutes is None:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        AVG(value),
                        MIN(value),
                        MAX(value),
                        SQRT(AVG(value * value))
                    FROM measurements
                    WHERE sensor_id = %s
                    """,
                    (sensor_id,),
                )

            else:
                cur.execute(
                    """
                    SELECT
                        COUNT(*),
                        AVG(value),
                        MIN(value),
                        MAX(value),
                        SQRT(AVG(value * value))
                    FROM measurements
                    WHERE sensor_id = %s
                    AND time >= NOW() - (%s * INTERVAL '1 minute')
                    """,
                    (sensor_id, minutes),
                )

            row = cur.fetchone()

    return {
        "sensor_id": sensor_id,
        "count": row[0],
        "average": row[1],
        "minimum": row[2],
        "maximum": row[3],
        "rms": row[4],
    }
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(
        Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8"),
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get('/model', response_class=HTMLResponse)
def model_viewer():
    return Path(__file__).with_name('model.html').read_text(encoding='utf-8')
