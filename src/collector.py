import json
import time
import os
import logging

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

log = logging.getLogger("collector")

RANGES = {
    "temperature": (-40, 80),
    "humidity": (0, 100),
    "light": (0, 4095)
}

last_seq = {}
stats = {
    "ok": 0,
    "invalid": 0,
    "lost": 0
}

MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = 1883
MQTT_TOPIC = "iot/lab2-b23dcat235/+/sensors"

influx = InfluxDBClient(
    url=os.getenv("INFLUX_URL", "http://localhost:8086"),
    token=os.getenv("INFLUX_TOKEN", "my-super-token"),
    org=os.getenv("INFLUX_ORG", "uni")
)

write_api = influx.write_api(write_options=SYNCHRONOUS)


def validate(d):
    if not all(k in d for k in ("device_id", "seq", "ts_ms")):
        return False, "thiếu trường bắt buộc"

    if not any(k in d for k in RANGES):
        return False, "không có giá trị đo"

    for k, (lo, hi) in RANGES.items():
        if k in d:
            if not (
                isinstance(d[k], (int, float))
                and lo <= d[k] <= hi
            ):
                return False, f"{k} ngoài khoảng vật lý hợp lệ"

    return True, ""


def on_connect(client, userdata, flags, rc, props):
    log.info("Connected rc=%s", rc)

    result, mid = client.subscribe(
        MQTT_TOPIC,
        qos=1
    )

    log.info(
        "Subscribe topic=%s result=%s mid=%s",
        MQTT_TOPIC,
        result,
        mid
    )


def on_message(client, userdata, msg):
    recv_ms = int(time.time() * 1000)

    log.info(
        "RECEIVED topic=%s payload=%s",
        msg.topic,
        msg.payload.decode(errors="replace")
    )

    try:
        d = json.loads(msg.payload)
    except json.JSONDecodeError:
        stats["invalid"] += 1
        log.warning("JSON hỏng")
        return

    ok, why = validate(d)

    if not ok:
        stats["invalid"] += 1
        log.warning(
            "Bỏ gói: %s | %s",
            why,
            d
        )
        return

    dev = d["device_id"]

    if dev in last_seq and d["seq"] > last_seq[dev] + 1:
        lost = d["seq"] - last_seq[dev] - 1
        stats["lost"] += lost

        log.warning(
            "Phát hiện mất %s packet của %s",
            lost,
            dev
        )

    last_seq[dev] = d["seq"]

    p = (
        Point("sensor_raw")
        .tag("device_id", dev)
        .field("seq", int(d["seq"]))
        .field(
            "latency_ms",
            float(recv_ms - d["ts_ms"])
        )
        .time(
    recv_ms,
    WritePrecision.MS
)
    )

    for k in RANGES:
        if k in d:
            p = p.field(k, float(d[k]))

    try:
        write_api.write(
            bucket="iot_raw",
            record=p
        )

        stats["ok"] += 1

        log.info(
            "WRITE OK device=%s seq=%s",
            dev,
            d["seq"]
        )

    except Exception as e:
        log.error(
            "Ghi DB lỗi: %s",
            e
        )


c = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="b23dcat235-collector"
)

c.on_connect = on_connect
c.on_message = on_message

log.info(
    "Connecting MQTT %s:%s",
    MQTT_HOST,
    MQTT_PORT
)

c.connect(
    MQTT_HOST,
    MQTT_PORT
)

try:
    c.loop_forever()

finally:
    log.info(
        "Thống kê: %s",
        stats
    )