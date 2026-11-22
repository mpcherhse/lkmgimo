"""Понятное название устройства для списка сеансов: ua-parser (Apache-2.0) + Client Hints
(Chrome «заморозил» версии в User-Agent, точные приходят в Sec-CH-UA-*; их просит заголовок Accept-CH)."""
import re
from functools import lru_cache

ACCEPT_CH = "Sec-CH-UA-Platform-Version, Sec-CH-UA-Model, Sec-CH-UA-Full-Version-List"
BROWSERS = {"Chrome Mobile": "Chrome", "Chrome Mobile iOS": "Chrome", "Chrome Mobile WebView": "WebView", "Mobile Safari": "Safari",
            "Mobile Safari UI/WKWebView": "Safari", "Firefox Mobile": "Firefox", "Firefox iOS": "Firefox", "Yandex Browser": "Яндекс Браузер",
            "YandexSearch": "Яндекс", "Edge Mobile": "Edge", "Opera Mobile": "Opera", "HeadlessChrome": "Chrome без окна",
            "Huawei Browser": "Huawei Browser", "Other": "Браузер"}
BRANDS = {"Google Chrome": "Chrome", "Microsoft Edge": "Edge", "YaBrowser": "Яндекс Браузер", "Yandex": "Яндекс Браузер", "Opera": "Opera",
          "Brave": "Brave", "Vivaldi": "Vivaldi", "Samsung Internet": "Samsung Internet", "HeadlessChrome": "Chrome без окна", "Chromium": "Chromium"}
OSES = {"Mac OS X": "macOS", "Windows": "Windows", "iOS": "iOS", "Android": "Android", "Linux": "Linux", "Ubuntu": "Ubuntu",
        "Chrome OS": "ChromeOS", "HarmonyOS": "HarmonyOS", "Other": ""}
PLATFORMS = {"macOS": "macOS", "Windows": "Windows", "Android": "Android", "Chrome OS": "ChromeOS", "Linux": "Linux", "iOS": "iOS", "HarmonyOS": "HarmonyOS"}
GENERIC_MODELS = {"", "K", "Mac", "Other", "Smartphone", "Generic Smartphone", "Generic Tablet", "iPhone", "iPad"}


@lru_cache(maxsize=512)
def _parse(ua: str):
    try:
        from ua_parser import parse
        return parse(ua)
    except Exception:  # noqa: BLE001 — нет библиотеки или странная строка: название будет общим
        return None


def _hint(headers, name) -> str:
    return (headers.get(name) or "").strip().strip('"')[:100]


def _brand(headers):
    raw = headers.get("sec-ch-ua-full-version-list") or headers.get("sec-ch-ua") or ""
    best = None
    for name, ver in re.findall(r'"([^"]{1,60})";v="([^"]{1,30})"', raw[:600]):
        label = BRANDS.get(name)
        if label and (best is None or best[0] == "Chromium"):
            best = (label, ver.split(".")[0])
    return best


def describe(headers) -> dict:
    """-> {browser, os, model, mobile, label}: «Chrome 151 · macOS 27», «Safari 27 · iOS 27»"""
    ua = (headers.get("user-agent") or "")[:512]
    r = _parse(ua) if ua else None
    browser, version, os_name, os_ver, model = "Браузер", "", "", "", ""
    if r is not None:
        if r.user_agent:
            browser = BROWSERS.get(r.user_agent.family, r.user_agent.family)
            version = r.user_agent.major or ""
        if r.os:
            os_name = OSES.get(r.os.family, r.os.family)
            frozen = os_name in ("macOS", "Windows") or (os_name == "Android" and "; K)" in ua)
            os_ver = "" if frozen else (r.os.major or "")
        if r.device and (r.device.model or "") not in GENERIC_MODELS:
            model = r.device.model
    if "HarmonyOS" in ua or "OpenHarmony" in ua:
        os_name, os_ver = "HarmonyOS", ""
    brand = _brand(headers)
    if brand:
        browser, version = brand
    platform = _hint(headers, "sec-ch-ua-platform")
    if platform:
        os_name = PLATFORMS.get(platform, platform)
    pver = _hint(headers, "sec-ch-ua-platform-version")
    if pver and re.match(r"^\d+(\.\d+)*$", pver):
        major = int(pver.split(".")[0])
        os_ver = ("11" if major >= 13 else "10") if os_name == "Windows" else str(major)
    hint_model = _hint(headers, "sec-ch-ua-model")
    if hint_model:
        model = hint_model
    mobile = headers.get("sec-ch-ua-mobile") == "?1" or os_name in ("Android", "iOS", "HarmonyOS")
    parts = [f"{browser} {version}".strip(), f"{os_name} {os_ver}".strip(), model]
    label = " · ".join(p for p in parts if p)[:120] or "Неизвестное устройство"
    return {"browser": f"{browser} {version}".strip()[:60], "os": f"{os_name} {os_ver}".strip()[:60], "model": model[:60],
            "mobile": mobile, "label": label}
