"""기상청 API허브(apihub.kma.go.kr) 초단기실황 연동 및 캠퍼스 미기후 관측 모듈.

기상청 API허브의 단기예보 조회서비스(초단기실황)를 호출하여 실시간 대기 기온(T1H),
습도(REH), 풍속(WSD)을 수집하고, 일사량 추정을 위한 기초 환경 물리 변수로 변환합니다.
"""

from datetime import datetime, timedelta
import math
from typing import Any, Dict, Tuple
import requests
import streamlit as st


def convert_lat_lon_to_kma_grid(lat: float, lon: float) -> Tuple[int, int]:
    """위·경도(WGS84) 좌표를 기상청 Lambert 정각원추도법 격자 좌표(nx, ny)로 변환합니다."""
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (math.pow(sf, sn) * math.cos(slat1)) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = (re * sf) / math.pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = (re * sf) / math.pow(ra, sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
    ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))

    return nx, ny


def _get_base_date_and_time() -> Tuple[str, str]:
    """초단기실황 API 호출용 기준 일자 및 시간을 산출합니다. (매시 45분 이후 최신 생성)"""
    now = datetime.now()
    if now.minute < 45:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now

    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")
    return base_date, base_time


@st.cache_data(ttl=900)
def fetch_realtime_kma_weather(
    lat: float = 36.4675,
    lon: float = 127.1405,
) -> Dict[str, Any]:
    """기상청 API허브 초단기실황 API를 호출하여 기상 관측값을 반환합니다."""
    fallback_data: Dict[str, Any] = {
        "status": "fallback",
        "air_temp_c": 21.0,
        "humidity_pct": 60.0,
        "wind_speed_ms": 1.5,
        "precipitation_type": 0,
        "solar_rad": 0.0,
        "observation_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "nx": 68,
        "ny": 103,
    }

    auth_key = st.secrets.get("KMA_API_KEY")
    if not auth_key:
        fallback_data["message"] = "KMA_API_KEY 미설정으로 기본 표준 기상값을 사용합니다."
        return fallback_data

    nx, ny = convert_lat_lon_to_kma_grid(lat, lon)
    base_date, base_time = _get_base_date_and_time()

    # 기상청 API허브 전용 엔드포인트
    endpoint = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    params = {
        "authKey": auth_key.strip(),  # API허브는 파라미터명이 authKey 입니다.
        "pageNo": "1",
        "numOfRows": "1000",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": str(nx),
        "ny": str(ny),
    }

    try:
        response = requests.get(endpoint, params=params, timeout=5.0)
        if response.status_code != 200:
            fallback_data["message"] = f"기상청 API허브 HTTP 오류 ({response.status_code})"
            return fallback_data

        data = response.json()
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "00":
            fallback_data["message"] = f"기상청 API허브 오류: {header.get('resultMsg')}"
            return fallback_data

        items = data["response"]["body"]["items"]["item"]
        parsed: Dict[str, float] = {}
        for item in items:
            cat = item.get("category")
            val = float(item.get("obsrValue", 0.0))
            parsed[cat] = val

        air_temp = parsed.get("T1H", fallback_data["air_temp_c"])
        humidity = parsed.get("REH", fallback_data["humidity_pct"])
        wind_speed = parsed.get("WSD", fallback_data["wind_speed_ms"])
        pty = int(parsed.get("PTY", 0))

        # 주간 태양 고도 기반 일사량 약식 물리 추정 모델 (심야 시간 0 W/m²)
        current_hour = datetime.now().hour
        if 6 <= current_hour <= 18:
            solar_est = max(0.0, math.sin((current_hour - 6) / 12.0 * math.pi) * 850.0)
            if pty > 0:
                solar_est *= 0.25
        else:
            solar_est = 0.0

        return {
            "status": "success",
            "air_temp_c": round(air_temp, 1),
            "humidity_pct": round(humidity, 1),
            "wind_speed_ms": round(wind_speed, 1),
            "precipitation_type": pty,
            "solar_rad": round(solar_est, 1),
            "observation_time": f"{base_date[:4]}-{base_date[4:6]}-{base_date[6:]} {base_time[:2]}:00",
            "nx": nx,
            "ny": ny,
        }

    except Exception as e:
        fallback_data["message"] = f"기상청 API허브 통신 예외({str(e)})"
        return fallback_data