File uploads
============

GQL supports file uploads with the :ref:`aiohttp transport <aiohttp_transport>`, the
:ref:`requests transport <requests_transport>`, the :ref:`httpx transport <httpx_transport>`,
and the :ref:`httpx async transport <httpx_async_transport>`,
using the `GraphQL multipart request spec`_.

.. _GraphQL multipart request spec: https://github.com/jaydenseric/graphql-multipart-request-spec

Single File
-----------

In order to upload a single file, you need to:

* set the file as a variable value in the mutation
* create a :class:`FileVar <gql.FileVar>` object with your file path
* provide the `FileVar` instance to the `variable_values` attribute of your query
* set the `upload_files` argument to True

.. code-block:: python

    from gql import client, gql, FileVar

    transport = AIOHTTPTransport(url='YOUR_URL')
    # Or transport = RequestsHTTPTransport(url='YOUR_URL')
    # Or transport = HTTPXTransport(url='YOUR_URL')
    # Or transport = HTTPXAsyncTransport(url='YOUR_URL')

    client = Client(transport=transport)

    query = gql('''
      mutation($file: Upload!) {
        singleUpload(file: $file) {
          id
        }
      }
    ''')

    query.variable_values = {"file": FileVar("YOUR_FILE_PATH")}

    result = client.execute(query, upload_files=True)

Setting the content-type
^^^^^^^^^^^^^^^^^^^^^^^^

If you need to set a specific Content-Type attribute to a file,
you can set the :code:`content_type` attribute of :class:`FileVar <gql.FileVar>`:

.. code-block:: python

    # Setting the content-type to a pdf file for example
    filevar = FileVar(
        "YOUR_FILE_PATH",
        content_type="application/pdf",
    )

Setting the uploaded file name
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To modify the uploaded filename, use the :code:`filename` attribute of :class:`FileVar <gql.FileVar>`:

.. code-block:: python

    # Setting the content-type to a pdf file for example
    filevar = FileVar(
        "YOUR_FILE_PATH",
        filename="filename1.txt",
    )

File list
---------

It is also possible to upload multiple files using a list.

.. code-block:: python

    from gql import client, gql, FileVar

    transport = AIOHTTPTransport(url='YOUR_URL')
    # Or transport = RequestsHTTPTransport(url='YOUR_URL')
    # Or transport = HTTPXTransport(url='YOUR_URL')
    # Or transport = HTTPXAsyncTransport(url='YOUR_URL')

    client = Client(transport=transport)

    query = gql('''
      mutation($files: [Upload!]!) {
        multipleUpload(files: $files) {
          id
        }
      }
    ''')

    f1 = FileVar("YOUR_FILE_PATH_1")
    f2 = FileVar("YOUR_FILE_PATH_2")

    query.variable_values = {"files": [f1, f2]}

    result = client.execute(query, upload_files=True)


Streaming
---------

If you use the above methods to send files, then the entire contents of the files
must be loaded in memory before the files are sent.
If the files are not too big and you have enough RAM, it is not a problem.
On another hand if you want to avoid using too much memory, then it is better
to read the files and send them in small chunks so that the entire file contents
don't have to be in memory at once.

We provide methods to do that for two different uses cases:

* Sending local files
* Streaming downloaded files from an external URL to the GraphQL API

.. note::
    Streaming is only supported with the :ref:`aiohttp transport <aiohttp_transport>`

Streaming local files
^^^^^^^^^^^^^^^^^^^^^

aiohttp allows to upload files using an asynchronous generator.
See `Streaming uploads on aiohttp docs`_.

From gql version 4.0, it is possible to activate file streaming simply by
setting the `streaming` argument of :class:`FileVar <gql.FileVar>` to `True`

.. code-block:: python

    transport = AIOHTTPTransport(url='YOUR_URL')

    client = Client(transport=transport)

    query = gql('''
      mutation($file: Upload!) {
        singleUpload(file: $file) {
          id
        }
      }
    ''')

    f1 = FileVar(
        file_name='YOUR_FILE_PATH',
        streaming=True,
    )

    query.variable_values = {"file": f1}

    result = client.execute(query, upload_files=True)

Another option is to use an async generator to provide parts of the file.

You can use `aiofiles`_
to read the files in chunks and create this asynchronous generator.

.. _Streaming uploads on aiohttp docs: https://docs.aiohttp.org/en/stable/client_quickstart.html#streaming-uploads
.. _aiofiles: https://github.com/Tinche/aiofiles

.. code-block:: python

    async def file_sender(file_name):
        async with aiofiles.open(file_name, 'rb') as f:
            while chunk := await f.read(64*1024):
                yield chunk

    f1 = FileVar(file_sender(file_name='YOUR_FILE_PATH'))
    query.variable_values = {"file": f1}

    result = client.execute(query, upload_files=True)

Streaming downloaded files
^^^^^^^^^^^^^^^^^^^^^^^^^^

If the file you want to upload to the GraphQL API is not present locally
and needs to be downloaded from elsewhere, then it is possible to chain the download
and the upload in order to limit the amout of memory used.

Because the `content` attribute of an aiohttp response is a `StreamReader`
(it provides an async iterator protocol), you can chain the download and the upload
together.

In order to do that, you need to:

* get the response from an aiohttp request and then get the StreamReader instance
  from `resp.content`
* provide the StreamReader instance to the `variable_values` attribute of your query

Example:

.. code-block:: python

    # First request to download your file with aiohttp
    async with aiohttp.ClientSession() as http_client:
        async with http_client.get('YOUR_DOWNLOAD_URL') as resp:

            # We now have a StreamReader instance in resp.content
            # and we provide it to the variable_values attribute of the query

            transport = AIOHTTPTransport(url='YOUR_GRAPHQL_URL')

            client = Client(transport=transport)

            query = gql('''
              mutation($file: Upload!) {
                singleUpload(file: $file) {
                  id
                }
              }
            ''')

            query.variable_values = {"file": FileVar(resp.content)}

            result = client.execute(query, upload_files=True)
