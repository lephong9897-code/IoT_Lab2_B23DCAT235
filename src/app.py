"""
IoT Monitor - dashboard giám sát dữ liệu cảm biến (Streamlit + InfluxDB).

Chạy:  streamlit run src/app.py
Cần:   pip install -U streamlit plotly influxdb-client pandas numpy
Cấu hình qua biến môi trường (giống collector.py):
INFLUX_URL, INFLUX_TOKEN, INFLUX_ORG
"""

import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from influxdb_client import InfluxDBClient


URL = os.getenv("INFLUX_URL", "http://localhost:8086")
TOKEN = os.getenv("INFLUX_TOKEN", "my-super-token")
ORG = os.getenv("INFLUX_ORG", "uni")

RAW = "iot_raw"
PROC = "iot_processed"

TZ = "Asia/Ho_Chi_Minh"

C_TEMP = "#E5484D"
C_HUM = "#3E63DD"
C_LIGHT = "#E5A000"

C_ROLL = "#7C3AED"
C_BAD = "#D6292F"
C_MUTED = "rgba(128,128,128,0.6)"

VIEWS = [
    "Real-time (dữ liệu thô)",
    "Đã tiền xử lý",
    "So sánh thô và đã xử lý"
]


st.set_page_config(
    page_title="IoT Monitor",
    page_icon="📡",
    layout="wide"
)


st.markdown(
    """
<style>
.block-container {
    padding-top: 2.2rem;
    max-width: 1280px;
}

footer {
    visibility: hidden;
}

h1, h2, h3 {
    letter-spacing: -0.01em;
}

/* Dải chỉ số */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) {
    border: 1px solid rgba(128,128,128,0.28);
    border-radius: 10px;
    gap: 0;
    padding: 0.4rem 0;
}

div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"])
> div[data-testid="stColumn"] {
    padding: 0.2rem 1.2rem;
    border-right: 1px solid rgba(128,128,128,0.22);
}

div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"])
> div[data-testid="stColumn"]:last-child {
    border-right: none;
}

div[data-testid="stMetricLabel"] {
    opacity: 0.7;
    font-size: 0.85rem;
}

div[data-testid="stMetricValue"] {
    font-size: 1.9rem;
    font-weight: 600;
}

.status {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0.8rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 600;
    border: 1px solid;
}

.status i {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
    background: currentColor;
}

.status.ok {
    color: #12A150;
    border-color: rgba(18,161,80,0.4);
    background: rgba(18,161,80,0.08);
}

.status.warn {
    color: #C77700;
    border-color: rgba(199,119,0,0.4);
    background: rgba(199,119,0,0.08);
}

.status.bad {
    color: #D6292F;
    border-color: rgba(214,41,47,0.4);
    background: rgba(214,41,47,0.08);
}

.status.idle {
    color: #6B7280;
    border-color: rgba(107,114,128,0.4);
    background: rgba(107,114,128,0.08);
}
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------------------------------------------
# Dữ liệu
# ----------------------------------------------------------------

@st.cache_resource
def get_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=URL,
        token=TOKEN,
        org=ORG,
        timeout=15000
    )


@st.cache_data(ttl=10)
def list_devices() -> list[str]:

    flux = f'''
    import "influxdata/influxdb/schema"

    schema.tagValues(
        bucket: "{RAW}",
        tag: "device_id"
    )
    '''

    try:
        df = get_client().query_api().query_data_frame(flux)

        if isinstance(df, list):
            df = pd.concat(df) if df else pd.DataFrame()

        return (
            sorted(df["_value"].astype(str).tolist())
            if not df.empty
            else []
        )

    except Exception:
        return []


# Không cache dữ liệu realtime lâu
@st.cache_data(ttl=0, show_spinner=False)
def fetch(
    bucket: str,
    measurement: str,
    rng: str,
    device: str
) -> pd.DataFrame:

    flux = f'''
    from(bucket: "{bucket}")
      |> range(start: {rng})
      |> filter(fn: (r) => r._measurement == "{measurement}")
      |> filter(fn: (r) => r.device_id == "{device}")
      |> pivot(
          rowKey: ["_time", "device_id"],
          columnKey: ["_field"],
          valueColumn: "_value"
      )
    '''

    res = get_client().query_api().query_data_frame(flux)

    if isinstance(res, list):
        res = pd.concat(res) if res else pd.DataFrame()

    if res.empty:
        return res

    res = res.drop(
        columns=[
            c for c in (
                "result",
                "table",
                "_start",
                "_stop",
                "_measurement"
            )
            if c in res
        ]
    )

    res["_time"] = (
        pd.to_datetime(res["_time"])
        .dt.tz_convert(TZ)
    )

    return (
        res
        .sort_values("_time")
        .set_index("_time")
    )


def iqr_outliers(
    s: pd.Series,
    k: float = 1.5
) -> pd.Series:

    q1, q3 = s.quantile([0.25, 0.75])

    iqr = q3 - q1

    return (
        (s < q1 - k * iqr)
        |
        (s > q3 + k * iqr)
    )


def lost_packets(raw: pd.DataFrame) -> int:

    if raw.empty or "seq" not in raw:
        return 0

    d = raw["seq"].diff().dropna()

    return int(
        (d[d > 1] - 1).sum()
    )


def latest(
    df: pd.DataFrame,
    col: str
):

    if (
        df is None
        or df.empty
        or col not in df
    ):
        return None, None

    s = df[col].dropna()

    if s.empty:
        return None, None

    return (
        s.iloc[-1],
        s.iloc[-1] - s.iloc[-2]
        if len(s) > 1
        else None
    )


# ----------------------------------------------------------------
# Biểu đồ
# ----------------------------------------------------------------

def base_fig(
    title: str,
    unit: str,
    height: int = 330
) -> go.Figure:

    fig = go.Figure()

    fig.update_layout(
        title=dict(
            text=title,
            x=0,
            font=dict(size=15)
        ),
        height=height,
        margin=dict(
            l=8,
            r=8,
            t=56,
            b=8
        ),
        hovermode="x unified",
        yaxis_title=unit,
        legend=dict(
            orientation="h",
            x=1,
            xanchor="right",
            y=1.02,
            yanchor="bottom"
        ),
    )

    fig.update_xaxes(
        showgrid=False
    )

    fig.update_yaxes(
        gridcolor="rgba(128,128,128,0.2)",
        zeroline=False
    )

    return fig


def series_fig(
    view,
    title,
    unit,
    raw,
    proc,
    col,
    color,
    roll=None
):

    fig = base_fig(
        title,
        unit
    )

    show_raw = (
        view != VIEWS[1]
        and not raw.empty
        and col in raw
    )

    show_proc = (
        view != VIEWS[0]
        and not proc.empty
        and col in proc
    )

    if show_raw:

        only_raw = view == VIEWS[0]

        fig.add_scatter(
            x=raw.index,
            y=raw[col],
            name="Dữ liệu thô",
            mode="lines",
            line=dict(
                color=color
                if only_raw
                else C_MUTED,
                width=1.6
            ),
        )

        if only_raw:

            s = raw[col].dropna()

            if len(s) >= 8:

                m = iqr_outliers(s)

                if m.any():

                    fig.add_scatter(
                        x=s.index[m],
                        y=s[m],
                        mode="markers",
                        name="Outlier (IQR)",
                        marker=dict(
                            color=C_BAD,
                            size=9,
                            symbol="x"
                        ),
                    )

    if show_proc:

        fig.add_scatter(
            x=proc.index,
            y=proc[col],
            name="Đã xử lý",
            mode="lines",
            line=dict(
                color=color,
                width=2.2
            )
        )

        if roll and roll in proc:

            fig.add_scatter(
                x=proc.index,
                y=proc[roll],
                name="Rolling mean",
                mode="lines",
                line=dict(
                    color=C_ROLL,
                    width=2,
                    dash="dash"
                )
            )

    return fig


# ----------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------

with st.sidebar:

    st.subheader("Bộ lọc")

    view = st.radio(
        "Chế độ hiển thị",
        VIEWS
    )

    devices = list_devices()

    device = (
        st.selectbox(
            "Thiết bị",
            devices
        )
        if devices
        else None
    )

    rng = st.select_slider(
        "Khoảng thời gian",
        [
            "-5m",
            "-15m",
            "-30m",
            "-1h",
            "-6h",
            "-24h"
        ],
        value="-30m"
    )

    st.divider()

    auto = st.toggle(
        "Tự động làm mới",
        value=True
    )

    refresh = st.slider(
        "Chu kỳ làm mới (giây)",
        2,
        30,
        5,
        disabled=not auto
    )

    if st.button(
        "Làm mới ngay",
        use_container_width=True
    ):
        st.cache_data.clear()

    st.divider()

    try:
        ok = get_client().ping()
    except Exception:
        ok = False

    st.caption(
        f"InfluxDB: "
        f"{'đã kết nối' if ok else 'không kết nối được'}\n"
        f"{URL}"
    )


# ----------------------------------------------------------------
# Nội dung dashboard
# ----------------------------------------------------------------

@st.fragment(
    run_every=refresh if auto else None
)
def dashboard():

    if not device:

        st.title("IoT Monitor")

        st.info(
            "Chưa thấy thiết bị nào trong bucket "
            "iot_raw. Hãy chạy simulator hoặc Wokwi, "
            "rồi bật collector.py."
        )

        return

    try:

        raw = fetch(
            RAW,
            "sensor_raw",
            rng,
            device
        )

        proc = fetch(
            PROC,
            "sensor_processed",
            rng,
            device
        )

    except Exception as e:

        st.error(
            f"Không truy vấn được InfluxDB: {e}"
        )

        return


    # ------------------------------------------------------------
    # Đầu trang
    # ------------------------------------------------------------

    left, right = st.columns(
        [4, 1.2],
        vertical_alignment="center"
    )

    with left:

        st.title(
            "Giám sát cảm biến"
        )

        st.caption(
            f"Thiết bị {device}  ·  "
            f"{rng.lstrip('-')} gần nhất  ·  "
            f"cập nhật {datetime.now():%H:%M:%S}"
        )

    with right:

        if raw.empty:

            badge = (
                '<span class="status idle">'
                '<i></i>Chưa có dữ liệu'
                '</span>'
            )

        else:

            # ----------------------------------------------------
            # SỬA QUAN TRỌNG:
            # Lấy thời gian mới nhất của bản ghi thực tế.
            # ----------------------------------------------------

            last_time = raw.index.max()

            now = pd.Timestamp.now(
                tz=TZ
            )

            age = (
                now - last_time
            ).total_seconds()

            # ESP32 gửi khoảng 2 giây/lần.
            # Dashboard refresh mặc định 5 giây.
            #
            # Không để ngưỡng quá ngắn để tránh:
            # Đang nhận -> Chậm -> Mất tín hiệu
            # dù collector vẫn đang ghi dữ liệu.

            if age < 15:

                badge = (
                    '<span class="status ok">'
                    '<i></i>Đang nhận dữ liệu'
                    '</span>'
                )

            elif age < 45:

                badge = (
                    f'<span class="status warn">'
                    f'<i></i>Chậm {age:.0f} giây'
                    f'</span>'
                )

            else:

                badge = (
                    f'<span class="status bad">'
                    f'<i></i>Mất tín hiệu '
                    f'{age / 60:.1f} phút'
                    f'</span>'
                )

        st.markdown(
            f'<div style="text-align:right">'
            f'{badge}'
            f'</div>',
            unsafe_allow_html=True
        )


    # ------------------------------------------------------------
    # Dải chỉ số
    # ------------------------------------------------------------

    main = (
        proc
        if (
            view == VIEWS[1]
            and not proc.empty
        )
        else raw
    )

    t, dt = latest(
        main,
        "temperature"
    )

    h, dh = latest(
        main,
        "humidity"
    )

    lx, _ = latest(
        raw,
        "light"
    )

    lat = (
        raw["latency_ms"].dropna()
        if "latency_ms" in raw
        else pd.Series(dtype=float)
    )

    lost = lost_packets(raw)


    k = st.columns(5)

    k[0].metric(
        "Nhiệt độ",
        "—"
        if t is None
        else f"{t:.1f} °C",
        None
        if dt is None
        else f"{dt:+.1f}",
        delta_color="off"
    )

    k[1].metric(
        "Độ ẩm",
        "—"
        if h is None
        else f"{h:.1f} %",
        None
        if dh is None
        else f"{dh:+.1f}",
        delta_color="off"
    )

    k[2].metric(
        "Ánh sáng",
        "—"
        if lx is None
        else f"{lx:.0f}"
    )

    k[3].metric(
        "Độ trễ p95",
        "—"
        if lat.empty
        else f"{np.percentile(lat, 95):.0f} ms"
    )

    k[4].metric(
        "Gói mất",
        f"{lost}"
    )


    st.write("")


    tab1, tab2, tab3 = st.tabs(
        [
            "Giám sát",
            "Độ trễ và chất lượng",
            "Bảng dữ liệu"
        ]
    )


    # ------------------------------------------------------------
    # TAB 1
    # ------------------------------------------------------------

    with tab1:

        if (
            view == VIEWS[1]
            and proc.empty
        ):

            st.info(
                "Bucket iot_processed chưa có dữ liệu "
                "trong khoảng này. Chạy "
                "`python src/preprocess.py` để tạo."
            )

        elif (
            raw.empty
            and view != VIEWS[1]
        ):

            st.info(
                "Chưa có dữ liệu thô trong khoảng này. "
                "Kiểm tra collector.py và nguồn phát."
            )

        else:

            st.plotly_chart(
                series_fig(
                    view,
                    "Nhiệt độ",
                    "°C",
                    raw,
                    proc,
                    "temperature",
                    C_TEMP,
                    "temp_roll_mean"
                ),
                use_container_width=True
            )

            c1, c2 = st.columns(2)

            c1.plotly_chart(
                series_fig(
                    view,
                    "Độ ẩm",
                    "%",
                    raw,
                    proc,
                    "humidity",
                    C_HUM
                ),
                use_container_width=True
            )

            if "light" in raw:

                fig = base_fig(
                    "Ánh sáng (LDR)",
                    "ADC 0-4095"
                )

                fig.add_scatter(
                    x=raw.index,
                    y=raw["light"],
                    name="Ánh sáng",
                    mode="lines",
                    line=dict(
                        color=C_LIGHT,
                        width=1.8
                    ),
                    fill="tozeroy",
                    fillcolor="rgba(229,160,0,0.10)"
                )

                fig.update_layout(
                    showlegend=False
                )

                c2.plotly_chart(
                    fig,
                    use_container_width=True
                )

            else:

                c2.info(
                    "Không có dữ liệu ánh sáng "
                    "trong khoảng này."
                )


    # ------------------------------------------------------------
    # TAB 2
    # ------------------------------------------------------------

    with tab2:

        if lat.empty:

            st.info(
                "Chưa có dữ liệu độ trễ. "
                "Trường latency_ms do collector.py "
                "ghi vào iot_raw."
            )

        else:

            s = st.columns(5)

            s[0].metric(
                "Trung bình",
                f"{lat.mean():.0f} ms"
            )

            s[1].metric(
                "p50",
                f"{np.percentile(lat, 50):.0f} ms"
            )

            s[2].metric(
                "p95",
                f"{np.percentile(lat, 95):.0f} ms"
            )

            s[3].metric(
                "p99",
                f"{np.percentile(lat, 99):.0f} ms"
            )

            s[4].metric(
                "Lớn nhất",
                f"{lat.max():.0f} ms"
            )

            st.write("")

            a, b = st.columns([3, 2])

            fig = base_fig(
                "Độ trễ đầu cuối theo thời gian",
                "ms",
                320
            )

            fig.add_scatter(
                x=lat.index,
                y=lat,
                mode="lines",
                name="latency_ms",
                line=dict(
                    color=C_ROLL,
                    width=1.6
                )
            )

            fig.add_hline(
                y=float(
                    np.percentile(
                        lat,
                        95
                    )
                ),
                line_dash="dot",
                line_color=C_BAD,
                annotation_text="p95",
                annotation_position="top left"
            )

            fig.update_layout(
                showlegend=False
            )

            a.plotly_chart(
                fig,
                use_container_width=True
            )

            hist = base_fig(
                "Phân bố độ trễ",
                "số mẫu",
                320
            )

            hist.add_histogram(
                x=lat,
                nbinsx=30,
                marker_color=C_ROLL,
                name=""
            )

            hist.update_layout(
                showlegend=False,
                bargap=0.05,
                xaxis_title="ms"
            )

            b.plotly_chart(
                hist,
                use_container_width=True
            )

            if (lat < 0).any():

                st.warning(
                    "Có độ trễ âm: đồng hồ thiết bị "
                    "và máy chạy collector đang lệch nhau. "
                    "Hãy đồng bộ NTP cho cả hai."
                )


        st.write("")

        total = len(raw)

        n_out = (
            int(
                iqr_outliers(
                    raw["temperature"].dropna()
                ).sum()
            )
            if (
                "temperature" in raw
                and total >= 8
            )
            else 0
        )

        n_proc = (
            int(
                proc["outlier_count"].sum()
            )
            if "outlier_count" in proc
            else 0
        )

        q = st.columns(5)

        q[0].metric(
            "Số mẫu thô",
            f"{total}"
        )

        q[1].metric(
            "Gói mất",
            f"{lost}"
        )

        q[2].metric(
            "Tỷ lệ mất",
            (
                f"{100 * lost / (total + lost):.1f} %"
                if total + lost
                else "—"
            )
        )

        q[3].metric(
            "Outlier trong dữ liệu thô",
            f"{n_out}"
        )

        q[4].metric(
            "Outlier đã xử lý",
            f"{n_proc}"
        )


    # ------------------------------------------------------------
    # TAB 3
    # ------------------------------------------------------------

    with tab3:

        src = st.radio(
            "Nguồn",
            [
                "Dữ liệu thô",
                "Đã xử lý"
            ],
            horizontal=True
        )

        df = (
            raw
            if src == "Dữ liệu thô"
            else proc
        )

        if df.empty:

            st.info(
                "Không có dữ liệu."
            )

        else:

            show = (
                df
                .drop(
                    columns=["device_id"],
                    errors="ignore"
                )
                .iloc[::-1]
                .round(2)
            )

            st.dataframe(
                show.head(300),
                use_container_width=True,
                height=420
            )

            st.download_button(
                "Tải CSV",
                show.to_csv().encode("utf-8"),
                file_name=(
                    f"{device}_"
                    f"{'raw' if src == 'Dữ liệu thô' else 'processed'}"
                    ".csv"
                ),
                mime="text/csv"
            )


dashboard()