#include <Arduino.h>
#include <sys/time.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <time.h>
#include <math.h>

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;
const char* DEVICE_ID = "esp32-01";
const char* TOPIC     = "iot/lab2-b23dcat235/esp32-01/sensors";

#define DHTPIN 4
#define LDRPIN 34

// true  = tự động thay đổi giá trị
// false = dùng đúng giá trị cảm biến trên Wokwi
#define AUTO_MODE true

DHT dht(DHTPIN, DHT22);
WiFiClient wifi;
PubSubClient mqtt(wifi);
unsigned long seq = 0;

int64_t nowMs() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (int64_t)tv.tv_sec * 1000 + tv.tv_usec / 1000;
}

void connectAll() {
  Serial.print("WiFi...");
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println(" OK");

  Serial.print("NTP...");
  configTime(0, 0, "pool.ntp.org");

  while (time(nullptr) < 100000) {
    delay(200);
    Serial.print(".");
  }

  Serial.println(" OK");

  mqtt.setServer(MQTT_HOST, MQTT_PORT);

  while (!mqtt.connected()) {
    Serial.print("MQTT...");

    if (mqtt.connect("b23dcat235-esp32-01")) {
      Serial.println(" OK");
    } else {
      Serial.printf(" lỗi rc=%d, thử lại\n", mqtt.state());
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  connectAll();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED || !mqtt.connected()) {
    connectAll();
  }

  mqtt.loop();

  float t = dht.readTemperature();
  float h = dht.readHumidity();
  int light = analogRead(LDRPIN);

  // =========================
  // CHẾ ĐỘ TỰ ĐỘNG
  // =========================
  if (AUTO_MODE) {
    float timeValue = millis() / 1000.0;

    // Nhiệt độ dao động nhẹ quanh giá trị thực
    if (!isnan(t)) {
      t += 1.5 * sin(timeValue / 20.0);
    }

    // Độ ẩm dao động nhẹ
    if (!isnan(h)) {
      h += 3.0 * sin(timeValue / 25.0);
    }

    // Ánh sáng tự động thay đổi
    light = 1800 + 1200 * sin(timeValue / 15.0);

    // Giới hạn giá trị
    if (h < 0) h = 0;
    if (h > 100) h = 100;

    if (light < 0) light = 0;
    if (light > 4095) light = 4095;
  }

  StaticJsonDocument<256> doc;

  doc["device_id"] = DEVICE_ID;
  doc["seq"] = seq++;
  doc["ts_ms"] = (int64_t)nowMs();

  if (!isnan(t)) {
    doc["temperature"] = t;
  }

  if (!isnan(h)) {
    doc["humidity"] = h;
  }

  doc["light"] = light;

  char buf[256];

  serializeJson(doc, buf);

  mqtt.publish(TOPIC, buf);

  Serial.println(buf);

  delay(2000);
}