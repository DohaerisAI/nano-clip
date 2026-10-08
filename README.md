# nano-clip

[![build](https://github.com/DohaerisAI/nano-clip/actions/workflows/build.yml/badge.svg)](https://github.com/DohaerisAI/nano-clip/actions/workflows/build.yml)

**Use your mouse in nano like in any other editor:** drag to select, double-click a word, and copy straight to your system clipboard.

## Install: one command

Open a terminal and paste this:

```sh
curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-clip/main/install.sh | bash
```

That's it. Open a **new** terminal window and use `nano` as usual.

It takes a few seconds. It doesn't need your password, and it doesn't touch the nano that came with your system. You can remove it again at any time (see [Undo](#undo)).

## Works on

| Your system | Supported |
|---|---|
| Ubuntu 22.04 LTS | ✅ |
| Ubuntu 24.04 LTS | ✅ |
| Ubuntu 26.04 LTS | ✅ |
| Debian 12 | ✅ |
| Windows with WSL (Ubuntu) | ✅ |
| Anything else | ❌ not yet (the installer says so and changes nothing) |

Both normal PCs (x86_64) and ARM machines (arm64) work. Not sure which Ubuntu you have? Run `lsb_release -d`.

## What you can do

| Do this | What happens |
|---|---|
| **Drag** with the mouse | Selects text. Drag past the top or bottom and it keeps scrolling. |
| **Double-click** | Selects a word. |
| **Triple-click** | Selects the whole line. |
| **Alt+click** | Extends the selection to where you click. |
| **Type** while text is selected | Replaces it, like any editor. Backspace and Delete remove it. Alt+U undoes. |
| **Alt+6** (copy) or **Ctrl+K** (cut) | Also puts the text on your **system clipboard**, ready to paste into any other app. |

The first time you select something, nano shows a short hint at the bottom. Press **Ctrl+G** in nano and scroll to the end for the full list.

## Undo

To remove nano-clip and get your normal nano back:

```sh
curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-clip/main/uninstall.sh | bash
```

## Questions

**It still behaves like the old nano.** Open a *new* terminal window first. If it still does, run `which nano`. If that shows `/usr/bin/nano`, add `export PATH="$HOME/.local/bin:$PATH"` to the end of `~/.bashrc` and open a new terminal.

**Copy works in nano, but I can't paste in other apps.** Your terminal needs to support "OSC 52", the way programs put text on the clipboard. Windows Terminal, kitty, WezTerm, Alacritty and foot do. iTerm2 does once you allow clipboard access in its settings. In other terminals, everything except the clipboard still works.

**Shift+click doesn't work (Windows Terminal).** Windows Terminal keeps Shift+click for its own selection. Use **Alt+click** instead.

**Will a system update break it?** No. `apt upgrade` updates the system's nano in `/usr/bin` and never touches this one. Your settings (`~/.nanorc`) and colours stay the same.

**Can I install it for every user on the machine?** Yes: `curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-clip/main/install.sh | bash -s -- --system`. This asks for your password, and installs into `/usr/local/bin`.

**I'd rather build it myself.** Clone the repository and run `./install.sh --from-source`. It downloads the official nano source, checks it, applies the patch, builds, and runs the automated tests before installing.

## Changes from the normal nano

Everything works as before, except:

- Typing, pasting, Backspace or Delete while text is selected with the mouse or Shift+arrows replaces it. (Normal nano drops the selection and types at the cursor. The Ctrl+6 mark mode is unchanged.)
- Two quick clicks on the same spot are a double-click. Clicking on the cursor still sets the mark if you click a bit slower.
- Copies and cuts also go to the system clipboard. Anything over 100 KB stays in nano only.

---

## For the curious

### What's in this repository

| | |
|---|---|
| [`install.sh`](install.sh), [`uninstall.sh`](uninstall.sh) | The installer and uninstaller |
| [`patches/`](patches/) | The changes to nano's source, one file per nano version: [6.2](patches/nano-6.2.patch) (Ubuntu 22.04), [7.2](patches/nano-7.2.patch) (Ubuntu 24.04, Debian 12), [8.7.1](patches/nano-8.7.1.patch) (Ubuntu 26.04) |
| [`tests/`](tests/) | Automated tests |
| [`upstream/`](upstream/) | A version proposed to the official nano developers (see [Status](#status)) |

### How the installer works

1. It reads `/etc/os-release` to find your system, and so which nano version it needs.
2. It downloads the ready-made nano for that system and your CPU from [Releases](https://github.com/DohaerisAI/nano-clip/releases), and checks its SHA-256 checksum.
3. It installs it into `~/.local/bin`, which comes before `/usr/bin` in `PATH`, so `nano` runs the new one. It keeps a list of what it installed, so the uninstaller removes exactly that.
4. It adds `set mouse` to `~/.nanorc`, marked so the uninstaller can remove it again.

With `--from-source`, step 2 instead downloads the official nano source (checksum-verified), applies the patch, builds it, and runs the tests, comparing the mouse wheel and scrollbar with your system's own nano. `./install.sh --help` lists all options.

### How the patch works

- **Drag reporting:** nano asks the terminal for drag events (xterm mode 1002). ncurses doesn't do this itself, and it turns the mode off again after every resize or suspend, so nano re-requests it each time.
- **Event handling:** when mouse events arrive in a burst, ncurses hands them over as a group, newest first before its 20250913 patch and oldest first since. nano checks the ncurses version and handles them in the right order. Double- and triple-clicks are counted by nano, because ncurses' own click detection has to be off to get drag events.
- **Clipboard:** the text goes to the terminal's clipboard with the OSC 52 escape sequence.
- **Replacing text:** typing over a selection uses nano's existing "zap" (delete without touching the cutbuffer), so it can be undone.

### Testing

[`tests/nanotest.py`](tests/nanotest.py) runs nano in a pseudo-terminal and sends it real xterm mouse sequences. It checks the clipboard data and the saved files: selection, autoscroll, multi-clicks, Alt/Shift+click, typing over, undo, softwrap, line numbers, resizing, suspend, Unicode and bursts of fast input. It also checks that the mouse wheel and scrollbar behave exactly like the unpatched nano of the same version.

On every change, GitHub builds and tests it from source on clean Ubuntu 22.04, 24.04 (x86_64 and arm64), 26.04 and Debian 12 machines. Each release's ready-made binaries are tested again on their own system before they're published, and then the one-line installer itself is run on each system.

```sh
python3 tests/nanotest.py                                          # tests ~/.local/bin/nano
NANO=/path/to/nano STOCK_NANO=/usr/bin/nano python3 tests/nanotest.py
```

### Status

This is an independent project. It is **not part of GNU nano** and not endorsed by the GNU project.

A version reshaped for the current nano (9.x) has been proposed to the nano developers. See [`upstream/`](upstream/). In that version, typing over a selection is opt-in through `--zap`, and there's no built-in clipboard, because nano 8.7 and later can bind OSC 52 copying in the nanorc.

### License

GPL-3.0-or-later, the same as GNU nano. See [LICENSE](LICENSE).
