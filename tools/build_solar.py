"""Build data/solar.js - the Sun, planets, Pluto, and major moons.

Static facts and JPL Keplerian elements are tabulated below; positions are
computed live in the browser. The script fetches and bakes two things:

 - lead-image thumbnails from the Wikipedia REST summary API
 - each moon's circular-orbit basis (p/q unit vectors, ecliptic J2000) from a
   JPL Horizons state vector at the J2000 epoch, so the in-browser model
   pos(t) = p*cos(n*dt) + q*sin(n*dt) has the correct plane, phase, and
   direction of motion (including Triton's retrograde orbit)

Usage:
    python tools/build_solar.py

Output: data/solar.js defining window.SOLAR = { sun, planets, moons }.
"""
import json
import math
import re
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "MessierAtlas/1.0 (https://yourcio.ca/messier-atlas/)"}
J2000_JD = 2451545.0

# JPL "Approximate Positions of the Planets" Table 1 (valid 1800-2050 AD).
# [a (AU), a/cy, e, e/cy, I (deg), I/cy, L (deg), L/cy, peri (deg), peri/cy,
#  node (deg), node/cy]   (peri = longitude of perihelion, node = asc. node)
KEPLER = {
    "mercury": [0.38709927, 0.00000037, 0.20563593, 0.00001906,
                7.00497902, -0.00594749, 252.25032350, 149472.67411175,
                77.45779628, 0.16047689, 48.33076593, -0.12534081],
    "venus":   [0.72333566, 0.00000390, 0.00677672, -0.00004107,
                3.39467605, -0.00078890, 181.97909950, 58517.81538729,
                131.60246718, 0.00268329, 76.67984255, -0.27769418],
    "earth":   [1.00000261, 0.00000562, 0.01671123, -0.00004392,
                -0.00001531, -0.01294668, 100.46457166, 35999.37244981,
                102.93768193, 0.32327364, 0.0, 0.0],
    "mars":    [1.52371034, 0.00001847, 0.09339410, 0.00007882,
                1.84969142, -0.00813131, -4.55343205, 19140.30268499,
                -23.94362959, 0.44441088, 49.55953891, -0.29257343],
    "jupiter": [5.20288700, -0.00011607, 0.04838624, -0.00013253,
                1.30439695, -0.00183714, 34.39644051, 3034.74612775,
                14.72847983, 0.21252668, 100.47390909, 0.20469106],
    "saturn":  [9.53667594, -0.00125060, 0.05386179, -0.00050991,
                2.48599187, 0.00193609, 49.95424423, 1222.49362201,
                92.59887831, -0.41897216, 113.66242448, -0.28867794],
    "uranus":  [19.18916464, -0.00196176, 0.04725744, -0.00004397,
                0.77263783, -0.00242939, 313.23810451, 428.48202785,
                170.95427630, 0.40805281, 74.01692503, 0.04240589],
    "neptune": [30.06992276, 0.00026291, 0.00859048, 0.00005105,
                1.77004347, 0.00035372, -55.12002969, 218.45945325,
                44.96476227, -0.32241464, 131.78422574, -0.00508664],
    "pluto":   [39.48211675, -0.00031596, 0.24882730, 0.00005170,
                17.14001206, 0.00004818, 238.92903833, 145.20780515,
                224.06891629, -0.04062942, 110.30393684, -0.01183482],
}

# name, slug, kind, wiki title, color, sprite scale, fly-to distance,
# diameter (km), orbital period (display string)
PLANETS = [
    ("Mercury", "mercury", "planet", "Mercury (planet)", "#b8b5ad", 0.20, 1.8, 4879,   "88.0 days"),
    ("Venus",   "venus",   "planet", "Venus",            "#e8cda2", 0.28, 1.8, 12104,  "224.7 days"),
    ("Earth",   "earth",   "planet", "Earth",            "#6ea8ff", 0.30, 1.8, 12742,  "365.25 days"),
    ("Mars",    "mars",    "planet", "Mars",             "#ff8e63", 0.24, 1.8, 6779,   "687.0 days"),
    ("Jupiter", "jupiter", "planet", "Jupiter",          "#e8b582", 0.52, 2.6, 139820, "11.86 years"),
    ("Saturn",  "saturn",  "planet", "Saturn",           "#f2d49b", 0.46, 2.6, 116460, "29.45 years"),
    ("Uranus",  "uranus",  "planet", "Uranus",           "#9fe3e3", 0.36, 2.2, 50724,  "84.0 years"),
    ("Neptune", "neptune", "planet", "Neptune",          "#6f96ff", 0.36, 2.2, 49244,  "164.8 years"),
    ("Pluto",   "pluto",   "dwarf",  "Pluto",            "#d8c8c0", 0.18, 1.5, 2377,   "247.9 years"),
]

# name, slug, parent slug, wiki title, color, sprite scale, scene offset from
# planet, diameter (km), mean orbit radius (km), period (days),
# Horizons target id, Horizons center  (Earth's Moon uses an in-browser
# series instead of a baked basis, so it has no Horizons ids)
MOONS = [
    ("Moon",     "moon",     "earth",   "Moon",            "#d9dde6", 0.15, 0.26, 3475,   384400, 27.321661, None, None),
    ("Io",       "io",       "jupiter", "Io (moon)",       "#ffd966", 0.12, 0.24, 3643,   421700, 1.769138, "501", "500@599"),
    ("Europa",   "europa",   "jupiter", "Europa (moon)",   "#e8e0cf", 0.11, 0.32, 3122,   671034, 3.551181, "502", "500@599"),
    ("Ganymede", "ganymede", "jupiter", "Ganymede (moon)", "#a89f91", 0.14, 0.40, 5268,   1070412, 7.154553, "503", "500@599"),
    ("Callisto", "callisto", "jupiter", "Callisto (moon)", "#8d8678", 0.13, 0.50, 4821,   1882709, 16.689017, "504", "500@599"),
    ("Titan",    "titan",    "saturn",  "Titan (moon)",    "#e8b45e", 0.14, 0.30, 5150,   1221870, 15.945421, "606", "500@699"),
    ("Triton",   "triton",   "neptune", "Triton (moon)",   "#ecd9d0", 0.12, 0.26, 2707,   354759, 5.876854, "801", "500@899"),
    ("Charon",   "charon",   "pluto",   "Charon (moon)",   "#c0b8b4", 0.10, 0.20, 1212,   19591, 6.387221, "901", "500@999"),
]

THUMB_BUCKETS = (500, 330, 250)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wiki_summary(title: str) -> tuple[str, str]:
    """Return (thumbnail url, canonical page url) for a Wikipedia title."""
    url = ("https://en.wikipedia.org/api/rest_v1/page/summary/"
           + urllib.parse.quote(title.replace(" ", "_")))
    data = fetch_json(url)
    img = ""
    thumb = data.get("thumbnail", {}).get("source", "")
    width = data.get("originalimage", {}).get("width", 0)
    if thumb:
        bucket = next((b for b in THUMB_BUCKETS if b < width), None)
        img = (re.sub(r"(?<=[/-])\d+px-", f"{bucket}px-", thumb, count=1)
               if bucket else thumb)
    page = data.get("content_urls", {}).get("desktop", {}).get("page", "")
    return img, page


def horizons_state(target: str, center: str) -> tuple[list, list]:
    """Position/velocity (km, km/s; ecliptic J2000) of target about center
    at the J2000 epoch."""
    params = {
        "format": "text", "COMMAND": f"'{target}'", "CENTER": f"'{center}'",
        "EPHEM_TYPE": "VECTORS", "VEC_TABLE": "'2'", "REF_PLANE": "ECLIPTIC",
        "REF_SYSTEM": "'J2000'", "TLIST": f"'{J2000_JD}'",
        "OUT_UNITS": "'KM-S'", "CSV_FORMAT": "'YES'", "OBJ_DATA": "'NO'",
    }
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        text = resp.read().decode("utf-8")
    m = re.search(r"\$\$SOE\s*(.+?)\s*\$\$EOE", text, re.S)
    if not m:
        raise ValueError(f"no state vector for {target}:\n{text[:600]}")
    fields = [f.strip() for f in m.group(1).splitlines()[0].split(",")]
    x, y, z, vx, vy, vz = (float(v) for v in fields[2:8])
    return [x, y, z], [vx, vy, vz]


def orbit_basis(r: list, v: list, period_days: float) -> dict:
    """p/q unit vectors spanning the orbit plane: p along r at epoch, q along
    the direction of motion, so phase advances with positive mean motion."""
    rn = math.hypot(*r)
    p = [c / rn for c in r]
    h = [r[1] * v[2] - r[2] * v[1],
         r[2] * v[0] - r[0] * v[2],
         r[0] * v[1] - r[1] * v[0]]
    hn = math.hypot(*h)
    n_hat = [c / hn for c in h]
    q = [n_hat[1] * p[2] - n_hat[2] * p[1],
         n_hat[2] * p[0] - n_hat[0] * p[2],
         n_hat[0] * p[1] - n_hat[1] * p[0]]
    return {
        "p": [round(c, 6) for c in p],
        "q": [round(c, 6) for c in q],
        "n": round(360.0 / period_days, 7),   # deg/day
        "epoch": J2000_JD,
    }


def main() -> None:
    img, page = wiki_summary("Sun")
    sun = {
        "kind": "star", "name": "Sun", "slug": "sun", "color": "#ffd76a",
        "diameter_km": 1391400, "period": "25.4 days (rotation)",
        "img": img, "wiki": page or "https://en.wikipedia.org/wiki/Sun",
    }
    print(f"Sun: img {'ok' if img else 'MISSING'}")

    planets = []
    for name, slug, kind, title, color, scale, fly, diam, period in PLANETS:
        img, page = wiki_summary(title)
        planets.append({
            "kind": kind, "name": name, "slug": slug, "color": color,
            "scale": scale, "flyDist": fly, "diameter_km": diam,
            "period": period, "kepler": KEPLER[slug],
            "img": img, "wiki": page,
        })
        print(f"{name}: img {'ok' if img else 'MISSING'}")

    moons = []
    for (name, slug, parent, title, color, scale, offset, diam, a_km,
         period, hid, hcenter) in MOONS:
        img, page = wiki_summary(title)
        moon = {
            "kind": "moon", "name": name, "slug": slug, "parent": parent,
            "color": color, "scale": scale, "offset": offset,
            "diameter_km": diam, "a_km": a_km, "period_days": period,
            "img": img, "wiki": page,
        }
        if hid:
            r, v = horizons_state(hid, hcenter)
            moon["orbit"] = orbit_basis(r, v, period)
            print(f"{name}: img {'ok' if img else 'MISSING'}, "
                  f"|r| {math.hypot(*r):,.0f} km (mean a {a_km:,.0f})")
        else:
            print(f"{name}: img {'ok' if img else 'MISSING'}, in-browser series")
        moons.append(moon)

    out = Path(__file__).resolve().parent.parent / "data" / "solar.js"
    payload = json.dumps({"sun": sun, "planets": planets, "moons": moons},
                         ensure_ascii=False, indent=1)
    out.write_text(
        "// Generated by tools/build_solar.py\n"
        "// Facts + JPL Keplerian elements (Table 1, 1800-2050 AD) for the planets;\n"
        "// moons carry a circular-orbit basis (p/q, ecliptic J2000) baked from a\n"
        "// JPL Horizons state vector at J2000 so phase and plane are correct.\n"
        f"window.SOLAR = {payload};\n",
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
