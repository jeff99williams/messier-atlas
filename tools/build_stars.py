"""Build data/stars.js from the Hipparcos Main Catalogue.

Usage:
    python tools/build_stars.py

By default this fetches the CDS/VizieR I/239 hip_main.dat fixed-width file and
keeps stars with:

 - RA/Dec, Johnson V magnitude, parallax, and parallax error present
 - positive parallax
 - parallax_error / parallax <= 0.5

Output: data/stars.js defining window.STAR_CATALOG = { bright, hipparcos }.
The bright layer is the naked-eye subset (V <= 6.5); hipparcos is the remaining
usable-distance Hipparcos stars.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path


SOURCE_URL = "https://cdsarc.cds.unistra.fr/ftp/I/239/hip_main.dat"
BRIGHT_MAG_LIMIT = 6.5
MAX_RELATIVE_PARALLAX_ERROR = 0.5
LY_PER_PC = 3.26156


def field(line: str, start: int, end: int) -> str:
    """Return a 1-based inclusive fixed-width field."""
    return line[start - 1 : end].strip()


def parse_float(line: str, start: int, end: int) -> float | None:
    raw = field(line, start, end)
    return float(raw) if raw else None


def parse_int(line: str, start: int, end: int) -> int | None:
    raw = field(line, start, end)
    return int(raw) if raw else None


def compact_float(value: float, places: int) -> float:
    rounded = round(value, places)
    return int(rounded) if rounded.is_integer() else rounded


def read_source(source: str) -> list[str]:
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "MessierAtlas/1.0"})
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.read().decode("ascii", errors="replace").splitlines()
    return Path(source).read_text(encoding="ascii", errors="replace").splitlines()


def star_color_index(line: str) -> float | None:
    bv = parse_float(line, 246, 251)
    if bv is not None:
        return compact_float(bv, 2)
    return None


def spectral_type(line: str) -> str:
    return field(line, 436, 447)


def parse_catalog(lines: list[str], max_rel_parallax_error: float) -> tuple[list, list, dict]:
    bright = []
    hipparcos = []
    skipped = {
        "total": 0,
        "missing_core": 0,
        "nonpositive_parallax": 0,
        "large_parallax_error": 0,
    }

    for line in lines:
        skipped["total"] += 1
        hip = parse_int(line, 9, 14)
        vmag = parse_float(line, 42, 46)
        ra = parse_float(line, 52, 63)
        dec = parse_float(line, 65, 76)
        parallax = parse_float(line, 80, 86)
        parallax_error = parse_float(line, 120, 125)
        if None in (hip, vmag, ra, dec, parallax, parallax_error):
            skipped["missing_core"] += 1
            continue
        if parallax <= 0:
            skipped["nonpositive_parallax"] += 1
            continue
        if parallax_error / parallax > max_rel_parallax_error:
            skipped["large_parallax_error"] += 1
            continue

        dist_ly = (1000.0 / parallax) * LY_PER_PC
        base = [
            hip,
            compact_float(ra, 4),
            compact_float(dec, 4),
            compact_float(dist_ly, 2),
            compact_float(vmag, 2),
            star_color_index(line),
        ]
        if vmag <= BRIGHT_MAG_LIMIT:
            hd = parse_int(line, 391, 396)
            bright.append(base + [hd, spectral_type(line)])
        else:
            hipparcos.append(base)

    bright.sort(key=lambda row: (row[4], row[0]))
    hipparcos.sort(key=lambda row: row[0])
    return bright, hipparcos, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE_URL, help="Local hip_main.dat path or URL")
    parser.add_argument(
        "--max-relative-parallax-error",
        type=float,
        default=MAX_RELATIVE_PARALLAX_ERROR,
        help="Keep stars with e_Plx / Plx at or below this value",
    )
    args = parser.parse_args()

    lines = read_source(args.source)
    bright, hipparcos, skipped = parse_catalog(lines, args.max_relative_parallax_error)

    payload = {
        "meta": {
            "source": "CDS/VizieR I/239 hip_main.dat, Hipparcos Main Catalogue",
            "source_url": SOURCE_URL,
            "distance_rule": (
                "dist_ly = 3261.56 / Plx(mas); Plx > 0; "
                f"e_Plx / Plx <= {args.max_relative_parallax_error:g}"
            ),
            "bright_mag_limit": BRIGHT_MAG_LIMIT,
            "columns_bright": ["hip", "ra", "dec", "dist_ly", "mag", "bv", "hd", "spectral"],
            "columns_hipparcos": ["hip", "ra", "dec", "dist_ly", "mag", "bv"],
            "bright_count": len(bright),
            "hipparcos_count": len(hipparcos),
            "source_records": skipped["total"],
            "skipped": skipped,
        },
        "bright": bright,
        "hipparcos": hipparcos,
    }

    out = Path(__file__).resolve().parent.parent / "data" / "stars.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    out.write_text(
        "// Generated by tools/build_stars.py from CDS/VizieR I/239 hip_main.dat\n"
        "// bright: naked-eye Hipparcos stars (V <= 6.5) with usable parallax\n"
        "// hipparcos: remaining Hipparcos stars with usable parallax\n"
        f"window.STAR_CATALOG={text};\n",
        encoding="ascii",
    )
    print(f"wrote {out}")
    print(f"bright stars: {len(bright):,}")
    print(f"hipparcos remainder: {len(hipparcos):,}")
    print(f"usable total: {len(bright) + len(hipparcos):,}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
