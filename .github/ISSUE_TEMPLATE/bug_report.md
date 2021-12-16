---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**Common problems**
- If you receive a TransportQueryError, it means the error is coming from the backend (See [Error Handling](https://gql.readthedocs.io/en/latest/advanced/error_handling.html)) and has probably nothing to do with gql
- If you use IPython (Jupyter, Spyder), then [you need to use the async version](https://gql.readthedocs.io/en/latest/async/async_usage.html#ipython)
- Before sending a bug report, please consider [activating debug logs](https://gql.readthedocs.io/en/latest/advanced/logging.html) to see the messages exchanged between the client and the backend

**Describe the bug**
A clear and concise description of what the bug is.
Please provide a full stack trace if you have one.
If you can, please provide the backend URL, the GraphQL schema, the code you used.

**To Reproduce**
Steps to reproduce the behavior:

**Expected behavior**
A clear and concise description of what you expected to happen.

**System info (please complete the following information):**
 - OS:
 - Python version:
 - gql version:
 - graphql-core version:
