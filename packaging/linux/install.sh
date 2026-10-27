#!/bin/sh
# Universal Sidee installer for any Linux distribution.
#
# Run it from an extracted Sidee folder (the one that contains sidee.py):
#   ./install.sh            install for every user (writes to /usr/local, needs root)
#   ./install.sh --user     install for the current user only (no root)
#   ./install.sh --prefix /opt --system
#   ./install.sh --no-icon --no-systemd
#
# The TV connection library is installed into <install>/vendor when the
# selected Python 3 does not already provide paho-mqtt.
set -eu

usage() {
    cat <<'EOF'
Install Sidee on Linux.

Options:
  --user            install into ~/.local (no root rights needed)
  --system          install into /usr/local (default; may need sudo)
  --prefix PATH     change the base prefix for a system install
  --no-icon         skip the desktop icon
  --no-desktop      skip the application menu entry
  --no-systemd      skip the user service unit
  --no-vendor       never download the TV connection library (offline install;
                    install paho-mqtt from your distribution instead)
  -h, --help        show this help
EOF
}

mode=system
prefix=
with_icon=1
with_desktop=1
with_systemd=1
with_vendor=1
while [ $# -gt 0 ]; do
    case $1 in
        --user) mode=user ;;
        --system) mode=system ;;
        --prefix)
            shift
            [ $# -gt 0 ] || { echo "--prefix needs a path" >&2; exit 2; }
            prefix=$1
            ;;
        --no-icon) with_icon=0 ;;
        --no-desktop) with_desktop=0 ;;
        --no-systemd) with_systemd=0 ;;
        --no-vendor) with_vendor=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ -f "$script_dir/sidee.py" ]; then
    source_dir=$script_dir
elif [ -f "$script_dir/../../sidee.py" ]; then
    source_dir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
else
    echo "Run install.sh from the extracted Sidee folder that contains sidee.py." >&2
    exit 1
fi

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
    if [ "$(id -u)" != "0" ]; then
        # Create a prefix this user is allowed to create (for example a folder in
        # their home directory) so only privileged locations ask for sudo.
        mkdir -p "$prefix" 2>/dev/null || true
        if [ ! -w "$prefix" ]; then
            echo "Installing into $prefix needs root rights." >&2
            echo "Run it again as: sudo $0 --system --prefix $prefix" >&2
            echo "Or install for your user only: $0 --user" >&2
            exit 1
        fi
    fi
fi
sidee_home=$data_dir/sidee

echo "Installing Sidee into $sidee_home"
mkdir -p "$sidee_home" "$bin_dir"
for item in sidee.py core assets docs README.md LICENSE; do
    [ -e "$source_dir/$item" ] || { echo "Missing $item in $source_dir" >&2; exit 1; }
    rm -rf "$sidee_home/$item"
    cp -R "$source_dir/$item" "$sidee_home/$item"
done
# A source folder that ran Sidee already holds bytecode for this Python only.
find "$sidee_home" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$sidee_home" -name '*.pyc' -delete 2>/dev/null || true

# The launcher ships with an empty placeholder so a custom --prefix still finds
# its program files.
escaped_home=$(printf '%s' "$sidee_home" | sed 's/[&|\\]/\\&/g')
sed "s|^sidee_home_installed=.*|sidee_home_installed='$escaped_home'|" \
    "$source_dir/packaging/linux/sidee" > "$bin_dir/sidee"
chmod 0755 "$bin_dir/sidee"

if [ "$with_desktop" = 1 ]; then
    desktop_dir=$data_dir/applications
    mkdir -p "$desktop_dir"
    sed "s|^Exec=sidee|Exec=$bin_dir/sidee|; s|^TryExec=sidee|TryExec=$bin_dir/sidee|" \
        "$source_dir/packaging/linux/sidee.desktop" > "$desktop_dir/sidee.desktop"
    chmod 0644 "$desktop_dir/sidee.desktop"
fi

if [ "$with_icon" = 1 ]; then
    icon_dir=$data_dir/icons/hicolor/256x256/apps
    mkdir -p "$icon_dir"
    cp "$source_dir/assets/sidee-logo.png" "$icon_dir/sidee.png"
    chmod 0644 "$icon_dir/sidee.png"
fi

if [ "$with_systemd" = 1 ]; then
    mkdir -p "$systemd_dir"
    sed "s|^ExecStart=/usr/bin/sidee|ExecStart=$bin_dir/sidee|" \
        "$source_dir/packaging/linux/sidee.service" > "$systemd_dir/sidee.service"
    chmod 0644 "$systemd_dir/sidee.service"
fi

# The TV connection library: reuse the interpreter's copy when it exists.
python=
for candidate in python3 python3.14 python3.13 python3.12 python3.11 \
        python3.10 python3.9 python; do
    if command -v "$candidate" >/dev/null 2>&1 && \
            "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
                >/dev/null 2>&1; then
        python=$candidate
        break
    fi
done
vendor_library() {
    SIDEE_HOME="$sidee_home" "$python" <<'PYTHON'
import hashlib
import os
import pathlib
import urllib.request
import zipfile

url = ("https://files.pythonhosted.org/packages/c4/cb/00451c3cf31790287768bb12c6bec834f5d292eaf3022afc88e14b8afc94/"
       "paho_mqtt-2.1.0-py3-none-any.whl")
expected = "6db9ba9b34ed5bc6b6e3812718c7e06e2fd7444540df2455d2c51bd58808feee"
home = pathlib.Path(os.environ["SIDEE_HOME"])
vendor = home / "vendor"
staging = home / "vendor-staging"
with urllib.request.urlopen(url, timeout=90) as response:
    data = response.read()
if hashlib.sha256(data).hexdigest() != expected:
    raise SystemExit("The TV connection library failed its integrity check.")
archive = staging.with_suffix(".whl")
archive.write_bytes(data)
if vendor.exists():
    import shutil
    shutil.rmtree(vendor)
with zipfile.ZipFile(archive) as wheel:
    wheel.extractall(staging)
staging.rename(vendor)
archive.unlink()
PYTHON
}

if [ "$with_vendor" = 0 ]; then
    echo "Skipping the TV connection library (--no-vendor)."
elif [ -z "$python" ]; then
    echo
    echo "Note: python3 was not found. Install Python 3.9 or newer before using Sidee."
elif env -u PYTHONPATH "$python" -c 'import paho.mqtt.client' >/dev/null 2>&1; then
    # Checked without PYTHONPATH: a launcher started from the menu or a fresh
    # shell will not inherit the installing shell's environment.
    echo "Using the TV connection library already available to $python."
else
    echo "Downloading the TV connection library into $sidee_home/vendor..."
    if ! vendor_library; then
        echo "Sidee is installed, but the TV connection library could not be downloaded." >&2
        echo "Install it with your package manager and try again, for example:" >&2
        echo "  Debian/Ubuntu: sudo apt install python3-paho-mqtt" >&2
        echo "  Fedora/RHEL:   sudo dnf install python3-paho-mqtt" >&2
        echo "  Arch:          sudo pacman -S python-paho-mqtt" >&2
    fi
fi

echo
echo "Sidee is installed."
if [ "$mode" = user ]; then
    echo "Make sure $bin_dir is in your PATH, then run: sidee"
else
    echo "Run: $bin_dir/sidee"
fi
if [ "$with_systemd" = 1 ]; then
    echo "Optional: enable the background dashboard with"
    echo "  systemctl --user daemon-reload && systemctl --user enable --now sidee"
    echo "  (installed unit: $systemd_dir/sidee.service)"
fi
