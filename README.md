# Messier Atlas

**Live site: <https://yourcio.ca/messier-atlas/>**

An interactive 3D map of all 110 Messier objects, rendered in the browser with
[Three.js](https://threejs.org/). The Sun sits at the origin; every object is
placed in its true direction on the sky (J2000 coordinates rotated into the
galactic frame, so the Milky Way's plane is horizontal) at a **log-compressed
distance** — each concentric ring is 10× farther than the last, from 1,000
light-years out to 100 million.

Because the positions are real, the map shows genuine structure: open clusters
hug the galactic plane, globular clusters swarm in a halo around the galactic
centre, and most of the catalogue's galaxies bunch toward the north galactic
pole in the direction of the Virgo Cluster.

## Features

- Rotate (drag), zoom (scroll, toward cursor), pan (right-drag)
- Hover any object for a quick tooltip; click it to fly the camera there and
  open an info panel with photo, type, distance, constellation, magnitude,
  apparent size, position, and a link to its Wikipedia article
- Search by Messier number, common name, type, NGC number, or constellation
- Legend toggles to show/hide categories (galaxies, globulars, open clusters…)
- Deep links: `index.html#m31` opens with Andromeda selected
- Sun and Galactic Centre markers, procedural starfield with a Milky Way band

## Running it

Everything is client-side static files. Either:

- **Double-click `index.html`** (needs internet access for the Three.js CDN and
  Wikimedia photos), or
- serve the folder if your browser is strict about `file://` pages:

  ```
  python -m http.server 8123
  ```

  then open <http://localhost:8123>.

It can be hosted anywhere static files go (GitHub Pages, Azure Static Web
Apps, etc.) — there is no backend.

## Data

`data/messier.js` holds all 110 objects (positions, distances, types,
magnitudes, image URLs) and is generated from Wikipedia's
[List of Messier objects](https://en.wikipedia.org/wiki/List_of_Messier_objects):

```
curl.exe -sL "https://en.wikipedia.org/wiki/List_of_Messier_objects" -o messier_list.html
python tools/build_data.py messier_list.html
```

Distances are catalogue midpoints in thousands of light-years. Photos are
hotlinked from Wikimedia Commons at standard thumbnail sizes (Wikimedia only
serves 120/250/330/500px buckets and refuses to upscale small originals —
`tools/build_data.py` handles both rules).

## Files

| Path                 | Purpose                                      |
| -------------------- | -------------------------------------------- |
| `index.html`         | The whole app: scene, UI, styles, logic      |
| `data/messier.js`    | Generated catalogue (`window.MESSIER = […]`) |
| `tools/build_data.py`| Regenerates `data/messier.js` from Wikipedia |

## Ideas for later

- Constellation boundaries / lines for orientation
- NGC catalogue or bright-star (Gaia/Hipparcos) layers
- A true-scale mode with camera flythrough
- Distance-uncertainty visualization (some Messier distances are rough)
