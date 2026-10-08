#!/usr/bin/env bash
# Build and install GNU nano 7.2 with the nano-mouse patch.
#
#   ./install.sh            install for the current user, in ~/.local/bin
#   ./install.sh --system   install for every user, in /usr/local/bin (uses sudo)
#
# The distribution's own nano (/usr/bin/nano) is never touched, so apt upgrades
# cannot break or overwrite this one.  Undo everything with ./uninstall.sh.
set -euo pipefail

NANO_VERSION=7.2
TARBALL_SHA256=86f3442768bd2873cec693f83cdf80b4b444ad3cc14760b74361474fc87a4526
TARBALL_URLS=(
	"https://www.nano-editor.org/dist/v7/nano-${NANO_VERSION}.tar.xz"
	"http://deb.debian.org/debian/pool/main/n/nano/nano_${NANO_VERSION}.orig.tar.xz"
	"http://archive.ubuntu.com/ubuntu/pool/main/n/nano/nano_${NANO_VERSION}.orig.tar.xz"
)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

prefix="$HOME/.local"
system=false
install_deps=true
run_tests=true
force=false

usage() {
	sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
	cat <<-EOF

	Options:
	  --system        install into /usr/local for all users (needs sudo)
	  --prefix DIR    install into DIR instead (binary goes to DIR/bin)
	  --no-deps       do not apt-get install the build dependencies
	  --skip-tests    do not run the automated tests before installing
	  --force         build even on an unsupported OS
	EOF
}

while [ $# -gt 0 ]; do
	case "$1" in
		--system) system=true; prefix=/usr/local ;;
		--prefix) prefix="$2"; shift ;;
		--no-deps) install_deps=false ;;
		--skip-tests) run_tests=false ;;
		--force) force=true ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
	esac
	shift
done

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

# Run a command as root: directly when we are root, otherwise through sudo.
as_root() {
	if [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

# --- 1. Check that this is a system the patch is meant for. ---
. /etc/os-release 2>/dev/null || true
case "${ID:-}:${VERSION_ID:-}" in
	ubuntu:24.04|debian:12) say "Detected ${PRETTY_NAME}" ;;
	*)
		$force || die "Supported systems are Ubuntu 24.04 and Debian 12 (both ship nano ${NANO_VERSION});
       this is ${PRETTY_NAME:-unknown}.  Use --force to build anyway."
		say "Unsupported system ${PRETTY_NAME:-unknown}; continuing because of --force" ;;
esac

if command -v dpkg-query >/dev/null && dpkg-query -W -f='${Version}' nano >/dev/null 2>&1; then
	installed="$(dpkg-query -W -f='${Version}' nano)"
	case "$installed" in
		"${NANO_VERSION}"-*) ;;
		*) $force || die "The system nano is version ${installed}, not ${NANO_VERSION}.  Use --force to build anyway." ;;
	esac
fi

# --- 2. Build dependencies. ---
needed=()
for pkg in build-essential libncurses-dev curl ca-certificates xz-utils patch; do
	dpkg -s "$pkg" >/dev/null 2>&1 || needed+=("$pkg")
done
if [ ${#needed[@]} -gt 0 ]; then
	if $install_deps; then
		say "Installing build dependencies: ${needed[*]}"
		as_root apt-get update -qq
		as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${needed[@]}"
	else
		say "Not installing (--no-deps): ${needed[*]}"
	fi
fi

# --- 3. Fetch and verify the pristine nano source. ---
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tarball="$work/nano-${NANO_VERSION}.tar.xz"

for url in "${TARBALL_URLS[@]}"; do
	say "Downloading $url"
	if curl -fsSL --retry 2 -o "$tarball" "$url" &&
			echo "${TARBALL_SHA256}  ${tarball}" | sha256sum -c --quiet - 2>/dev/null; then
		ok=true
		break
	fi
	ok=false
	echo "   (download failed or checksum mismatch; trying the next mirror)"
done
${ok:-false} || die "Could not download a verified nano-${NANO_VERSION} tarball."

# --- 4. Patch and build. ---
say "Applying nano-mouse.patch"
tar -xJf "$tarball" -C "$work"
src="$work/nano-${NANO_VERSION}"
patch -d "$src" -p1 --quiet < "$HERE/nano-mouse.patch"

say "Building"
# --sysconfdir=/etc: read the distribution's /etc/nanorc, like the stock nano.
if ! ( cd "$src" && ./configure --prefix="$prefix" --sysconfdir=/etc &&
		make -j"$(nproc)" ) > "$work/build.log" 2>&1; then
	tail -n 30 "$work/build.log"
	die "The build failed (see the output above)."
fi

# --- 5. Test the freshly built binary. ---
if $run_tests; then
	if command -v python3 >/dev/null; then
		say "Running the automated tests (about two minutes)"
		mkdir -p "$work/tests"
		NANO="$src/src/nano" WORK="$work/tests" python3 "$HERE/tests/nanotest.py" \
						> "$work/tests.log" 2>&1 || true
		tail -n 1 "$work/tests.log"
		if grep -q '^FAIL' "$work/tests.log" || ! grep -q ' passed$' "$work/tests.log"; then
			grep '^FAIL' "$work/tests.log" || tail -n 20 "$work/tests.log"
			die "Tests failed, so nothing was installed.  (--skip-tests skips them.)"
		fi
	else
		say "Skipping the tests: python3 is not installed"
	fi
fi

# --- 6. Install, keeping a list of the installed files for uninstall.sh. ---
say "Installing into $prefix"
stage="$work/stage"
make -C "$src" install DESTDIR="$stage" >> "$work/build.log" 2>&1 ||
	{ tail -n 30 "$work/build.log"; die "Staging the installation failed."; }
manifest_dir="$prefix/share/nano-mouse"
# The info "dir" index is shared with other packages, so it is not ours to remove.
( cd "$stage" && find . \( -type f -o -type l \) ! -path '*/share/info/dir' |
		sed 's|^\.||' ) > "$work/installed-files"
echo "$manifest_dir/installed-files" >> "$work/installed-files"

# Use root only when the prefix is not writable (e.g. /usr/local).
needs_root=false
if [ -e "$prefix" ]; then
	[ -w "$prefix" ] || needs_root=true
else
	[ -w "$(dirname "$prefix")" ] || needs_root=true
fi
maybe_root() {
	if $needs_root; then as_root "$@"; else "$@"; fi
}
# Copy without preserving ownership, so that a system install is owned by root.
maybe_root mkdir -p "$prefix" "$manifest_dir"
maybe_root cp -dR --preserve=mode,timestamps "$stage$prefix/." "$prefix/"
maybe_root cp "$work/installed-files" "$manifest_dir/installed-files"

# --- 7. Tell the user how to start using it. ---
hash -r 2>/dev/null || true
say "Installed: $prefix/bin/nano"
found="$(command -v nano || true)"
if [ "$found" != "$prefix/bin/nano" ]; then
	echo
	echo "Note: 'nano' currently runs ${found:-nothing}, not the patched one."
	echo "Put $prefix/bin before /usr/bin in PATH, for example by adding this to ~/.bashrc:"
	echo "    export PATH=\"$prefix/bin:\$PATH\""
	echo "Then open a new terminal."
fi
if ! grep -qs '^[[:space:]]*set[[:space:]]\+mouse' "$HOME/.nanorc" /etc/nanorc; then
	echo
	echo "To use the mouse, enable it once:   echo 'set mouse' >> ~/.nanorc"
	echo "(or press Alt+M inside nano)."
fi
echo
echo "Inside nano, press Ctrl+G and scroll to the end for the list of mouse actions."
