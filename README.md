<div align="left">

![Raspberry Pi](https://img.shields.io/badge/-Raspberry%20Pi-C51A4A?style=for-the-badge&logo=Raspberry-Pi)
![Linux](https://img.shields.io/badge/-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/-macOS-000000?style=for-the-badge&logo=apple)

# shelltide

An astronomical tide clock for the terminal. Driven by real lunar and solar positions — no API key, no NOAA, no internet required for the tide data itself. A little boat sails across the surface. A flag on a tide pole shows wind direction and speed.


</div>
<img width="827" height="598" alt="Image" src="https://github.com/user-attachments/assets/6e9f36fa-70c7-4d28-8429-008ff90a4840" />
</br>
</br>
Expand the window and watch the water fall. 
<img width="752" height="671" alt="Image" src="https://github.com/user-attachments/assets/13471c18-6375-4f61-bfbe-c38e237aae56" />

## Install

```bash
git clone https://github.com/HorseyofCoursey/shelltide.git && cd shelltide && bash install.sh
```

Then from anywhere:

```bash
shelltide --location "Bar Harbor, ME"
```

## Usage

```bash
# By location name or zip code
shelltide --location "Bar Harbor, ME"
shelltide --location "04609"
shelltide --location "Bristol" --country gb
shelltide --location "Sydney" --country au

# By coordinates
shelltide --lat 44.39 --lon -68.20

# Options
shelltide --location "Galway" --12h          # 12-hour clock + mph wind
shelltide --kiosk --location "Galway"        # HDMI display mode (Pi, requires sudo)

# Testing
shelltide --tide 0.0    # force low tide
shelltide --tide 1.0    # force high tide
shelltide --wind 25     # force 25mph wind
shelltide --wind 20 --winddir 90   # easterly wind

# Press Q or Esc to quit
```

## How it works

Tidal potential is computed from the actual altitude of the Moon and Sun above your horizon using [ephem](https://rhodesmill.org/pyephem/). The two dominant constituents are:

- **M2** — principal lunar semidiurnal (~12h 25m period)
- **S2** — principal solar semidiurnal (~12h period)

This won't match NOAA tables exactly — local harbour geometry isn't modelled — but the astronomical rhythm is real. Spring tides at new and full moon, neap tides at quarters.

Wind data comes from [Open-Meteo](https://open-meteo.com) (no API key required). Location lookup uses [Nominatim/OSM](https://nominatim.org).

## Display

| Element | Description |
|---------|-------------|
| Big clock | Local time for the selected location |
| High / Low | Next high and low tide times (local) |
| Sparkline | Tide curve ±3 hours from now |
| Water level | Fills screen based on current tide |
| Boat | Sails with the wind, speed tied to mph |
| Flag | Direction and speed, animates with wind |
| Pole | Red/white tide marker, visible above waterline |

## Kiosk mode

Runs fullscreen on HDMI via `/dev/tty1`. Stops getty, loads a Unicode font, switches the display. Restores on exit.

```bash
shelltide --kiosk --location "Bar Harbor, ME"
```

## Notes

- Coastal locations give the most meaningful results. shelltide works anywhere but tides are most visible at the coast
- macOS: works in iTerm2 and Terminal.app. Braille gradient characters require a Unicode font (Nerd Font recommended)
- `--kiosk` is Raspberry Pi / Linux only

## Dependencies

- `ephem` — planetary positions (no ephemeris download)
- `drawille` — Braille pixel canvas for wave surface
- `curses` — standard library
- `venv` — creates isolated workspaces for individual projects
- Python 3.8+
- pip 

## Related projects

- [stormshell](https://github.com/HorseyofCoursey/stormshell) — terminal weather display

## Development Inspiration

- https://www.youtube.com/watch?v=vcaPiiFZu2o
