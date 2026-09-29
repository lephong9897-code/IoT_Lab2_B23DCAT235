import pandas as pd, numpy as np
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from sklearn.preprocessing import MinMaxScaler

URL, TOKEN, ORG = "http://localhost:8086", "my-super-token", "uni"
client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=30000)

# 1. Đọc theo khoảng thời gian
flux = '''
from(bucket: "iot_raw") |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "sensor_raw")
  |> filter(fn: (r) => r._field == "temperature" or r._field == "humidity" or r._field == "light")
  |> pivot(rowKey:["_time","device_id"], columnKey:["_field"], valueColumn:"_value")
'''
df = client.query_api().query_data_frame(flux)
df = df.rename(columns={"_time": "time"})[["time", "device_id", "temperature", "humidity", "light"]]
df = df.set_index("time").sort_index()
print("Số dòng thô:", len(df), "| thiếu:\n", df.isna().sum())

# 2. Loại trùng
df = df[~df.index.duplicated(keep="last")]

# 3. Outlier bằng IQR
def iqr_mask(s, k=1.5):
    q1, q3 = s.quantile([.25, .75]); i = q3 - q1
    return (s < q1 - k*i) | (s > q3 + k*i)

out = pd.DataFrame(index=df.index)
for col in ["temperature", "humidity"]:
    out[f"{col}_out"] = iqr_mask(df[col])
df["is_outlier"] = out.any(axis=1)
n_out = int(df["is_outlier"].sum())
df.loc[out["temperature_out"], "temperature"] = np.nan
df.loc[out["humidity_out"], "humidity"] = np.nan

# 4. Missing: nội suy theo thời gian
df[["temperature", "humidity"]] = df[["temperature", "humidity"]].interpolate(
    method="time", limit=5)

# 5. Resample 10 giây
res = (df.groupby("device_id")
         .resample("10s")
         .agg({"temperature": "mean", "humidity": "mean", "light": "mean", "is_outlier": "sum"})
         .reset_index().set_index("time"))
res = res.dropna(subset=["temperature", "humidity"])

# 6. Đặc trưng
res["temp_roll_mean"] = res.groupby("device_id")["temperature"].transform(
    lambda s: s.rolling(6, min_periods=1).mean())
res["temp_delta"] = res.groupby("device_id")["temperature"].diff().fillna(0)

# 7. Chuẩn hóa Min-Max
scaler = MinMaxScaler()
res[["temp_norm", "hum_norm"]] = scaler.fit_transform(res[["temperature", "humidity"]])

# 8. Ghi vào bucket mới
write_api = client.write_api(write_options=SYNCHRONOUS)
points = []
for ts, r in res.iterrows():
    points.append(Point("sensor_processed").tag("device_id", r["device_id"])
        .field("temperature", float(r.temperature)).field("humidity", float(r.humidity))
        .field("temp_roll_mean", float(r.temp_roll_mean)).field("temp_delta", float(r.temp_delta))
        .field("temp_norm", float(r.temp_norm)).field("hum_norm", float(r.hum_norm))
        .field("outlier_count", int(r.is_outlier))
        .time(ts.to_pydatetime(), WritePrecision.S))
write_api.write(bucket="iot_processed", record=points)
print(f"Đã ghi {len(points)} điểm | outlier phát hiện: {n_out}")