#!/bin/sh
# Remove a Sidee installation made by packaging/linux/install.sh.
# Saved pairings in ~/.sidee and runtime state are left untouched.
set -eu

usage() {
    cat <<'EOF'
Remove a Sidee installation made by install.sh.

Options:
  --user            remove a per-user install from ~/.local
  --system          remove a system install from /usr/local (default)
  --prefix PATH     use the same prefix that was used to install
  --purge           also delete saved pairings and runtime state
  -h, --help        show this help
EOF
}

mode=system
prefix=
purge=0
while [ $# -gt 0 ]; do
    case $1 in
        --user) mode=user ;;
        --system) mode=system ;;
        --prefix)
            shift
            [ $# -gt 0 ] || { echo "--prefix needs a path" >&2; exit 2; }
            prefix=$1
            ;;
        --purge) purge=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if [ "$mode" = user ]; then
    data_dir=${XDG_DATA_HOME:-$HOME/.local/share}
    bin_dir=${XDG_BIN_HOME:-$HOME/.local/bin}
    systemd_dir=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user
    [ -n "$prefix" ] || prefix=$HOME/.local
else
    [ -n "$prefix" ] || prefix=/usr/local
    data_dir=$prefix/share
    bin_dir=$prefix/bin
    systemd_dir=$prefix/lib/systemd/user
    if [ "$(id -u)" != "0" ] && [ -e "$prefix" ] && [ ! -w "$prefix" ]; then
        echo "Removing the install in $prefix needs root rights." >&2
        echo "Run it again as: sudo $0 --system --prefix $prefix" >&2
        exit 1
    fi
fi

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now sidee >/dev/null 2>&1 || true
fi

rm -rf "$data_dir/sidee"
rm -f "$bin_dir/sidee"
rm -f "$data_dir/applications/sidee.desktop"
rm -f "$data_dir/icons/hicolor/256x256/apps/sidee.png"
rm -f "$systemd_dir/sidee.service"

if [ "$purge" = 1 ]; then
    rm -rf "$HOME/.sidee" "$HOME/.vidaa-tile"
    rm -rf "${XDG_STATE_HOME:-$HOME/.local/state}/sidee"
    echo "Removed saved pairings and runtime state."
fi

echo "Sidee was removed from $prefix."
if [ "$purge" != 1 ]; then
    echo "Saved pairings in ~/.sidee were kept. Use --purge to delete them."
fi
