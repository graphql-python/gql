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
* provide the opened file to the `variable_values` argument of `execute`
* set the `upload_files` argument to True

.. code-block:: python

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

    with open("YOUR_FILE_PATH", "rb") as f:

        params = {"file": f}

        result = client.execute(
            query, variable_values=params, upload_files=True
        )

Setting the content-type
^^^^^^^^^^^^^^^^^^^^^^^^

If you need to set a specific Content-Type attribute to a file,
you can set the :code:`content_type` attribute of the file like this:

.. code-block:: python

    with open("YOUR_FILE_PATH", "rb") as f:

        # Setting the content-type to a pdf file for example
        f.content_type = "application/pdf"

        params = {"file": f}

        result = client.execute(
            query, variable_values=params, upload_files=True
        )

File list
---------

It is also possible to upload multiple files using a list.

.. code-block:: python

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

    f1 = open("YOUR_FILE_PATH_1", "rb")
    f2 = open("YOUR_FILE_PATH_2", "rb")

    params = {"files": [f1, f2]}

    result = client.execute(
        query, variable_values=params, upload_files=True
    )

    f1.close()
    f2.close()


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


In order to stream local files, instead of providing opened files to the
`variable_values` argument of `execute`, you need to provide an async generator
which will provide parts of the files.

You can use `aiofiles`_
to read the files in chunks and create this asynchronous generator.

.. _Streaming uploads on aiohttp docs: https://docs.aiohttp.org/en/stable/client_quickstart.html#streaming-uploads
.. _aiofiles: https://github.com/Tinche/aiofiles

Example:

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

    async def file_sender(file_name):
        async with aiofiles.open(file_name, 'rb') as f:
            chunk = await f.read(64*1024)
                while chunk:
                    yield chunk
                    chunk = await f.read(64*1024)

    params = {"file": file_sender(file_name='YOUR_FILE_PATH')}

    result = client.execute(
		query, variable_values=params, upload_files=True
	)

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
* provide the StreamReader instance to the `variable_values` argument of `execute`

Example:

.. code-block:: python

    # First request to download your file with aiohttp
    async with aiohttp.ClientSession() as http_client:
        async with http_client.get('YOUR_DOWNLOAD_URL') as resp:

            # We now have a StreamReader instance in resp.content
            # and we provide it to the variable_values argument of execute

            transport = AIOHTTPTransport(url='YOUR_GRAPHQL_URL')

            client = Client(transport=transport)

            query = gql('''
              mutation($file: Upload!) {
                singleUpload(file: $file) {
                  id
                }
              }
            ''')

            params = {"file": resp.content}

            result = client.execute(
                query, variable_values=params, upload_files=True
            )
