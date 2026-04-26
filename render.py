"""
render.py — shelltide curses renderer.
Two-phase fill on resize: vertical drip streamers first, then horizontal flood.
"""

import curses
import math
import random
import os

PAIR_SKY    = 1
PAIR_SURF   = 2
PAIR_C_ON_C = 3
PAIR_C_ON_B = 4
PAIR_B_ON_B = 5
PAIR_DEEP   = 6
PAIR_TITLE  = 7
PAIR_STATUS = 8
PAIR_DIM    = 9
PAIR_RISE   = 10
PAIR_FALL   = 11
PAIR_DRIP   = 12
PAIR_B_ON_C = 13   # blue on cyan — bridge between cyan and blue bands
PAIR_W_ON_C = 14   # white on cyan — bright sub-surface zone
PAIR_HEAD   = 15   # yellow on black — boat person's head
PAIR_BOAT_B = 16   # blue on black — boat bracket

GRADIENT = [
    ('⣿', PAIR_C_ON_C, True),   # cyan on cyan bold   — bright upper water
    ('⣿', PAIR_C_ON_C, False),  # cyan on cyan        — upper water
    ('⣿', PAIR_B_ON_C, True),   # blue on cyan bold   — bridge bright
    ('⣿', PAIR_B_ON_C, False),  # blue on cyan        — bridge
    ('⣿', PAIR_C_ON_B, True),   # cyan on blue bold
    ('⣿', PAIR_C_ON_B, False),  # cyan on blue
    ('⣿', PAIR_B_ON_B, True),   # blue on blue bold
    ('⣿', PAIR_B_ON_B, False),  # blue on blue
    (' ',  PAIR_DEEP,   False),  # abyss
]

_prev_h = 0
_prev_w = 0
_spark_cache      = None   # cached (rows, label)
_spark_cache_time = 0.0    # monotonic time of last compute

# vertical drip streamers: [col, row_float, speed, bottom]
_streamers = []

# per-row flood fill: {row: fill_float}  — starts after streamers pass
_flood = {}

# rows that have completed flooding
_filled_rows = set()

# the top of the new space revealed by resize
_new_space_top = 0


def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(PAIR_SKY,    curses.COLOR_BLACK, curses.COLOR_BLACK)
    curses.init_pair(PAIR_SURF,   curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(PAIR_C_ON_C, curses.COLOR_CYAN,  curses.COLOR_CYAN)
    curses.init_pair(PAIR_C_ON_B, curses.COLOR_CYAN,  curses.COLOR_BLUE)
    curses.init_pair(PAIR_B_ON_B, curses.COLOR_BLUE,  curses.COLOR_BLUE)
    curses.init_pair(PAIR_DEEP,   curses.COLOR_BLACK, curses.COLOR_BLUE)
    curses.init_pair(PAIR_TITLE,  curses.COLOR_CYAN,  curses.COLOR_BLACK)
    curses.init_pair(PAIR_STATUS, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(PAIR_DIM,    curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(PAIR_RISE,   curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(PAIR_FALL,   curses.COLOR_RED,   curses.COLOR_BLACK)
    curses.init_pair(PAIR_DRIP,   curses.COLOR_CYAN,  curses.COLOR_BLACK)
    curses.init_pair(PAIR_B_ON_C, curses.COLOR_BLUE,  curses.COLOR_CYAN)
    curses.init_pair(PAIR_W_ON_C, curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(PAIR_HEAD,   curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(PAIR_BOAT_B, curses.COLOR_BLUE,   curses.COLOR_BLACK)


def _dims():
    ts = os.get_terminal_size()
    return ts.lines, ts.columns


def _fill_frac(combined, kiosk=False):
    max_fill = 0.55 if kiosk else 0.65
    return 0.20 + ((combined + 1.0) / 2.0) * max_fill


def _gradient_for_depth(depth_frac):
    # Pin: 0.0 = first entry, 1.0 = last entry, linear in between.
    # Use a small epsilon so depth=1.0 doesn't overshoot the last index.
    n = len(GRADIENT)
    idx = int(depth_frac * (n - 1) + 0.5)
    idx = max(0, min(idx, n - 1))
    ch, pair, bold = GRADIENT[idx]
    attr = curses.color_pair(pair)
    if bold:
        attr |= curses.A_BOLD
    return ch, attr


def _put(stdscr, r, c, s, attr, h, w):
    if r < 0 or r >= h - 1 or c < 0 or c >= w:
        return
    s = s[:w - c]
    if not s:
        return
    try:
        stdscr.addstr(r, c, s, attr)
    except curses.error:
        pass


def _fill_row(stdscr, r, ch, attr, h, w, up_to=None):
    if r < 0 or r >= h - 1:
        return
    n = (w if up_to is None else min(int(up_to), w))
    if n <= 0:
        return
    try:
        if n >= w:
            stdscr.addstr(r, 0, ch * (w - 1), attr)
            stdscr.insstr(r, w - 1, ch, attr)
        else:
            stdscr.addstr(r, 0, ch * n, attr)
    except curses.error:
        pass


def _spawn_fill(old_h, new_h, w):
    """Spawn streamers and reset flood state for newly revealed rows."""
    global _streamers, _flood, _filled_rows, _new_space_top
    _new_space_top = old_h - 1   # first newly visible row

    # vertical streamers — fall slowly so flood fill above keeps up
    count = max(8, w // 4)
    cols  = random.sample(range(w), min(count, w))
    for col in cols:
        speed = random.uniform(0.15, 0.45)   # slow enough that flood stays coherent
        _streamers.append([col, float(old_h - 1), speed, float(new_h - 2)])

    # flood fill entries — one per new row, starts empty
    for r in range(old_h - 1, new_h - 1):
        _flood[r] = 0.0
    _filled_rows -= set(range(old_h - 1, new_h - 1))


def _step(w):
    """Advance streamers and flood fill each frame."""
    global _streamers, _flood, _filled_rows, _new_space_top

    # advance streamers
    alive = []
    for s in _streamers:
        s[1] += s[2]
        if s[1] < s[3]:
            alive.append(s)
    _streamers = alive

    # flood fill: a row starts filling once a streamer has passed through it
    streamer_rows = set(int(s[1]) for s in _streamers)
    # also rows below the lowest streamer head
    if _streamers:
        lowest = max(int(s[1]) for s in _streamers)
    else:
        lowest = -1

    for r in list(_flood.keys()):
        if r in _filled_rows:
            continue
        # this row starts flooding once a streamer has been on it
        row_has_been_dripped = any(
            int(s[1]) >= r or s[1] >= s[3]   # streamer passed through or finished
            for s in _streamers
        ) or (lowest >= r) or (not _streamers and r in _flood)

        if row_has_been_dripped:
            # flood speed: slower for rows further from the top of new space
            speed = random.uniform(w * 0.025, w * 0.06)
            _flood[r] = min(_flood[r] + speed, float(w))
            if _flood[r] >= w:
                _filled_rows.add(r)

    # remove completed rows from _flood so they stop blocking the wave
    for r in list(_filled_rows):
        _flood.pop(r, None)

    # reset new_space_top once all flooding and streamers are done
    if not _streamers and not _flood:
        _new_space_top = 0
        _filled_rows.clear()


def render_frame(stdscr, tide_data, tick, kiosk):
    global _prev_h, _prev_w

    h, w = _dims()
    if h < 4 or w < 8:
        return

    combined    = tide_data.get('combined', 0.0)
    direction   = tide_data.get('direction', 'slack')
    phase_glyph = tide_data.get('phase_glyph', '🌕')
    phase_name  = tide_data.get('phase_name', '')
    spring_neap = tide_data.get('spring_neap', 0.5)
    dt          = tide_data.get('dt')

    frac       = _fill_frac(combined, kiosk=kiosk)
    water_rows = max(2, int(frac * h))
    surface    = h - water_rows
    amp        = max(1, h // 20)   # wave amplitude — needed for foam zone

    # ── detect resize ──────────────────────────────────────────────────────────
    if h != _prev_h or w != _prev_w:
        if h > _prev_h and _prev_h > 0:
            _spawn_fill(_prev_h, h, w)
        curses.resizeterm(h, w)
        stdscr.erase()
        stdscr.refresh()
        _prev_h = h
        _prev_w = w

    _step(w)

    # ── sky ────────────────────────────────────────────────────────────────────
    sky_attr = curses.color_pair(PAIR_SKY)
    for r in range(surface):
        _fill_row(stdscr, r, ' ', sky_attr, h, w)

    # ── water ──────────────────────────────────────────────────────────────────
    wave_profile = []  # populated in wave section below; init here for water fill
    # Compute boat row range for water fill exclusion
    # _boat_cols tracks x range; compute y range from wave surface
    boat_l, boat_r = _boat_cols
    boat_top_r  = 0
    boat_wave_r = 0
    if wave_profile and boat_l < len(wave_profile):
        centre      = min(boat_l + (boat_r - boat_l) // 2, len(wave_profile) - 1)
        boat_wave_r = wave_profile[max(0, centre)]
        boat_top_r  = boat_wave_r - len(BOAT_RIGHT) + 1

    for r in range(surface, h - 1):
        depth    = (r - surface) / max(1, water_rows - 1)
        ch, attr = _gradient_for_depth(depth)

        if r in _flood and r not in _filled_rows:
            _fill_row(stdscr, r, ' ', sky_attr, h, w)
            fill_to = _flood[r]
            if fill_to > 0:
                _fill_row(stdscr, r, ch, attr, h, w, up_to=fill_to)
        else:
            # For rows within boat bounding box, paint around the boat
            if boat_top_r <= r <= boat_wave_r and boat_l < boat_r:
                # left of boat
                if boat_l > 0:
                    try:
                        stdscr.addstr(r, 0, ch * boat_l, attr)
                    except curses.error:
                        pass
                # right of boat
                if boat_r < w - 1:
                    try:
                        stdscr.addstr(r, boat_r, ch * (w - 1 - boat_r), attr)
                        stdscr.insstr(r, w - 1, ch, attr)
                    except curses.error:
                        pass
            else:
                _fill_row(stdscr, r, ch, attr, h, w)

    # ── pole — drawn after water, before wave so wave crests show over it ──
    _draw_pole(stdscr, tide_data, tick, h, w, surface)

    # ── surface wave ──────────────────────────────────────────────────────────
    # Multi-sine Gerstner-style: irrational frequency ratios give
    # non-repeating organic ocean motion.
    wave_attr = curses.color_pair(PAIR_SURF) | curses.A_BOLD
    sky_attr  = curses.color_pair(PAIR_SKY)
    wave_amp  = max(2, amp)

    components = [
        (0.040, 1.20, 1.00),
        (0.071, 2.10, 0.60),
        (0.113, 3.30, 0.35),
        (0.157, 1.70, 0.25),
        (0.029, 0.90, 0.40),
    ]
    total_weight = sum(wt for _, _, wt in components)

    # On slow hardware compute every column — sine is cheap enough
    wave_profile = []
    for c in range(w - 1):
        val = sum(wt * math.sin(c * sf + tick * tf)
                  for sf, tf, wt in components)
        yo = int((val / total_weight) * wave_amp)
        wave_profile.append(surface + yo)
    # Smooth profile: interpolate any single-row gaps for cleaner look
    for c in range(1, len(wave_profile) - 1):
        prev, curr, nxt = wave_profile[c-1], wave_profile[c], wave_profile[c+1]
        if abs(curr - prev) > 1:
            wave_profile[c] = (prev + curr) // 2

    baseline = surface + wave_amp + 1

    # Clear entire wave zone sky in one pass before per-column work —
    # avoids black flash from column-by-column sky clearing during render
    sky_clear_top = max(0, surface - wave_amp - 1)
    pole_col_skip = w - 8   # don't erase the pole column
    for r in range(sky_clear_top, surface):
        # fill left of pole
        if pole_col_skip > 0:
            try:
                stdscr.addstr(r, 0, ' ' * (pole_col_skip), curses.color_pair(PAIR_SKY))
            except curses.error:
                pass
        # fill right of pole
        right_start = pole_col_skip + 1
        if right_start < w - 1:
            try:
                stdscr.addstr(r, right_start, ' ' * (w - 1 - right_start), curses.color_pair(PAIR_SKY))
                stdscr.insstr(r, w - 1, ' ', curses.color_pair(PAIR_SKY))
            except curses.error:
                pass

    for c, wave_r in enumerate(wave_profile):
        if wave_r < 0 or wave_r >= h - 1 or wave_r in _flood:
            continue
        _put(stdscr, wave_r, c, '~', wave_attr, h, w)
        # skip braille fill under the boat so hull doesn't sink into water
        boat_l, boat_r = _boat_cols
        if boat_l <= c < boat_r:
            continue
        for r in range(wave_r + 1, min(baseline + 1, h - 1)):
            if r not in _flood:
                depth    = max(0, (r - surface) / max(1, water_rows - 1))
                ch, attr = _gradient_for_depth(depth)
                _put(stdscr, r, c, ch, attr, h, w)


    # ── boat ─────────────────────────────────────────────────────────────────
    _draw_boat(stdscr, tide_data, wave_profile, h, w, surface, water_rows, wave_amp)

    # ── streamer drips ─────────────────────────────────────────────────────────
    # Only draw streamers on rows that haven't been flooded yet.
    # Use the correct water gradient color as background so no black artifacts.
    for col, row_f, speed, bottom in _streamers:
        r0 = int(row_f)
        for offset in range(5):
            r = r0 - offset
            if r < _new_space_top or r >= h - 1:
                continue
            # skip cells already filled by flood — water color handles those
            if r in _filled_rows:
                continue
            flood_here = _flood.get(r, 0)
            if flood_here > col:
                continue   # this cell already flooded, skip
            # depth-matched background — same pair the water fill would use
            depth        = (r - surface) / max(1, water_rows - 1)
            _, water_attr = _gradient_for_depth(depth)
            ch   = '|' if offset < 2 else ':'
            bold = curses.A_BOLD if offset == 0 else curses.A_DIM
            # render as bright cyan using the water pair's background
            # extract just the bg by using water_attr base + white fg
            # simplest: use A_REVERSE on the water attr so fg/bg flip
            _put(stdscr, r, col, ch, water_attr | bold, h, w)

    # ── status panel ─────────────────────────────────────────────────────────
    _draw_status(stdscr, tide_data, tick, h, w, surface)

    stdscr.refresh()

# ── Big digit glyphs ──────────────────────────────────────────────────────────
_BIG5 = {
    '0': [' ___ ', '|   |', '|   |', '|   |', '|___|'],
    '1': ['     ', '  |  ', '  |  ', '  |  ', '  |  '],
    '2': [' ___ ', '    |', ' ___|', '|    ', '|____'],
    '3': [' ___ ', '    |', ' ___|', '    |', ' ___|'],
    '4': ['     ', '|   |', '|___|', '    |', '    |'],
    '5': [' ____', '|    ', '|___ ', '    |', ' ___|'],
    '6': [' ___ ', '|    ', '|___ ', '|   |', '|___|'],
    '7': [' ____', '    |', '    |', '    |', '    |'],
    '8': [' ___ ', '|   |', '|___|', '|   |', '|___|'],
    '9': [' ___ ', '|   |', '|___|', '    |', ' ___|'],
    ':': ['     ', '  .  ', '     ', '  .  ', '     '],
    ' ': ['     ', '     ', '     ', '     ', '     '],
}

def _render_big(text):
    rows = [''] * 5
    for ch in text:
        g = _BIG5.get(ch, _BIG5[' '])
        for i in range(5):
            rows[i] += g[i]
    return rows


def _sparkline(lat, lon, dt, width=13, spark_h=4):
    from datetime import timedelta
    import astronomy as _astro
    points = []
    half = width // 2
    for i in range(width):
        offset = (i - half) * 0.5
        t  = dt + timedelta(hours=offset)
        td = _astro.tidal_potential(lat, lon, t)
        points.append((td['combined'] + 1.0) / 2.0)
    lo  = min(points)
    hi  = max(points)
    rng = max(0.01, hi - lo)
    rows = []
    for row in range(spark_h):
        threshold = 1.0 - ((row + 0.5) / spark_h)
        line = ''
        for j, p in enumerate(points):
            norm = (p - lo) / rng
            if j == half:
                line += '│' if norm >= threshold else '┆'
            else:
                line += '█' if norm >= threshold else ' '
        rows.append(line)
    label = f'-3h {"now":^{max(1,width-8)}} +3h'
    return rows, label


_spark_cache      = None
_spark_cache_time = 0.0


def _draw_status(stdscr, tide_data, tick, h, w, surface=0):
    # Never render status text below the waterline
    h_cap = min(h, surface) if surface > 6 else h
    combined    = tide_data.get('combined', 0.0)
    direction   = tide_data.get('direction', 'slack')
    phase_glyph = tide_data.get('phase_glyph', '🌕')
    phase_name  = tide_data.get('phase_name', '')
    spring_neap = tide_data.get('spring_neap', 0.5)
    dt          = tide_data.get('dt')
    lat         = tide_data.get('lat', 53.27)
    lon         = tide_data.get('lon', -9.05)
    tide_pct    = int((combined + 1.0) / 2.0 * 100)

    x   = 2
    row = 1

    if h < 8 or w < 30:
        return

    # Big clock — always read current time directly, never from cached tide_data
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    use_12h    = tide_data.get('use_12h', False)
    wind       = tide_data.get('wind')
    utc_offset = wind.get('utc_offset', 0) if wind else 0
    now_local  = _dt.now(_tz.utc) + _td(seconds=utc_offset)
    if use_12h:
        hour     = now_local.hour % 12 or 12
        time_str = f'{hour}:{now_local.strftime("%M")}'
    else:
        time_str = now_local.strftime('%H:%M')
    if h > 10:
        big_rows = _render_big(time_str)
        clk_attr = curses.color_pair(PAIR_TITLE) | curses.A_BOLD
        for i, r in enumerate(big_rows):
            if row + i < h - 1:
                _put(stdscr, row + i, x, r[:w - x - 1], clk_attr, h, w)
        row += 6

    # Next high / low tide times
    tides = tide_data.get('tides')
    if tides and row < h_cap and w > 28:
        def fmt_t(t):
            if t is None: return '--:--'
            from datetime import timezone, timedelta
            local = t.astimezone(timezone.utc) + timedelta(seconds=utc_offset)
            if use_12h:
                hour = local.hour % 12 or 12
                return f'{hour}:{local.strftime("%M")}'
            return local.strftime('%H:%M')
        high_str = fmt_t(tides.get('high'))
        low_str  = fmt_t(tides.get('low'))
        _put(stdscr, row,     x, f'High  {high_str}',
             curses.color_pair(PAIR_RISE)   | curses.A_BOLD, h, w)
        _put(stdscr, row + 1, x, f'Low   {low_str}',
             curses.color_pair(PAIR_FALL)   | curses.A_BOLD, h, w)
        row += 3


    # Sparkline — inline right of clock in kiosk, stacked below in normal mode
    SPARK_H  = 4
    SPARK_W  = 13
    kiosk    = tide_data.get('kiosk', False)
    tall_mode = (not kiosk) and (
        (h > 26) if tide_pct < 60 else (h > surface + 5 + SPARK_H + 8)
    )
    spark_w = SPARK_W if not tall_mode else min(25, w - x - 4)
    if spark_w % 2 == 0:
        spark_w -= 1

    # Only draw if we have coords and time
    if lat and lon:
        from datetime import datetime as _dtnow, timezone as _tzsp
        _dt_now = _dtnow.now(_tzsp.utc)
        try:
            import time as _time
            global _spark_cache, _spark_cache_time
            if (_spark_cache is None or
                    _time.monotonic() - _spark_cache_time > 300 or
                    len(_spark_cache[0][0]) != spark_w):
                _spark_cache = _sparkline(lat, lon, _dt_now, width=spark_w, spark_h=SPARK_H)
                _spark_cache_time = _time.monotonic()
            spark_rows, spark_label = _spark_cache
            spark_attr  = curses.color_pair(PAIR_C_ON_B) | curses.A_BOLD
            marker_attr = curses.color_pair(PAIR_TITLE)  | curses.A_BOLD

            if tall_mode:
                # stacked below clock and high/low
                for sr in spark_rows:
                    if row < h_cap:
                        for ci, ch in enumerate(sr):
                            attr = marker_attr if ch in ('│', '┆') else spark_attr
                            _put(stdscr, row, x + ci, ch, attr, h, w)
                        row += 1
                if row < h_cap:
                    _put(stdscr, row, x, spark_label[:spark_w],
                         curses.color_pair(PAIR_DIM), h, w)
            else:
                # inline: right of big clock, starting row 2
                clock_w = len(_render_big('00:00')[0])
                sx = x + clock_w + 3
                for si, sr in enumerate(spark_rows):
                    r = 2 + si
                    for ci, ch in enumerate(sr):
                        attr = marker_attr if ch in ('│', '┆') else spark_attr
                        _put(stdscr, r, sx + ci, ch, attr, h, w)
                _put(stdscr, 2 + SPARK_H, sx, spark_label[:spark_w],
                     curses.color_pair(PAIR_DIM), h, w)
        except Exception:
            pass



def _draw_pole(stdscr, tide_data, tick, h, w, surface):
    wind     = tide_data.get('wind')
    pole_col = w - 8
    pole_top = 3
    pole_bot = min(h - 2, surface)

    if pole_col < 10 or pole_bot <= pole_top or h < 12:
        return

    # Pole — red/white above waterline only
    for r in range(pole_top, pole_bot):
        if r >= surface:
            break
        attr = (curses.color_pair(PAIR_FALL) | curses.A_BOLD if r % 2 == 0
                else curses.color_pair(PAIR_STATUS) | curses.A_BOLD)
        _put(stdscr, r, pole_col, '┃', attr, h, w)

    if pole_top + 1 >= surface:
        return

    # No wind data yet — bare pole, no flag or labels
    if not wind:
        return

    flag_attr = curses.color_pair(PAIR_RISE) | curses.A_BOLD

    # Wind direction: direction_deg is where wind comes FROM
    # Flag blows away from source: FROM west (270) → flag points east (right)
    # FROM east (90) → flag points west (left)
    right_flag = True
    speed_mph  = 0
    if wind:
        deg       = wind['direction_deg']
        speed_mph = wind['speed_mph']
        # W(270)→left, E(90)→right, N(0/360)→right, S(180)→left
        if 180 < deg <= 360 or deg == 0:
            right_flag = False

    FRAMES_RIGHT = [
        ['-__--_', '-__-- '],
        ['_--__', '_--__-'],
    ]
    # Left frames — read right to left, pole attachment at right end
    # Frame A: '_--__-┃' / '  --__-┃'
    # Frame B: '__--_┃'  / '-__--_┃'
    FRAMES_LEFT = [
        ['_--__-', '  --__-'],
        ['__--_', '-__--_'],
    ]

    # Animation rate tied to wind speed:
    # calm (<5mph): 0.2/tick → slow
    # moderate (5-15mph): 0.5/tick → medium
    # strong (>15mph): 1.0/tick → fast
    if speed_mph < 5:
        anim_rate = 0.4
    elif speed_mph < 15:
        anim_rate = 2.0
    else:
        anim_rate = 2.0

    frames    = FRAMES_RIGHT if right_flag else FRAMES_LEFT
    frame_idx = int(tick * anim_rate) % 2
    frame     = frames[frame_idx]
    row0, row1 = frame
    r0, r1 = pole_top, pole_top + 1

    if right_flag:
        if r0 < surface:
            _put(stdscr, r0, pole_col + 1, row0, flag_attr, h, w)
        if r1 < surface:
            _put(stdscr, r1, pole_col + 1, row1, flag_attr, h, w)
    else:
        if r0 < surface:
            for fi, ch in enumerate(reversed(row0)):
                _put(stdscr, r0, pole_col - 1 - fi, ch, flag_attr, h, w)
        if r1 < surface:
            for fi, ch in enumerate(reversed(row1)):
                _put(stdscr, r1, pole_col - 1 - fi, ch, flag_attr, h, w)

    if wind:
        label     = f'{wind["speed_mph"]:.0f}mph'
        dir_label = wind['direction_str']
        label_row = r1 + 3
        label_col = pole_col + 2
        if label_row < surface and label_row < h - 1 and label_col + len(label) < w:
            _put(stdscr, label_row - 1, label_col, dir_label,
                 curses.color_pair(PAIR_DIM), h, w)
            _put(stdscr, label_row, label_col, label,
                 curses.color_pair(PAIR_DIM), h, w)


# ── Boat state ────────────────────────────────────────────────────────────────
_boat_x     = 0.0     # float position, left edge of boat
_boat_dir   = 1       # 1 = sailing right, -1 = sailing left
_boat_speed = 0.15    # base speed — slowest, overridden by wind each frame
_boat_cols  = (0, 0)  # (left, right) column range of boat this frame

BOAT_RIGHT = [
    "           /|",
    "          / |",
    " \\   _   /  |",
    "  \\ (_) /___|",
    "  _\\[_]_____|__",
    "  \\ o   o   o /",
]

BOAT_LEFT = [
    "    |\\    ",
    "    | \\    ",
    "    |  \\   _   /",
    "    |___\\ (_) /",
    "  __|_____[_]/_ ",
    "  \\ o   o   o /",
]


def _draw_boat(stdscr, tide_data, wave_profile, h, w, surface, water_rows, wave_amp):
    global _boat_x, _boat_dir

    if not wave_profile:
        return

    wind      = tide_data.get('wind')
    boat_art  = BOAT_RIGHT if _boat_dir == 1 else BOAT_LEFT
    boat_w    = max(len(row) for row in boat_art)
    boat_h    = len(boat_art)

    # Advance boat position
    # Scale boat speed to wind mph
    mph = wind['speed_mph'] if wind else 0
    if   mph <  5: speed = 0.15
    elif mph < 12: speed = 0.25
    elif mph < 20: speed = 0.40
    elif mph < 30: speed = 0.55
    else:          speed = 0.70
    _boat_x += speed * _boat_dir

    # Bounce at edges with margin
    margin = 2
    if _boat_x + boat_w >= w - margin:
        _boat_dir = -1
    elif _boat_x <= margin:
        _boat_dir = 1

    bx = int(_boat_x)
    global _boat_cols
    _boat_cols = (bx, bx + boat_w)

    # Boat bottom row sits on wave surface at centre of boat
    centre_col = min(bx + boat_w // 2, len(wave_profile) - 1)
    wave_r     = wave_profile[max(0, centre_col)]

    # Boat rows paint upward from wave surface
    # Row index boat_h-1 is the hull bottom (sits on wave), row 0 is sail top
    boat_top_r = wave_r - boat_h

    # Boat color attrs
    red_attr   = curses.color_pair(PAIR_FALL)   | curses.A_BOLD  # red
    white_attr = curses.color_pair(PAIR_STATUS) | curses.A_BOLD  # white
    head_attr  = curses.color_pair(PAIR_HEAD)   | curses.A_BOLD  # yellow
    blue_attr  = curses.color_pair(PAIR_BOAT_B) | curses.A_BOLD  # blue bracket

    # Per-character color maps for right-facing boat (row index: char index)
    # Row 0: "           /|"          — sail white, mast red
    # Row 1: "          / |"          — sail white, mast red
    # Row 2: " \   _   /  |"          — arm white, body blue, sail white, mast red
    # Row 3: "  \ (_) /___|"          — arm white, head yellow, body blue, hull red
    # Row 4: "  _\[_]_____|__"        — hull red, porthole white
    # Row 5: "  \ o   o   o /"        — hull red, portholes white

    # Per-character color lookup based on (row_index, col_index)
    # Generated from user color picker — exact per-character mapping
    BOAT_COLORS = {
        (0, 11): white_attr, (0, 12): white_attr,
        (1, 10): white_attr, (1, 12): white_attr,
        (2,  1): white_attr, (2,  5): head_attr,  (2,  9): white_attr, (2, 12): white_attr,
        (3,  2): white_attr, (3,  4): head_attr,  (3,  5): head_attr,  (3,  6): head_attr,
        (3,  8): white_attr, (3,  9): white_attr, (3, 10): white_attr, (3, 11): white_attr, (3, 12): white_attr,
        (4,  2): red_attr,   (4,  3): white_attr,
        (4,  4): blue_attr,  (4,  5): blue_attr,  (4,  6): blue_attr,
        (4,  7): red_attr,   (4,  8): red_attr,   (4,  9): red_attr,   (4, 10): red_attr,
        (4, 11): red_attr,   (4, 12): white_attr, (4, 13): red_attr,   (4, 14): red_attr,
        (5,  2): red_attr,   (5,  4): white_attr, (5,  8): white_attr, (5, 12): white_attr,
        (5, 14): red_attr,
    }

    # Default colors for chars not in lookup
    def default_attr(row_i, ch):
        if row_i in (0, 1): return white_attr
        if row_i == 2: return white_attr
        if row_i == 3: return white_attr
        if row_i == 4: return red_attr
        if row_i == 5: return red_attr
        return white_attr

    def char_attr_right(row_i, col_i, ch):
        return BOAT_COLORS.get((row_i, col_i), default_attr(row_i, ch))

    BOAT_LEFT_COLORS = {
        (0,  4): white_attr, (0,  5): white_attr,
        (1,  4): white_attr, (1,  6): white_attr,
        (2,  4): white_attr, (2,  7): white_attr, (2, 11): head_attr,  (2, 15): white_attr,
        (3,  4): white_attr, (3,  5): white_attr, (3,  6): white_attr, (3,  7): white_attr,
        (3,  8): white_attr, (3, 10): head_attr,  (3, 11): head_attr,  (3, 12): head_attr,
        (3, 14): white_attr,
        (4,  2): red_attr,   (4,  3): red_attr,   (4,  4): white_attr, (4,  5): red_attr,
        (4,  6): red_attr,   (4,  7): red_attr,   (4,  8): red_attr,   (4,  9): red_attr,
        (4, 10): blue_attr,  (4, 11): blue_attr,  (4, 12): blue_attr,  (4, 13): white_attr,
        (4, 14): red_attr,
        (5,  2): red_attr,   (5,  4): white_attr, (5,  8): white_attr, (5, 12): white_attr,
        (5, 14): red_attr,
    }

    def char_attr_left(row_i, col_i, ch):
        return BOAT_LEFT_COLORS.get((row_i, col_i), default_attr(row_i, ch))

    char_attr = char_attr_right if _boat_dir == 1 else char_attr_left

    black_attr = curses.color_pair(PAIR_SKY)

    # Paint solid black rectangle over entire boat bounding box first
    # Use each row's stripped width so box is tight to actual content
    for i, row in enumerate(boat_art):
        r = boat_top_r + i
        if r < 0 or r >= h - 1:
            continue
        # find first and last non-space char for tight bounding
        stripped = row.rstrip()
        if not stripped:
            continue
        first = len(row) - len(row.lstrip())
        row_w = len(stripped) - first
        col   = bx + first
        if col < w - 1 and row_w > 0:
            try:
                stdscr.addstr(r, col, ' ' * min(row_w, w - col - 1), black_attr)
            except curses.error:
                pass

    # Now draw boat characters on top of black background
    for i, row in enumerate(boat_art):
        r = boat_top_r + i
        if r < 0 or r >= h - 1:
            continue
        for ci, ch in enumerate(row):
            c = bx + ci
            if ch != ' ' and 0 <= c < w - 1:
                attr = char_attr(i, ci, ch)
                _put(stdscr, r, c, ch, attr, h, w)

    # Repaint water gradient only BELOW the boat's current bottom row
    # Fixes black holes when boat rises on a wave without overwriting boat
    boat_bottom = boat_top_r + boat_h
    wave_zone_bot = surface + wave_amp + 2
    for ci in range(boat_w):
        c = bx + ci
        if c < 0 or c >= w - 1:
            continue
        for r in range(boat_bottom, min(wave_zone_bot + 1, h - 1)):
            if r < surface:
                _put(stdscr, r, c, ' ', curses.color_pair(PAIR_SKY), h, w)
            else:
                depth    = max(0, (r - surface) / max(1, water_rows - 1))
                ch, attr = _gradient_for_depth(depth)
                _put(stdscr, r, c, ch, attr, h, w)
