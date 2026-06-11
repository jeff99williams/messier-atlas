"""Build data/messier.js from Wikipedia's "List of Messier objects" page.

Usage:
    curl.exe -sL "https://en.wikipedia.org/wiki/List_of_Messier_objects" -o messier_list.html
    python tools/build_data.py messier_list.html

Output: data/messier.js defining window.MESSIER = [ {...}, x110 ].
Distances are in thousands of light-years (kly), matching the table's sort values.
"""
import html as htmllib
import json
import re
import sys
from pathlib import Path

SOFT_HYPHEN = "­"


def cell_text(cell_html: str) -> str:
    """Strip tags/refs from a table cell and return clean text."""
    # drop a leading attribute remnant like ' data-sort-value="6.5">'
    text = re.sub(r"^\s*[^<>]*>", "", cell_html)
    text = re.sub(r"<[^>]+>", "", text)
    text = htmllib.unescape(text)
    text = text.replace(SOFT_HYPHEN, "")
    text = re.sub(r"\[\d+\]", "", text)  # leftover citation brackets
    return text.strip()


def parse_ra(text: str) -> float:
    m = re.search(r"(\d+)h\s*([\d.]+)m(?:\s*([\d.]+)s)?", text)
    if not m:
        raise ValueError(f"bad RA: {text!r}")
    h, mi = float(m.group(1)), float(m.group(2))
    s = float(m.group(3)) if m.group(3) else 0.0
    return round(15.0 * (h + mi / 60 + s / 3600), 4)


def parse_dec(text: str) -> float:
    # e.g. +22° 00′ 52.2″  or  −14° 48′ 36″ (minus may be U+2212)
    t = text.replace("−", "-").replace(" ", " ")
    m = re.search(r"([+-]?)\s*(\d+)°\s*([\d.]+)[′'](?:\s*([\d.]+)[″\"])?", t)
    if not m:
        raise ValueError(f"bad Dec: {text!r}")
    sign = -1.0 if m.group(1) == "-" else 1.0
    d, mi = float(m.group(2)), float(m.group(3))
    s = float(m.group(4)) if m.group(4) else 0.0
    return round(sign * (d + mi / 60 + s / 3600), 4)


def parse_distance_kly(cell_html: str) -> float:
    m = re.search(r'data-sort-value="([\d.,]+)"', cell_html)
    if m:
        return float(m.group(1).replace(",", ""))
    text = cell_text(cell_html).replace(",", "")
    nums = [float(n) for n in re.findall(r"[\d.]+", text)]
    if not nums:
        raise ValueError(f"bad distance: {text!r}")
    return sum(nums[:2]) / min(len(nums), 2)


def categorize(obj_type: str) -> str:
    t = obj_type.lower()
    if "galaxy" in t:
        return "galaxy"
    if "globular" in t:
        return "globular"
    if "open cluster" in t:
        return "open"
    if "planetary" in t:
        return "planetary"
    if "nebula" in t or "supernova" in t or "h ii" in t:
        return "nebula"
    return "other"  # star cloud, double star, asterism


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "messier_list.html")
    page = src.read_text(encoding="utf-8")

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S)
    objects = []
    for row in rows:
        head = re.match(
            r'\s*<th scope="row"><a href="(/wiki/[^"]+)"[^>]*>M(\d+)</a>', row
        )
        if not head:
            continue
        wiki_path, m_num = head.group(1), int(head.group(2))
        cells = re.findall(r"<td[^>]*>.*?(?=\n<td|\n?</tr>|$)", row, re.S)
        # Columns: NGC | common name | image | type | distance(kly) |
        #          constellation | magnitude | angular size | RA | Dec
        cells = re.split(r"\n<td", row)[1:]
        if len(cells) != 10:
            raise ValueError(f"M{m_num}: expected 10 cells, got {len(cells)}")
        img = ""
        img_m = re.search(r'src="(//upload\.wikimedia\.org/[^"]+)"', cells[2])
        if img_m:
            src = img_m.group(1)
            width_m = re.search(r'data-file-width="(\d+)"', cells[2])
            file_width = int(width_m.group(1)) if width_m else 0
            # Wikimedia only serves standard thumbnail buckets and refuses to
            # upscale, so pick the largest bucket below the source width.
            bucket = next((b for b in (500, 330, 250) if b < file_width), None)
            # TIFF thumbs look like .../lossy-page1-120px-Foo.tif.jpg, so the
            # size token may follow either '/' or another modifier ending in '-'
            img = "https:" + (
                re.sub(r"(?<=[/-])\d+px-", f"{bucket}px-", src, count=1)
                if bucket
                else src
            )
        name = cell_text(cells[1])
        if name in ("—", "-", ""):
            name = ""
        obj_type = cell_text(cells[3])
        mag_text = cell_text(cells[6])
        mag_nums = re.findall(r"[\d.]+", mag_text)
        objects.append(
            {
                "m": m_num,
                "ngc": cell_text(cells[0]),
                "name": name,
                "type": obj_type,
                "cat": categorize(obj_type),
                "dist_kly": parse_distance_kly(cells[4]),
                "const": cell_text(cells[5]),
                "mag": float(mag_nums[0]) if mag_nums else None,
                "size": cell_text(cells[7]),
                "ra": parse_ra(cell_text(cells[8])),
                "dec": parse_dec(cell_text(cells[9])),
                "img": img,
                "wiki": "https://en.wikipedia.org" + wiki_path,
            }
        )

    objects.sort(key=lambda o: o["m"])
    nums = [o["m"] for o in objects]
    assert nums == list(range(1, 111)), f"missing/dup objects: {len(nums)} found"

    out = Path(__file__).resolve().parent.parent / "data" / "messier.js"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(objects, ensure_ascii=False, indent=1)
    out.write_text(
        "// Generated by tools/build_data.py from Wikipedia: List of Messier objects\n"
        "// Fields: m, ngc, name, type, cat, dist_kly (thousands of light-years),\n"
        "//         const, mag, size, ra (deg J2000), dec (deg J2000), img, wiki\n"
        f"window.MESSIER = {payload};\n",
        encoding="utf-8",
    )
    print(f"wrote {out} with {len(objects)} objects")

    # spot-check summary, ASCII only for Windows console
    for n in (1, 13, 31, 42, 45, 87, 104, 110):
        o = objects[n - 1]
        print(
            f"M{o['m']:<3} {o['cat']:<9} {o['dist_kly']:>9} kly  "
            f"{o['const']:<12} mag {o['mag']}  ra {o['ra']:.2f} dec {o['dec']:.2f}"
        )


if __name__ == "__main__":
    main()
