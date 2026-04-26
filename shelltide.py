#!/usr/bin/env python3
"""
shelltide — astronomical tide visualiser.

Usage:
  python3 shelltide.py [--lat LAT] [--lon LON] [--kiosk] [--interval SECS]

  --kiosk   Takes over HDMI TTY1, restores on exit. Requires sudo.
  Press Q or Esc to quit in normal mode.
"""

import curses
import argparse
import time
import signal
import os
import sys
import atexit
import subprocess
import threading
from datetime import datetime, timezone

import astronomy
import render

_resize_flag = False


def handle_resize(signum, frame):
    global _resize_flag
    _resize_flag = True


_wind_result  = None
_wind_lock    = threading.Lock()

def _wind_thread(lat, lon, interval):
    """Fetch wind in background, never blocks main loop."""
    global _wind_result
    while True:
        try:
            result = astronomy.fetch_wind(lat, lon)
            with _wind_lock:
                _wind_result = result
        except Exception:
            pass
        time.sleep(interval)


def main(stdscr, lat, lon, kiosk, interval, tide_override=None, wind_override=None, wind_dir=180.0, kiosk_display=False):
    global _resize_flag

    signal.signal(signal.SIGWINCH, handle_resize)
    curses.curs_set(0)
    stdscr.nodelay(True)

    render.init_colors()

    # start wind fetch thread
    wt = threading.Thread(target=_wind_thread, args=(lat, lon, 60),
                          daemon=True)
    wt.start()

    tick       = 0.0
    last_astro = 0.0
    tide_data  = {}

    while True:
        now = time.monotonic()

        if now - last_astro >= 30 or not tide_data:
            dt = datetime.now(timezone.utc)
            try:
                td                = astronomy.tidal_potential(lat, lon, dt)
                td['phase']       = astronomy.moon_phase(dt)
                td['phase_glyph'] = astronomy.moon_phase_glyph(td['phase'])
                td['phase_name']  = astronomy.moon_phase_name(td['phase'])
                td['lat']         = lat
                td['lon']         = lon
                td['location']    = location_name
                td['tides']       = astronomy.next_high_low(lat, lon, dt)
                # direction and spring_neap — reuse from last if recent
                if tide_data:
                    td['direction']   = tide_data.get('direction', 'slack')
                    td['spring_neap'] = tide_data.get('spring_neap', 0.5)
                else:
                    td['direction']   = astronomy.tide_direction(lat, lon, dt)
                    td['spring_neap'] = astronomy.spring_neap_factor(dt)
                # slow extras every 5 minutes
                if now - last_astro > 300 or not tide_data:
                    td['direction']   = astronomy.tide_direction(lat, lon, dt)
                    td['spring_neap'] = astronomy.spring_neap_factor(dt)
                # wind updated live from thread each frame below
                # override combined to a fixed level for testing
                if tide_override is not None:
                    td['combined'] = (tide_override * 2.0) - 1.0
                tide_data         = td
            except Exception:
                pass
            last_astro = now

        if _resize_flag:
            _resize_flag = False

        if tide_data:
            tide_data['use_12h'] = args.use_12h
            tide_data['kiosk']   = kiosk or args._kiosk_display
            # inject latest wind reading every frame (or override for testing)
            if wind_override is not None:
                from astronomy import fetch_wind as _fw
                dirs = ['N','NE','E','SE','S','SW','W','NW']
                dstr = dirs[round(wind_dir / 45) % 8]
                bf = 0
                m = wind_override
                if   m <  1: bf=0
                elif m <  4: bf=1
                elif m <  8: bf=2
                elif m < 13: bf=3
                elif m < 19: bf=4
                elif m < 25: bf=5
                elif m < 32: bf=6
                else:        bf=7
                tide_data['wind'] = {
                    'speed_mph': wind_override,
                    'direction_deg': wind_dir,
                    'direction_str': dstr,
                    'beaufort': bf,
                }
            else:
                with _wind_lock:
                    tide_data['wind'] = _wind_result
            render.render_frame(stdscr, tide_data, tick, kiosk or kiosk_display)

        tick += 0.03

        if not kiosk:
            key = stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
        else:
            stdscr.getch()

        time.sleep(0.05)


def parse_args():
    p = argparse.ArgumentParser(description='shelltide — astronomical tide visualiser')
    p.add_argument('--location', type=str,   default=None,
                   help='Place name or zip code (e.g. "Bar Harbor, ME" or "04609")')
    p.add_argument('--country',  type=str,   default='',
                   help='ISO country code to narrow search (e.g. gb, ie, au)')
    p.add_argument('--lat',      type=float, default=None)
    p.add_argument('--lon',      type=float, default=None)
    p.add_argument('--kiosk',    action='store_true',
                   help='Take over HDMI TTY1 display (requires sudo)')
    p.add_argument('--interval', type=float, default=None)
    p.add_argument('--tide',     type=float, default=None,
                   help='Override tide level 0.0 (low) to 1.0 (high) for testing')
    p.add_argument('--wind',     type=float, default=None,
                   help='Override wind speed in mph for testing (e.g. --wind 25)')
    p.add_argument('--winddir',  type=float, default=180.0,
                   help='Wind direction in degrees for testing (default 180=S, flag blows N/right)')
    p.add_argument('--12h',      action='store_true', dest='use_12h',
                   help='Display clock in 12-hour format')
    p.add_argument('--_tty_mode',      action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--_kiosk_display', action='store_true', help=argparse.SUPPRESS)
    return p.parse_args()


def restore_tty():
    subprocess.run(['systemctl', 'start', 'getty@tty1'], capture_output=True)


if __name__ == '__main__':
    args = parse_args()
    ivl  = args.interval or (5.0 if args.kiosk else 2.0)

    # Resolve location
    lat, lon, location_name = args.lat, args.lon, ''
    if args.location:
        try:
            print(f'Looking up {args.location}...')
            lat, lon, location_name = astronomy.resolve_location(args.location, args.country)
            print(f'Found: {location_name} ({lat:.4f}, {lon:.4f})')
        except Exception as e:
            print(f'Error: {e}')
            sys.exit(1)
    elif lat is None:
        lat, lon, location_name = 53.27, -9.05, 'Galway Bay'
    else:
        location_name = f'{lat:.2f}, {lon:.2f}'

    if args.kiosk:
        # Re-launch with sudo if not root
        if os.geteuid() != 0:
            os.execvp('sudo', ['sudo', sys.executable] + sys.argv)
            sys.exit(0)

        FONT = '/usr/share/consolefonts/Uni2-TerminusBold28x14.psf.gz'
        TTY  = '/dev/tty1'

        atexit.register(restore_tty)
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

        subprocess.run(['systemctl', 'stop',  'getty@tty1'], capture_output=True)
        subprocess.run(['setfont', FONT, '-C', TTY],         capture_output=True)
        subprocess.run(['chvt', '1'],                        capture_output=True)
        time.sleep(0.3)

        child_args = [a for a in sys.argv[1:] if a != '--kiosk']
        child_args.append('--_tty_mode')
        child_args.append('--_kiosk_display')

        tty_fh = open(TTY, 'wb', buffering=0)
        os.environ['TERM'] = 'linux'

        errlog = '/tmp/shelltide.log'
        try:
            with open(errlog, 'wb') as err_fh:
                subprocess.run(
                    [sys.executable, os.path.abspath(__file__)] + child_args,
                    stdin=None,
                    stdout=tty_fh,
                    stderr=err_fh,
                )
        except KeyboardInterrupt:
            pass
        finally:
            tty_fh.close()

        try:
            err = open(errlog).read().strip()
            if err:
                print(f'\n  shelltide error:\n{err}\n')
        except Exception:
            pass

        restore_tty()
        print('\n  shelltide closed. TTY1 restored.\n')

    else:
        if args._tty_mode:
            os.environ.setdefault('TERM', 'linux')
        try:
            curses.wrapper(main, lat, lon, args.kiosk, ivl, args.tide, args.wind, args.winddir, args._kiosk_display)
        except KeyboardInterrupt:
            pass
