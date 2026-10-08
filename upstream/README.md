# Proposed for GNU nano: selecting text with the mouse

This folder holds a **proposal for the official GNU nano** (the development version, git master). It isn't part of nano and hasn't been accepted. It's a working prototype for the nano developers to look at.

The five patches apply to nano's git master at commit `4be01411` (2026-10-07, "v9.2-40"). They also apply unchanged to the 9.2 release. In nano's `git log` style:

| # | Commit | Default |
|---|---|---|
| 1 | new feature: allow selecting text by dragging the mouse | on with `--mouse` |
| 2 | new feature: double-click selects a word, triple-click selects a line | on with `--mouse` |
| 3 | new feature: Shift+click or Alt+click extends the selection | on with `--mouse` |
| 4 | new feature: with --zap, typed and pasted text replace a marked region | only with `--zap` |
| 5 | docs: describe selecting text with the mouse, and the extended --zap | |

## How this differs from nano-mouse for 7.2

This version is shaped to fit how nano is developed today:

- **No built-in clipboard.** Since nano 8.7, you can copy to the system clipboard with an OSC 52 key binding in your nanorc (see `doc/sample.nanorc`). That binding works with mouse selections, and the tests use it.
- **Typing over a selection is opt-in.** It extends the existing `--zap` option (which already makes Backspace and Delete erase a marked region), instead of changing default behaviour.
- **No status-bar hint and no help-screen section.** The man pages and the texinfo manual are updated instead.
- **The scrollbar keeps working.** nano 9.0 made a click in the scrollbar column (`--indicator`) jump through the buffer, and a press there does not start a drag.
- **The mouse wheel keeps working.** It scrolls the viewport exactly as in nano 9.x.
- **Works with old and new ncurses.** ncurses changed the order in which `getmouse()` returns a burst of events (newest first before its 20250913 patch, oldest first since). The patches check the running ncurses version and handle both. The tests pass with ncurses 6.4 (Ubuntu 24.04) and 6.6 (Fedora Rawhide, Debian unstable).

## Try it

```sh
git clone https://git.savannah.gnu.org/git/nano.git && cd nano
git checkout 4be01411
git am /path/to/nano-mouse/upstream/*.patch
./autogen.sh && ./configure && make
src/nano --mouse somefile
```

## Tests

The same harness as the 7.2 version runs in "upstream" mode:

```sh
FLAVOR=upstream NANO=src/nano STOCK_NANO=/path/to/unpatched/nano python3 tests/nanotest.py
```

It covers 69 checks: dragging, autoscroll, multi-clicks, Shift/Alt+click, `--zap` typing and pasting, undo, softwrap, line numbers, resizing, Unicode and bursts of fast input. It also checks that clicks, prompts and the shortcut bar behave as before, and that the mouse wheel and scrollbar clicks give **exactly** the same results as an unpatched nano.

On every push, CI builds nano master with these patches, using nano's own `autogen.sh`, on Ubuntu 24.04, Fedora Rawhide and Debian unstable, and runs the tests there. Locally, the series was also checked:
- **Building:** each commit builds on its own with no warnings under `-Wall -Wextra`. `--enable-tiny`, `--enable-tiny --enable-mouse` and `--disable-mouse` builds behave like unpatched nano.
- **Sanitizers:** the whole suite runs clean under AddressSanitizer and UBSan.

## Authorship

The patches were written with substantial help from an AI assistant (Claude). Each commit says so with an `Assisted-by:` trailer, and they carry no `Signed-off-by:`. Given GNU's caution about LLM-generated code, they're offered as a reference implementation. The nano developers are welcome to implement the behaviour in their own way.
