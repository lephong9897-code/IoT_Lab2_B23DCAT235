\# IoT Lab 2 - B23DCAT235



\## 1. Giới thiệu



Đây là project IoT Lab 2 xây dựng hệ thống thu thập, truyền,

lưu trữ, tiền xử lý và trực quan hóa dữ liệu cảm biến.



Hệ thống sử dụng ESP32 kết nối với cảm biến DHT22 và LDR.

Dữ liệu cảm biến được truyền thông qua giao thức MQTT đến MQTT

Broker, sau đó được chương trình Collector tiếp nhận và lưu vào

InfluxDB.



Dữ liệu sau khi được tiền xử lý được sử dụng để hiển thị trên

Dashboard xây dựng bằng Streamlit.



\---



\## 2. Kiến trúc hệ thống



```text

&#x20;            ┌─────────────────┐

&#x20;            │      DHT22      │

&#x20;            │ Nhiệt độ/Độ ẩm  │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     │

&#x20;            ┌────────▼────────┐

&#x20;            │       LDR       │

&#x20;            │     Ánh sáng    │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │      ESP32      │

&#x20;            │  Sensor Device  │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     │ MQTT

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │   HiveMQ Broker │

&#x20;            │ broker.hivemq   │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     │ Subscribe

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │  collector.py   │

&#x20;            │ Thu thập dữ liệu│

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │    InfluxDB     │

&#x20;            │    iot\_raw      │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │ preprocess.py   │

&#x20;            │ Tiền xử lý      │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │  iot\_processed  │

&#x20;            └────────┬────────┘

&#x20;                     │

&#x20;                     ▼

&#x20;            ┌─────────────────┐

&#x20;            │ Streamlit App   │

&#x20;            │    Dashboard    │

&#x20;            └─────────────────┘

```



\---



\## 3. Chức năng hệ thống



Hệ thống thực hiện các chức năng chính:



\- Đọc nhiệt độ từ cảm biến DHT22.

\- Đọc độ ẩm từ cảm biến DHT22.

\- Đọc giá trị ánh sáng từ cảm biến LDR.

\- Gửi dữ liệu từ ESP32 thông qua MQTT.

\- Thu thập dữ liệu MQTT bằng Collector.

\- Kiểm tra tính hợp lệ của dữ liệu.

\- Phát hiện mất packet thông qua số thứ tự `seq`.

\- Tính độ trễ truyền dữ liệu.

\- Lưu dữ liệu thô vào InfluxDB.

\- Tiền xử lý dữ liệu.

\- Lưu dữ liệu sau xử lý vào InfluxDB.

\- Hiển thị dữ liệu trên Streamlit Dashboard.

\- Theo dõi trạng thái nhận dữ liệu của thiết bị.

\- Theo dõi packet loss và latency.



\---



\## 4. Thiết bị và phần cứng



\### ESP32



Thiết bị chính sử dụng để đọc cảm biến và gửi dữ liệu.



\### DHT22



DHT22 được sử dụng để đo:



\- Nhiệt độ.

\- Độ ẩm.



\### LDR



LDR được sử dụng để thu thập giá trị ánh sáng thông qua

ngõ vào analog của ESP32.



\### Mô phỏng



Firmware ESP32 có thể được chạy và mô phỏng bằng Wokwi.



\---



\## 5. Firmware ESP32



Firmware nằm tại:



```text

firmware/esp32\_sensor/

```



Cấu trúc:



```text

firmware/

└── esp32\_sensor/

&#x20;   ├── src/

&#x20;   │   └── main.cpp

&#x20;   ├── platformio.ini

&#x20;   ├── diagram.json

&#x20;   ├── wokwi.toml

&#x20;   └── .gitignore

```



\### Các file chính



`main.cpp`



Chương trình điều khiển ESP32, đọc dữ liệu cảm biến và gửi

dữ liệu thông qua MQTT.



`platformio.ini`



File cấu hình môi trường PlatformIO.



`diagram.json`



Sơ đồ mạch mô phỏng trên Wokwi.



`wokwi.toml`



File cấu hình chạy firmware trên Wokwi.



\---



\## 6. MQTT



\### MQTT Broker



Hệ thống sử dụng MQTT Broker:



```text

broker.hivemq.com

```



Port:



```text

1883

```



\### MQTT Topic của ESP32



ESP32 gửi dữ liệu đến:



```text

iot/lab2-b23dcat235/esp32-01/sensors

```



\### Topic Collector Subscribe



Collector subscribe:



```text

iot/lab2-b23dcat235/+/sensors

```



Cách sử dụng wildcard `+` cho phép Collector nhận dữ liệu

từ nhiều thiết bị có cùng cấu trúc topic.



\---



\## 7. Định dạng dữ liệu MQTT



Dữ liệu được gửi dưới dạng JSON.



Ví dụ:



```json

{

&#x20;   "device\_id": "esp32-01",

&#x20;   "seq": 123,

&#x20;   "ts\_ms": 1750000000000,

&#x20;   "temperature": 25.5,

&#x20;   "humidity": 60.2,

&#x20;   "light": 2300

}

```



\### Ý nghĩa các trường



| Trường | Ý nghĩa |

|---|---|

| `device\_id` | ID của thiết bị |

| `seq` | Số thứ tự packet |

| `ts\_ms` | Timestamp của dữ liệu |

| `temperature` | Nhiệt độ |

| `humidity` | Độ ẩm |

| `light` | Giá trị ánh sáng |



\---



\## 8. Collector



File:



```text

src/collector.py

```



Collector có nhiệm vụ:



1\. Kết nối đến MQTT Broker.

2\. Subscribe topic cảm biến.

3\. Nhận dữ liệu JSON.

4\. Kiểm tra cấu trúc dữ liệu.

5\. Kiểm tra phạm vi hợp lệ của các giá trị cảm biến.

6\. Theo dõi số thứ tự packet.

7\. Phát hiện packet bị mất.

8\. Tính latency.

9\. Ghi dữ liệu vào InfluxDB.



\### Kiểm tra dữ liệu



Collector kiểm tra các trường bắt buộc:



```text

device\_id

seq

ts\_ms

```



Các giá trị cảm biến được kiểm tra theo khoảng:



```text

Temperature: -40 → 80 °C

Humidity:      0 → 100 %

Light:         0 → 4095

```



\---



\## 9. InfluxDB



InfluxDB được sử dụng để lưu trữ dữ liệu cảm biến.



\### Cấu hình



```text

URL:

http://localhost:8086

```



Organization:



```text

uni

```



Raw bucket:



```text

iot\_raw

```



Processed bucket:



```text

iot\_processed

```



\### Dữ liệu Raw



Dữ liệu nhận từ MQTT được lưu vào:



```text

iot\_raw

```



Measurement:



```text

sensor\_raw

```



Các trường dữ liệu gồm:



```text

device\_id

seq

temperature

humidity

light

latency\_ms

```



\---



\## 10. Tiền xử lý dữ liệu



File:



```text

src/preprocess.py

```



Chương trình đọc dữ liệu từ bucket:



```text

iot\_raw

```



Sau đó thực hiện các bước tiền xử lý cần thiết và lưu kết quả

vào:



```text

iot\_processed

```



Dữ liệu sau xử lý được sử dụng cho việc phân tích và hiển thị

trên Dashboard.



\---



\## 11. Streamlit Dashboard



File:



```text

src/app.py

```



Dashboard được xây dựng bằng Streamlit.



Dashboard cung cấp các thông tin:



\### Thông tin thiết bị



\- Device ID.

\- Trạng thái nhận dữ liệu.

\- Thời gian nhận dữ liệu gần nhất.



\### Dữ liệu cảm biến



\- Nhiệt độ.

\- Độ ẩm.

\- Ánh sáng.



\### Thông tin truyền dữ liệu



\- Sequence.

\- Packet loss.

\- Latency.

\- Thời gian cập nhật dữ liệu.



\### Hiển thị dữ liệu



Dashboard hỗ trợ:



\- Biểu đồ dữ liệu cảm biến.

\- Biểu đồ latency.

\- Bảng dữ liệu.

\- Theo dõi dữ liệu theo thiết bị.

\- Tự động làm mới dữ liệu.



\---



\## 12. Simulator



File:



```text

src/simulator.py

```



Simulator được sử dụng để hỗ trợ tạo dữ liệu mô phỏng trong

quá trình kiểm thử hệ thống khi cần thiết bị phát dữ liệu mẫu.



\---



\## 13. Cấu trúc thư mục



```text

IoT\_Lab2/

│

├── firmware/

│   └── esp32\_sensor/

│       ├── src/

│       │   └── main.cpp

│       ├── platformio.ini

│       ├── diagram.json

│       ├── wokwi.toml

│       └── .gitignore

│

├── mosquitto/

│   └── config/

│       └── mosquitto.conf

│

├── src/

│   ├── app.py

│   ├── collector.py

│   ├── preprocess.py

│   └── simulator.py

│

├── .env.example

├── .gitignore

├── docker-compose.yml

├── requirements.txt

└── README.md

```



\---



\## 14. Yêu cầu môi trường



Cần cài đặt:



\- Python 3

\- PlatformIO

\- Docker Desktop

\- Git

\- Wokwi (nếu sử dụng mô phỏng)

\- InfluxDB

\- MQTT Broker



\---



\## 15. Cài đặt Python



Cài các thư viện trong:



```text

requirements.txt

```



Sử dụng lệnh:



```bash

pip install -r requirements.txt

```



Khuyến nghị sử dụng virtual environment:



```bash

python -m venv venv

```



Windows:



```powershell

venv\\Scripts\\activate

```



Sau đó:



```powershell

pip install -r requirements.txt

```



\---



\## 16. Cấu hình môi trường



Project cung cấp file mẫu:



```text

.env.example

```



Tạo file `.env` từ file mẫu và điền các thông tin cấu hình

cần thiết.



Ví dụ:



```text

INFLUX\_URL=http://localhost:8086

INFLUX\_TOKEN=your-token

INFLUX\_ORG=uni

```



Không đưa file `.env` chứa token hoặc thông tin bảo mật thật

lên GitHub.



\---



\## 17. Chạy hệ thống bằng Docker



Từ thư mục gốc:



```bash

docker compose up -d

```



Kiểm tra container:



```bash

docker compose ps

```



Dừng hệ thống:



```bash

docker compose down

```



\---



\## 18. Chạy Firmware



Mở thư mục:



```text

firmware/esp32\_sensor/

```



Build firmware bằng PlatformIO:



```bash

pio run

```



Nếu sử dụng Wokwi, mở project và chạy mô phỏng.



\---



\## 19. Chạy Collector



Từ thư mục gốc project:



```bash

python src/collector.py

```



Collector sẽ kết nối đến MQTT Broker và nhận dữ liệu từ:



```text

iot/lab2-b23dcat235/+/sensors

```



Sau khi nhận dữ liệu hợp lệ, Collector ghi dữ liệu vào InfluxDB.



\---



\## 20. Chạy tiền xử lý



Chạy:



```bash

python src/preprocess.py

```



Dữ liệu sau xử lý được lưu vào:



```text

iot\_processed

```



\---



\## 21. Chạy Dashboard



Chạy:



```bash

streamlit run src/app.py

```



Sau khi Streamlit khởi động, mở địa chỉ được hiển thị trong

terminal để truy cập Dashboard.



\---



\## 22. Quy trình chạy đầy đủ



Thứ tự chạy hệ thống:



```text

1\. Docker / InfluxDB

&#x20;       ↓

2\. MQTT Broker

&#x20;       ↓

3\. ESP32 / Wokwi

&#x20;       ↓

4\. collector.py

&#x20;       ↓

5\. InfluxDB - iot\_raw

&#x20;       ↓

6\. preprocess.py

&#x20;       ↓

7\. InfluxDB - iot\_processed

&#x20;       ↓

8\. Streamlit Dashboard

```



\---



\## 23. Kiểm tra hệ thống



Sau khi chạy, kiểm tra lần lượt:



\### ESP32



Kiểm tra Serial Monitor để xác nhận ESP32 đọc được cảm biến

và gửi MQTT.



\### MQTT



Kiểm tra Collector có nhận được message hay không.



\### Collector



Kiểm tra log:



```text

RECEIVED

WRITE OK

```



\### InfluxDB



Kiểm tra dữ liệu trong:



```text

iot\_raw

```



và:



```text

iot\_processed

```



\### Dashboard



Kiểm tra:



\- Nhiệt độ.

\- Độ ẩm.

\- Ánh sáng.

\- Latency.

\- Packet loss.

\- Trạng thái thiết bị.

\- Dữ liệu cập nhật.



\---



\## 24. Xử lý một số lỗi thường gặp



\### Không nhận được MQTT



Kiểm tra:



```text

MQTT\_HOST = broker.hivemq.com

MQTT\_PORT = 1883

```



và kiểm tra topic:



```text

iot/lab2-b23dcat235/esp32-01/sensors

```



\### Collector không nhận dữ liệu



Kiểm tra Collector đang subscribe:



```text

iot/lab2-b23dcat235/+/sensors

```



và đảm bảo ESP32 sử dụng đúng topic.



\### Không ghi được InfluxDB



Kiểm tra:



```text

INFLUX\_URL

INFLUX\_TOKEN

INFLUX\_ORG

```



và kiểm tra InfluxDB đang hoạt động.



\### Dashboard không có dữ liệu



Kiểm tra theo thứ tự:



```text

ESP32

&#x20;↓

MQTT

&#x20;↓

Collector

&#x20;↓

InfluxDB

&#x20;↓

preprocess

&#x20;↓

Streamlit

```



\---



\## 25. Bảo mật



Các thông tin nhạy cảm như:



\- InfluxDB token

\- Password

\- API key

\- Secret key



không được lưu trực tiếp trong source code hoặc commit lên

repository.



File `.env` được đưa vào `.gitignore` để tránh upload thông tin

cấu hình bí mật.



\---



\## 26. Tác giả



\*\*Sinh viên:\*\* B23DCAT235



\*\*Project:\*\* IoT Lab 2



\*\*Repository:\*\*



https://github.com/lephong9897-code/IoT\_Lab2\_B23DCAT235

