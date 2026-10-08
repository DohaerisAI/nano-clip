#!/usr/bin/env bash
# Remove nano-mouse, as installed by install.sh.  The distribution's own nano
# (/usr/bin/nano) takes over again.
#
#   ./uninstall.sh            remove the per-user install (~/.local)
#   ./uninstall.sh --system   remove the system-wide install (/usr/local, uses sudo)
#   ./uninstall.sh --prefix DIR
set -euo pipefail

prefix="$HOME/.local"
while [ $# -gt 0 ]; do
	case "$1" in
		--system) prefix=/usr/local ;;
		--prefix) prefix="$2"; shift ;;
		-h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
		*) echo "Unknown option: $1" >&2; exit 2 ;;
	esac
	shift
done

manifest="$prefix/share/nano-mouse/installed-files"
[ -f "$manifest" ] || { echo "nano-mouse is not installed in $prefix (no $manifest)." >&2; exit 1; }

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
run rmdir --ignore-fail-on-non-empty "$prefix/share/nano-mouse" "$prefix/share/nano" \
	"$prefix/share/doc/nano" 2>/dev/null || true

hash -r 2>/dev/null || true
echo "Removed $count files from $prefix."
echo "'nano' now runs: $(command -v nano || echo 'nothing found in PATH')"
