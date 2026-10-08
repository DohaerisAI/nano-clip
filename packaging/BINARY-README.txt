nano-mouse: GNU nano 7.2 with editor-style mouse selection and system clipboard
https://github.com/DohaerisAI/nano-mouse

For Ubuntu 24.04 and Debian 12 (both ship nano 7.2).

Install for yourself (no root needed):

    mkdir -p ~/.local/bin && cp nano ~/.local/bin/
    hash -r && which nano     # should print ~/.local/bin/nano

Or for every user on the machine:

    sudo cp nano /usr/local/bin/

Both come before /usr/bin in PATH, so they take precedence over the system
nano without touching it.  apt upgrades never overwrite them.  To go back to
the stock nano, delete the copied file.

Turn the mouse on once:   echo 'set mouse' >> ~/.nanorc

Inside nano, press Ctrl+G and scroll to the end for the list of mouse actions.

License: GPL-3.0-or-later (see LICENSE).  Source: the repository above.
