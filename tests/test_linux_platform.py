"""Linux interface discovery and read-only-prefix state handling."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import platform_support as platform

LINUX_ONLY = unittest.skipUnless(sys.platform.startswith("linux"),
                                 "Linux-specific behavior")

# `ip -o -4 addr show` packs each address onto one line.
IP_ADDR_OUTPUT = """\
1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever
2: eth0    inet 192.168.88.5/24 brd 192.168.88.255 scope global dynamic eth0\\       valid_lft 86393sec preferred_lft 86393sec
3: wlan0    inet 10.23.7.5/21 brd 10.23.7.255 scope global wlan0\\       valid_lft forever preferred_lft forever
4: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever
5: eth1    inet 169.254.7.9/16 brd 169.254.255.255 scope link eth1\\       valid_lft forever preferred_lft forever
6: tun0    inet 10.8.0.2/32 scope global tun0\\       valid_lft forever preferred_lft forever
"""

# net-tools `ifconfig` shows only UP interfaces by default.
LINUX_IFCONFIG = """\
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 192.168.88.5  netmask 255.255.255.0  broadcast 192.168.88.255
        inet6 fe80::1  prefixlen 64  scopeid 0x20<link>
lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
wlan0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500
        inet 10.23.7.5  netmask 255.255.248.0  broadcast 10.23.7.255
"""


class TestLinuxInterfaceParsing(unittest.TestCase):
    def test_ip_addr_addresses_match_their_broadcasts(self):
        self.assertEqual(platform._interfaces_from_ip_addr(IP_ADDR_OUTPUT),
                         [("10.23.7.5", "10.23.7.255"),
                          ("172.17.0.1", "172.17.255.255"),
                          ("192.168.88.5", "192.168.88.255")])

    def test_broadcast_is_derived_from_the_prefix(self):
        output = "2: eth0    inet 172.19.208.1/20 brd 172.19.208.255 scope global eth0\n"
        self.assertEqual(platform.broadcasts_from_ip_addr(output),
                         ["172.19.223.255"])

    def test_loopback_linklocal_multicast_and_single_hosts_are_ignored(self):
        for record in ("1: lo    inet 127.0.0.1/8 scope host lo",
                       "2: eth0    inet 169.254.1.2/16 brd 169.254.255.255 scope link eth0",
                       "3: eth0    inet 224.0.0.1/4 scope global eth0",
                       "4: eth0    inet 0.0.0.0/24 scope global eth0",
                       "5: tun0    inet 10.8.0.2/32 scope global tun0",
                       "6: ppp0    inet 10.9.0.2/31 scope global ppp0",
                       "7: eth0    inet 10.0.0.999/24 brd 10.0.0.255 scope global eth0",
                       "8: eth0    inet 10.0.0.5/99 scope global eth0"):
            with self.subTest(record=record):
                self.assertEqual(platform.broadcasts_from_ip_addr(record), [])

    def test_legacy_ifconfig_output_is_also_understood(self):
        self.assertEqual(platform.broadcasts_from_ifconfig(LINUX_IFCONFIG),
                         ["10.23.7.255", "192.168.88.255"])


class TestLinuxInterfaceSelection(unittest.TestCase):
    def test_iproute2_is_preferred_and_no_windows_flag_is_passed(self):
        response = Mock(returncode=0, stdout=IP_ADDR_OUTPUT)
        with patch.object(platform.sys, "platform", "linux"), \
                patch.object(platform.subprocess, "run", return_value=response) as run:
            self.assertEqual(platform.local_ipv4_interfaces(),
                             [("10.23.7.5", "10.23.7.255"),
                              ("172.17.0.1", "172.17.255.255"),
                              ("192.168.88.5", "192.168.88.255")])
        run.assert_called_once_with(["ip", "-o", "-4", "addr", "show"],
                                    capture_output=True, text=True,
                                    errors="replace", timeout=3)

    def test_missing_iproute2_falls_back_to_net_tools(self):
        results = [OSError("ip: not found"),
                   Mock(returncode=0, stdout=LINUX_IFCONFIG)]
        with patch.object(platform.sys, "platform", "linux"), \
                patch.object(platform.subprocess, "run", side_effect=results) as run:
            self.assertEqual(platform.local_broadcasts(),
                             ["10.23.7.255", "192.168.88.255"])
        self.assertEqual(run.call_args_list[1].args[0], ["ifconfig"])

    def test_empty_or_failing_inspection_preserves_discovery_fallback(self):
        empty = Mock(returncode=0, stdout="")
        with patch.object(platform.sys, "platform", "linux"), \
                patch.object(platform.subprocess, "run", return_value=empty):
            self.assertEqual(platform.local_broadcasts(), [])
        with patch.object(platform.sys, "platform", "linux"), \
                patch.object(platform.subprocess, "run",
                             side_effect=subprocess.TimeoutExpired("ip", 3)):
            self.assertEqual(platform.local_broadcasts(), [])

    def test_other_unix_systems_still_return_no_interfaces(self):
        with patch.object(platform.sys, "platform", "freebsd13"), \
                patch.object(platform.subprocess, "run") as run:
            self.assertEqual(platform.local_ipv4_interfaces(), [])
        run.assert_not_called()


class TestReadOnlyPrefixState(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name).resolve()
        env = patch.dict(os.environ, {"SIDEE_STATE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)

    def test_writable_source_keeps_its_folder_runtime(self):
        with patch.object(platform.sys, "frozen", False, create=True):
            self.assertEqual(platform.dashboard_state_path(self.folder),
                             self.folder / ".runtime" / "dashboard.json")

    def test_read_only_prefix_defers_to_the_user_state_directory(self):
        user = self.folder / "user-state"
        with patch.object(platform.sys, "frozen", False, create=True), \
                patch.object(platform, "_writable", return_value=False), \
                patch.object(platform, "user_state_dir", return_value=user):
            self.assertEqual(platform.dashboard_state_path("/usr/share/sidee"),
                             user / "runtime" / "dashboard.json")

    def test_read_only_fallback_never_writes_into_the_install_prefix(self):
        with patch.object(platform.sys, "frozen", False, create=True), \
                patch.object(platform, "_writable", return_value=False):
            state = platform.dashboard_state_path("/usr/share/sidee")
        self.assertNotIn("/usr/share/sidee", state.as_posix())
        self.assertEqual(state, platform.user_state_dir() / "runtime"
                         / "dashboard.json")

    @LINUX_ONLY
    def test_xdg_state_home_is_respected_for_system_installs(self):
        xdg = self.folder / "xdg"
        with patch.dict(os.environ, {"XDG_STATE_HOME": str(xdg)}), \
                patch.object(platform, "_writable", return_value=False):
            self.assertEqual(platform.user_state_dir(), xdg / "sidee")
            self.assertEqual(platform.dashboard_state_path("/nix/store/sidee"),
                             xdg / "sidee" / "runtime" / "dashboard.json")

    @unittest.skipUnless(sys.platform == "darwin", "macOS-specific directory")
    def test_macos_user_directory_is_outside_the_app(self):
        self.assertEqual(platform.user_state_dir(),
                         Path(os.path.expanduser("~")) / "Library"
                         / "Application Support" / "Sidee")

    @unittest.skipUnless(os.name == "nt", "Windows-specific directory")
    def test_windows_user_directory_uses_local_appdata(self):
        base = os.environ.get("LOCALAPPDATA")
        expected = (Path(base) if base else Path(os.path.expanduser("~"))
                    / "AppData" / "Local") / "Sidee"
        self.assertEqual(platform.user_state_dir(), expected)


if __name__ == "__main__":
    unittest.main()
