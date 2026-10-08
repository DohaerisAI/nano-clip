#!/usr/bin/env bash
# nano-mouse installer: GNU nano with mouse selection and system clipboard.
#
# One line, no clone needed:
#   curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-mouse/main/install.sh | bash
#
# Or from a clone:   ./install.sh [options]
#
# By default it installs a ready-made, tested nano for your system into
# ~/.local/bin (no root needed).  The distribution's own nano is never touched,
# and `uninstall.sh` puts everything back.
set -euo pipefail

REPO=DohaerisAI/nano-mouse
RAW="https://raw.githubusercontent.com/$REPO/main"
# (NANO_MOUSE_RELEASES can point elsewhere, e.g. a local folder, for testing.)
RELEASES="${NANO_MOUSE_RELEASES:-https://github.com/$REPO/releases/latest/download}"

prefix="$HOME/.local"
system=false
from_source=false
install_deps=true
run_tests=true
nano_version=""

usage() {
	cat <<-EOF
	Install nano-mouse: GNU nano with mouse selection and system clipboard.

	Usage: install.sh [options]

	  --system           install for every user, into /usr/local (uses sudo)
	  --prefix DIR       install into DIR (the program goes into DIR/bin)
	  --from-source      build from source instead of using a ready-made binary
	  --no-deps          when building, do not apt-get install build tools
	  --skip-tests       when building, do not run the automated tests
	  --nano VERSION     build this nano version (6.2, 7.2, or 8.7.1); implies
	                     --from-source and skips the system check
	  -h, --help         show this help

	Supported: Ubuntu 22.04 (nano 6.2), Ubuntu 24.04 and Debian 12 (nano 7.2),
	and Ubuntu 26.04 (nano 8.7.1), on x86_64 and arm64.
	EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
		--system) system=true; prefix=/usr/local ;;
		--prefix) prefix="$2"; shift ;;
		--from-source) from_source=true ;;
		--no-deps) install_deps=false ;;
		--skip-tests) run_tests=false ;;
		--nano) nano_version="$2"; from_source=true; shift ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
	esac
	shift
done

if [ -t 1 ]; then bold=$'\033[1m'; red=$'\033[1;31m'; green=$'\033[1;32m'; plain=$'\033[0m'
else bold=""; red=""; green=""; plain=""; fi
say() { printf '%s==> %s%s\n' "$bold" "$*" "$plain"; }
die() { printf '%sError:%s %s\n' "$red" "$plain" "$*" >&2; exit 1; }

# Run a command as root: directly when we are root, otherwise through sudo.
as_root() {
	if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

# Download a URL to a file, quietly, with a few retries.
fetch() {
	curl -fsSL --retry 3 --retry-delay 2 -o "$2" "$1"
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# --- 1. Which nano does this system need? ---
# shellcheck source=/dev/null
. /etc/os-release 2>/dev/null || true
system_name="${PRETTY_NAME:-an unknown system}"

if [ -z "$nano_version" ]; then
	case "${ID:-}:${VERSION_ID:-}" in
		ubuntu:22.04)            nano_version=6.2 ;;
		ubuntu:24.04|debian:12)  nano_version=7.2 ;;
		ubuntu:26.04)            nano_version=8.7.1 ;;
		*)
			die "nano-mouse supports Ubuntu 22.04, 24.04 and 26.04, and Debian 12.
       This is $system_name.  (Experts: --nano VERSION builds a specific version.)" ;;
	esac
fi

case "$nano_version" in
	6.2)   tarball_sha256=2bca1804bead6aaf4ad791f756e4749bb55ed860eec105a97fba864bc6a77cb3 ;;
	7.2)   tarball_sha256=86f3442768bd2873cec693f83cdf80b4b444ad3cc14760b74361474fc87a4526 ;;
	8.7.1) tarball_sha256=76f0dcb248f2e2f1251d4ecd20fd30fb400a360a3a37c6c340e0a52c2d1cdedf ;;
	*) die "There is no nano-mouse for nano $nano_version (available: 6.2, 7.2, 8.7.1)." ;;
esac

case "$(uname -m)" in
	x86_64|amd64)  arch=x86_64 ;;
	aarch64|arm64) arch=arm64 ;;
	*)             arch="$(uname -m)" ;;
esac

say "This is $system_name ($arch), which comes with nano $nano_version"

# Use root only when the target directory is not writable by us.
needs_root=false
if $system; then
	needs_root=true
elif [ -e "$prefix" ]; then
	[ -w "$prefix" ] || needs_root=true
else
	[ -w "$(dirname "$prefix")" ] || needs_root=true
fi
maybe_root() {
	if $needs_root; then as_root "$@"; else "$@"; fi
}

manifest_dir="$prefix/share/nano-mouse"
stage="$work/stage"
mkdir -p "$stage"

# --- 2a. The quick way: a ready-made binary, tested for this system. ---
install_binary() {
	local asset="nano-mouse-nano$nano_version-linux-$arch.tar.gz"

	say "Downloading the ready-made nano $nano_version for $arch"
	fetch "$RELEASES/$asset" "$work/$asset" && fetch "$RELEASES/$asset.sha256" "$work/$asset.sha256" ||
		return 1

	( cd "$work" && sha256sum -c --quiet "$asset.sha256" ) || die "The download is damaged (checksum mismatch)."
	tar -xzf "$work/$asset" -C "$work"

	mkdir -p "$stage$prefix/bin"
	cp "$work"/nano-mouse-*/nano "$stage$prefix/bin/nano"
	ln -s nano "$stage$prefix/bin/rnano"
	"$stage$prefix/bin/nano" --version > /dev/null || die "The downloaded nano does not run here."
}

# --- 2b. The thorough way: build from the official source, and test it. ---
install_from_source() {
	local here="" src="$work/nano-$nano_version" tarball="$work/nano-$nano_version.tar.xz"
	local major="${nano_version%%.*}"

	# The patch and the tests: next to this script, or else from GitHub.
	if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "$(dirname "${BASH_SOURCE[0]}")/patches/nano-$nano_version.patch" ]; then
		here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	else
		say "Downloading the nano-mouse patch"
		here="$work/nano-mouse"
		mkdir -p "$here/patches" "$here/tests"
		fetch "$RAW/patches/nano-$nano_version.patch" "$here/patches/nano-$nano_version.patch" ||
			die "Could not download the patch."
		fetch "$RAW/tests/nanotest.py" "$here/tests/nanotest.py" || run_tests=false
	fi

	local needed=()
	for pkg in build-essential libncurses-dev curl ca-certificates xz-utils patch; do
		dpkg -s "$pkg" >/dev/null 2>&1 || needed+=("$pkg")
	done
	if [ ${#needed[@]} -gt 0 ]; then
		if $install_deps; then
			say "Installing the build tools: ${needed[*]}"
			as_root apt-get update -qq
			as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${needed[@]}" > /dev/null
		else
			say "Not installing (--no-deps): ${needed[*]}"
		fi
	fi

	local ok=false
	for url in "https://www.nano-editor.org/dist/v$major/nano-$nano_version.tar.xz" \
			"http://archive.ubuntu.com/ubuntu/pool/main/n/nano/nano_$nano_version.orig.tar.xz" \
			"http://deb.debian.org/debian/pool/main/n/nano/nano_$nano_version.orig.tar.xz"; do
		say "Downloading the official nano $nano_version source"
		if fetch "$url" "$tarball" && echo "$tarball_sha256  $tarball" | sha256sum -c --quiet - 2>/dev/null; then
			ok=true
			break
		fi
		echo "   (that mirror failed; trying the next one)"
	done
	$ok || die "Could not download a verified nano-$nano_version tarball."

	say "Applying the patch"
	tar -xJf "$tarball" -C "$work"
	patch -d "$src" -p1 --quiet < "$here/patches/nano-$nano_version.patch"

	say "Building (about a minute)"
	# --sysconfdir=/etc: read the distribution's /etc/nanorc, like the stock nano.
	if ! ( cd "$src" && ./configure --prefix="$prefix" --sysconfdir=/etc &&
			make -j"$(nproc)" ) > "$work/build.log" 2>&1; then
		tail -n 30 "$work/build.log"
		die "The build failed (see above)."
	fi

	if $run_tests && command -v python3 >/dev/null; then
		say "Testing it (about two minutes; --skip-tests skips this)"
		# Compare with the system's own nano where it is the same version.
		local stock=""
		if /usr/bin/nano --version 2>/dev/null | grep -q "version $nano_version\$\|version $nano_version "; then
			stock=/usr/bin/nano
		fi
		mkdir -p "$work/tests"
		NANO="$src/src/nano" STOCK_NANO="$stock" WORK="$work/tests" \
				python3 "$here/tests/nanotest.py" > "$work/tests.log" 2>&1 || true
		tail -n 1 "$work/tests.log"
		if grep -q '^FAIL' "$work/tests.log" || ! grep -q ' passed$' "$work/tests.log"; then
			grep '^FAIL' "$work/tests.log" || tail -n 20 "$work/tests.log"
			die "Tests failed, so nothing was installed."
		fi
	fi

	make -C "$src" install DESTDIR="$stage" >> "$work/build.log" 2>&1 ||
		{ tail -n 30 "$work/build.log"; die "Staging the installation failed."; }
}

if $from_source; then
	install_from_source
elif ! install_binary; then
	say "No ready-made nano for this system yet; building it from source instead"
	install_from_source
fi

# --- 3. Install, keeping a list of the installed files for uninstall.sh. ---
say "Installing into $prefix"
# The info "dir" index is shared with other packages, so it is not ours to remove.
( cd "$stage" && find . \( -type f -o -type l \) ! -path '*/share/info/dir' | sed 's|^\.||' ) \
		> "$work/installed-files"
echo "$manifest_dir/installed-files" >> "$work/installed-files"

maybe_root mkdir -p "$prefix" "$manifest_dir"
# Copy without preserving ownership, so that a system install is owned by root.
maybe_root cp -dR --preserve=mode,timestamps "$stage$prefix/." "$prefix/"
maybe_root cp "$work/installed-files" "$manifest_dir/installed-files"

# --- 4. Switch the mouse on (for a personal install), and say how to start. ---
if ! $system && ! grep -qs '^[[:space:]]*\(set\|unset\)[[:space:]]\+mouse' "$HOME/.nanorc"; then
	echo "set mouse  # added by nano-mouse" >> "$HOME/.nanorc"
	mouse_note="The mouse is switched on in ~/.nanorc."
else
	mouse_note="To use the mouse, have 'set mouse' in your nanorc (or press Alt+M in nano)."
fi

hash -r 2>/dev/null || true
echo
printf '%sDone!%s nano-mouse is installed in %s\n' "$green" "$plain" "$prefix/bin/nano"
echo "$mouse_note"

case ":$PATH:" in
	*":$prefix/bin:"*)
		echo "Just type:  nano somefile" ;;
	*)
		echo
		echo "One more step: open a NEW terminal window, then type:  nano somefile"
		echo "(If 'which nano' still shows /usr/bin/nano there, add this line to ~/.bashrc:"
		echo "    export PATH=\"$prefix/bin:\$PATH\""
		echo " and open a new terminal again.)" ;;
esac
echo
echo "In nano: drag to select, double-click a word, Alt+6 to copy.  Ctrl+G shows all mouse actions."
echo "To remove it again:  curl -fsSL $RAW/uninstall.sh | bash"
