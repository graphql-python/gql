class TransportError(Exception):
    pass


class TransportProtocolError(TransportError):
    """ An answer received from the server does not correspond to the transport protocol"""


class TransportServerError(TransportError):
    """ The server returned a global error

    This exception will close the transport connection
    """


class TransportQueryError(Exception):
    """ The server returned an error for a specific query

    This exception should not close the transport connection
    """

    def __init__(self, msg, query_id=None):
        super().__init__(msg)
        self.query_id = query_id


class TransportClosed(TransportError):
    """ Exception generated when the client is trying to use the transport
    while the transport was previously closed """
