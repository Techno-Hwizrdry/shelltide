"""
Resize test v7 — use os.get_terminal_size() as ground truth, not getmaxyx.
"""
import curses, signal, time, os

_resize = False

def handle_resize(s, f):
    global _resize
    _resize = True

def main(stdscr):
    global _resize
    signal.signal(signal.SIGWINCH, handle_resize)
    curses.curs_set(0)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_GREEN)

    stdscr.nodelay(True)
    tick = 0

    while True:
        if _resize:
            _resize = False
            # Use OS terminal size as ground truth
            ts = os.get_terminal_size()
            curses.resizeterm(ts.lines, ts.columns)
            stdscr.erase()
            stdscr.refresh()

        # Get size from OS, not ncurses
        ts  = os.get_terminal_size()
        h   = ts.lines
        w   = ts.columns
        split = h // 2

        try:
            stdscr.addstr(1, 0, f'pre-paint h={h} w={w} t={tick}    ', curses.color_pair(3))
        except curses.error:
            pass
        stdscr.refresh()
        time.sleep(2)

        for r in range(h - 1):
            ch   = ' ' if r < split else '~'
            attr = curses.color_pair(2) if r < split else curses.color_pair(1)
            try:
                stdscr.addstr(r, 0, ch * (w - 1), attr)
                stdscr.insstr(r, w - 1, ch, attr)
            except curses.error:
                pass

        status = f' h={h} w={w} t={tick} '
        try:
            stdscr.addstr(0, 0, status[:w - 1], curses.color_pair(3))
        except curses.error:
            pass

        stdscr.refresh()
        tick += 1

        if stdscr.getch() in (ord('q'), 27):
            break

curses.wrapper(main)
