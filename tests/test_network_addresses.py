"""TV descriptors and Jellyfin addresses must work on other home networks."""
import http.client
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, Mock, patch

from core import client, presets, webui
import sidee


class TestDescriptorAddresses(unittest.TestCase):
    def descriptor(self):
        response = Mock(status=200)
        response.read.return_value = b"<root><friendlyName>Bedroom TV</friendlyName><modelDescription>vidaa_support</modelDescription></root>"
        connection = Mock()
        connection.getresponse.return_value = response
        return connection

    def test_descriptor_accepts_implicit_http_port_on_another_subnet(self):
        connection = self.descriptor()
        with patch.object(client.http.client, "HTTPConnection", return_value=connection) as connect:
            tv = client.fetch_descriptor("10.23.7.42", "http://10.23.7.42/description.xml?device=tv")
        connect.assert_called_once_with("10.23.7.42", 80, timeout=3)
        connection.request.assert_called_once_with("GET", "/description.xml?device=tv")
        connection.close.assert_called_once()
        self.assertTrue(tv.is_vidaa)
        self.assertEqual(tv.host, "10.23.7.42")

    def test_descriptor_uses_advertised_port_and_name(self):
        connection = self.descriptor()
        with patch.object(client.http.client, "HTTPConnection", return_value=connection) as connect:
            tv = client.fetch_descriptor("172.20.4.7", "http://172.20.4.7:38400/description.xml")
        connect.assert_called_once_with("172.20.4.7", 38400, timeout=3)
        self.assertEqual(tv.friendly_name, "Bedroom TV")

    def test_failed_descriptor_closes_connection(self):
        connection = self.descriptor()
        connection.request.side_effect = http.client.HTTPException("Bad reply")
        with patch.object(client.http.client, "HTTPConnection", return_value=connection):
            self.assertIsNone(client.fetch_descriptor("192.168.88.73", "http://192.168.88.73/"))
        connection.close.assert_called_once()

    def test_descriptor_falls_back_to_the_older_description_path(self):
        # Sets that predate the MediaServer layout answer 404 on that path.
        missing = Mock()
        missing.getresponse.return_value = Mock(status=404, read=Mock(return_value=b""))
        found = self.descriptor()
        connections = [missing, found]
        with patch.object(client.http.client, "HTTPConnection",
                          side_effect=connections):
            tv = client.fetch_descriptor("192.168.88.73")
        self.assertIsNotNone(tv)
        self.assertTrue(tv.is_vidaa)
        missing.request.assert_called_once_with(
            "GET", "/MediaServer/rendererdevicedesc.xml")
        found.request.assert_called_once_with("GET", "/description.xml")
        for connection in connections:
            connection.close.assert_called_once()

    def test_self_signed_https_descriptor_on_the_same_port_is_accepted(self):
        # A TLS-only listener accepts the connection and then drops plain HTTP,
        # which reaches us as a timeout rather than a refusal.
        offline = Mock()
        offline.request.side_effect = OSError("no plain HTTP descriptor")
        secure = self.descriptor()
        with patch.object(client.http.client, "HTTPConnection", return_value=offline), \
                patch.object(client.http.client, "HTTPSConnection",
                             return_value=secure) as https:
            tv = client.fetch_descriptor("192.168.88.73")
        self.assertTrue(tv.is_vidaa)
        https.assert_called_once_with("192.168.88.73", 18400, timeout=3,
                                      context=ANY)
        secure.request.assert_called_once_with(
            "GET", "/MediaServer/rendererdevicedesc.xml")

    def test_every_descriptor_port_is_tried_with_both_schemes(self):
        locations = client._descriptor_locations("192.168.88.73")
        self.assertEqual(len(locations), len(client.UPNP_PORTS) * 2
                         * len(client.UPNP_PATHS))
        self.assertIn("https://192.168.88.73:18400/description.xml", locations)
        self.assertIn("https://192.168.88.73:38400/description.xml", locations)
        # The plain-HTTP probe of a port immediately precedes its TLS probe.
        self.assertEqual(locations.index(
            "https://192.168.88.73:18400/MediaServer/rendererdevicedesc.xml"),
            locations.index(
                "http://192.168.88.73:18400/MediaServer/rendererdevicedesc.xml") + 2)

    def test_generic_descriptor_does_not_shadow_the_vidaa_one(self):
        router = Mock()
        router.getresponse.return_value = Mock(
            status=200, read=Mock(return_value=b"<root><friendlyName>Router</friendlyName></root>"))
        real = self.descriptor()
        with patch.object(client.http.client, "HTTPConnection",
                          side_effect=[router, real]):
            tv = client.fetch_descriptor("192.168.88.73")
        self.assertTrue(tv.is_vidaa)
        self.assertEqual(tv.friendly_name, "Bedroom TV")

    def test_generic_descriptor_alone_stays_unverified(self):
        router = Mock()
        router.getresponse.return_value = Mock(
            status=200, read=Mock(return_value=b"<root><friendlyName>Router</friendlyName></root>"))
        with patch.object(client.http.client, "HTTPConnection", return_value=router):
            tv = client.fetch_descriptor("192.168.88.73")
        # Reported, but never accepted as a TV: an open port cannot self-approve.
        self.assertIsNotNone(tv)
        self.assertFalse(tv.is_vidaa)

    def test_invalid_descriptor_urls_do_not_open_connections(self):
        with patch.object(client.http.client, "HTTPConnection") as connect:
            for location in ("ftp://10.23.7.42/", "http://10.23.7.42:99999/", "invalid",
                             "http://user:password@10.23.7.42/"):
                with self.subTest(location=location):
                    self.assertIsNone(client.fetch_descriptor("10.23.7.42", location))
            connect.assert_not_called()


class TestJellyfinAddresses(unittest.TestCase):
    def test_other_private_networks_use_the_entered_server(self):
        for host in ("10.23.7.50", "172.20.4.50", "192.168.88.50"):
            with self.subTest(host=host):
                url = presets.build_server_url(host + ":8096")
                self.assertEqual(url, "http://" + host + ":8096/web/index.html")
                webui._validate_preset(dict(presets.get("jellyfin"), url=url))

    def test_localhost_and_loopback_are_rejected(self):
        for server in ("localhost:8096", "https://localhost./", "127.0.0.1:8096",
                       "127.5.6.7", "0.0.0.0:8096", "http://[::1]:8096", "[::]:8096"):
            with self.subTest(server=server):
                with self.assertRaisesRegex(ValueError, "LAN IP"):
                    presets.build_server_url(server)

    def test_private_server_path_and_ipv6_do_not_confuse_the_port(self):
        self.assertEqual(presets.build_server_url("nas.home.local/jellyfin"),
                         "http://nas.home.local:8096/jellyfin/web/index.html")
        self.assertEqual(presets.build_server_url("[fd00::50]"),
                         "http://[fd00::50]:8096/web/index.html")

    def test_explicit_full_urls_keep_their_port_and_path(self):
        self.assertEqual(presets.build_server_url("https://media.example.com/jellyfin"),
                         "https://media.example.com/jellyfin/web/index.html")
        self.assertEqual(presets.build_server_url("http://10.23.7.50:9000/web/index.html"),
                         "http://10.23.7.50:9000/web/index.html")

    def test_invalid_localhost_does_not_attempt_tv_installation(self):
        handler = object.__new__(webui.Handler)
        with patch.object(client.Session, "load") as load:
            with self.assertRaisesRegex(ValueError, "LAN IP"):
                handler._install({"app": "jellyfin", "server": "localhost:8096"})
            load.assert_not_called()

    def test_cli_reports_localhost_error_without_a_traceback(self):
        with patch.object(client.Session, "load") as load, patch("builtins.print") as output:
            result = sidee.cmd_cli(SimpleNamespace(cmd="install", preset="jellyfin", server="localhost"))
        self.assertEqual(result, 2)
        self.assertIn("LAN IP", output.call_args.args[0])
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
