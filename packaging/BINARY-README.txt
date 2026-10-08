nano-clip: GNU nano with mouse selection and system clipboard
https://github.com/DohaerisAI/nano-clip

The easiest way to install is the one-line installer, which picks the right
download for your system automatically:

    curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-clip/main/install.sh | bash

To install this download by hand instead, check that it matches your system:

    nano-clip-nano6.2-...    Ubuntu 22.04
    nano-clip-nano7.2-...    Ubuntu 24.04 and Debian 12
    nano-clip-nano8.7.1-...  Ubuntu 26.04

then copy the program into place:

    mkdir -p ~/.local/bin && cp nano ~/.local/bin/      (just for you)
    sudo cp nano /usr/local/bin/                        (for everyone)

and switch the mouse on:   echo 'set mouse' >> ~/.nanorc

To go back to the system's own nano, delete the copied file.

License: GPL-3.0-or-later (see LICENSE).  Source: the repository above.
