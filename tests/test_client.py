import unittest
import unittest.mock

from websockets.client import *
from websockets.connection import CONNECTING, OPEN
from websockets.datastructures import Headers
from websockets.exceptions import InvalidHandshake, InvalidHeader
from websockets.http import USER_AGENT
from websockets.http11 import Request, Response
from websockets.utils import accept_key

from .extensions.utils import (
    ClientOpExtensionFactory,
    ClientRsv2ExtensionFactory,
    OpExtension,
    Rsv2Extension,
)
from .test_utils import ACCEPT, KEY
from .utils import DATE


class ConnectTests(unittest.TestCase):
    def test_send_connect(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("wss://example.com/test")
        request = client.connect()
        self.assertIsInstance(request, Request)
        bytes_to_send = client.send_request(request)
        self.assertEqual(
            bytes_to_send,
            (
                f"GET /test HTTP/1.1\r\n"
                f"Host: example.com\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {KEY}\r\n"
                f"Sec-WebSocket-Version: 13\r\n"
                f"User-Agent: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )

    def test_connect_request(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("wss://example.com/test")
        request = client.connect()
        self.assertEqual(request.path, "/test")
        self.assertEqual(
            request.headers,
            Headers(
                {
                    "Host": "example.com",
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Key": KEY,
                    "Sec-WebSocket-Version": "13",
                    "User-Agent": USER_AGENT,
                }
            ),
        )

    def test_path(self):
        client = ClientConnection("wss://example.com/endpoint?test=1")
        request = client.connect()

        self.assertEqual(request.path, "/endpoint?test=1")

    def test_port(self):
        for uri, host in [
            ("ws://example.com/", "example.com"),
            ("ws://example.com:80/", "example.com"),
            ("ws://example.com:8080/", "example.com:8080"),
            ("wss://example.com/", "example.com"),
            ("wss://example.com:443/", "example.com"),
            ("wss://example.com:8443/", "example.com:8443"),
        ]:
            with self.subTest(uri=uri):
                client = ClientConnection(uri)
                request = client.connect()

                self.assertEqual(request.headers["Host"], host)

    def test_user_info(self):
        client = ClientConnection("wss://hello:iloveyou@example.com/")
        request = client.connect()

        self.assertEqual(request.headers["Authorization"], "Basic aGVsbG86aWxvdmV5b3U=")

    def test_origin(self):
        client = ClientConnection("wss://example.com/", origin="https://example.com")
        request = client.connect()

        self.assertEqual(request.headers["Origin"], "https://example.com")

    def test_extensions(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory()]
        )
        request = client.connect()

        self.assertEqual(request.headers["Sec-WebSocket-Extensions"], "x-op; op")

    def test_subprotocols(self):
        client = ClientConnection("wss://example.com/", subprotocols=["chat"])
        request = client.connect()

        self.assertEqual(request.headers["Sec-WebSocket-Protocol"], "chat")

    def test_extra_headers(self):
        for extra_headers in [
            Headers({"X-Spam": "Eggs"}),
            {"X-Spam": "Eggs"},
            [("X-Spam", "Eggs")],
        ]:
            with self.subTest(extra_headers=extra_headers):
                client = ClientConnection(
                    "wss://example.com/", extra_headers=extra_headers
                )
                request = client.connect()

                self.assertEqual(request.headers["X-Spam"], "Eggs")

    def test_extra_headers_overrides_user_agent(self):
        client = ClientConnection(
            "wss://example.com/", extra_headers={"User-Agent": "Other"}
        )
        request = client.connect()

        self.assertEqual(request.headers["User-Agent"], "Other")


class AcceptRejectTests(unittest.TestCase):
    def test_receive_accept(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [response], bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {ACCEPT}\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(bytes_to_send, [])
        self.assertEqual(client.state, OPEN)

    def test_receive_reject(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [response], bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 404 Not Found\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"Content-Length: 13\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"Sorry folks.\n"
            ).encode(),
        )
        self.assertIsInstance(response, Response)
        self.assertEqual(bytes_to_send, [])
        self.assertEqual(client.state, CONNECTING)

    def test_accept_response(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [response], _bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 101 Switching Protocols\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {ACCEPT}\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"\r\n"
            ).encode(),
        )
        self.assertEqual(response.status_code, 101)
        self.assertEqual(response.reason_phrase, "Switching Protocols")
        self.assertEqual(
            response.headers,
            Headers(
                {
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Accept": ACCEPT,
                    "Date": DATE,
                    "Server": USER_AGENT,
                }
            ),
        )
        self.assertIsNone(response.body)

    def test_reject_response(self):
        with unittest.mock.patch("websockets.client.generate_key", return_value=KEY):
            client = ClientConnection("ws://example.com/test")
        client.connect()
        [response], _bytes_to_send = client.receive_data(
            (
                f"HTTP/1.1 404 Not Found\r\n"
                f"Date: {DATE}\r\n"
                f"Server: {USER_AGENT}\r\n"
                f"Content-Length: 13\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n"
                f"Connection: close\r\n"
                f"\r\n"
                f"Sorry folks.\n"
            ).encode(),
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.reason_phrase, "Not Found")
        self.assertEqual(
            response.headers,
            Headers(
                {
                    "Date": DATE,
                    "Server": USER_AGENT,
                    "Content-Length": "13",
                    "Content-Type": "text/plain; charset=utf-8",
                    "Connection": "close",
                }
            ),
        )
        self.assertEqual(response.body, b"Sorry folks.\n")

    def make_accept_response(self, client):
        request = client.connect()
        return Response(
            status_code=101,
            reason_phrase="Switching Protocols",
            headers=Headers(
                {
                    "Upgrade": "websocket",
                    "Connection": "Upgrade",
                    "Sec-WebSocket-Accept": accept_key(
                        request.headers["Sec-WebSocket-Key"]
                    ),
                }
            ),
        )

    def test_basic(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)

    def test_missing_connection(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Connection"]
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "missing Connection header")

    def test_invalid_connection(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Connection"]
        response.headers["Connection"] = "close"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "invalid Connection header: close")

    def test_missing_upgrade(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Upgrade"]
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "missing Upgrade header")

    def test_invalid_upgrade(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Upgrade"]
        response.headers["Upgrade"] = "h2c"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "invalid Upgrade header: h2c")

    def test_missing_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Sec-WebSocket-Accept"]
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "missing Sec-WebSocket-Accept header")

    def test_multiple_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Accept"] = ACCEPT
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(
            str(raised.exception),
            "invalid Sec-WebSocket-Accept header: "
            "more than one Sec-WebSocket-Accept header found",
        )

    def test_invalid_accept(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        del response.headers["Sec-WebSocket-Accept"]
        response.headers["Sec-WebSocket-Accept"] = ACCEPT
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHeader) as raised:
            raise response.exception
        self.assertEqual(
            str(raised.exception), f"invalid Sec-WebSocket-Accept header: {ACCEPT}"
        )

    def test_no_extensions(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [])

    def test_no_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [OpExtension()])

    def test_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientRsv2ExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [Rsv2Extension()])

    def test_unexpected_extension(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "no extensions supported")

    def test_unsupported_extension(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientRsv2ExtensionFactory()]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(
            str(raised.exception),
            "Unsupported extension: name = x-op, params = [('op', None)]",
        )

    def test_supported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory("this")]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op=this"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [OpExtension("this")])

    def test_unsupported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/", extensions=[ClientOpExtensionFactory("this")]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op=that"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(
            str(raised.exception),
            "Unsupported extension: name = x-op, params = [('op', 'that')]",
        )

    def test_multiple_supported_extension_parameters(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[
                ClientOpExtensionFactory("this"),
                ClientOpExtensionFactory("that"),
            ],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op=that"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [OpExtension("that")])

    def test_multiple_extensions(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[ClientOpExtensionFactory(), ClientRsv2ExtensionFactory()],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op"
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [OpExtension(), Rsv2Extension()])

    def test_multiple_extensions_order(self):
        client = ClientConnection(
            "wss://example.com/",
            extensions=[ClientOpExtensionFactory(), ClientRsv2ExtensionFactory()],
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Extensions"] = "x-rsv2"
        response.headers["Sec-WebSocket-Extensions"] = "x-op; op"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.extensions, [Rsv2Extension(), OpExtension()])

    def test_no_subprotocols(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertIsNone(client.subprotocol)

    def test_no_subprotocol(self):
        client = ClientConnection("wss://example.com/", subprotocols=["chat"])
        response = self.make_accept_response(client)
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertIsNone(client.subprotocol)

    def test_subprotocol(self):
        client = ClientConnection("wss://example.com/", subprotocols=["chat"])
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.subprotocol, "chat")

    def test_unexpected_subprotocol(self):
        client = ClientConnection("wss://example.com/")
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "no subprotocols supported")

    def test_multiple_subprotocols(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "superchat"
        response.headers["Sec-WebSocket-Protocol"] = "chat"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(
            str(raised.exception), "multiple subprotocols: superchat, chat"
        )

    def test_supported_subprotocol(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "chat"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, OPEN)
        self.assertEqual(client.subprotocol, "chat")

    def test_unsupported_subprotocol(self):
        client = ClientConnection(
            "wss://example.com/", subprotocols=["superchat", "chat"]
        )
        response = self.make_accept_response(client)
        response.headers["Sec-WebSocket-Protocol"] = "otherchat"
        [response], _bytes_to_send = client.receive_data(response.serialize())

        self.assertEqual(client.state, CONNECTING)
        with self.assertRaises(InvalidHandshake) as raised:
            raise response.exception
        self.assertEqual(str(raised.exception), "unsupported subprotocol: otherchat")