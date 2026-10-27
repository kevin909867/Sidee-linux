#!/bin/sh
# Sidee for Linux: prepare a private runtime on first use, then open the
# dashboard. No root rights, no pip and no system Python packages are required.
#
# Usage:
#   ./start-linux.sh                 open the dashboard in your browser
#   ./start-linux.sh --headless      run the dashboard without a browser
#   ./start-linux.sh --port 8787     choose the dashboard port
#   ./start-linux.sh --prepare-only  prepare the runtime and exit (used by CI)
#
# Every other argument is passed straight to sidee.py.
set -eu

SIDEE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# The private runtime sits next to the app, unless that folder is read-only (for
# example a download that an administrator extracted into /opt).
SIDEE_RUNTIME="$SIDEE_ROOT/.runtime"
if [ ! -w "$SIDEE_RUNTIME" ] && [ ! -w "$SIDEE_ROOT" ]; then
    SIDEE_RUNTIME="${XDG_STATE_HOME:-$HOME/.local/state}/sidee/download"
fi
SIDEE_PACKAGE_VERSION=2.1.0
# Published paho-mqtt wheel and its SHA-256 checksum from PyPI. It is pure
# Python, so one file serves every CPU architecture.
SIDEE_PACKAGE_URL='https://files.pythonhosted.org/packages/c4/cb/00451c3cf31790287768bb12c6bec834f5d292eaf3022afc88e14b8afc94/paho_mqtt-2.1.0-py3-none-any.whl'
SIDEE_PACKAGE_SHA256='6db9ba9b34ed5bc6b6e3812718c7e06e2fd7444540df2455d2c51bd58808feee'
SIDEE_PACKAGE_DIR="$SIDEE_RUNTIME/packages/paho-mqtt-$SIDEE_PACKAGE_VERSION"
SIDEE_ARCHIVE_NAME="paho_mqtt-$SIDEE_PACKAGE_VERSION-py3-none-any.whl"

fail() {
    printf '\n%s\n' "$*" >&2
    exit 1
}

prepare_only=0
if [ "${1:-}" = "--prepare-only" ]; then
    prepare_only=1
    shift
fi

[ -f "$SIDEE_ROOT/sidee.py" ] || \
    fail "Extract the complete Sidee folder (or download) before running start-linux.sh."

# --- 1. Locate a Python 3.9+ interpreter ---------------------------------------
supports_sidee() {
    "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' \
        >/dev/null 2>&1
}

SIDEE_PYTHON=${SIDEE_PYTHON:-}
if [ -z "$SIDEE_PYTHON" ]; then
    # Try every name and keep the first one that is new enough, so an old
    # "python3" does not hide a working python3.12 alongside it.
    for candidate in python3 python3.14 python3.13 python3.12 python3.11 \
            python3.10 python3.9 python; do
        if command -v "$candidate" >/dev/null 2>&1 && supports_sidee "$candidate"; then
            SIDEE_PYTHON=$candidate
            break
        fi
    done
fi
[ -n "$SIDEE_PYTHON" ] || fail "Python 3.9 or newer is required. Install python3 \
with your distribution's package manager and run start-linux.sh again."
supports_sidee "$SIDEE_PYTHON" \
    || fail "$SIDEE_PYTHON is too old. Sidee needs Python 3.9 or newer."

release_setup_lock() {
    rm -rf "$SIDEE_RUNTIME/setup.lock" "$SIDEE_RUNTIME/setup-$$" 2>/dev/null || true
}

run_sidee() {
    release_setup_lock
    trap - EXIT INT TERM
    if [ "$prepare_only" = "1" ]; then
        echo "Setup complete. The dashboard is ready to open."
        return 0
    fi
    export PYTHONPATH="$SIDEE_PACKAGE_DIR${PYTHONPATH:+:$PYTHONPATH}"
    exec "$SIDEE_PYTHON" -u "$SIDEE_ROOT/sidee.py" "$@"
}

# --- 2. Reuse a TV connection library the interpreter already has --------------
# --prepare-only always builds the private runtime, so unpacking the download is
# reproducible on machines that also happen to have paho-mqtt installed.
if [ "$prepare_only" = "0" ] && \
        "$SIDEE_PYTHON" -c 'import paho.mqtt.client' >/dev/null 2>&1; then
    run_sidee "$@"
fi

# --- 3. Otherwise download the pinned, checksum-verified wheel -----------------
file_sha256() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d' ' -f1
    elif command -v openssl >/dev/null 2>&1; then
        openssl dgst -sha256 "$1" | sed 's/^.*[ =]//'
    else
        "$SIDEE_PYTHON" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
    fi
}

download() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 3 --connect-timeout 30 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -T 30 -O "$2" "$1"
    else
        "$SIDEE_PYTHON" -c 'import sys,urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "$1" "$2"
    fi
}

lock_owner_alive() {
    owner=$(cat "$SIDEE_RUNTIME/setup.lock/pid" 2>/dev/null || true)
    [ -n "$owner" ] || return 1
    kill -0 "$owner" 2>/dev/null
}

take_setup_lock() {
    if mkdir "$SIDEE_RUNTIME/setup.lock" 2>/dev/null; then
        printf '%s\n' "$$" >"$SIDEE_RUNTIME/setup.lock/pid"
        return 0
    fi
    # A recycled process id or a locked-up run must not block setup forever, so
    # an hour-old lock is reclaimed too.
    if lock_owner_alive && [ -z "$(find "$SIDEE_RUNTIME/setup.lock" -maxdepth 0 \
            -mmin +60 2>/dev/null)" ]; then
        return 1
    fi
    # The previous run was interrupted (Ctrl+C, reboot, closed terminal) and
    # left its lock behind. Reclaim it instead of failing every later launch.
    rm -rf "$SIDEE_RUNTIME/setup.lock"
    mkdir "$SIDEE_RUNTIME/setup.lock" 2>/dev/null || return 1
    printf '%s\n' "$$" >"$SIDEE_RUNTIME/setup.lock/pid"
}

mkdir -p "$SIDEE_RUNTIME" 2>/dev/null || fail "Sidee cannot write to $SIDEE_RUNTIME."
take_setup_lock || \
    fail "Sidee is already preparing this folder. Wait for its other run to finish."
trap release_setup_lock EXIT INT TERM

if [ ! -f "$SIDEE_PACKAGE_DIR/paho/mqtt/client.py" ]; then
    echo "First launch: preparing the app. Internet access is needed once."
    echo "Downloading the TV connection library..."
    mkdir -p "$SIDEE_RUNTIME/downloads"
    archive="$SIDEE_RUNTIME/downloads/$SIDEE_ARCHIVE_NAME"
    if [ ! -f "$archive" ] || [ "$(file_sha256 "$archive")" != "$SIDEE_PACKAGE_SHA256" ]; then
        rm -f "$archive"
        download "$SIDEE_PACKAGE_URL" "$archive" || \
            fail "The setup download failed. Check your Internet connection and try again."
        [ "$(file_sha256 "$archive")" = "$SIDEE_PACKAGE_SHA256" ] || \
            fail "A setup download failed its integrity check. Please try again."
    fi
    staging="$SIDEE_RUNTIME/setup-$$"
    mkdir -p "$staging"
    "$SIDEE_PYTHON" - "$archive" "$staging" <<'PYTHON'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as wheel:
    wheel.extractall(sys.argv[2])
PYTHON
    [ -f "$staging/paho/mqtt/client.py" ] || \
        fail "The setup package is incomplete. Please try again."
    rm -rf "$SIDEE_PACKAGE_DIR"
    mkdir -p "$(dirname -- "$SIDEE_PACKAGE_DIR")"
    mv "$staging" "$SIDEE_PACKAGE_DIR"
fi

run_sidee "$@"
