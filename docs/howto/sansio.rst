Integrate the Sans-I/O layer
============================

.. currentmodule:: websockets

.. note::

    The discussion of the :doc:`design of websockets <../topics/design>`
    explains how responsibilities are split between the Sans-I/O layer
    provided by websockets and the integration layer you're working on.

This guide explains how to integrate the Sans-I/O layer of websockets to add
support for WebSocket in another library.

As a prerequisite, you should decide how you will handle network I/O and
asynchronous control flow.

Your integration will provide an API for the application on one side, will
talk to the network on the other side, and rely on websockets to implement
the protocol in the middle, as shown in this diagram.

.. image:: ../topics/data-flow.svg

Initializing a connection
-------------------------

If you're building a client, open a network connection to the server and
initialize a :class:`~client.ClientConnection`::

    from websockets.client import ClientConnection

    connection = ClientConnection()

An API for WebSocket clients will usually return a wrapper around the network
connection and the :class:`~client.ClientConnection`.

If you're building a server, accept network connections from clients and, for
each one, initialize a :class:`~server.ServerConnection`::

    from websockets.server import ServerConnection

    connection = ServerConnection()

An API for WebSockets servers will usually build a wrapper around the network
connection and the :class:`~server.ServerConnection` and invoke a connection
handler. It may support closing all connections and shutting down gracefully.

Going forwards, this guide focuses on handling an individual connection.

From network to application
---------------------------

Go through the four steps below until you reach the end of the data stream.

Receive data
............

When receiving data from the network, feed it
to :meth:`~connection.Connection.receive_data`.

When reaching the end of the data stream,
call :meth:`~connection.Connection.receive_eof`.

For example, if ``sock`` is a :class:`~socket.socket`::

    data = sock.recv(4096)
    if data:
        connection.receive_data(data)
    else:
        connection.receive_eof()

These methods aren't expected to raise exceptions — unless you call them again
after calling :meth:`~connection.Connection.receive_eof`, which is an error.
(If you get an exception, please file a bug!)

Send data
.........

Then, call :meth:`~connection.Connection.data_to_send` and send its output to
the network::

    for data in connection.data_to_send():
        if data:
            sock.sendall(data)
        else:
            sock.shutdown(socket.SHUT_WR)

The empty bytestring signals the end of the data stream. When you see it, you
must half-close the TCP connection.

Sending data right after receiving data is necessary because websockets
responds to ping frames, close frames, and incorrect inputs automatically.

Close TCP connection
....................

If you called :meth:`~connection.Connection.receive_eof`, close the TCP
connection now. This is a clean closure because the receive buffer is empty.

Note that :meth:`~connection.Connection.receive_eof` signals the end of the
read stream, :meth:`~connection.Connection.data_to_send` always signals the
end of the write stream, unless it already ended. The only reason for closing
the TCP connection here is to release resources related to the socket.

At this point, you can break out of the loop relaying data from the network to
the application.

Closing a WebSocket connection normally involves a two-way WebSocket closing
handshake. Then, regardless of whether the closure is normal or abnormal, the
server starts the four-way TCP closing handshake. If the network fails at the
wrong point, you can end up waiting until the TCP timeout, which is very long.

To prevent dangling TCP connections when you expect the end of the data stream
but you never reach it, call :meth:`~connection.Connection.close_expected`
and, if it returns ``True``, schedule closing the TCP connection after a
short timeout::

    # start a new execution thread to run this code
    sleep(10)
    sock.close()  # does nothing if the socket is already closed
    connection.receive_eof()

Receive events
..............

Finally, call :meth:`~connection.Connection.events_received` to obtain events
parsed from data provided to :meth:`~connection.Connection.receive_data`::

    events = self.connection.events_received()

The first event will be the WebSocket opening handshake request or response.
See :ref:`Opening a connection` below for details.

All later events are WebSocket frames. There are two types of frames:

* Data frames contain messages transferred over the WebSocket connections. You
  should provide them to the application. See :ref:`Fragmentation` below for
  how to reassemble messages from frames.
* Control frames provide information about the connection's state. The main
  use case is to expose to the application an abstraction over ping and pong.
  Keep in mind that websockets responds to ping frames and close frames
  automatically. Don't duplicate this functionality!

From application to network
---------------------------

The connection object provides one method for each type of WebSocket frame.

For data frames:

* :meth:`~connection.Connection.send_continuation`
* :meth:`~connection.Connection.send_text`
* :meth:`~connection.Connection.send_binary`

These methods raise :exc:`~exceptions.ProtocolError` if you don't set the
``FIN`` bit correctly in fragmented messages.

For control frames:

* :meth:`~connection.Connection.send_close`
* :meth:`~connection.Connection.send_ping`
* :meth:`~connection.Connection.send_pong`

:meth:`~connection.Connection.send_close` initiates the closing handshake.
See :ref:`Closing a connection` below for details.

If you encounter an unrecoverable error and you must fail the WebSocket
connection, call :meth:`~connection.Connection.fail`.

Then, call :meth:`~connection.Connection.data_to_send` and send its output to
the network, as shown in :ref:`Send data` above.

If you called :meth:`~connection.Connection.send_close`
or :meth:`~connection.Connection.fail`, then you expect the end of the data
stream. You should prevent dangling TCP connection, as discussed in
:ref:`Close TCP connection` above.

Opening a connection
--------------------

TODO

Closing a connection
--------------------

Under normal circumstances, when a server wants to close the TCP connection:

* it closes the write side, as shown above;
* it reads until the end of the stream, because it expects the client to close
  the read side;
* it closes the socket.

When a client wants to close the TCP connection:

* it reads until the end of the stream, because it expects the client to close
  the read side;
* it closes the write side, as shown above;
* it closes the socket.

TODO

Fragmentation
-------------

TODO

Tips
----

* **Serialize operations**

The Sans-I/O layer expects to run sequentially. If your interact with it from
multiple threads or coroutines, you must ensure correct serialization. This
will happen automatically in a cooperative multitasking environment.

However, make sure you don't break this property. For example, serialize
writes to the network when :meth:`~connection.Connection.data_to_send`
returns multiple values, to prevent concurrent writes from interleaving
incorrectly.
