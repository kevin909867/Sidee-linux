"""Build Sidee's Linux downloads and native packages.

The tarball is a self-contained folder that opens with ``./start-linux.sh``.
The Debian and RPM packages install the same program files into
``/usr/share/sidee`` and add the launcher, menu entry, icon and user service.
Debian and RPM builds must run on Linux with ``dpkg-deb`` or ``rpmbuild``
installed; the checksums and layouts are asserted by the test suite.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging" / "linux"
DEFAULT_VERSION = "0.1.4.2"
DEBIAN_REVISION = "1"
MAINTAINER = "Sidee contributors"
HOMEPAGE = "https://github.com/Empi9245/Sidee"

# Program files shared by every Linux distribution.
PAYLOAD = ("sidee.py", "core", "assets", "docs", "README.md", "LICENSE")
# Extra files only the source tarball needs. The Arch PKGBUILD, the Nix flake
# and the build tools ship too, so every documented install method works from
# the download without a git clone.
TARBALL_EXTRAS = ("requirements.txt", "start-linux.sh")
TARBALL_DIRECTORIES = ("packaging", "tools")
TARBALL_FILES = ("flake.nix",)
IGNORED_NAMES = ("__pycache__", ".git", ".runtime", ".sidee", ".vidaa-tile",
                 ".venv", "session.json", "certs.bin.k", "dashboard.json")
IGNORED = shutil.ignore_patterns(*IGNORED_NAMES, "*.pyc", ".DS_Store")

DEBIAN_ARCHITECTURES = {
    "x86_64": "amd64", "amd64": "amd64",
    "aarch64": "arm64", "arm64": "arm64",
    "armv7l": "armhf", "armv6l": "armhf", "armhf": "armhf",
    "i386": "i386", "i486": "i386", "i586": "i386", "i686": "i386",
    "riscv64": "riscv64", "ppc64le": "ppc64el", "s390x": "s390x",
}


def validate_version(value: str) -> str:
    value = value.removeprefix("v")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", value):
        raise ValueError("The release version must use X.Y.Z or X.Y.Z.N "
                         "(optionally prefixed with v).")
    return value


def debian_architecture(value: str | None = None) -> str:
    machine = (value or platform.machine()).lower()
    try:
        return DEBIAN_ARCHITECTURES[machine]
    except KeyError:
        raise ValueError(f"Unsupported Linux architecture: {machine}") from None


def release_files(source: Path = ROOT) -> list[Path]:
    """Every file that must exist before a package can be assembled."""
    files: list[Path] = []
    for name in PAYLOAD + TARBALL_EXTRAS:
        path = source / name
        if not path.exists():
            raise FileNotFoundError(f"Release file is missing: {name}")
        files.append(path)
    for name in ("sidee", "sidee.desktop", "sidee.service"):
        path = PACKAGING / name
        if not path.is_file():
            raise FileNotFoundError(f"Packaging file is missing: {path}")
        files.append(path)
    return files


def copy_payload(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in PAYLOAD:
        origin = source / name
        target = destination / name
        if origin.is_dir():
            shutil.copytree(origin, target, ignore=IGNORED, dirs_exist_ok=True)
        else:
            shutil.copyfile(origin, target)


def payload_files(source: Path) -> list[tuple[Path, str]]:
    """Every shipped file paired with its archive path, minus local state.

    ``__pycache__`` in particular must never be packaged: bytecode built by the
    packager's interpreter would be stale (or wrong) on the target system.
    """
    members: list[tuple[Path, str]] = []
    for name in PAYLOAD:
        path = source / name
        if path.is_file():
            members.append((path, path.relative_to(source).as_posix()))
            continue
        for member in sorted(path.rglob("*")):
            if member.is_dir() or member.suffix == ".pyc":
                continue
            if any(part in IGNORED_NAMES for part in member.parts):
                continue
            members.append((member, member.relative_to(source).as_posix()))
    return members


def _install(source: Path, target: Path, mode: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    os.chmod(target, mode)


def debian_control(version: str, architecture: str) -> str:
    return "\n".join([
        "Package: sidee",
        f"Version: {version}-{DEBIAN_REVISION}",
        "Section: utils",
        "Priority: optional",
        f"Architecture: {architecture}",
        "Depends: python3 (>= 3.9), python3-paho-mqtt",
        f"Maintainer: {MAINTAINER}",
        f"Homepage: {HOMEPAGE}",
        "Description: manage web-app launcher tiles on your VIDAA TV",
        " Sidee finds and pairs with a VIDAA TV on the local network and adds",
        " web-app launcher tiles through the TV's authorized control interface.",
        " The dashboard runs on this computer and is opened in a browser.",
    ]) + "\n"


def rpm_spec(version: str) -> str:
    return f"""\
# Built by tools/build_linux_release.py. Build with: rpmbuild -bb sidee.spec
%global _userunitdir %{{_prefix}}/lib/systemd/user
Name:           sidee
Version:        {version}
Release:        {DEBIAN_REVISION}%{{?dist}}
Summary:        Manage web-app launcher tiles on your VIDAA TV
License:        MIT
URL:            {HOMEPAGE}
Source0:        %{{name}}-%{{version}}.tar.gz
BuildArch:      noarch
Requires:       python3 >= 3.9
Requires:       python3-paho-mqtt

%description
Sidee finds and pairs with a VIDAA TV on the local network and adds web-app
launcher tiles through the TV's authorized control interface. The dashboard
runs on this computer and is opened in a browser.

%prep
%setup -q

%build

%install
rm -rf %{{buildroot}}
install -d %{{buildroot}}%{{_datadir}}/sidee
cp -R sidee.py core assets docs README.md LICENSE %{{buildroot}}%{{_datadir}}/sidee/
install -d %{{buildroot}}%{{_bindir}}
install -m 0755 packaging/linux/sidee %{{buildroot}}%{{_bindir}}/sidee
install -d %{{buildroot}}%{{_datadir}}/applications %{{buildroot}}%{{_datadir}}/pixmaps
install -m 0644 packaging/linux/sidee.desktop %{{buildroot}}%{{_datadir}}/applications/sidee.desktop
install -m 0644 assets/sidee-logo.png %{{buildroot}}%{{_datadir}}/pixmaps/sidee.png
install -d %{{buildroot}}%{{_userunitdir}}
install -m 0644 packaging/linux/sidee.service %{{buildroot}}%{{_userunitdir}}/sidee.service

%files
%doc README.md
%license LICENSE
%{{_datadir}}/sidee
%{{_bindir}}/sidee
%{{_datadir}}/applications/sidee.desktop
%{{_datadir}}/pixmaps/sidee.png
%{{_userunitdir}}/sidee.service

%changelog
"""


def _add_tree(archive: tarfile.TarFile, path: Path, source: Path) -> None:
    """Add a file or directory under its path relative to the project root."""
    if path.is_file():
        archive.add(path, "Sidee/" + path.relative_to(source).as_posix())
        return
    for member in sorted(path.rglob("*")):
        if any(part in IGNORED_NAMES for part in member.parts):
            continue
        if member.is_dir() or member.suffix == ".pyc":
            continue
        archive.add(member, "Sidee/" + member.relative_to(source).as_posix())


def build_tarball(destination: Path | None = None, source: Path = ROOT) -> Path:
    release_files(source)
    destination = Path(destination or ROOT / "dist" / "sidee-linux.tar.gz")
    destination.parent.mkdir(parents=True, exist_ok=True)
    names = [source / name for name in
             PAYLOAD + TARBALL_EXTRAS + TARBALL_DIRECTORIES + TARBALL_FILES]
    with tarfile.open(destination, "w:gz") as archive:
        for path in names:
            if not path.exists():
                raise FileNotFoundError(f"Release file is missing: {path.name}")
            _add_tree(archive, path, source)
        # A copy of the installer next to start-linux.sh for convenience.
        archive.add(PACKAGING / "install.sh", "Sidee/install.sh")
    return destination


def debian_tree(root: Path, version: str, architecture: str,
                source: Path = ROOT) -> Path:
    """Lay out a Debian package directory (DEBIAN/ plus the payload)."""
    release_files(source)
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o755)
    copy_payload(source, root / "usr" / "share" / "sidee")
    _install(PACKAGING / "sidee", root / "usr" / "bin" / "sidee", 0o755)
    _install(PACKAGING / "sidee.desktop",
             root / "usr" / "share" / "applications" / "sidee.desktop", 0o644)
    _install(source / "assets" / "sidee-logo.png",
             root / "usr" / "share" / "pixmaps" / "sidee.png", 0o644)
    _install(PACKAGING / "sidee.service",
             root / "usr" / "lib" / "systemd" / "user" / "sidee.service", 0o644)
    (root / "DEBIAN").mkdir(parents=True, exist_ok=True)
    (root / "DEBIAN" / "control").write_text(
        debian_control(version, architecture), encoding="utf-8")
    return root


def build_deb(destination: Path | None = None, version: str = DEFAULT_VERSION,
              architecture: str | None = None, source: Path = ROOT) -> Path:
    if sys.platform != "linux":
        raise RuntimeError("Debian packages must be built on Linux with dpkg-deb.")
    if not shutil.which("dpkg-deb"):
        raise RuntimeError("dpkg-deb is required to build the Debian package.")
    version = validate_version(version)
    architecture = debian_architecture(architecture)
    destination = Path(destination or ROOT / "dist"
                       / f"sidee_{version}-{DEBIAN_REVISION}_{architecture}.deb")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sidee-deb-") as temporary:
        debian_tree(Path(temporary), version, architecture, source)
        command = ["dpkg-deb", "--root-owner-group", "--build"]
        result = subprocess.run(command + [temporary, str(destination)],
                                capture_output=True, text=True)
        if result.returncode:
            # Older dpkg-deb releases lack --root-owner-group.
            result = subprocess.run(["dpkg-deb", "--build", temporary,
                                     str(destination)], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("dpkg-deb failed: " + (result.stderr or result.stdout))
    return destination


def build_rpm(destination: Path | None = None, version: str = DEFAULT_VERSION,
              source: Path = ROOT) -> Path:
    if sys.platform != "linux":
        raise RuntimeError("RPM packages must be built on Linux with rpmbuild.")
    if not shutil.which("rpmbuild"):
        raise RuntimeError("rpmbuild is required to build the RPM package. "
                           "Install the 'rpm' package first.")
    version = validate_version(version)
    destination = Path(destination or ROOT / "dist"
                       / f"sidee-{version}-{DEBIAN_REVISION}.noarch.rpm")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sidee-rpm-") as temporary:
        top = Path(temporary)
        for name in ("SOURCES", "SPECS", "BUILD", "RPMS", "SRPMS"):
            (top / name).mkdir(parents=True, exist_ok=True)
        tarball = top / "SOURCES" / f"sidee-{version}.tar.gz"
        with tarfile.open(tarball, "w:gz") as archive:
            for path, relative in payload_files(source):
                archive.add(path, f"sidee-{version}/{relative}")
            for name in ("sidee", "sidee.desktop", "sidee.service"):
                archive.add(PACKAGING / name,
                            f"sidee-{version}/packaging/linux/{name}")
        spec = top / "SPECS" / "sidee.spec"
        spec.write_text(rpm_spec(version), encoding="utf-8")
        result = subprocess.run(
            ["rpmbuild", "--define", f"_topdir {top}", "-bb", str(spec)],
            capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError("rpmbuild failed: " + (result.stderr or result.stdout))
        built = sorted((top / "RPMS").rglob("*.rpm"))
        if not built:
            raise RuntimeError("rpmbuild did not produce a package.")
        shutil.copyfile(built[0], destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=os.environ.get("SIDEE_BUILD_VERSION",
                                                            DEFAULT_VERSION))
    parser.add_argument("--architecture",
                        help="Debian architecture (default: detect from uname)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tarball", action="store_true")
    mode.add_argument("--deb", action="store_true")
    mode.add_argument("--rpm", action="store_true")
    arguments = parser.parse_args()

    built: list[Path] = []
    if arguments.tarball:
        built.append(build_tarball())
    elif arguments.deb:
        built.append(build_deb(version=arguments.version,
                               architecture=arguments.architecture))
    elif arguments.rpm:
        built.append(build_rpm(version=arguments.version))
    else:
        built.append(build_tarball())
        if sys.platform == "linux":
            built.append(build_deb(version=arguments.version,
                                   architecture=arguments.architecture))
            if shutil.which("rpmbuild"):
                built.append(build_rpm(version=arguments.version))
            else:
                print("Skipping the RPM: rpmbuild is not installed.", file=sys.stderr)
    for path in built:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
