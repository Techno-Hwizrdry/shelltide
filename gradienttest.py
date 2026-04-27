#!/usr/bin/env python3
"""
gradient_test.py — render gradient options side by side in actual color.
Press q to quit, 1/2/3 to highlight an option.
"""
import curses, os

C_SKY    = 1
C_SURF   = 2
C_C_ON_C = 3
C_C_ON_B = 4
C_B_ON_B = 5
C_DEEP   = 6
C_B_ON_C = 7
C_W_ON_C = 8
C_LABEL  = 9

def init(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(C_SKY,    curses.COLOR_BLACK, curses.COLOR_BLACK)
    curses.init_pair(C_SURF,   curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(C_C_ON_C, curses.COLOR_CYAN,  curses.COLOR_CYAN)
    curses.init_pair(C_C_ON_B, curses.COLOR_CYAN,  curses.COLOR_BLUE)
    curses.init_pair(C_B_ON_B, curses.COLOR_BLUE,  curses.COLOR_BLUE)
    curses.init_pair(C_DEEP,   curses.COLOR_BLACK, curses.COLOR_BLUE)
    curses.init_pair(C_B_ON_C, curses.COLOR_BLUE,  curses.COLOR_CYAN)
    curses.init_pair(C_W_ON_C, curses.COLOR_WHITE, curses.COLOR_CYAN)
    curses.init_pair(C_LABEL,  curses.COLOR_WHITE, curses.COLOR_BLACK)

# Each option is a list of (char, pair, bold, label) from surface down
OPTIONS = {
    'A': [
        ('≋', C_SURF,   True,  'white/cyan  wave'),
        ('⠿', C_W_ON_C, False, 'white/cyan  sparse'),
        ('⣷', C_W_ON_C, True,  'white/cyan  bold'),
        ('⣿', C_C_ON_C, False, 'cyan/cyan   solid'),
        ('⣷', C_C_ON_C, False, 'cyan/cyan   light'),
        ('⣿', C_B_ON_C, True,  'blue/cyan   bridge bold'),
        ('⣷', C_B_ON_C, False, 'blue/cyan   bridge'),
        ('⣿', C_C_ON_B, True,  'cyan/blue   bold'),
        ('⣿', C_C_ON_B, False, 'cyan/blue'),
        ('⠿', C_C_ON_B, False, 'cyan/blue   sparse'),
        ('⠒', C_C_ON_B, False, 'cyan/blue   v.sparse'),
        ('⣿', C_B_ON_B, True,  'blue/blue   bold'),
        ('⣿', C_B_ON_B, False, 'blue/blue'),
        ('⠿', C_B_ON_B, False, 'blue/blue   sparse'),
        ('⠂', C_B_ON_B, False, 'blue/blue   v.sparse'),
        (' ', C_DEEP,   False, 'black/blue  abyss'),
    ],
    'B': [
        ('≋', C_SURF,   True,  'white/cyan  wave'),
        ('⠂', C_C_ON_C, False, 'cyan/cyan   v.sparse'),
        ('⠒', C_C_ON_C, False, 'cyan/cyan   sparse'),
        ('⠿', C_C_ON_C, False, 'cyan/cyan   mid'),
        ('⣷', C_C_ON_C, False, 'cyan/cyan   heavy'),
        ('⣿', C_C_ON_C, False, 'cyan/cyan   solid'),
        ('⣿', C_B_ON_C, True,  'blue/cyan   bridge bold'),
        ('⣷', C_B_ON_C, False, 'blue/cyan   bridge'),
        ('⣿', C_C_ON_B, True,  'cyan/blue   bold'),
        ('⠿', C_C_ON_B, False, 'cyan/blue   sparse'),
        ('⣿', C_B_ON_B, False, 'blue/blue'),
        (' ', C_DEEP,   False, 'black/blue  abyss'),
    ],
    'C': [
        ('≋', C_SURF,   True,  'white/cyan  wave'),
        ('⣿', C_C_ON_C, False, 'cyan/cyan   solid'),
        ('⣿', C_B_ON_C, True,  'blue/cyan   bridge bold'),
        ('⣷', C_B_ON_C, False, 'blue/cyan   lighter'),
        ('⣿', C_C_ON_B, True,  'cyan/blue   bold'),
        ('⠿', C_C_ON_B, False, 'cyan/blue   sparse'),
        ('⣿', C_B_ON_B, False, 'blue/blue'),
        (' ', C_DEEP,   False, 'black/blue  abyss'),
    ],
}

def main(stdscr):
    init(stdscr)
    curses.curs_set(0)
    stdscr.nodelay(True)

    W = 20   # width of each option column
    GAP = 4

    while True:
        h, w = os.get_terminal_size()
        stdscr.erase()

        col_starts = {'A': 2, 'B': 2 + W + GAP, 'C': 2 + (W + GAP) * 2}

        for opt, bands in OPTIONS.items():
            cx = col_starts[opt]
            # Header
            try:
                stdscr.addstr(0, cx, f'Option {opt}',
                              curses.color_pair(C_LABEL) | curses.A_BOLD)
            except curses.error:
                pass

            # Sky rows
            for r in range(2, 5):
                try:
                    stdscr.addstr(r, cx, ' ' * (W-1), curses.color_pair(C_SKY))
                    stdscr.insstr(r, cx + W - 1, ' ', curses.color_pair(C_SKY))
                except curses.error:
                    pass

            # Gradient bands — 2 rows each so you can see them clearly
            row = 5
            for ch, pair, bold, label in bands:
                attr = curses.color_pair(pair)
                if bold:
                    attr |= curses.A_BOLD
                for rr in range(2):
                    if row + rr < h - 1:
                        try:
                            stdscr.addstr(row + rr, cx, ch * (W-1), attr)
                            stdscr.insstr(row + rr, cx + W - 1, ch, attr)
                        except curses.error:
                            pass
                # Label on first row, right of option C only
                if opt == 'C' and row < h - 1:
                    lx = col_starts['C'] + W + 2
                    try:
                        stdscr.addstr(row, lx, label,
                                      curses.color_pair(C_LABEL))
                    except curses.error:
                        pass
                row += 2

        try:
            stdscr.addstr(h - 2, 0,
                          ' q=quit  |  tell me which option or mix you prefer ',
                          curses.color_pair(C_LABEL))
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), ord('Q'), 27):
            break

        import time
        time.sleep(0.05)

curses.wrapper(main)
