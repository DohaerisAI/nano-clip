#!/usr/bin/env bash
# Remove nano-clip, as installed by install.sh.  The distribution's own nano
# (/usr/bin/nano) takes over again.
#
#   curl -fsSL https://raw.githubusercontent.com/DohaerisAI/nano-clip/main/uninstall.sh | bash
#
#   ./uninstall.sh            remove the personal install (~/.local)
#   ./uninstall.sh --system   remove the system-wide install (/usr/local, uses sudo)
#   ./uninstall.sh --prefix DIR
set -euo pipefail

prefix="$HOME/.local"
system=false
while [ $# -gt 0 ]; do
	case "$1" in
		--system) prefix=/usr/local; system=true ;;
		--prefix) prefix="$2"; shift ;;
		-h|--help) sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
		*) echo "Unknown option: $1" >&2; exit 2 ;;
	esac
	shift
done

manifest="$prefix/share/nano-clip/installed-files"
# (This project used to be called nano-mouse.)
[ -f "$manifest" ] || [ ! -f "$prefix/share/nano-mouse/installed-files" ] ||
	manifest="$prefix/share/nano-mouse/installed-files"
if [ ! -f "$manifest" ]; then
	echo "nano-clip is not installed in $prefix."
	[ "$prefix" = "$HOME/.local" ] && [ -f /usr/local/share/nano-clip/installed-files ] &&
		echo "It is installed system-wide; remove that with:  ./uninstall.sh --system"
	exit 1
fi

run() {
	if [ -w "$prefix" ] || [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi
}

# Only remove files that the install recorded, and only below the prefix.
count=0
while IFS= read -r file; do
	case "$file" in
		"$prefix"/*) ;;
		*) continue ;;
	esac
	if [ -e "$file" ] || [ -L "$file" ]; then
		run rm -f -- "$file"
		count=$((count + 1))
	fi
done < "$manifest"

# Remove directories that are now empty (never the prefix itself).
run rmdir --ignore-fail-on-non-empty "$prefix/share/nano-clip" "$prefix/share/nano-mouse" "$prefix/share/nano" \
	"$prefix/share/doc/nano" 2>/dev/null || true

# Take out the 'set mouse' line that the installer added, and nothing else.
if ! $system && grep -qs '# added by nano-\(clip\|mouse\)$' "$HOME/.nanorc"; then
	sed -i '/# added by nano-\(clip\|mouse\)$/d' "$HOME/.nanorc"
	[ -s "$HOME/.nanorc" ] || rm -f "$HOME/.nanorc"
fi

hash -r 2>/dev/null || true
echo "Removed nano-clip ($count files)."
echo "'nano' now runs: $(command -v nano || echo 'nothing found in PATH') (open a new terminal if it still shows the old one)"
