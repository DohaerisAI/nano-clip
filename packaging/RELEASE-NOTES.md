GNU nano with mouse selection and system clipboard, ready-made for **Ubuntu 22.04, 24.04 and 26.04** and **Debian 12**, on x86_64 and arm64.

**Easiest:** you don't need to download anything here by hand. Just run:

```sh
curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-mouse/main/install.sh | bash
```

It picks the right file below for your system, checks it, installs it into `~/.local/bin` and switches the mouse on.

| File | For |
|---|---|
| `nano-mouse-nano6.2-linux-*.tar.gz` | Ubuntu 22.04 |
| `nano-mouse-nano7.2-linux-*.tar.gz` | Ubuntu 24.04, Debian 12 |
| `nano-mouse-nano8.7.1-linux-*.tar.gz` | Ubuntu 26.04 |

Each binary was built on the system it's for, and passed the full automated test suite on a clean machine of that system before this release was published.
