import json, time, random, math
import paho.mqtt.client as mqtt

MQTT_HOST = "broker.hivemq.com"
MQTT_PORT = 1883

TOPIC = "iot/lab2-b23dcat235/sim-01/sensors"
DEVICE_ID = "sim-01"

c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.connect(MQTT_HOST, MQTT_PORT)
c.loop_start()

seq = 0

print(f"🚀 Đang phát dữ liệu giả lập lên '{TOPIC}'...")

while True:
    t = 28 + 3 * math.sin(seq / 50) + random.gauss(0, 0.3)
    h = 70 + 5 * math.cos(seq / 60) + random.gauss(0, 1)

    if random.random() < 0.02:
        t += random.choice([-30, 40])

    msg = {
        "device_id": DEVICE_ID,
        "seq": seq,
        "ts_ms": int(time.time() * 1000),
        "temperature": round(t, 2),
        "humidity": round(h, 2),
        "light": random.randint(200, 900)
    }

    if random.random() < 0.03:
        del msg["temperature"]

    c.publish(TOPIC, json.dumps(msg))
    print(f"[SEND] {msg}")

    seq += 1

    if random.random() < 0.02:
        seq += 1

    time.sleep(1)