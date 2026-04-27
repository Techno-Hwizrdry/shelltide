"""
astronomy.py — tidal potential from real lunar/solar positions via ephem.
No ephemeris file download required. Works offline after pip install ephem.
"""

import math
import ephem
from datetime import datetime, timezone, timedelta


def _observer_at(lat_deg, lon_deg, dt):
    obs = ephem.Observer()
    obs.lat = math.radians(lat_deg)
    obs.lon = math.radians(lon_deg)
    obs.elevation = 0
    obs.pressure = 0
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    obs.date = ephem.Date(dt)
    return obs


def tidal_potential(lat_deg, lon_deg, dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    obs = _observer_at(lat_deg, lon_deg, dt)
    moon = ephem.Moon(obs)
    sun = ephem.Sun(obs)
    moon_alt = float(moon.alt)
    sun_alt = float(sun.alt)
    moon_z = math.pi / 2 - moon_alt
    sun_z = math.pi / 2 - sun_alt
    lunar_raw = 1.5 * math.cos(moon_z)**2 - 0.5
    solar_raw = (1.0 / 2.17) * (1.5 * math.cos(sun_z)**2 - 0.5)
    max_combined = 1.0 + (1.0 / 2.17)
    combined = (lunar_raw + solar_raw) / max_combined
    return {
        'lunar': lunar_raw,
        'solar': solar_raw,
        'combined': combined,
        'moon_alt_deg': math.degrees(moon_alt),
        'sun_alt_deg': math.degrees(sun_alt),
        'moon_az_deg': math.degrees(float(moon.az)),
        'dt': dt,
    }


def moon_phase(dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    m = ephem.Moon()
    dt_naive = dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    m.compute(ephem.Date(dt_naive))
    return m.phase / 100.0


def moon_phase_glyph(phase):
    glyphs = ['🌑','🌒','🌓','🌔','🌕','🌖','🌗','🌘']
    return glyphs[int(phase * 8) % 8]


def moon_phase_name(phase):
    names = [
        (0.03, 'New Moon'), (0.22, 'Waxing Crescent'), (0.28, 'First Quarter'),
        (0.47, 'Waxing Gibbous'), (0.53, 'Full Moon'), (0.72, 'Waning Gibbous'),
        (0.78, 'Last Quarter'), (0.97, 'Waning Crescent'), (1.01, 'New Moon'),
    ]
    for threshold, name in names:
        if phase <= threshold:
            return name
    return 'New Moon'


def tide_direction(lat_deg, lon_deg, dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    past = dt - timedelta(minutes=10)
    now_val = tidal_potential(lat_deg, lon_deg, dt)['combined']
    past_val = tidal_potential(lat_deg, lon_deg, past)['combined']
    delta = now_val - past_val
    if delta > 0.001:
        return 'rising'
    elif delta < -0.001:
        return 'falling'
    return 'slack'


def spring_neap_factor(dt=None):
    if dt is None:
        dt = datetime.now(timezone.utc)
    dt_naive = dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt
    date = ephem.Date(dt_naive)
    moon = ephem.Moon(date)
    sun = ephem.Sun(date)
    sep = abs(float(moon.hlong) - float(sun.hlong))
    if sep > math.pi:
        sep = 2 * math.pi - sep
    return math.cos(sep / 2)**2


if __name__ == '__main__':
    lat, lon = 53.27, -9.05
    result = tidal_potential(lat, lon)
    print(f"Lunar:     {result['lunar']:+.4f}")
    print(f"Solar:     {result['solar']:+.4f}")
    print(f"Combined:  {result['combined']:+.4f}")
    phase = moon_phase()
    print(f"Phase:     {phase:.3f}  {moon_phase_glyph(phase)}  {moon_phase_name(phase)}")
    print(f"Direction: {tide_direction(lat, lon)}")
    print(f"Spring/neap: {spring_neap_factor():.3f}")


def fetch_wind(lat_deg: float, lon_deg: float, use_mph: bool = False) -> dict:
    """
    Fetch current wind speed and direction from Open-Meteo.
    Returns dict with speed, unit, direction_deg, direction_str, beaufort.
    Falls back to None on any error.
    """
    import urllib.request
    import urllib.parse
    import json

    wind_unit = 'mph' if use_mph else 'kmh'
    params = urllib.parse.urlencode({
        'latitude':        lat_deg,
        'longitude':       lon_deg,
        'current':         'wind_speed_10m,wind_direction_10m',
        'wind_speed_unit': wind_unit,
        'timezone':        'auto',
        'forecast_days':   1,
    })
    try:
        req = urllib.request.Request(
            f'https://api.open-meteo.com/v1/forecast?{params}',
            headers={'User-Agent': 'shelltide/1.0'}
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        c     = data['current']
        speed = float(c.get('wind_speed_10m', 0))
        deg   = float(c.get('wind_direction_10m', 0))

        # Cardinal direction the wind is blowing TO (flag points this way)
        dirs  = ['N','NE','E','SE','S','SW','W','NW']
        dstr  = dirs[round(deg / 45) % 8]

        # Beaufort scale
        if   speed <  1: bf = 0
        elif speed <  4: bf = 1
        elif speed <  8: bf = 2
        elif speed < 13: bf = 3
        elif speed < 19: bf = 4
        elif speed < 25: bf = 5
        elif speed < 32: bf = 6
        else:            bf = 7

        utc_offset = int(data.get('utc_offset_seconds', 0))

        speed_mph = speed if use_mph else speed * 0.621371

        return {
            'speed':         speed,
            'speed_mph':     speed_mph,
            'unit':          'mph' if use_mph else 'km/h',
            'direction_deg': deg,
            'direction_str': dstr,
            'beaufort':      bf,
            'utc_offset':    utc_offset,
        }
    except Exception:
        return None


def next_high_low(lat_deg: float, lon_deg: float, dt=None) -> dict:
    """
    Find the next high and low tide times by sampling tidal potential
    at 10-minute intervals over the next 13 hours (covers one full M2 cycle).
    Returns dict with 'high' and 'low' as datetime objects (UTC).
    """
    from datetime import timedelta

    if dt is None:
        dt = datetime.now(timezone.utc)

    # Sample every 10 minutes for 13 hours
    samples = []
    for i in range(79):
        t = dt + timedelta(minutes=i * 10)
        val = tidal_potential(lat_deg, lon_deg, t)['combined']
        samples.append((t, val))

    # Find direction at start
    current = samples[0][1]
    next_val = samples[1][1]
    rising = next_val > current

    next_high = None
    next_low  = None

    for i in range(1, len(samples) - 1):
        prev_v = samples[i-1][1]
        curr_v = samples[i][1]
        next_v = samples[i+1][1]
        # local maximum
        if curr_v >= prev_v and curr_v >= next_v and next_high is None:
            if not rising or i > 1:
                next_high = samples[i][0]
        # local minimum
        if curr_v <= prev_v and curr_v <= next_v and next_low is None:
            if rising or i > 1:
                next_low = samples[i][0]
        if next_high and next_low:
            break

    return {'high': next_high, 'low': next_low}


def resolve_location(location: str, country: str = '') -> tuple:
    """
    Resolve a place name or zip code to (lat, lon, display_name).
    Uses Nominatim/OSM — no API key required.
    """
    import urllib.request
    import urllib.parse
    import json

    def _search(params):
        params.update({'format': 'json', 'limit': 1, 'addressdetails': 1})
        req = urllib.request.Request(
            'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(params),
            headers={'User-Agent': 'shelltide/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    data = []

    # Try postal code first
    p = {'postalcode': location}
    if country:
        p['country'] = country
    elif location.replace(' ', '').isdigit():
        p['country'] = 'us'
    try:
        data = _search(p)
    except Exception:
        pass

    # Try city name with country
    if not data and country:
        try:
            data = _search({'q': location, 'countrycodes': country})
        except Exception:
            pass

    # Try global city name
    if not data and not location.replace(' ', '').isdigit():
        try:
            data = _search({'q': location})
        except Exception:
            pass

    if not data:
        raise ValueError(f"Could not find '{location}'. Try a city name, zip code, or add --country CC.")

    item = data[0]
    addr = item.get('address', {})
    city = (addr.get('city') or addr.get('town') or addr.get('village')
            or addr.get('municipality') or addr.get('county')
            or addr.get('state') or location)

    return float(item['lat']), float(item['lon']), city
