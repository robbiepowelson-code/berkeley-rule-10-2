# Where Rule 10.2 Applies

An interactive map of every City of Berkeley zoning district, colored by what **Administrative Regulation 10.2** — the city's rule on personal belongings ("temporary non-commercial objects") on public sidewalks — means in each one: prohibited in residential districts, permitted with strict limits in commercial and manufacturing districts.

- **`index.html`** — the interactive map (self-contained; Leaflet + City of Berkeley GIS data embedded, works offline)
- **`report.html`** — how the map was made: the regulation, the data, the method, and limitations
- **`sites.json`** + **`photos/`** — surveyed sites: geotagged field photos and what the zoning layer says around each
- **`tools/survey_sites.py`** — regenerates the site layer from a folder of geotagged photos (`python3 tools/survey_sites.py --photos ../survey-photos`). Reads GPS, timestamp and heading from EXIF, writes web-sized copies into `photos/`, matches each point to the zoning district it falls in or abuts, and rewrites the `SITES` block in `index.html`. Hand-written `label` and `notes` fields in `sites.json` survive a re-run.

Data: City of Berkeley Community GIS Portal (Land Use Planning service — zoning districts, street centerlines, city boundary), retrieved August 27, 2026. Rule text: [Administrative Regulation 10.2](https://berkeleyca.gov/sites/default/files/documents/Administrative%20Regulation%2010.2.pdf) (rev. January 2025).

A pin marks where a photograph was taken — not a finding that the spot is lawful, available, or usable. This is information, not legal advice, and AR 10.2 is not a camping permit — other city, state, and university rules still apply. Generated with Claude. Not affiliated with the City of Berkeley.
