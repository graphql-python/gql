File uploads
============

GQL supports file uploads with the :ref:`aiohttp transport <aiohttp_transport>`
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

    client = Client(transport=sample_transport)

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

File list
---------

It is also possible to upload multiple files using a list.

.. code-block:: python

    transport = AIOHTTPTransport(url='YOUR_URL')

    client = Client(transport=sample_transport)

    query = gql('''
      mutation($files: [Upload!]!) {
        multipleUpload(files: $files) {
          id
        }
      }
    ''')

    f1 = open("YOUR_FILE_PATH_1", "rb")
    f2 = open("YOUR_FILE_PATH_1", "rb")

    params = {"files": [f1, f2]}

    result = client.execute(
        query, variable_values=params, upload_files=True
    )

    f1.close()
    f2.close()


Aiohttp StreamReader
--------------------

In order to upload a aiohttp StreamReader, you need to:

* get response from aiohttp request and then get StreamReader from `resp.content`
* provide the StreamReader to the `variable_values` argument of `execute`
* set the `upload_files` argument to True


.. code-block:: python

   async with ClientSession() as client:
       async with client.get('YOUR_URL') as resp:
           transport = AIOHTTPTransport(url='YOUR_URL')
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

Asynchronous Generator
----------------------

In order to upload a single file use asynchronous generator(https://docs.aiohttp.org/en/stable/client_quickstart.html#streaming-uploads), you need to:

* сreate a asynchronous generator
* set the generator as a variable value in the mutation
* provide the opened file to the `variable_values` argument of `execute`
* set the `upload_files` argument to True

.. code-block:: python

    transport = AIOHTTPTransport(url='YOUR_URL')

    client = Client(transport=sample_transport)

    query = gql('''
      mutation($file: Upload!) {
        singleUpload(file: $file) {
          id
        }
      }
    ''')

    async def file_sender(file_name=None):
        async with aiofiles.open(file_name, 'rb') as f:
            chunk = await f.read(64*1024)
                while chunk:
                    yield chunk
                    chunk = await f.read(64*1024)

    params = {"file": file_sender(file_name='YOUR_FILE_PATH')}

    result = client.execute(
		query, variable_values=params, upload_files=True
	)