# nano-mouse

[![build](https://github.com/DohaerisAI/nano-mouse/actions/workflows/build.yml/badge.svg)](https://github.com/DohaerisAI/nano-mouse/actions/workflows/build.yml)

Editor-style mouse selection and a working system clipboard for **GNU nano 7.2**, the nano version in **Ubuntu 24.04 LTS** and **Debian 12**.

Stock nano 7.2 can place the cursor with the mouse, but it can't select text with it, and its copy (Alt+6) never reaches your system clipboard. This patch adds both. Nothing else changes.

```sh
git clone https://github.com/DohaerisAI/nano-mouse.git
cd nano-mouse && ./install.sh
echo 'set mouse' >> ~/.nanorc
```

## What you get

| Action | What it does |
|---|---|
| **Drag** | Selects text. Hold the pointer above or below the text and it keeps scrolling while the selection grows. |
| **Double-click** | Selects a word (letters, digits, `_`), a run of spaces or a run of punctuation. Keep the button down and drag to extend word by word. |
| **Triple-click** | Selects the whole line. Drag to extend line by line. |
| **Alt+click** (or Shift+click) | Extends the selection to the clicked spot, or starts one at the cursor. |
| **Type, paste, Backspace, Delete** | Replace or remove the selection, like any editor. Alt+U undoes it. |
| **Alt+6 / Ctrl+K / Alt+T** | Copy or cut as usual, and the text also goes to the **system clipboard**, so you can paste it into other apps. |

The first time you select something with the mouse, the status bar shows `M-6 copies to clipboard, ^K cuts, typing replaces, Alt+click extends`. The Ctrl+G help screen ends with a list of all the mouse actions:

```
 Mouse actions (with 'set mouse' or M-M):

Drag             select text; hold the pointer above or below the text to scroll
Double-click     select a word; keep the button down and drag to extend by words
Triple-click     select a whole line; drag to extend by lines
Alt+click        extend the selection to the clicked spot (also Shift+click)
Typing           replace the selection (also pasting, Backspace, Delete)
M-6, ^K          copy or cut; the text also goes to the system clipboard
```

## Requirements

- **nano version:** GNU nano **7.2** only. The patch does not apply to other versions.
- **OS:** **Ubuntu 24.04 LTS** or **Debian 12**, on x86_64 or arm64. WSL2 counts, since it runs Ubuntu.
- **Terminal:** any terminal with xterm mouse reporting, which nearly all of them have. For the clipboard, the terminal must also support **OSC 52**, as Windows Terminal, kitty, WezTerm, Alacritty, foot and iTerm2 (with clipboard access turned on in its settings) do. Other terminals ignore the clipboard part, and everything else still works.

It was developed and tested on **Ubuntu 24.04 in WSL2 with Windows Terminal**. Every push is also built and tested automatically on clean Ubuntu 24.04 (x86_64 and arm64) and Debian 12 machines.

## Install

### From source (recommended)

```sh
git clone https://github.com/DohaerisAI/nano-mouse.git
cd nano-mouse
./install.sh            # just for you: installs into ~/.local/bin
./install.sh --system   # or for every user: installs into /usr/local/bin (uses sudo)
```

The script:
1. checks that you are on Ubuntu 24.04 or Debian 12 with nano 7.2;
2. installs the build tools (`build-essential`, `libncurses-dev`) with apt if they are missing;
3. downloads the official nano 7.2 source and checks its SHA-256;
4. applies the patch and builds;
5. runs the 81 automated tests (about two minutes; skip them with `--skip-tests`);
6. installs, keeping a list of the installed files so that `uninstall.sh` can remove exactly those.

### Ready-made binary

If you don't want to compile, download a `.tar.gz` for your CPU from [Releases](https://github.com/DohaerisAI/nano-mouse/releases). Then:

```sh
tar -xzf nano-mouse-*-linux-x86_64.tar.gz
mkdir -p ~/.local/bin && cp nano-mouse-*/nano ~/.local/bin/    # or: sudo cp … /usr/local/bin/
```

### Turn on the mouse

Run `echo 'set mouse' >> ~/.nanorc` once, or press **Alt+M** inside nano.

## How it replaces your nano (and how to go back)

Nothing of the distribution's nano is changed or removed. The patched nano goes in `~/.local/bin` (for you) or `/usr/local/bin` (for everyone). On Ubuntu and Debian, both come **before** `/usr/bin` in `PATH`, so typing `nano` runs the patched one. That has some useful side effects:

- `apt upgrade` can't overwrite it or break it.
- It reads the same `/etc/nanorc` and `~/.nanorc` as before, so your settings and syntax colours stay the same.
- To go back, run `./uninstall.sh` (or `./uninstall.sh --system`), and `nano` is the stock one again.

If `which nano` still shows `/usr/bin/nano` after installing, `~/.local/bin` is not in your `PATH` yet. Open a new terminal, or add `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`.

## Notes for Windows Terminal (WSL)

- **Use Alt+click to extend a selection.** Windows Terminal keeps Shift+click and Shift+drag for its own text selection, which still works as usual and bypasses nano.
- The clipboard works out of the box. Alt+6 in nano, then Ctrl+V in any Windows app.

## Changes from stock nano 7.2

Keyboard behaviour is unchanged, except in these places:

- **Typing over a selection:** typing, pasting, Backspace and Delete now replace a selection made with the mouse or with Shift+arrows. Stock nano drops the selection and inserts at the cursor. The Ctrl+6 / Alt+A mark mode is unchanged.
- **Clicking the cursor twice:** clicking on the cursor still sets or unsets the mark, but two clicks on the same spot within half a second now count as a double-click.
- **Clipboard:** copies and cuts also go to the system clipboard. Selections over 100 KB are kept in nano only, and nano shows a warning on the status bar.

## How it works

The patch is [`nano-mouse.patch`](nano-mouse.patch), about 550 lines in six files of nano's source. In short:

- **Drag reporting:** nano asks the terminal for drag events (xterm mode 1002). ncurses doesn't do this itself, and it turns the mode off again after every resize or suspend, so nano re-requests it each time.
- **Event handling:** mouse events are handled one by one and in order. With fast input, ncurses groups several events together and returns them newest first, which stock nano mishandles. Double- and triple-clicks are counted in nano, because ncurses' own click detection had to be turned off to get drag events.
- **Clipboard:** the text is sent to the terminal's clipboard with the OSC 52 escape sequence (base64-encoded).
- **Replacing text:** typing over a selection uses nano's existing "zap" (delete without touching the cutbuffer), so it can be undone.

To apply the patch by hand: `cd nano-7.2 && patch -p1 < nano-mouse.patch`.

## Tests

[`tests/nanotest.py`](tests/nanotest.py) runs nano in a pseudo-terminal and sends it real xterm mouse sequences. It checks the clipboard data nano sends and the files it saves: selection, autoscroll, multi-clicks, Alt/Shift+click, typing over, undo, the clipboard, softwrap, line numbers, resizing, suspend, Unicode and bursts of fast input. It also checks that clicks, the mouse wheel, the shortcut bar and the prompts still behave as before.

```sh
python3 tests/nanotest.py                        # tests ~/.local/bin/nano
NANO=/path/to/nano python3 tests/nanotest.py     # tests another binary
```

## Status

This is an independent patch. It is **not part of GNU nano** and is not endorsed by the GNU project. It targets nano 7.2 only. The plan is to propose these features to the nano developers for the current version of nano.

## License

GPL-3.0-or-later, the same as GNU nano. See [LICENSE](LICENSE).
