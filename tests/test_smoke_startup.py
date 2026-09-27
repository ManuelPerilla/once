"""Regresiones de la carrera entre Docker, el entrypoint de NGINX y el smoke test."""

import http.client
import io
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from scripts.smoke_test import expect_unauthorized, wait_for_api


def http_error(code):
    return urllib.error.HTTPError("http://localhost/api/partidos/", code, "test", {}, io.BytesIO())


class StartupTests(unittest.TestCase):
    @patch("scripts.smoke_test.time.sleep")
    @patch("scripts.smoke_test.urllib.request.urlopen")
    def test_retries_reset_disconnect_and_gateway_until_auth_is_ready(self, request, sleep):
        request.side_effect = [
            ConnectionResetError(104, "Connection reset by peer"),
            http.client.RemoteDisconnected("Remote end closed connection"),
            urllib.error.URLError("connection refused"),
            TimeoutError(),
            http_error(502),
            http_error(503),
            http_error(504),
            http_error(401),
        ]
        wait_for_api("http://localhost", attempts=8)
        self.assertEqual(request.call_count, 8)
        self.assertEqual(sleep.call_count, 7)

    @patch("scripts.smoke_test.time.sleep")
    @patch("scripts.smoke_test.urllib.request.urlopen")
    def test_timeout_is_bounded_and_diagnostic(self, request, sleep):
        request.side_effect = ConnectionResetError()
        with self.assertRaisesRegex(RuntimeError, "3 intentos.*ConnectionResetError"):
            wait_for_api("http://localhost", attempts=3)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_count, 2)

    @patch("scripts.smoke_test.time.sleep")
    @patch("scripts.smoke_test.urllib.request.urlopen")
    def test_unprotected_200_fails_immediately(self, request, sleep):
        request.return_value.__enter__.return_value.status = 200
        with self.assertRaisesRegex(AssertionError, "HTTP 200"):
            wait_for_api("http://localhost")
        sleep.assert_not_called()

    @patch("scripts.smoke_test.time.sleep")
    @patch("scripts.smoke_test.urllib.request.urlopen")
    def test_configuration_or_application_errors_are_not_hidden_by_retries(self, request, sleep):
        for status in (403, 404, 500):
            request.side_effect = http_error(status)
            with self.assertRaisesRegex(AssertionError, str(status)):
                wait_for_api("http://localhost")
        sleep.assert_not_called()

    def test_auth_assertions_do_not_tolerate_connection_failures(self):
        opener = MagicMock()
        opener.open.side_effect = ConnectionResetError()
        with self.assertRaises(ConnectionResetError):
            expect_unauthorized(opener, "http://localhost/api/partidos/", "Logout")

    def test_auth_assertions_require_401(self):
        opener = MagicMock()
        opener.open.side_effect = http_error(401)
        expect_unauthorized(opener, "http://localhost/api/partidos/", "Logout")
        opener.open.side_effect = http_error(500)
        with self.assertRaisesRegex(AssertionError, "500 en vez de 401"):
            expect_unauthorized(opener, "http://localhost/api/partidos/", "Logout")


if __name__ == "__main__":
    unittest.main()
