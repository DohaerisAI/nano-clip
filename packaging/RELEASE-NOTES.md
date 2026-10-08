Ready-made GNU nano 7.2 with the nano-mouse patch, for **Ubuntu 24.04** and **Debian 12**.

- `nano-mouse-…-linux-x86_64.tar.gz`: Intel/AMD 64-bit, including WSL2
- `nano-mouse-…-linux-arm64.tar.gz`: ARM 64-bit

Install: unpack it, then `cp nano ~/.local/bin/` (just you) or `sudo cp nano /usr/local/bin/` (everyone). Then enable the mouse with `echo 'set mouse' >> ~/.nanorc`. The included README.txt has the details.

To build from source instead, see the [README](https://github.com/DohaerisAI/nano-mouse#install).

The binaries were built on Debian 12 and passed the full automated test suite on clean Ubuntu 24.04 machines before this release was published.
