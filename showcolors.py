#!/usr/bin/env python3
"""
show_colors.py — display all available curses color pairs and attributes.
Run this in your terminal to see exactly what renders on your setup.
Press q to quit.
"""
import curses
import os

def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.nodelay(True)

    import os
    h, w = os.get_terminal_size()

    # Init all fg/bg combos we use in shelltide
    colors = [
        curses.COLOR_BLACK,
        curses.COLOR_RED,
        curses.COLOR_GREEN,
        curses.COLOR_YELLOW,
        curses.COLOR_BLUE,
        curses.COLOR_MAGENTA,
        curses.COLOR_CYAN,
        curses.COLOR_WHITE,
    ]
    names = ['BLK','RED','GRN','YEL','BLU','MAG','CYN','WHT']

    # Build pairs: pair index = fg*8 + bg + 1
    for fi, fg in enumerate(colors):
        for bi, bg in enumerate(colors):
            pair = fi * 8 + bi + 1
            if pair < curses.COLOR_PAIRS:
                curses.init_pair(pair, fg, bg)

    stdscr.erase()

    # Header
    try:
        stdscr.addstr(0, 0, 'SHELLTIDE COLOR TEST — bg across top, fg down side — q to quit')
    except curses.error:
        pass

    # Column headers (bg colors)
    for bi, bn in enumerate(names):
        try:
            stdscr.addstr(1, 4 + bi * 8, bn)
        except curses.error:
            pass

    # Rows: each fg color
    sample = 'AbCdEf'
    for fi, (fg, fn) in enumerate(zip(colors, names)):
        row = fi * 3 + 2
        try:
            stdscr.addstr(row,     0, fn)
            stdscr.addstr(row + 1, 0, 'bold')
            stdscr.addstr(row + 2, 0, 'dim ')
        except curses.error:
            pass

        for bi, bg in enumerate(colors):
            pair = fi * 8 + bi + 1
            if pair >= curses.COLOR_PAIRS:
                continue
            col = 4 + bi * 8
            attr_n    = curses.color_pair(pair)
            attr_b    = curses.color_pair(pair) | curses.A_BOLD
            attr_d    = curses.color_pair(pair) | curses.A_DIM
            try:
                stdscr.addstr(row,     col, sample, attr_n)
                stdscr.addstr(row + 1, col, sample, attr_b)
                stdscr.addstr(row + 2, col, sample, attr_d)
            except curses.error:
                pass

    # Also show the braille chars we use for gradient
    brow = 8 * 3 + 3
    try:
        stdscr.addstr(brow, 0, 'GRADIENT CHARS:')
        stdscr.addstr(brow + 1, 0, '≋ ⣿ ⣷ ⠿ ⠒ ⠂ ~ ≈   (surface to deep)')
    except curses.error:
        pass

    stdscr.refresh()

    while True:
        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):
            break

curses.wrapper(main)
