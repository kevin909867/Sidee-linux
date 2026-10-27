# Sidee on Linux

Sidee runs the same browser dashboard and TV control core on Linux as it does on
Windows and macOS. Everything runs as your normal user: there is no daemon, no
kernel module and no system service running as root. The only network traffic is
to your TV on the local network (SSDP discovery and MQTT/TLS on port 36669).

This guide covers every supported way to install Sidee on Linux, including
Debian/Ubuntu, Fedora/RHEL, openSUSE, Arch Linux and NixOS, plus the generic
installer for every other distribution.

- [Requirements](#requirements)
- [Which method should I use?](#which-method-should-i-use)
- [1. Run it from the download folder](#1-run-it-from-the-download-folder)
- [2. Universal installer](#2-universal-installer)
- [3. Debian and Ubuntu](#3-debian-and-ubuntu)
- [4. Fedora, RHEL, CentOS Stream, Rocky and AlmaLinux](#4-fedora-rhel-centos-stream-rocky-and-almalinux)
- [5. openSUSE and SLES](#5-opensuse-and-sles)
- [6. Arch Linux, Manjaro and EndeavourOS](#6-arch-linux-manjaro-and-endeavouros)
- [7. NixOS and Nix](#7-nixos-and-nix)
- [8. Alpine, Gentoo, Void and other distributions](#8-alpine-gentoo-void-and-other-distributions)
- [Run the dashboard in the background](#run-the-dashboard-in-the-background)
- [Using the dashboard](#using-the-dashboard)
- [Where Sidee keeps files](#where-sidee-keeps-files)
- [Firewall, VPN and discovery](#firewall-vpn-and-discovery)
- [Headless computers and SSH](#headless-computers-and-ssh)
- [Troubleshooting](#troubleshooting)
- [Updating and uninstalling](#updating-and-uninstalling)
- [Building the packages yourself](#building-the-packages-yourself)

## Requirements

- A 64-bit or 32-bit Linux distribution with **Python 3.9 or newer**
  (`python3 --version`). Python is already installed on almost every desktop
  distribution; no Python packages are needed if you use an installer, because
  Sidee either reuses the distribution package or downloads its own private,
  checksum-verified copy of its one dependency (`paho-mqtt`).
- A VIDAA TV (Hisense, Toshiba, and other VIDAA-based brands) on the same
  home Wi-Fi/Ethernet network as the computer.
- Internet access once if the TV connection library is not already installed.
- A browser for the dashboard. A desktop environment is **not** required: Sidee
  can run headless and be opened from another computer or phone (see
  [Headless computers and SSH](#headless-computers-and-ssh)).

`iproute2` (`ip`) is used to pick the right network interfaces for discovery. It
is installed by default everywhere, and Sidee falls back to
`ifconfig` (net-tools) and then to plain broadcast/multicast discovery when
neither is available.

## Which method should I use?

| Distribution | Recommended method | Section |
| --- | --- | --- |
| Any (just want to try it) | Extract the download and run `./start-linux.sh` | [1](#1-run-it-from-the-download-folder) |
| Any (no build tools) | `packaging/linux/install.sh` | [2](#2-universal-installer) |
| Debian, Ubuntu, Mint, Pop!_OS, Kali, Raspberry Pi OS | `.deb` package or `apt` | [3](#3-debian-and-ubuntu) |
| Fedora, RHEL, CentOS Stream, Rocky, AlmaLinux, Oracle | `.rpm` package or `dnf` | [4](#4-fedora-rhel-centos-stream-rocky-and-almalinux) |
| openSUSE Leap/Tumbleweed, SLES | Universal installer (or the RPM) | [5](#5-opensuse-and-sles) |
| Arch Linux, Manjaro, EndeavourOS, CachyOS | `PKGBUILD` or AUR | [6](#6-arch-linux-manjaro-and-endeavouros) |
| NixOS and other Nix systems | Flake package and NixOS module | [7](#7-nixos-and-nix) |
| Alpine, Gentoo, Void, Devuan, Slackware, ... | Universal installer | [8](#8-alpine-gentoo-void-and-other-distributions) |

Sidee is pure Python, so the same build works on every CPU architecture
(`x86_64`, `aarch64`, `armv7l`, `riscv64`, `ppc64le`, `s390x`, ...). Only the
package file name changes (for example `amd64` or `arm64` for Debian, and
`any` for Arch and Nix).

## 1. Run it from the download folder

This needs no installation, no root rights and no Python packages.

1. Download `sidee-linux.tar.gz` from
   [Releases](https://github.com/Empi9245/Sidee/releases) or from a successful
   [build workflow](https://github.com/Empi9245/Sidee/actions/workflows/build.yml).
2. Extract it and start the launcher:

   ```bash
   tar xzf sidee-linux.tar.gz
   cd Sidee
   ./start-linux.sh
   ```

On the first run, Sidee downloads a version-pinned `paho-mqtt` wheel from
PyPI, verifies its SHA-256 checksum and unpacks it into `.runtime/`. Later runs
reuse it. If your distribution already provides the library (for example
`python3-paho-mqtt`), Sidee detects it and skips the download entirely.

Options:

```bash
./start-linux.sh --headless          # dashboard without opening a browser
./start-linux.sh --port 8787         # pick the dashboard port
./start-linux.sh --prepare-only      # build the private runtime and exit
SIDEE_PYTHON=/usr/bin/python3.12 ./start-linux.sh   # choose the interpreter
```

`--prepare-only` always builds the private `.runtime/`, even when the system
Python already has `paho-mqtt`, so it can be used to pre-download the library
before going offline. A run that was interrupted while downloading is recovered
automatically: the next start removes the stale lock and tries again.

If the folder is read-only (for example an administrator extracted the download
into `/opt`), the runtime goes to
`$XDG_STATE_HOME/sidee/download` (`~/.local/state/sidee/download` by default)
and the dashboard state follows it. No `sudo` is needed.

Any other argument is passed to `sidee.py`, so the command line interface also
works this way:

```bash
./start-linux.sh discover
./start-linux.sh pair 192.168.1.50
./start-linux.sh install jellyfin --server 192.168.1.20:8096
```

## 2. Universal installer

`packaging/linux/install.sh` (also shipped as `install.sh` in the download)
works on any distribution. It copies the program files, adds the `sidee`
launcher, the application-menu entry, the icon and the optional systemd user
unit, and installs the TV connection library into `vendor/` when the system
Python does not have it.

```bash
# Per-user install, no root needed (installs into ~/.local):
./install.sh --user

# System install for every user (installs into /usr/local):
sudo ./install.sh

# Custom prefix:
sudo ./install.sh --prefix /opt
```

Other options: `--no-desktop`, `--no-icon`, `--no-systemd`, `--no-vendor`.

`--no-vendor` skips the download entirely, for air-gapped machines or when you
prefer the distribution package (`sudo apt install python3-paho-mqtt`). Sidee
then relies on that system package.

A custom `--prefix` works: the installed launcher records where its program
files went, so `--prefix /opt` (or any other folder, including paths with
spaces) runs correctly. The installer prints the exact unit path it used; the
service unit is only picked up automatically from `/usr/lib/systemd/user`,
`/usr/local/lib/systemd/user` or your XDG config directory, so copy or symlink
it when you install somewhere else.

If `~/.local/bin` is not on your `PATH`, add it:

```bash
export PATH="$HOME/.local/bin:$PATH"      # add to ~/.profile to make it permanent
```

Remove it again with the matching uninstaller:

```bash
./uninstall.sh --user     # or: sudo ./uninstall.sh
./uninstall.sh --user --purge   # also delete saved pairings and runtime state
```

## 3. Debian and Ubuntu

Debian, Ubuntu, Linux Mint, Pop!\_OS, Kali, elementary, Zorin, Raspberry Pi OS
and everything else using `apt`/`dpkg` is covered by the `.deb` package.

Download `sidee_<version>-1_<arch>.deb` (for example
`sidee_0.1.4.2-1_amd64.deb`, or `arm64` on a Raspberry Pi 4/5 or other 64-bit
ARM board) from Releases or the build workflow, then install it:

```bash
sudo apt install ./sidee_0.1.4.2-1_amd64.deb
sidee
```

`apt` resolves the two dependencies (`python3` and `python3-paho-mqtt`)
automatically. If you installed the file with `dpkg -i` instead, finish the
dependencies with:

```bash
sudo apt-get install -f
```

Check what the package will install with:

```bash
dpkg-deb --info sidee_0.1.4.2-1_amd64.deb
dpkg-deb --contents sidee_0.1.4.2-1_amd64.deb
```

On Debian testing/unstable and Ubuntu 24.04+, `sudo apt install
./sidee_*.deb` is the simplest form; on older `apt` releases, use the full
absolute path (`sudo apt install "$PWD/sidee_0.1.4.2-1_amd64.deb"`).

Uninstall:

```bash
sudo apt remove sidee
sudo apt purge sidee        # also removes the package's configuration files
rm -rf ~/.sidee             # saved TV pairings (only if you want to forget the TV)
```

## 4. Fedora, RHEL, CentOS Stream, Rocky and AlmaLinux

Download `sidee-<version>-1.<dist>.noarch.rpm` and install it:

```bash
sudo dnf install ./sidee-0.1.4.2-1.fc41.noarch.rpm
sidee
```

or, with the older tools still found on some RHEL clones:

```bash
sudo yum localinstall ./sidee-0.1.4.2-1.el9.noarch.rpm
sudo rpm -i ./sidee-0.1.4.2-1.el9.noarch.rpm     # does not resolve dependencies
```

The package requires `python3` and `python3-paho-mqtt`. On RHEL and its clones,
enable [EPEL](https://docs.fedoraproject.org/en-US/epel/) first if `dnf` cannot
find `python3-paho-mqtt`.

The RPM installs the code under `/usr/share/sidee` and the user service under
`/usr/lib/systemd/user/sidee.service`. If you copied files into place by hand
instead of installing the RPM, restore the SELinux file labels so Python can
read them:

```bash
sudo restorecon -R /usr/share/sidee /usr/bin/sidee
```

On an enforcing SELinux system, check for denials after the first run:

```bash
sudo ausearch -m AVC -ts recent
```

Uninstall:

```bash
sudo dnf remove sidee
```

## 5. openSUSE and SLES

openSUSE ships `python3-paho-mqtt`, so the universal installer works without any
extra steps:

```bash
sudo zypper install python3 python3-paho-mqtt
./install.sh --prefix /usr
sidee
```

The Fedora/RHEL RPM also installs cleanly on openSUSE Leap/Tumbleweed when the
dependency is already satisfied:

```bash
sudo zypper install python3-paho-mqtt
sudo rpm -i --nodeps sidee-0.1.4.2-1.noarch.rpm
```

openSUSE's own RPM build (`rpmbuild` with the openSUSE macros) differs from
Fedora's, so the prebuilt RPM is not published for openSUSE; use the universal
installer unless you want to build the spec yourself (see
[Building the packages yourself](#building-the-packages-yourself)).

Uninstall:

```bash
sudo ./uninstall.sh --prefix /usr
```

## 6. Arch Linux, Manjaro and EndeavourOS

Arch packages are built from a `PKGBUILD`. One is included in the download and
in the repository at `packaging/linux/PKGBUILD`.

The `PKGBUILD` packages the source tree it sits in, so it needs no download and
works from either the release download or a git clone:

```bash
# From the release download
tar xzf sidee-linux.tar.gz
cd Sidee/packaging/linux
makepkg -si

# Or from a git clone
git clone https://github.com/Empi9245/Sidee
cd Sidee/packaging/linux
makepkg -si
```

`makepkg` pulls in `python` and `python-paho-mqtt` from the official
repositories (`extra`). The package is architecture-independent, so `arch=('any')`
works on both `x86_64` and `aarch64`. Because the sources are local, the build
works offline and never needs a checksum; it also excludes any `__pycache__`
left in a development checkout.

**AUR**, if you prefer `yay`, `paru` or another AUR helper: an AUR package must
download a released archive instead of reading the local tree. Change the source
lines to the commented example at the bottom of the `PKGBUILD` (release URL plus
`makepkg -g` checksum) and point `_srcdir` at `"${srcdir}/Sidee-${pkgver}"`, then
use `makepkg --printsrcinfo > .SRCINFO`. The tag must already contain
`packaging/linux`, so bump `pkgver` to the release that includes the Linux
files.

Uninstall:

```bash
sudo pacman -Rns sidee
```

## 7. NixOS and Nix

The repository is a flake that exposes a package, an overlay and a NixOS module.
Runtime state is written to your XDG state directory because the Nix store is
read-only.

### Try it without installing

```bash
nix run github:Empi9245/Sidee
```

### Install for a user (Nix profile or Home Manager)

```bash
nix profile install github:Empi9245/Sidee
sidee
```

Or, from a local checkout:

```bash
nix build .#sidee
./result/bin/sidee
```

### NixOS system configuration

Add the flake as an input and enable the module. The module installs the
package, adds the desktop entry and runs the dashboard as a per-user service.

```nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    sidee.url = "github:Empi9245/Sidee";
  };

  outputs = { self, nixpkgs, sidee, ... }: {
    nixosConfigurations.my-pc = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        sidee.nixosModules.default
        ({ ... }: {
          services.sidee = {
            enable = true;
            # port = 8787;   # optional: pin the dashboard port
            # installToSystem = true;   # default: add `sidee` to systemPackages
          };
        })
      ];
    };
  };
}
```

Then rebuild:

```bash
sudo nixos-rebuild switch --flake .#my-pc
```

The dashboard runs as a **systemd user service**. A user manager must be running
for it to start, so either log in graphically or enable lingering:

```bash
loginctl enable-linger "$USER"
systemctl --user enable --now sidee
```

Inspect it like any user unit:

```bash
systemctl --user status sidee
journalctl --user -u sidee -n 50
```

Because the Nix package uses `python3.withPackages`, everything is built from
source with no vendored downloads and no network access at runtime.

No firewall change is needed for the default configuration: SSDP replies and the
MQTT connection are outbound-initiated, and NixOS allows outbound traffic.

If you already use an overlay, this works too:

```nix
nixpkgs.overlays = [ sidee.overlays.default ];
environment.systemPackages = [ pkgs.sidee ];
```

### Ad-hoc shell

```bash
nix shell github:Empi9245/Sidee
sidee
```

### Flake note

The flake has no committed `flake.lock` yet, so the first `nix build`, `nix run`
or `nixos-rebuild` will create one and pin `nixpkgs`. If you clone the
repository and the packaging files are untracked, use the `path:` form
(`nix build path:.#sidee`) or commit them, because Git-based flakes only see
tracked files.

## 8. Alpine, Gentoo, Void and other distributions

Use the universal installer, which needs nothing beyond Python 3 and a package
manager for the optional dependency:

```bash
# Alpine
sudo apk add python3 py3-paho-mqtt
./install.sh --prefix /usr

# Gentoo
sudo emerge dev-lang/python dev-python/paho-mqtt
sudo ./install.sh

# Void
sudo xbps-install python3 python3-paho-mqtt
sudo ./install.sh

# Devuan, Slackware, Void, ... (Python 3 present)
./install.sh --user
```

The installer downloads the checksum-verified `paho-mqtt` wheel into
`<install>/vendor` when the interpreter does not already provide it, so these
distributions need nothing pre-packaged. On musl systems (Alpine) the pure
Python wheel works unchanged.

## Run the dashboard in the background

Every installer ships a systemd **user** unit (`sidee.service`). It runs
`sidee --headless` and restarts on failure. The dashboard URL contains a private
access key, so the unit keeps the startup lines out of the journal.

```bash
systemctl --user daemon-reload
systemctl --user enable --now sidee     # start now and at every login
systemctl --user status sidee
```

Because a second launch reuses the dashboard that is already running, you can
just run `sidee` to open it in your browser:

```bash
sidee
```

If you are not logged into a graphical session, enable lingering so the user
manager starts at boot:

```bash
loginctl enable-linger "$USER"
```

Systems without systemd (Alpine with OpenRC, Void with runit, Devuan with
sysvinit) can start the same command from their own service manager:

```sh
sidee --headless --port 8787
```

## Using the dashboard

The dashboard itself is described in the [main README](../README.md#connect-your-tv).
In short: **Find TV** → **Request code** → enter the four-digit PIN shown on the
TV → choose the launcher tile to add. Sidee prints two links at startup:

```
Sidee (this computer): http://127.0.0.1:<port>/?key=<access key>
Sidee (from your phone, same network): http://<lan ip>:<port>/?key=<access key>
```

Keep the access-key link private. The dashboard shows a QR code for opening the
same controls on a phone on the same network.

## Where Sidee keeps files

| Path | Contents |
| --- | --- |
| `/usr/share/sidee` (packages) or `/usr/local/share/sidee`, `~/.local/share/sidee` | Program files: `sidee.py`, `core/`, `assets/`, `docs/`, and `vendor/` when the installer provided the library |
| `/usr/bin/sidee`, `/usr/local/bin/sidee`, `~/.local/bin/sidee` | Launcher |
| `~/.sidee/session.json` | Saved TV pairing (mode `600`). Legacy `~/.vidaa-tile` is still recognised |
| `~/.local/state/sidee/runtime/dashboard.json` | Running dashboard port and access key (mode `600`). Honours `XDG_STATE_HOME` |
| `<source folder>/.runtime/` | Same runtime state when you run Sidee from an unpacked download |
| `~/.local/state/sidee/download/` | Download runtime (library plus lock) when the download folder itself is read-only |
| `~/.local/share/applications/sidee.desktop`, `/usr/share/applications/sidee.desktop` | Application-menu entry |
| `~/.config/systemd/user/sidee.service`, `/usr/lib/systemd/user/sidee.service` | Optional background service |

A source checkout uses the folder's own `.runtime/` directory; a read-only
install prefix (a distro package or the Nix store) automatically falls back to
the XDG state directory, so Sidee never tries to write into `/usr`.
`SIDEE_STATE_DIR` overrides the runtime location (used by the test suite).

## Firewall, VPN and discovery

Sidee finds the TV with SSDP (UDP port 1900, multicast `239.255.255.250` plus
the subnet broadcast address of each interface) and controls it with MQTT over
TLS on TCP port 36669. Both are outbound from your computer; the TV's replies
return on the existing connection.

- Desktop firewalls normally allow this. To restrict it explicitly:

  ```bash
  # ufw (Ubuntu/Debian)
  sudo ufw allow out to 239.255.255.250 port 1900 proto udp
  sudo ufw allow out to 192.168.1.0/24 port 36669 proto tcp   # your LAN

  # firewalld (Fedora/RHEL)
  sudo firewall-cmd --permanent --add-rich-rule='rule family=ipv4 destination address=239.255.255.250/32 port port=1900 protocol=udp accept'
  sudo firewall-cmd --reload
  ```

- A **VPN** can steal the default route and hide the LAN. If **Find TV** fails,
  enter the TV's IP address manually (TV **Settings → Network**) — Sidee verifies
  the address and port 36669 before allowing pairing.
- **Guest Wi-Fi / client isolation** blocks device-to-device traffic. Use the
  main network.
- Docker, libvirt and other virtual bridges add extra interfaces; Sidee inspects
  each real interface and sends directed discovery packets per subnet, which is
  why `iproute2` helps.

## Headless computers and SSH

A server or Raspberry Pi without a desktop works fine:

```bash
sidee --headless --port 8787
```

`--headless` never tries to open a browser. Print the dashboard URL with the
access key from the state file, or open the dashboard from another computer by
forwarding the port:

```bash
ssh -N -L 8787:127.0.0.1:8787 user@server
# then open http://127.0.0.1:8787/?key=<access key> on your own computer
```

The phone QR code needs a LAN address, so run Sidee on a machine that is on the
same network as the TV rather than through a loopback-only tunnel.

## Troubleshooting

**`python3: command not found` or a version error.** Install Python 3.9+ (for
example `sudo apt install python3`, `sudo dnf install python3`,
`sudo pacman -S python`). Sidee's launchers report this before doing anything.

**`The TV connection certificate is missing.`** The `core/tv-client.bundle`
file is missing, which means the copy is incomplete. Re-extract the download or
reinstall the package.

**`Find TV` shows nothing.**
1. Confirm both devices are on the same network and the TV is on.
2. Check the firewall and VPN notes above.
3. Enter the TV's IP manually; Sidee verifies the descriptor on port 18400/38400
   and that TCP 36669 is reachable.

**`Port 36669 responds, but Sidee could not verify a VIDAA TV`.** The address is
reachable but the device description does not look like VIDAA. Check the IP.

**Pairing is refused (`rc=5`) or the PIN never appears.** Some firmware needs a
different authentication profile; Sidee tries the documented ones automatically
and prints what it tried. See the
[Toshiba compatibility notes](toshiba-compatibility.md).

**The dashboard does not open in the browser.** Sidee printed the full URL with
its access key; open it manually. On headless machines there is no browser,
which is expected.

**Permission denied when the installer writes to `/usr/local`.** Use
`sudo ./install.sh` or install per user with `./install.sh --user`.

**The launcher says the program files were not found.** Reinstall, or point
`SIDEE_HOME` at the directory that contains `sidee.py`:

```bash
SIDEE_HOME=/opt/sidee sidee
```

**`Sidee is already preparing this folder`.** Another launch is downloading the
library in the same folder, and the lock names the process that owns it. Sidee
reclaims locks left behind by interrupted runs, so this message means a second
copy really is running: wait for it or close it, and start again.

**A newer Python is installed, but the launcher reports an old one.** Both the
download launcher and the installed `sidee` command test every interpreter they
find (`python3`, `python3.14` ... `python3.9`, `python`) and keep the first that
is at least 3.9, so this should not happen; set `SIDEE_PYTHON` to the full path
of the interpreter you want if your `PATH` resolves to an unusable one.

**The background service is not found after a custom `--prefix`.** Only the
standard unit directories are searched. Copy the unit the installer printed
into `~/.config/systemd/user/`, then run `systemctl --user daemon-reload`.

**`ModuleNotFoundError: No module named 'paho'` after `--no-vendor`.** Install
the distribution package (`python3-paho-mqtt`) or run the installer again
without `--no-vendor` to download Sidee's own copy.

**Diagnostics.** Run the built-in check (no TV and no GUI required):

```bash
sidee --self-test
```

For deeper checks, start a source checkout with isolated state so your real
pairing is untouched:

```bash
SIDEE_STATE_DIR=/tmp/sidee-test python3 sidee.py --headless --port 0
```

Keep `session.json`, PINs, tokens and dashboard links private when reporting a
problem.

## Updating and uninstalling

| Install method | Update | Remove |
| --- | --- | --- |
| Download folder | replace `sidee-linux.tar.gz`, keep `.runtime/` if you like | delete the folder |
| Universal installer | `./install.sh --user` (or with `sudo`) over the top | `./uninstall.sh --user` / `sudo ./uninstall.sh` |
| Debian/Ubuntu `.deb` | `sudo apt install ./sidee_<new>.deb` | `sudo apt remove sidee` |
| Fedora/RHEL `.rpm` | `sudo dnf upgrade ./sidee-<new>.rpm` | `sudo dnf remove sidee` |
| Arch | `makepkg -si` with the updated PKGBUILD | `sudo pacman -Rns sidee` |
| NixOS / Nix | update the flake input and rebuild | remove the module option or `nix profile remove sidee` |

Saved TV pairings in `~/.sidee` are kept by every update and uninstall unless you
delete them, so you do not have to re-enter the PIN for the same TV.

## Building the packages yourself

Everything is produced by one tool. It needs only Python 3 and, for the native
packages, `dpkg-deb` and/or `rpmbuild`.

```bash
# Everything that the current machine can build:
python3 tools/build_linux_release.py

# Individually:
python3 tools/build_linux_release.py --tarball
python3 tools/build_linux_release.py --deb  --architecture arm64 --version 0.1.4.2
python3 tools/build_linux_release.py --rpm  --version 0.1.4.2
```

Outputs land in `dist/`:

- `sidee-linux.tar.gz` – the self-contained download used by `./start-linux.sh`
- `sidee_<version>-1_<arch>.deb` – Debian/Ubuntu package
- `sidee-<version>-1.noarch.rpm` – Fedora/RHEL package

Install the build tools with your package manager if they are missing:

```bash
sudo apt install dpkg-dev rpm      # Debian/Ubuntu, also builds the RPM
sudo dnf install rpm-build         # Fedora/RHEL
sudo pacman -S base-devel          # Arch (for makepkg)
```

The Arch `PKGBUILD` and the Nix flake build from the source tree directly; the
`.deb` and `.rpm` use the layouts asserted by
[`tests/test_linux_packaging.py`](../tests/test_linux_packaging.py).

`--rpm` needs `rpmbuild` (`sudo apt install rpm` on Debian/Ubuntu, `sudo dnf
install rpm-build` on Fedora). If it is missing, the default run prints
`Skipping the RPM` and still produces the tarball and `.deb`. The tool never
ships `__pycache__` or saved pairings in any of the three artifacts.

Run the full test suite and the headless smoke test before publishing:

```bash
python3 -m pip install -r requirements.txt      # or use your distribution package
python3 -m unittest discover -s tests
python3 tools/smoke_test.py --source
```

The [CI workflow](../.github/workflows/build.yml) runs these checks on Ubuntu
for every change and builds the tarball, `.deb` and `.rpm` artifacts.
