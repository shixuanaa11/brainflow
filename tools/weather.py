"""天气工具：Open-Meteo 地理编码 + 天气预报（免费，无需 API Key）"""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from core.logs import get_logger

log = get_logger("weather")

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TZ = timezone(timedelta(hours=8))

DAY_OFFSETS = {"今天": 0, "今日": 0, "明天": 1, "明日": 1, "后天": 2, "大后天": 3}
NOISE_WORDS = (
    "天气", "气温", "温度", "怎么样", "如何", "怎样", "查询", "查一下", "查下",
    "帮我", "帮忙", "看看", "想知道", "请问", "会", "吗", "呢", "的", "一下",
    "下雨", "下雪", "降水", "风力", "风速", "湿度",
)
WMO_DESC = {
    0: "晴", 1: "主要晴朗", 2: "局部多云", 3: "多云",
    45: "雾", 48: "雾凇",
    51: "小毛毛雨", 53: "中毛毛雨", 55: "大毛毛雨",
    56: "冻毛毛雨", 57: "强冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨",
    66: "冻雨", 67: "强冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "雪粒",
    80: "小阵雨", 81: "中阵雨", 82: "大阵雨",
    85: "小阵雪", 86: "大阵雪",
    95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
}


def _http_get(url: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{url}?{qs}", headers={"User-Agent": "BrainFlow/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_day_offset(query: str) -> tuple[str, int]:
    text = query.strip()
    for word, offset in DAY_OFFSETS.items():
        if word in text:
            text = text.replace(word, " ")
            return text, offset
    return text, 0


def _extract_city(query: str) -> str:
    text, _ = _parse_day_offset(query)
    for word in sorted(NOISE_WORDS, key=len, reverse=True):
        text = text.replace(word, " ")
    city = re.sub(r"[\s，,。.!！?？、]+", "", text).strip()
    return city or "北京"


def _wmo_desc(code: int | None) -> str:
    if code is None:
        return "未知"
    return WMO_DESC.get(code, f"代码{code}")


def _geocode(city: str) -> dict:
    data = _http_get(GEO_URL, {"name": city, "count": 1, "language": "zh"})
    results = data.get("results") or []
    if not results:
        raise ValueError(f"未找到城市「{city}」，请换个地名试试")
    hit = results[0]
    name = hit.get("name", city)
    admin = hit.get("admin1") or hit.get("country") or ""
    label = f"{name}（{admin}）" if admin and admin != name else name
    return {
        "label": label,
        "latitude": hit["latitude"],
        "longitude": hit["longitude"],
    }


def _fetch_forecast(lat: float, lon: float) -> dict:
    return _http_get(FORECAST_URL, {
        "latitude": lat,
        "longitude": lon,
        "timezone": "Asia/Shanghai",
        "forecast_days": 4,
        "current": "temperature_2m,relative_humidity_2m,weather_code,precipitation,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
    })


def _day_label(offset: int) -> str:
    day = datetime.now(TZ).date() + timedelta(days=offset)
    if offset == 0:
        return "今天"
    if offset == 1:
        return "明天"
    if offset == 2:
        return "后天"
    return day.strftime("%m月%d日")


def _format_result(city_label: str, query: str, forecast: dict, day_offset: int) -> str:
    daily = forecast.get("daily") or {}
    dates = daily.get("time") or []
    if day_offset >= len(dates):
        raise ValueError("预报天数超出范围，请换个日期试试")

    day_name = _day_label(day_offset)
    date_str = dates[day_offset]
    wx = _wmo_desc((daily.get("weather_code") or [None])[day_offset])
    t_max = (daily.get("temperature_2m_max") or [None])[day_offset]
    t_min = (daily.get("temperature_2m_min") or [None])[day_offset]
    rain_p = (daily.get("precipitation_probability_max") or [None])[day_offset]

    lines = [
        f"【{city_label} · {day_name}（{date_str}）天气】",
        f"天气：{wx}",
        f"气温：{t_min}~{t_max}°C" if t_min is not None and t_max is not None else "气温：暂无",
    ]
    if rain_p is not None:
        lines.append(f"降水概率：{rain_p}%")

    if day_offset == 0:
        cur = forecast.get("current") or {}
        if cur.get("temperature_2m") is not None:
            lines.append(f"当前：{cur['temperature_2m']}°C，{ _wmo_desc(cur.get('weather_code')) }")
        if cur.get("relative_humidity_2m") is not None:
            lines.append(f"湿度：{cur['relative_humidity_2m']}%")
        if cur.get("wind_speed_10m") is not None:
            lines.append(f"风速：{cur['wind_speed_10m']} km/h")

    return "\n".join(lines)


def query_weather(query: str = "", **kwargs) -> str:
    """查询指定城市天气，支持「今天/明天/后天」。"""
    text = (query or kwargs.get("text") or "").strip()
    if not text:
        return "请告诉我你想查哪个城市的天气，例如：深圳今天天气怎么样"

    _, day_offset = _parse_day_offset(text)
    city = _extract_city(text)
    log.info(f"天气查询: city={city}, day_offset={day_offset}, query={text[:80]}")

    try:
        geo = _geocode(city)
        forecast = _fetch_forecast(geo["latitude"], geo["longitude"])
        return _format_result(geo["label"], text, forecast, day_offset)
    except Exception as e:
        log.warning(f"天气查询失败: {e}")
        return f"天气查询失败：{e}"
