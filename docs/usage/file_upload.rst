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
