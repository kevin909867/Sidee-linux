"""Linux downloads and native packages must ship the whole app, and nothing private."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

from tools import build_linux_release as packaging

POSIX_SHELL = unittest.skipUnless(os.name == "posix" and shutil.which("bash"),
                                  "A POSIX shell is required")


class TestLinuxVersions(unittest.TestCase):
    def test_versions_follow_the_existing_release_tag_format(self):
        self.assertEqual(packaging.validate_version("v0.1.4.2"), "0.1.4.2")
        self.assertEqual(packaging.validate_version("0.1.1"), "0.1.1")
        for value in ("v1", "1.2.3-preview", "1.2.3/../other", "1.2.3\n", "1.2.3.4.5"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                packaging.validate_version(value)

    def test_debian_architectures_cover_the_common_machines(self):
        self.assertEqual(packaging.debian_architecture("x86_64"), "amd64")
        self.assertEqual(packaging.debian_architecture("aarch64"), "arm64")
        self.assertEqual(packaging.debian_architecture("armv7l"), "armhf")
        self.assertEqual(packaging.debian_architecture("riscv64"), "riscv64")
        with self.assertRaises(ValueError):
            packaging.debian_architecture("sparc64")


class TestLinuxMetadata(unittest.TestCase):
    def test_debian_control_declares_the_runtime_dependencies(self):
        control = packaging.debian_control("0.1.4.2", "amd64")
        self.assertIn("Package: sidee\n", control)
        self.assertIn("Version: 0.1.4.2-1\n", control)
        self.assertIn("Architecture: amd64\n", control)
        self.assertIn("Depends: python3 (>= 3.9), python3-paho-mqtt\n", control)
        self.assertTrue(control.endswith("\n"))

    def test_rpm_spec_installs_every_shared_asset(self):
        spec = packaging.rpm_spec("0.1.4.2")
        for directive in ("Name:           sidee",
                          "Version:        0.1.4.2",
                          "BuildArch:      noarch",
                          "Requires:       python3-paho-mqtt"):
            self.assertIn(directive, spec)
        for destination in ("%{_bindir}/sidee",
                            "%{_datadir}/applications/sidee.desktop",
                            "%{_datadir}/pixmaps/sidee.png",
                            "%{_userunitdir}/sidee.service"):
            self.assertIn(destination, spec)
        self.assertIn("%setup -q", spec)


class TestLinuxTarball(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_download_contains_the_launcher_and_every_runtime_file(self):
        archive = packaging.build_tarball(self.folder / "sidee-linux.tar.gz")
        with tarfile.open(archive) as downloaded:
            names = downloaded.getnames()
        for name in ("Sidee/sidee.py", "Sidee/start-linux.sh", "Sidee/requirements.txt",
                     "Sidee/core/tv-client.bundle", "Sidee/core/dashboard.html",
                     "Sidee/core/platform_support.py", "Sidee/assets/sidee-logo.png",
                     "Sidee/install.sh", "Sidee/packaging/linux/install.sh",
                     "Sidee/packaging/linux/uninstall.sh", "Sidee/packaging/linux/sidee",
                     "Sidee/packaging/linux/PKGBUILD", "Sidee/packaging/linux/sidee.install",
                     "Sidee/packaging/linux/nix/package.nix",
                     "Sidee/packaging/linux/nix/module.nix",
                     "Sidee/flake.nix",
                     "Sidee/tools/build_linux_release.py",
                     "Sidee/docs/linux.md"):
            self.assertIn(name, names)
        self.assertFalse([name for name in names
                          if any(part in name for part in
                                 ("session.json", "certs.bin.k", "__pycache__",
                                  ".runtime/", ".sidee/"))])


class TestPayloadFiltering(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_packaged_payload_never_contains_bytecode_or_user_state(self):
        for relative in ("core/__pycache__/client.cpython-312.pyc",
                         "core/client.py", "sidee.py",
                         "core/session.json", "docs/linux.md"):
            target = self.folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture", encoding="utf-8")
        names = [relative for _, relative in packaging.payload_files(self.folder)]
        self.assertIn("core/client.py", names)
        self.assertIn("sidee.py", names)
        self.assertIn("docs/linux.md", names)
        self.assertEqual([name for name in names
                          if "__pycache__" in name or name.endswith(".pyc")], [])
        self.assertEqual([name for name in names if name.endswith("session.json")], [])


@POSIX_SHELL
class TestArchPackaging(unittest.TestCase):
    def test_pkgbuild_packages_this_source_tree(self):
        """The PKGBUILD builds the local tree, so it must work offline."""
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "pkgdir"
            script = (
                "set -eu; pkgdir=$1; startdir=$2; srcdir=$3; "
                "source ./packaging/linux/PKGBUILD; package")
            subprocess.run(["bash", "-c", script, "bash", str(destination),
                            str(packaging.PACKAGING), temporary],
                           cwd=packaging.ROOT, check=True,
                           capture_output=True, text=True)
            for relative in ("usr/bin/sidee", "usr/share/sidee/sidee.py",
                             "usr/share/sidee/core/tv-client.bundle",
                             "usr/share/applications/sidee.desktop",
                             "usr/share/pixmaps/sidee.png",
                             "usr/lib/systemd/user/sidee.service",
                             "usr/share/licenses/sidee/LICENSE"):
                with self.subTest(path=relative):
                    self.assertTrue((destination / relative).is_file(), relative)
            self.assertTrue(os.access(destination / "usr/bin/sidee", os.X_OK))
            self.assertEqual(
                [path for path in destination.rglob("*")
                 if "__pycache__" in path.parts or path.suffix == ".pyc"], [])

    def test_pkgbuild_needs_no_remote_archive(self):
        text = (packaging.PACKAGING / "PKGBUILD").read_text(encoding="utf-8")
        self.assertIn("source=()", text)
        self.assertIn("sha256sums=()", text)


@POSIX_SHELL
class TestInstalledLauncher(unittest.TestCase):
    def test_custom_prefix_launcher_finds_its_program_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "my opt"
            subprocess.run(["bash", "packaging/linux/install.sh", "--system",
                            "--prefix", str(prefix), "--no-vendor",
                            "--no-systemd", "--no-desktop", "--no-icon"],
                           cwd=packaging.ROOT, check=True,
                           capture_output=True, text=True)
            self.assertFalse((prefix / "share" / "sidee" / "vendor").exists())
            # Replace the app with a stub so the launcher can be run without any
            # third-party dependency, and prove it resolved the prefix.
            (prefix / "share" / "sidee" / "sidee.py").write_text(
                "import sys\nprint('stub', *sys.argv[1:])\n", encoding="utf-8")
            result = subprocess.run([str(prefix / "bin" / "sidee"), "--headless"],
                                    capture_output=True, text=True, check=True)
            self.assertIn("stub --headless", result.stdout)


class TestLinuxPackages(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)

    def test_debian_tree_places_the_launcher_menu_entry_and_service(self):
        root = self.folder / "debian"
        packaging.debian_tree(root, "0.1.4.2", "amd64")
        expected = ("DEBIAN/control", "usr/bin/sidee",
                    "usr/share/sidee/sidee.py",
                    "usr/share/sidee/core/tv-client.bundle",
                    "usr/share/sidee/assets/sidee-logo.png",
                    "usr/share/applications/sidee.desktop",
                    "usr/share/pixmaps/sidee.png",
                    "usr/lib/systemd/user/sidee.service")
        for relative in expected:
            with self.subTest(path=relative):
                self.assertTrue((root / relative).is_file())
        self.assertTrue(os.access(root / "usr/bin/sidee", os.X_OK))
        # The XDG state directory is used at runtime, never the prefix.
        control = (root / "DEBIAN" / "control").read_text(encoding="utf-8")
        self.assertIn("Version: 0.1.4.2-1", control)

    def test_debian_tree_never_ships_user_state(self):
        root = self.folder / "debian"
        packaging.debian_tree(root, "0.1.4.2", "amd64")
        leaked = [path for path in root.rglob("*")
                  if path.name in ("session.json", "certs.bin.k", "dashboard.json")
                  or "__pycache__" in path.parts]
        self.assertEqual(leaked, [])

    @unittest.skipUnless(sys.platform == "linux" and shutil.which("dpkg-deb"),
                         "dpkg-deb is required to build the Debian package")
    def test_real_debian_package_builds_and_lists_its_contents(self):
        archive = packaging.build_deb(self.folder / "sidee.deb", version="0.1.4.2",
                                      architecture="amd64")
        self.assertTrue(archive.is_file())
        listed = subprocess.run(["dpkg-deb", "--contents", archive],
                                capture_output=True, text=True, check=True).stdout
        for relative in ("./usr/bin/sidee", "./usr/share/sidee/sidee.py",
                         "./usr/share/applications/sidee.desktop"):
            with self.subTest(path=relative):
                self.assertIn(relative, listed)
        self.assertNotIn("session.json", listed)


if __name__ == "__main__":
    unittest.main()
