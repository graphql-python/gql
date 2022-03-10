HTTP Headers
============

If you want to add additional http headers for your connection, you can specify these in your transport:

.. code-block:: python

    transport = AIOHTTPTransport(url='YOUR_URL', headers={'Authorization': 'token'})

After the connection, the latest response headers can be found in :code:`transport.response_headers`
