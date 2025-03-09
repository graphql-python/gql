import asyncio
import functools

from aiohttp import ClientSession


def create_aiohttp_closed_event(session: ClientSession) -> asyncio.Event:
    """Work around aiohttp issue that doesn't properly close transports on exit.

    See https://github.com/aio-libs/aiohttp/issues/1925#issuecomment-639080209

    Returns:
       An event that will be set once all transports have been properly closed.
    """

    ssl_transports = 0
    all_is_lost = asyncio.Event()

    def connection_lost(exc, orig_lost):
        nonlocal ssl_transports

        try:
            orig_lost(exc)
        finally:
            ssl_transports -= 1
            if ssl_transports == 0:
                all_is_lost.set()

    def eof_received(orig_eof_received):
        try:  # pragma: no cover
            orig_eof_received()
        except AttributeError:  # pragma: no cover
            # It may happen that eof_received() is called after
            # _app_protocol and _transport are set to None.
            pass

    assert session.connector is not None

    for conn in session.connector._conns.values():
        for handler, _ in conn:
            proto = getattr(handler.transport, "_ssl_protocol", None)
            if proto is None:
                continue

            ssl_transports += 1
            orig_lost = proto.connection_lost
            orig_eof_received = proto.eof_received

            proto.connection_lost = functools.partial(
                connection_lost, orig_lost=orig_lost
            )
            proto.eof_received = functools.partial(
                eof_received, orig_eof_received=orig_eof_received
            )

    if ssl_transports == 0:
        all_is_lost.set()

    return all_is_lost
