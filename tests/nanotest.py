import os, pty, sys, time, select, re, base64, fcntl, termios, struct, signal, shutil

# Automated checks for the nano-clip patch: drives nano in a pseudo-terminal
# with xterm SGR mouse sequences and checks the OSC 52 payloads and saved files.
#   python3 tests/nanotest.py               # all tests, against ~/.local/bin/nano
#   NANO=path/to/nano python3 tests/nanotest.py t_drag_copy t_wheel
import tempfile
#   FLAVOR=upstream NANO=... STOCK_NANO=...   # the opt-in variant proposed for nano 9.x
NANO = os.environ.get("NANO", os.path.expanduser("~/.local/bin/nano"))
WORK = os.environ.get("WORK") or tempfile.mkdtemp(prefix="nanotest-")
os.makedirs(WORK, exist_ok=True)
# "upstream": no built-in clipboard (copying uses nano's own OSC 52 binding from
# sample.nanorc), and typing replaces a selection only with --zap.
UP = os.environ.get("FLAVOR") == "upstream"
STOCK_NANO = os.environ.get("STOCK_NANO")
TYPEOVER = ("--zap",) if UP else ()
RCFILE = os.path.join(WORK, "upstream.nanorc")
if UP:
    open(RCFILE, "w").write('set mouse\nbind M-* "{execute}|| printf "\\033]52;c;%s\\007" '
                            '"$(base64 | tr -d \'\\n\')" {enter}{undo}" main\n')

def press(x, y):   return f"\x1b[<0;{x+1};{y+1}M".encode()
def drag(x, y):    return f"\x1b[<32;{x+1};{y+1}M".encode()
def release(x, y): return f"\x1b[<0;{x+1};{y+1}m".encode()
def wheel_down(x, y): return f"\x1b[<65;{x+1};{y+1}M".encode()
def wheel_up(x, y):   return f"\x1b[<64;{x+1};{y+1}M".encode()
ALT6 = b"\x1b*" if UP else b"\x1b6"; CTRL_K = b"\x0b"; CTRL_X = b"\x18"; CTRL_S = b"\x13"; DOWN = b"\x1b[B"; ESC = b"\x1b"

class Nano:
    def __init__(self, content, args=(), rows=24, cols=80, name="f.txt", binary=None):
        self.path = os.path.join(WORK, name)
        open(self.path, "w").write(content)
        self.fd, sfd = pty.openpty()
        self.resize_pty(rows, cols, sfd)
        self.pid = os.fork()
        if self.pid == 0:
            os.close(self.fd); os.setsid()
            fcntl.ioctl(sfd, termios.TIOCSCTTY, 0)
            for i in (0, 1, 2): os.dup2(sfd, i)
            os.environ.update(TERM="xterm-256color", HOME=WORK)
            rc = ["--rcfile=" + RCFILE] if UP else ["--ignorercfiles", "--mouse"]
            exe = binary or NANO
            os.execv(exe, [exe, *rc, *os.environ.get("EXTRA", "").split(), *args, self.path])
        os.close(sfd)
        self.out = b""
        self.closed = False
        self.pump(0.6)
    def resize_pty(self, rows, cols, fd=None):
        fcntl.ioctl(fd if fd is not None else self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    def resize(self, rows, cols):
        self.resize_pty(rows, cols); os.kill(self.pid, signal.SIGWINCH); self.pump(0.4)
    def pump(self, t):
        end = time.time() + t
        while True:
            left = end - time.time()
            if left <= 0: break
            r, _, _ = select.select([self.fd], [], [], left)
            if r:
                try: d = os.read(self.fd, 65536)
                except OSError: break
                if not d: break
                self.out += d
    def send(self, *chunks, wait=0.15):
        for c in chunks:
            os.write(self.fd, c); self.pump(wait)
    def mark(self): return len(self.out)
    def osc52(self, since=0):
        if UP and not self.closed:   # copying runs a shell command, which may take a moment
            self.pump(0.4)
        found = re.findall(rb"\x1b\]52;c;([A-Za-z0-9+/=]*)\x07", self.out[since:])
        return [base64.b64decode(f).decode() for f in found]
    def alive(self):
        return os.waitpid(self.pid, os.WNOHANG) == (0, 0)
    def save_and_quit(self):
        self.send(CTRL_S, wait=0.3); self.send(CTRL_X, wait=0.4)
        return self.finish()
    def quit(self):
        self.send(CTRL_X, wait=0.3)
        if b"Save modified buffer" in self.out[-3000:]:
            self.send(b"n", wait=0.3)
        return self.finish()
    def finish(self):
        for _ in range(20):
            p, st = os.waitpid(self.pid, os.WNOHANG)
            if p: self.status = st; break
            time.sleep(0.05)
        else:
            os.kill(self.pid, 9); os.waitpid(self.pid, 0); self.status = "killed"
        os.close(self.fd)
        self.closed = True
        return open(self.path).read()
    def crashed(self):
        return any(k in self.out for k in (b"realloc", b"corrupted", b"Segmentation", b"Aborted", b"Received SIG"))

LINES = "".join(f"line number {i}\n" for i in range(1, 201))
def nano_version(exe=None):
    import subprocess
    out = subprocess.run([exe or NANO, "--version"], capture_output=True, text=True).stdout
    m = re.search(r"version (\d+)\.(\d+)", out)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

results = []
def skip(name, reason):
    print("SKIP " + name + "  -- " + reason)

def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -- {detail}"))

def no_selection(line, content=None):
    """What a copy sends when nothing is selected: the line (built-in clipboard),
    or the whole buffer (nano's {execute} binding pipes the buffer)."""
    return [content if content is not None else LINES] if UP else [line]

ONLY_72 = {"t_big_selection_cap", "t_clipboard_whole_lines", "t_selection_hint",
           "t_help_mouse_section", "t_view_mode", "t_wheel"}   # (not for the upstream flavor)

# Screen layout with --ignorercfiles: y=0 titlebar, y=1.. text (file line k at y=k), y=21 status, y=22-23 shortcuts.
def t_drag_copy():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(0, 3), drag(2, 4), drag(5, 5), release(5, 5), ALT6)
    got = n.osc52(s)
    check("drag-select + Alt+6 sends OSC52 with exact selection", got == ["line number 3\nline number 4\nline "], repr(got))
    check("1002 drag mode requested after ncurses mouse init",
          re.search(rb"\x1b\[\?1006;1000h.*\x1b\[\?1002h", n.out, re.S) is not None)
    after = n.quit()
    check("Alt+6 copy leaves file unchanged", after == LINES)
    check("no crash (drag-copy)", not n.crashed())

def t_drag_cut():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(5, 2), drag(5, 3), drag(5, 4), release(5, 4), CTRL_K)
    got = n.osc52(s)
    after = n.save_and_quit()
    exp_sel = "number 2\nline number 3\nline "
    if not UP:
        check("drag + Ctrl+K sends OSC52 with cut text", got == [exp_sel], repr(got))
    check("drag + Ctrl+K removes exactly the selection from file", after == LINES.replace(exp_sel, "", 1), repr(after[:80]))

def t_backwards_drag():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(4, 6), drag(3, 5), drag(2, 4), release(2, 4), ALT6)
    got = n.osc52(s)
    check("upward (reverse) drag selects anchor-to-pointer", got == ["ne number 4\nline number 5\nline"], repr(got))
    n.quit()

def t_autoscroll_bottom():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(0, 3), drag(0, 10))
    n.send(drag(0, 23), wait=1.0)          # pointer on the shortcut bar, held still for 1s
    n.send(release(0, 23), ALT6)
    got = n.osc52(s)
    ok = len(got) == 1 and got[0].startswith("line number 3\n")
    last = got[0].split("\n")[-2] if ok else ""
    lines_sel = got[0].count("\n") if ok else 0
    check("autoscroll down while pointer rests below text area (selected %d lines, ended near '%s')" % (lines_sel, last),
          ok and lines_sel > 25, repr(got)[:200])
    n.quit()
    return lines_sel

def t_autoscroll_stops():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(0, 3), drag(0, 23), wait=0.5)
    n.send(drag(0, 10), wait=0.8)   # back into text area: scrolling must stop
    n.send(release(0, 10), ALT6)
    got = n.osc52(s)
    cnt1 = got[0].count("\n") if got else -1
    check("autoscroll stops when pointer returns into text area (sel %d lines, sane bound)" % cnt1, got and 8 < cnt1 < 20, repr(got)[:120])
    n.quit()

def t_autoscroll_top():
    n = Nano(LINES)
    # move view down first: wheel down a lot
    for _ in range(20): n.send(wheel_down(5, 10), wait=0.03)
    n.pump(0.3)
    s = n.mark()
    n.send(press(0, 15), drag(0, 5))
    n.send(drag(0, 0), wait=1.0)   # titlebar
    n.send(release(0, 0), ALT6)
    got = n.osc52(s)
    ok = len(got) == 1
    cnt = got[0].count("\n") if ok else 0
    check("autoscroll up while pointer rests on titlebar (selected %d lines)" % cnt, ok and cnt > 25, repr(got)[:200])
    n.quit()

def t_click_moves_cursor():
    n = Nano(LINES)
    n.send(press(5, 4), release(5, 4), b"X")
    after = n.save_and_quit()
    check("single click moves cursor (typed X at line 4 col 5)", after.split("\n")[3] == "line Xnumber 4", after.split("\n")[3])
    check("single click does not create a selection (no OSC52)", n.osc52() == [])

def t_click_on_cursor_toggles_mark():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(0, 1), release(0, 1), wait=0.6)     # slower than a double click
    check("click on cursor sets mark", b"Mark Set" in n.out[s:])
    s = n.mark()
    n.send(press(0, 1), release(0, 1), wait=0.6)
    check("click on cursor again unsets mark", b"Mark Unset" in n.out[s:])
    n.quit()

def t_click_clears_drag_selection():
    n = Nano(LINES)
    n.send(press(0, 3), drag(4, 5), release(4, 5))
    s = n.mark()
    n.send(press(0, 10), release(0, 10), ALT6)   # click elsewhere then copy -> copies whole line 10 (no mark)
    got = n.osc52(s)
    check("click elsewhere discards the drag selection (Alt+6 copies the line)", got == no_selection("line number 10\n"), repr(got)[:80])
    n.quit()

def t_wheel():
    if nano_version() >= (8, 0):
        return   # covered by t_wheel_same_as_stock
    n = Nano(LINES)
    n.send(wheel_down(5, 5), wait=0.3); n.send(b"X")
    after = n.save_and_quit()
    check("mouse wheel still scrolls (cursor moved 3 lines down)", after.split("\n")[3].startswith("X"), after.split("\n")[:5])

def t_shortcut_bar():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(2, 22), release(2, 22), wait=0.5)   # ^G Help
    check("clicking ^G Help in shortcut bar opens help", b"Main nano help text" in n.out[s:] or b"help text" in n.out[s:])
    n.send(CTRL_X, wait=0.3)
    n.quit()

def t_arrow_clears_selection():
    n = Nano(LINES)
    n.send(press(0, 3), drag(4, 5), release(4, 5), DOWN)
    s = n.mark()
    n.send(ALT6)
    check("arrow key after drag clears selection (Alt+6 then copies the line)", n.osc52(s) == no_selection("line number 6\n"), repr(n.osc52(s))[:80])
    n.quit()

def t_typing_after_drag():
    n = Nano(LINES, args=TYPEOVER)
    s = n.mark()
    n.send(press(0, 3), drag(4, 5), release(4, 5), b"Z")
    after = n.save_and_quit()
    check("typing after drag replaces the selection", after == LINES.replace("line number 3\nline number 4\nline", "Z", 1), after.split("\n")[1:4])
    check("typing over a selection does not touch the clipboard", n.osc52(s) == [])

def t_softwrap():
    long = "".join(f"L{i} " + ("abcdefghij" * 12) + "\n" for i in range(1, 30))   # ~123 chars -> 2 rows each at 80 cols
    n = Nano(long, args=("--softwrap",))
    s = n.mark()
    # line1 occupies y=1,2 ; line2 y=3,4. Press at line1 chunk2 col 3 (y=2,x=3) -> data index 83 ; drag to line2 chunk1 col 10 (y=3,x=10)
    n.send(press(3, 2), drag(5, 3), drag(10, 3), release(10, 3), ALT6)
    got = n.osc52(s)
    L = long.split("\n")
    exp = L[0][83:] + "\n" + L[1][:10]
    check("softwrap: drag across wrapped chunks", got == [exp], f"{got!r} vs {exp!r}")
    s = n.mark()
    n.send(press(0, 1), drag(0, 23), wait=0.8); n.send(release(0, 23), ALT6)
    got = n.osc52(s)
    check("softwrap: autoscroll works", len(got) == 1 and got[0].count("\n") > 12, repr(got)[:100])
    n.quit()

def t_nosoftwrap_long():
    long = "".join(f"L{i} " + ("abcdefghij" * 12) + "\n" for i in range(1, 30))
    n = Nano(long)
    s = n.mark()
    n.send(press(3, 1), drag(10, 2), release(10, 2), ALT6)
    got = n.osc52(s); L = long.split("\n")
    check("no softwrap: drag on long lines", got == [L[0][3:] + "\n" + L[1][:10]], repr(got)[:120])
    n.quit()

def t_linenumbers():
    n = Nano(LINES, args=("--linenumbers",))
    s = n.mark()
    # margin = digits(200)+1 = 4
    n.send(press(4, 2), drag(8, 3), release(8, 3), ALT6)
    got = n.osc52(s)
    check("line numbers: columns account for margin", got == ["line number 2\nline"], repr(got))
    s = n.mark()
    n.send(press(6, 5), drag(0, 6), release(0, 6), ALT6)   # drag into the margin -> column 0
    got = n.osc52(s)
    check("line numbers: dragging into margin clamps to column 0", got == ["ne number 5\n"], repr(got))
    n.quit()

def t_key_during_drag():
    n = Nano(LINES, args=TYPEOVER)
    n.send(press(0, 3), drag(4, 5), b"Q", release(4, 7))
    n.send(ALT6)
    after_alive = n.alive()
    after = n.save_and_quit()
    check("keystroke mid-drag is not lost (replaces the selection) and nano survives", after_alive and after.split("\n")[2] == "Q number 5", after.split("\n")[1:5])
    check("release after interrupted drag is ignored (cursor not moved to it)", "line number 7\n" in after)

def t_resize_during_drag():
    n = Nano(LINES)
    n.send(press(0, 3), drag(4, 5))
    n.resize(30, 90)
    n.send(release(4, 5), wait=0.3)
    s = n.mark()
    n.send(press(0, 3), drag(4, 5), release(4, 5), ALT6)
    got = n.osc52(s)
    check("resize during drag: survives, and drag works after resize", n.alive() and got == ["line number 3\nline number 4\nline"], repr(got))
    re_req = n.out.rfind(b"\x1b[?1002h") > n.out.rfind(b"\x1b[?1006;1000h")
    check("after resize, 1002 re-requested after ncurses' mouse init", re_req)
    n.quit()

def t_toggle_mouse_off():
    n = Nano(LINES)
    s = n.mark()
    n.send(b"\x1bm", wait=0.3)   # Alt+M toggles mouse
    check("Alt+M (mouse off) sends 1002l", b"\x1b[?1002l" in n.out[s:])
    s = n.mark()
    n.send(b"\x1bm", wait=0.3); n.send(b"x"); n.send(b"\x7f", wait=0.3)
    check("Alt+M (mouse on) re-requests 1002h", b"\x1b[?1002h" in n.out[s:])
    n.quit()

def t_big_selection_cap():
    big = ("x" * 4999 + "\n") * 60      # 300 KB
    n = Nano(big, name="big.txt")
    n.send(b"\x1b\\", wait=0.2)  # Alt+\ go to top
    n.send(press(0, 1), drag(0, 23), wait=5.0)  # autoscroll through the whole file
    n.send(release(0, 23), ALT6, wait=0.4)
    check("selection > 100KB is not sent, warns instead", n.osc52() == [] and b"Too much text" in n.out, n.osc52()[:1] and len(n.osc52()[0]))
    s = n.mark()
    n.send(press(0, 1), drag(0, 3), release(0, 3), ALT6)   # a small selection still works afterwards
    check("small selection after an oversized one is still exported", len(n.osc52(s)) == 1)
    n.quit()

def t_unicode():
    txt = "héllo wörld ✓ 日本語\nsecond line\n" + LINES
    n = Nano(txt)
    s = n.mark()
    n.send(press(6, 1), drag(3, 2), release(3, 2), ALT6)
    got = n.osc52(s)
    check("UTF-8 text round-trips through OSC52 (incl. wide chars)", got == ["wörld ✓ 日本語\nsec"], repr(got))
    n.quit()


def t_prompt_click():
    n = Nano(LINES)
    n.send(b"\x17", wait=0.3)          # ^W search prompt on y=21: "Search: "
    n.send(b"abcdef", wait=0.2)
    n.send(press(10, 21), release(10, 21), b"X\r", wait=0.4)   # x=10 -> after "ab"
    check("click in a prompt still positions the prompt cursor", b'"abXcdef" not found' in n.out, n.out[-300:])
    n.quit()

def t_yesno_click():
    n = Nano(LINES)
    n.send(b"Q", wait=0.2); n.send(CTRL_X, wait=0.4)   # modified -> "Save modified buffer?" Y/N on y=22/23
    n.send(press(1, 23), release(1, 23), wait=0.4)     # " N No" is on y=23 at x=0..
    check("clicking N in the Yes/No prompt still works", not n.alive() or b"Save modified" in n.out, n.out[-200:])
    try: n.finish()
    except OSError: pass
    check("file untouched after clicking No", open(n.path).read() == LINES)

def t_view_mode():
    n = Nano(LINES, args=("--view",))
    s = n.mark()
    n.send(press(0, 2), drag(4, 3), release(4, 3), ALT6)
    check("view mode: drag + Alt+6 copies", n.osc52(s) == ["line number 2\nline"], repr(n.osc52(s)))
    n.send(CTRL_X, wait=0.3); n.finish()

def t_right_button_drag():
    n = Nano(LINES)
    s = n.mark()
    n.send(b"\x1b[<2;5;5M", b"\x1b[<34;6;6M", b"\x1b[<34;8;8M", b"\x1b[<2;8;8m", ALT6)
    check("right-button drag is ignored (no selection: Alt+6 copies the line)", n.osc52(s) == no_selection("line number 1\n") and n.alive(), repr(n.osc52(s))[:80])
    n.quit()

def t_fast_burst():
    n = Nano(LINES)
    s = n.mark()
    # whole gesture arrives in one write, as when the system is busy
    n.send(press(0, 3) + drag(2, 4) + drag(5, 6) + release(5, 6) + ALT6, wait=0.5)
    check("burst-delivered drag gesture is processed in order", n.osc52(s) == ["line number 3\nline number 4\nline number 5\nline "], repr(n.osc52(s)))
    n.quit()

def t_burst_click():
    n = Nano(LINES)
    n.send(press(5, 4) + release(5, 4), wait=0.3); n.send(b"X")
    after = n.save_and_quit()
    check("burst click (press+release in one read) still moves cursor", after.split("\n")[3] == "line Xnumber 4", after.split("\n")[3])

def t_burst_click_then_drag():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(5, 8) + release(5, 8) + press(0, 3) + drag(3, 4) + release(3, 4), wait=0.4); n.send(ALT6)
    check("burst click followed by drag: both handled in order", n.osc52(s) == ["line number 3\nlin"], repr(n.osc52(s)))
    n.quit()

SHIFT_PRESS = lambda x, y: f"\x1b[<4;{x+1};{y+1}M".encode()
SHIFT_RELEASE = lambda x, y: f"\x1b[<4;{x+1};{y+1}m".encode()
SHIFT_DRAG = lambda x, y: f"\x1b[<36;{x+1};{y+1}M".encode()
ALT_PRESS = lambda x, y: f"\x1b[<8;{x+1};{y+1}M".encode()
ALT_RELEASE = lambda x, y: f"\x1b[<8;{x+1};{y+1}m".encode()
def clicks(n_, x, y, k):
    for _ in range(k): n_.send(press(x, y), release(x, y), wait=0.05)
    n_.pump(0.2)

def t_double_click_word():
    n = Nano(LINES)
    s = n.mark(); clicks(n, 6, 4, 2); n.send(ALT6)
    check("double-click selects a word", n.osc52(s) == ["number"], repr(n.osc52(s)))
    s = n.mark(); clicks(n, 4, 4, 2); n.send(ALT6)
    check("double-click on a blank selects the blank run", n.osc52(s) == [" "], repr(n.osc52(s)))
    s = n.mark(); clicks(n, 40, 4, 2); n.send(ALT6)
    check("double-click past end of line selects the last word", n.osc52(s) == ["4"], repr(n.osc52(s)))
    n.quit()

def t_double_click_punct_and_utf8():
    n = Nano("foo(bar_baz, qux) == héllo;\n" + LINES)
    s = n.mark(); clicks(n, 6, 1, 2); n.send(ALT6)
    check("double-click: underscore is part of a word", n.osc52(s) == ["bar_baz"], repr(n.osc52(s)))
    s = n.mark(); clicks(n, 18, 1, 2); n.send(ALT6)
    check("double-click on punctuation selects the punctuation run", n.osc52(s) == ["=="], repr(n.osc52(s)))
    s = n.mark(); clicks(n, 23, 1, 2); n.send(ALT6)
    check("double-click on a UTF-8 word", n.osc52(s) == ["héllo"], repr(n.osc52(s)))
    n.quit()

def t_triple_click_line():
    n = Nano(LINES)
    s = n.mark(); clicks(n, 6, 4, 3); n.send(ALT6)
    check("triple-click selects the whole line incl. newline", n.osc52(s) == ["line number 4\n"], repr(n.osc52(s)))
    s = n.mark(); clicks(n, 6, 7, 4); n.send(ALT6)
    check("fourth click is a plain click again (Alt+6 copies the line)", n.osc52(s) == no_selection("line number 7\n"), repr(n.osc52(s))[:80])
    n.quit()

def t_slow_clicks_are_not_double():
    n = Nano(LINES)
    n.send(press(6, 4), release(6, 4), wait=0.6)
    s = n.mark()
    n.send(press(6, 4), release(6, 4), wait=0.3)
    check("two slow clicks on the same spot: second toggles the mark (old behavior)", b"Mark Set" in n.out[s:])
    s = n.mark()
    n.send(press(6, 4), release(6, 4), wait=0.05); n.send(press(6, 5), release(6, 5), wait=0.3); n.send(ALT6)
    check("quick clicks on different spots are not a double click", n.osc52(s) in ([], no_selection("line number 5\n")) or b"Mark" in n.out[s:], repr(n.osc52(s))[:80])
    n.quit()

def t_double_click_drag_words():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(6, 4), release(6, 4), wait=0.05); n.send(press(6, 4), drag(4, 5), drag(2, 6), release(2, 6), ALT6)
    check("double-click + drag down extends by words", n.osc52(s) == ["number 4\nline number 5\nline"], repr(n.osc52(s)))
    s = n.mark()
    n.send(press(6, 4), release(6, 4), wait=0.05); n.send(press(6, 4), drag(6, 3), drag(6, 2), release(6, 2), ALT6)
    check("double-click + drag up extends by words", n.osc52(s) == ["number 2\nline number 3\nline number"], repr(n.osc52(s)))
    n.quit()

def t_triple_click_drag_lines():
    n = Nano(LINES)
    s = n.mark()
    for _ in range(2): n.send(press(6, 4), release(6, 4), wait=0.05)
    n.send(press(6, 4), drag(3, 5), drag(1, 6), release(1, 6), ALT6)
    check("triple-click + drag extends by lines", n.osc52(s) == ["line number 4\nline number 5\nline number 6\n"], repr(n.osc52(s)))
    s = n.mark()
    for _ in range(2): n.send(press(6, 9), release(6, 9), wait=0.05)
    n.send(press(6, 9), drag(3, 8), release(3, 8), ALT6)
    check("triple-click + drag up extends by lines", n.osc52(s) == ["line number 8\nline number 9\n"], repr(n.osc52(s)))
    n.quit()

def t_shift_click_extends():
    n = Nano(LINES)
    s = n.mark()
    n.send(SHIFT_PRESS(5, 3), SHIFT_RELEASE(5, 3), ALT6)
    check("Shift+click without a selection selects from the cursor", n.osc52(s) == ["line number 1\nline number 2\nline "], repr(n.osc52(s)))
    s = n.mark()
    n.send(press(0, 3), drag(4, 4), release(4, 4), SHIFT_PRESS(2, 6), SHIFT_RELEASE(2, 6), ALT6)
    check("Shift+click extends an existing drag selection", n.osc52(s) == ["line number 3\nline number 4\nline number 5\nli"], repr(n.osc52(s)))
    s = n.mark()
    n.send(press(0, 5), drag(4, 5), release(4, 5), SHIFT_PRESS(2, 3), SHIFT_RELEASE(2, 3), ALT6)
    check("Shift+click before the anchor selects backwards from it", n.osc52(s) == ["ne number 3\nline number 4\n"], repr(n.osc52(s)))
    s = n.mark()
    n.send(press(0, 10), release(0, 10), wait=0.6)
    n.send(SHIFT_PRESS(3, 10), SHIFT_DRAG(3, 11), SHIFT_DRAG(6, 12), SHIFT_RELEASE(6, 12), ALT6)
    check("Shift+drag extends while dragging", n.osc52(s) == ["line number 10\nline number 11\nline n"], repr(n.osc52(s)))
    n.quit()

def t_alt_click_extends():
    n = Nano(LINES)
    s = n.mark()
    n.send(press(2, 2), release(2, 2), wait=0.6)
    n.send(ALT_PRESS(4, 3), ALT_RELEASE(4, 3), ALT6)
    check("Alt+click extends like Shift+click (Windows Terminal keeps Shift)", n.osc52(s) == ["ne number 2\nline"], repr(n.osc52(s)))
    n.quit()

def t_shift_click_keeps_hard_mark():
    n = Nano(LINES)
    n.send(b"\x1e", wait=0.2)              # ^6: hard mark at 1:0
    n.send(SHIFT_PRESS(4, 2), SHIFT_RELEASE(4, 2), DOWN, DOWN)
    s = n.mark(); n.send(ALT6)
    check("Shift+click with a hard mark keeps it a hard mark (arrows extend)", n.osc52(s) == ["line number 1\nline number 2\nline number 3\nline"], repr(n.osc52(s)))
    n.quit()

def t_type_over_and_undo():
    n = Nano(LINES, args=TYPEOVER)
    n.send(press(5, 2), drag(6, 3), release(6, 3), b"ZZ", wait=0.3)
    n.send(b"\x1bu", wait=0.2); n.send(b"\x1bu", wait=0.3)   # Alt+U twice
    after = n.save_and_quit()
    check("typed-over selection comes back with two undos", after == LINES, after.split("\n")[:4])

def t_backspace_delete_selection():
    n = Nano(LINES, args=TYPEOVER)
    n.send(press(5, 2), drag(6, 3), release(6, 3), b"\x7f", wait=0.2)          # Backspace
    n.send(press(0, 5), drag(5, 5), release(5, 5), b"\x1b[3~", wait=0.2)       # Delete
    after = n.save_and_quit()
    # Backspace joins "line " (line 2) with "umber 3"; the lines below move up a row,
    # so the second drag (row 5) hits line 6.
    L = LINES.split("\n"); L[1] = "line umber 3"; del L[2]; L[4] = "number 6"
    check("Backspace and Delete remove a selection", after == "\n".join(L), after.split("\n")[:5])

def t_shift_arrow_type_over():
    n = Nano(LINES, args=TYPEOVER)
    n.send(b"\x1b[1;2C" * 4, wait=0.2); n.send(b"Q")       # Shift+Right x4, type
    after = n.save_and_quit()
    check("typing over a Shift+arrow selection replaces it", after.split("\n")[0] == "Q number 1", after.split("\n")[0])

def t_hard_mark_not_typed_over():
    n = Nano(LINES, args=TYPEOVER)
    n.send(b"\x1e", wait=0.2); n.send(b"\x1b[C" * 4, wait=0.2); n.send(b"Q")   # ^6 mark, Right x4, type
    after = n.save_and_quit()
    if UP:   # with --zap, like Backspace and Delete, typing replaces any marked region
        check("--zap: typing replaces a region marked with ^6", after.split("\n")[0] == "Q number 1", after.split("\n")[0])
    else:
        check("typing with a hard mark (^6) inserts as before", after.split("\n")[0] == "lineQ number 1", after.split("\n")[0])

def t_empty_selection_type():
    n = Nano(LINES, args=TYPEOVER)
    n.send(press(4, 3), drag(6, 3), drag(4, 3), release(4, 3), b"Q")
    after = n.save_and_quit()
    check("typing with an empty drag selection just inserts", after.split("\n")[2] == "lineQ number 3", after.split("\n")[2])

def t_paste_over_selection():
    n = Nano(LINES, args=TYPEOVER)
    n.send(press(0, 2), drag(4, 3), release(4, 3), b"\x1b[200~PASTED\x1b[201~", wait=0.4)
    after = n.save_and_quit()
    check("bracketed paste replaces a selection", after.split("\n")[1] == "PASTED number 3", after.split("\n")[:3])

def t_clipboard_whole_lines():
    n = Nano(LINES)
    s = n.mark(); n.send(ALT6)
    check("Alt+6 without selection sends the line", n.osc52(s) == ["line number 1\n"], repr(n.osc52(s)))
    s = n.mark(); n.send(CTRL_K, wait=0.2); n.send(CTRL_K)
    got = n.osc52(s)
    check("consecutive Ctrl+K: clipboard holds all cut lines", got[-1:] == ["line number 2\nline number 3\n"], repr(got))
    s = n.mark(); n.send(b"\x1b/", wait=0.2); n.send(CTRL_K, wait=0.3)    # last (empty) line: nothing to cut
    check("nothing cut -> clipboard untouched", n.osc52(s) == [], repr(n.osc52(s)))
    s = n.mark(); n.send(b"\x1b[A" * 2, wait=0.2); n.send(b"\x1bt", wait=0.3)   # Alt+T cut till end
    check("Alt+T (cut till end) sends the cut text", n.osc52(s) == ["line number 199\nline number 200\n"], repr(n.osc52(s)))
    n.quit()

def t_multiclick_edges():
    n = Nano("alpha\n\nlast line")
    clicks(n, 0, 2, 2); n.send(b"Q")
    s = n.mark(); clicks(n, 2, 3, 3); n.send(ALT6)
    check("triple-click on the final line (nano keeps a newline after it)", n.osc52(s) == ["last line\n"], repr(n.osc52(s)))
    after = n.save_and_quit()
    check("double-click on an empty line selects nothing; typing just inserts", after.split("\n")[1] == "Q", after.split("\n"))

def t_softwrap_double_click():
    long = "".join(f"L{i} " + ("abcdefghij" * 12) + " tail word\n" for i in range(1, 30))
    n = Nano(long, args=("--softwrap",))
    s = n.mark(); clicks(n, 5, 2, 2); n.send(ALT6)
    check("softwrap: double-click on a wrapped word selects all of it", n.osc52(s) == ["abcdefghij" * 12], repr(n.osc52(s))[:60])
    n.quit()

HINT = b"M-6 copies to clipboard, ^K cuts, typing replaces, Alt+click extends"

def t_selection_hint():
    n = Nano(LINES)
    s = n.mark(); n.send(press(5, 4), release(5, 4), wait=0.3)
    check("hint: not shown after a plain click", HINT not in n.out[s:])
    s = n.mark(); n.send(press(0, 3), drag(4, 3), drag(4, 3), drag(3, 3), drag(0, 3), release(0, 3), wait=0.3)
    check("hint: not shown for an empty selection", HINT not in n.out[s:])
    s = n.mark(); n.send(press(0, 3), drag(4, 4), release(4, 4), wait=0.3)
    check("hint: shown after the first mouse selection", HINT in n.out[s:])
    n.send(b"\x1b[B", wait=0.2)
    s = n.mark(); n.send(press(0, 6), drag(4, 7), release(4, 7), wait=0.3)
    check("hint: shown only once per session", HINT not in n.out[s:])
    n.quit()
    n = Nano(LINES)
    s = n.mark(); clicks(n, 6, 4, 2)
    check("hint: also after a double-click selection", HINT in n.out[s:])
    n.quit()

def t_help_mouse_section():
    n = Nano(LINES)
    n.send(b"\x07", wait=0.4); n.send(b"\x1b/", wait=0.4)    # ^G help, M-/ to the end
    text = re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\(B", b"", n.out)
    check("help screen has the mouse section", b"Mouse actions (with 'set mouse' or M-M)" in text and b"Alt+click" in text and b"system clipboard" in text)
    n.send(CTRL_X, wait=0.3)
    n.quit()

def t_without_zap_typing_is_unchanged():
    if not UP: return
    n = Nano(LINES)
    n.send(press(0, 3), drag(4, 5), release(4, 5), b"Z")
    after = n.save_and_quit()
    exp = LINES.split("\n"); exp[4] = "lineZ number 5"
    check("without --zap, typing after a drag inserts and drops the selection (stock behavior)", after == "\n".join(exp), after.split("\n")[2:6])

def same_as_stock(label, args, steps):
    """Run the same keystrokes in the stock and the patched nano, then compare the saved files."""
    if not STOCK_NANO:
        skip(label, "set STOCK_NANO to an unpatched nano of the same version"); return
    results = []
    for exe in (STOCK_NANO, NANO):
        n = Nano(LINES, args=args, binary=exe)
        for chunk in steps: n.send(chunk, wait=0.25)
        n.send(b"X"); results.append(n.save_and_quit())
    check(label, results[0] == results[1], [r.split("\n").index(next(l for l in r.split("\n") if "X" in l)) for r in results])

def t_wheel_same_as_stock():
    if nano_version() < (8, 0) and not STOCK_NANO: return   # t_wheel covers it
    same_as_stock("mouse wheel behaves exactly as in stock nano", (),
                  [wheel_down(5, 5), wheel_down(5, 5), wheel_up(5, 5)])

def t_scrollbar_same_as_stock():
    same_as_stock("clicking the scrollbar (--indicator) behaves exactly as in stock nano", ("--indicator",),
                  [press(79, 12) + release(79, 12)])

tests = [t for name, t in list(globals().items()) if name.startswith("t_")]
only = sys.argv[1:]
for t in tests:
    if only and t.__name__ not in only: continue
    if UP and t.__name__ in ONLY_72: continue
    try: t()
    except Exception as e: check(t.__name__ + " raised", False, repr(e))
print(f"\n{sum(ok for _, ok in results)}/{len(results)} passed")
