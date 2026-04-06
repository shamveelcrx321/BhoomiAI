"""
this file fetches all data for bhoomiai
it gets weather, air quality, map details and population data
we use multiple sources so it does not fail
"""

import os
import re
import math
import asyncio
import aiohttp
import json
import random
import logging
from bs4 import BeautifulSoup
import trafilatura
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

RADIUS_KM = 15

# use different browser names so websites do not block our requests
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

def _rand_ua() -> str:
    return random.choice(_USER_AGENTS)

def _browser_headers(referer: str = "https://www.google.com/") -> dict:
    return {
        "User-Agent": _rand_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
        "Referer": referer,
        "DNT": "1",
    }

_API_HEADERS = {
    "User-Agent": "BhoomiAI/2.0 (research tool; contact@bhoomi.ai)",
    "Accept": "application/json",
}

# helper functions to download data from internet

async def _get_json(url: str, params: dict = None, timeout: int = 12) -> dict | None:
    try:
        async with aiohttp.ClientSession(headers=_API_HEADERS) as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                r.raise_for_status()
                return await r.json(content_type=None)
    except Exception as e:
        logger.debug(f"[JSON GET] {url} \u2192 {e}")
        return None

async def _get_html(url: str, referer: str = "https://www.google.com/", timeout: int = 15) -> str | None:
    try:
        async with aiohttp.ClientSession(headers=_browser_headers(referer)) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as r:
                if r.status == 200:
                    return await r.text(errors="replace")
                return None
    except Exception as e:
        logger.debug(f"[HTML GET] {url} \u2192 {e}")
        return None

async def _post_html(url: str, data: dict, referer: str = "https://duckduckgo.com/", timeout: int = 15) -> str | None:
    try:
        async with aiohttp.ClientSession(headers=_browser_headers(referer)) as session:
            async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
                if r.status == 200:
                    return await r.text(errors="replace")
                return None
    except Exception as e:
        logger.debug(f"[HTML POST] {url} \u2192 {e}")
        return None

async def _overpass(query: str, timeout: int = 35) -> dict | None:
    try:
        async with aiohttp.ClientSession(headers=_API_HEADERS) as session:
            async with session.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": query},
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as r:
                r.raise_for_status()
                return await r.json(content_type=None)
    except Exception as e:
        logger.warning(f"[OVERPASS] {e}")
        return None

# logic to convert city name to lat lon coordinates

async def forward_geocode(text_location: str) -> tuple[float | None, float | None]:
    """find coordinates from location name using different apis"""
    # try openstreetmap first
    try:
        data = await _get_json(
            "https://nominatim.openstreetmap.org/search",
            {"q": f"{text_location}, India", "format": "json", "limit": 1},
        )
        if data and len(data) > 0:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except: pass

    # if first fails, try open meteo
    try:
        data = await _get_json(
            "https://geocoding-api.open-meteo.com/v1/search",
            {"name": text_location, "count": 5, "language": "en", "format": "json"}
        )
        if data and data.get("results"):
            # prioritize indian results
            for res in data["results"]:
                if res.get("country_code") == "IN":
                    return res["latitude"], res["longitude"]
            return data["results"][0]["latitude"], data["results"][0]["longitude"]
    except: pass

    # try komoot as last option
    try:
        data = await _get_json(
            "https://photon.komoot.io/api/",
            {"q": f"{text_location} India", "limit": 1}
        )
        if data and data.get("features"):
            coords = data["features"][0]["geometry"]["coordinates"]
            return coords[1], coords[0]
    except: pass

    return None, None

async def get_address(lat: float, lon: float) -> dict | None:
    data = await _get_json(
        "https://nominatim.openstreetmap.org/reverse",
        {"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
    )
    if not data:
        return None
    addr = data.get("address", {})
    return {
        "display": data.get("display_name"),
        "place": addr.get("village") or addr.get("hamlet") or addr.get("suburb") or addr.get("neighbourhood"),
        "village": addr.get("village") or addr.get("hamlet"),
        "road": addr.get("road"),
        "neighbourhood": addr.get("neighbourhood"),
        "town": addr.get("town") or addr.get("city"),
        "district": addr.get("state_district") or addr.get("county"),
        "state": addr.get("state"),
        "postcode": addr.get("postcode"),
        "country": addr.get("country"),
    }

# functions to get weather and pollution data

async def get_elevation(lat: float, lon: float) -> float | None:
    # try open elevation api
    data = await _get_json("https://api.open-elevation.com/api/v1/lookup", {"locations": f"{lat},{lon}"})
    if data and data.get("results"):
        return data["results"][0].get("elevation")
    # if that fails try open meteo
    data = await _get_json("https://api.open-meteo.com/v1/elevation", {"latitude": lat, "longitude": lon})
    if data and data.get("elevation"):
        return data["elevation"][0]
    return None

async def get_climate(lat: float, lon: float) -> dict | None:
    data = await _get_json(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
        },
    )
    return data.get("current") if data else None

async def get_air_quality(lat: float, lon: float) -> dict | None:
    data = await _get_json(
        "https://air-quality-api.open-meteo.com/v1/air-quality",
        {
            "latitude": lat, "longitude": lon,
            "current": "pm10,pm2_5,nitrogen_dioxide,european_aqi",
        },
    )
    return data.get("current") if data else None

async def get_solar(lat: float, lon: float) -> dict | None:
    data = await _get_json(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": lat, "longitude": lon,
            "start_date": "2023-01-01", "end_date": "2023-12-31",
            "daily": "shortwave_radiation_sum",
        },
    )
    return data.get("daily") if data else None

# logic to find nearby facilities and land type

def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

async def get_batched_infrastructure(lat: float, lon: float) -> tuple[dict, dict]:
    r = RADIUS_KM * 1000
    query = f"""
    [out:json][timeout:45];
    (
      way["highway"~"motorway|trunk|primary|secondary|tertiary"](around:{r},{lat},{lon});
      nwr["amenity"~"hospital|clinic|school|college|university|marketplace|bank|atm|pharmacy"](around:{r},{lat},{lon});
      nwr["man_made"~"works|factory"](around:{r},{lat},{lon});
      nwr["landuse"~"industrial|forest|reservoir|farmland"](around:{r},{lat},{lon});
      nwr["railway"~"station"](around:{r},{lat},{lon});
      nwr["aeroway"~"aerodrome"](around:{r},{lat},{lon});
      nwr["power"~"substation|plant"](around:{r},{lat},{lon});
      nwr["natural"~"wood|water|forest|peak|scrub|sand"](around:{r},{lat},{lon});
    );
    out center;
    """
    data = await _overpass(query)
    
    best = {}  # type: dict[str, dict | None]
    for k in ("road", "hospital", "school", "factory_building", "railway_station", "airport", "power_substation", "market"):
        best[k] = None
    terrain_counts = {"forest_wood": 0, "water": 0, "mountain_peak": 0, "farmland": 0}

    if not data or not data.get("elements"):
        return best, terrain_counts

    for el in data["elements"]:
        elat = el.get("lat") or el.get("center", {}).get("lat")
        elon = el.get("lon") or el.get("center", {}).get("lon")
        if not elat: continue
        d = _haversine(lat, lon, elat, elon)
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("name:en") or "Unnamed"
        item = {"name": name, "distance_km": round(d, 3), "lat": elat, "lon": elon, "_d": d}

        def _upd(key):
            if best[key] is None or d < best[key]["_d"]:
                best[key] = item

        if "highway" in tags: _upd("road")
        if tags.get("amenity") in ("hospital", "clinic"): _upd("hospital")
        if tags.get("amenity") in ("school", "college", "university"): _upd("school")
        if "man_made" in tags or tags.get("landuse") == "industrial": _upd("factory_building")
        if tags.get("railway") == "station": _upd("railway_station")
        if tags.get("aeroway") == "aerodrome": _upd("airport")
        if tags.get("power") in ("substation", "plant"): _upd("power_substation")
        if tags.get("amenity") in ("marketplace", "market") or tags.get("shop") == "supermarket": _upd("market")

        nat = tags.get("natural", "")
        lus = tags.get("landuse", "")
        if nat in ("wood", "forest") or lus == "forest": terrain_counts["forest_wood"] += 1
        if nat in ("water", "sand") or lus == "reservoir": terrain_counts["water"] += 1
        if nat in ("peak", "scrub"): terrain_counts["mountain_peak"] += 1
        if lus == "farmland": terrain_counts["farmland"] += 1

    return best, terrain_counts

async def get_landuse(lat: float, lon: float) -> list[str]:
    r = 2000
    query = f'[out:json];(way["landuse"](around:{r},{lat},{lon});relation["landuse"](around:{r},{lat},{lon}););out tags;'
    data = await _overpass(query)
    if not data or not data.get("elements"): return []
    uses = [el.get("tags", {}).get("landuse") for el in data["elements"] if el.get("tags", {}).get("landuse")]
    return list(set(uses))

# logic to fetch wikipedia page content directly to use as AI context

async def get_wikipedia_summary(lat: float, lon: float) -> dict | None:
    geo_data = await _get_json(
        "https://en.wikipedia.org/w/api.php",
        {"action": "query", "list": "geosearch", "gsradius": 5000, "gscoord": f"{lat}|{lon}", "format": "json"},
    )
    if not geo_data or not geo_data.get("query", {}).get("geosearch"):
        return None
    title = geo_data["query"]["geosearch"][0]["title"]
    summary_data = await _get_json(
        "https://en.wikipedia.org/w/api.php",
        {"action": "query", "prop": "extracts", "exintro": True, "explaintext": True, "titles": title, "format": "json"},
    )
    if summary_data and "query" in summary_data:
        for page_id, page in summary_data["query"]["pages"].items():
            extract = page.get("extract", "")
            if extract:
                return {"title": title, "summary": extract[:1500]}
    return None

# logic to get population data from various government and public sites

CENSUS_2011 = {
    ("Kerala",       "Palakkad"):       (2809934,  78.37, 4480,  627),
    ("Kerala",       "Thiruvananthapuram"): (3301427, 93.02, 2192, 1508),
    ("Kerala",       "Ernakulam"):      (3282388,  95.89, 3068, 1070),
    ("Kerala",       "Thrissur"):       (3121200,  94.79, 3032, 1030),
    ("Kerala",       "Kozhikode"):      (3086293,  95.13, 2345, 1317),
    ("Kerala",       "Malappuram"):     (4112920,  93.55, 3550,  1158),
    ("Karnataka",    "Bengaluru Urban"):(9621551,  88.48,  2190, 4378),
    ("Maharashtra",  "Mumbai"):         (12478447, 89.73, 437, 28564),
    ("Maharashtra",  "Pune"):           (9426959,  87.19, 15642, 603),
    ("Tamil Nadu",   "Chennai"):        (7088000,  90.18,  426, 26903),
    ("Delhi",        "New Delhi"):      (11007835, 86.34,  1484, 7411),
}

def _lookup_census(district: str, state: str) -> dict | None:
    if not district or not state: return None
    key = (state, district)
    if key in CENSUS_2011:
        pop, lit, area, density = CENSUS_2011[key]
        return {"population": pop, "literacy": lit, "area": area, "density": density}
    # matching name roughly
    for (s, d), vals in CENSUS_2011.items():
        if s == state and district.lower() in d.lower():
            pop, lit, area, density = vals
            return {"population": pop, "literacy": lit, "area": area, "density": density}
    return None

async def _scrape_censusindia(district: str) -> str | None:
    slug = re.sub(r"[^a-z0-9]+", "-", district.lower()).strip("-")
    url = f"https://www.indiacensus.net/districts/{slug}"
    try:
        async with aiohttp.ClientSession(headers=_browser_headers()) as session:
            async with session.get(url, timeout=10) as r:
                if r.status == 200:
                    html = await r.text()
                    text = trafilatura.extract(html, include_tables=True)
                    return text[:1500] if text else None
    except: pass
    return None

async def _ddg_snippets(query: str) -> str | None:
    html = await _post_html("https://html.duckduckgo.com/html/", {"q": query})
    if not html:
        logger.warning(f"[DDG] No HTML returned for query: {query}")
        return None
    soup = BeautifulSoup(html, "lxml")
    snips = [s.get_text() for s in soup.find_all(class_="result__snippet")[:4]]
    if not snips:
        logger.warning(f"[DDG] No snippets found for query: {query}")
    return " | ".join(snips) if snips else None

async def get_demographics(addr: dict) -> dict:
    district = addr.get("district", "")
    state = addr.get("state", "")
    res = {"source": "none", "text": "Basic demographic data for this district is not yet indexed."}
    
    if not district: return res

    # try internal census data first
    c = _lookup_census(district, state)
    if c:
        text = f"District: {district}. Population (2011): {c['population']:,}. Literacy: {c['literacy']}%. Density: {c['density']}/km2."
        return {"source": "nic_gov_site", "text": text}

    # scrape government census site if internal fails
    web_census = await _scrape_censusindia(district)
    if web_census:
        return {"source": "ddg_page", "text": web_census}

    # search duckduckgo for quick info if all fails
    snip = await _ddg_snippets(f"{district} {state} population literacy census data")
    if snip:
        return {"source": "ddg_snippets", "text": snip}

    return res

async def get_web_context(addr: dict) -> str:
    loc = addr.get("town") or addr.get("district") or "India"
    return await _ddg_snippets(f"{loc} infrastructure development economy news") or "No recent news found."

# main function that brings all data together

async def generate_context_parallel(lat: float, lon: float, **kwargs) -> dict:
    # get address based on location first
    address = await get_address(lat, lon)
    
    # fetch all details at same time to be fast
    tasks = {
        "elevation":   get_elevation(lat, lon),
        "climate":     get_climate(lat, lon),
        "air_quality": get_air_quality(lat, lon),
        "infra_terrain":get_batched_infrastructure(lat, lon),
        "landuse":     get_landuse(lat, lon),
        "wikipedia":   get_wikipedia_summary(lat, lon),
    }
    
    if address:
        tasks["demographics"] = get_demographics(address)
        tasks["web_context"] = get_web_context(address)
    
    keys = list(tasks.keys())
    values = await asyncio.gather(*[tasks[k] for k in keys], return_exceptions=True)
    results = {k: v for k, v in zip(keys, values) if not isinstance(v, Exception)}
    
    infra, terrain = results.get("infra_terrain", ({}, {}))
    
    return {
        "coordinates":    {"lat": lat, "lon": lon},
        "address":        address,
        "elevation_m":    results.get("elevation"),
        "climate":        results.get("climate"),
        "air_quality":    results.get("air_quality"),
        "infrastructure": infra,
        "terrain_counts": terrain,
        "landuse":        results.get("landuse", []),
        "wikipedia":      results.get("wikipedia"),
        "demographics":   results.get("demographics", {}),
        "web_context":    results.get("web_context"),
    }

def context_to_text(ctx: dict) -> str:
    """
    makes simple text out of data dictionary 
    this text will be used as context for ai responses
    """
    lines = [f"### SITE ANALYSIS REPORT: {ctx['coordinates']['lat']}, {ctx['coordinates']['lon']} ###"]
    
    addr = ctx.get("address") or {}
    lines.append(f"Location: {addr.get('display', 'Unknown')}")
    
    if ctx.get("elevation_m"): lines.append(f"Elevation: {ctx['elevation_m']}m")
    
    clim = ctx.get("climate") or {}
    if clim: lines.append(f"Climate: {clim.get('temperature_2m')}C, {clim.get('relative_humidity_2m')}% humidity")

    aq = ctx.get("air_quality") or {}
    if aq: lines.append(f"Air Quality: PM2.5={aq.get('pm2_5')}, AQI={aq.get('european_aqi')}")

    infra = ctx.get("infrastructure") or {}
    lines.append("Infrastructure:")
    for k, v in infra.items():
        if v: lines.append(f"  - {k.title()}: {v['name']} ({v['distance_km']} km)")

    demo = ctx.get("demographics") or {}
    lines.append(f"Demographics ({demo.get('source')}): {demo.get('text')}")
    
    wiki = ctx.get("wikipedia") or {}
    if wiki: lines.append(f"Wikipedia Context: {wiki.get('summary')}")
    
    return "\n".join(lines)