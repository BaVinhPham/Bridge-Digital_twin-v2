import json
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

BROKER = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))

SENSORS = {
    "ACC_01": (0.0, 0.08, "m/s2"),
    "SG_01": (110.0, 140.0, "microstrain"),
    "TEMP_01": (20.0, 28.0, "C"),
    "DISP_01": (8.0, 15.0, "mm"),
}

# Add 200 test sensors
for i in range(1, 201):

    sensor_id = f"TEST_{i:03d}"

    SENSORS[sensor_id] = (
        0.0,      # minimum simulated value
        100.0,    # maximum simulated value
        "unit"
    )


client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.connect_async(BROKER, PORT, 60)
client.loop_start()

while True:
    if not client.is_connected():
        time.sleep(1)
        continue
    for sensor_id, (low, high, unit) in SENSORS.items():
        payload = {
            "sensor_id": sensor_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": round(random.uniform(low, high), 4),
            "unit": unit,
            "quality": "GOOD",
        }
        topic = f"bridge/sensors/{sensor_id}/data"
        client.publish(topic, json.dumps(payload))
        print(topic, payload)
    time.sleep(2)
