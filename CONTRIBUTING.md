# Contributing

Thanks for helping to make gql awesome!

We welcome all kinds of contributions:

- Bug fixes
- Documentation improvements
- New features
- Refactoring & tidying


## Getting started

If you have a specific contribution in mind, be sure to check the
[issues](https://github.com/graphql-python/gql/issues)
and [pull requests](https://github.com/graphql-python/gql/pulls)
in progress - someone could already be working on something similar
and you can help out.

## Project setup

### Development with virtualenv (recommended)

After cloning this repo, create a virtualenv:

```console
virtualenv gql-dev
```

Activate the virtualenv and install dependencies by running:

```console
python -m pip install -e.[dev]
```

If you are using Linux or MacOS, you can make use of Makefile command
`make dev-setup`, which is a shortcut for the above python command.

### Development on Conda

You must create a new env (e.g. `gql-dev`) with the following command:

```sh
conda create -n gql-dev python=3.8
```

Then activate the environment with `conda activate gql-dev`.

Proceed to install all dependencies by running:

```console
pip install -e.[dev]
```

And you ready to start development!

<!-- TODO: Provide environment.yml file for conda env -->

## Coding guidelines

Several tools are used to ensure a coherent coding style.
You need to make sure that your code satisfy those requirements
or the automated tests will fail.

- [black code formatter](https://github.com/psf/black)
- [flake8 style enforcement](https://flake8.pycqa.org/en/latest/index.html)
- [mypy static type checker](http://mypy-lang.org/)
- [isort to sort imports alphabetically](https://isort.readthedocs.io/en/stable/)

On Linux or MacOS, you can fix and check your code style by running
the Makefile command `make check` (this is also checked by running
the automated tests with tox but it is much faster with make)

In addition to the above checks, it is asked that:

- [type hints are used](https://docs.python.org/3/library/typing.html)
- tests are added to ensure complete code coverage

## Running tests

After developing, the full test suite can be evaluated by running:

```sh
pytest tests --cov=gql --cov-report=term-missing -vv
```

Please note that some tests which require external online resources are not
done in the automated tests. You can run those tests by running:

```sh
pytest tests --cov=gql --cov-report=term-missing --run-online -vv
```

If you are using Linux or MacOS, you can make use of Makefile commands
`make tests` and `make all_tests`, which are shortcuts for the above
python commands.

You can also test on several python environments by using tox.

### Running tox on virtualenv

Install tox:
```console
pip install tox
```

Run `tox` on your virtualenv (do not forget to activate it!)
and that's it!

### Running tox on Conda

In order to run `tox` command on conda, install
[tox-conda](https://github.com/tox-dev/tox-conda):

```sh
conda install -c conda-forge tox-conda
```

This install tox underneath so no need to install it before.

Then add the line `requires = tox-conda` in the `tox.ini` file under `[tox]`.

Run `tox` and you will see all the environments being created
and all passing tests. :rocket:

## How to create a good Pull Request

1. Make a fork of the master branch on github
2. Clone your forked repo on your computer
3. Create a feature branch `git checkout -b feature_my_awesome_feature`
4. Modify the code
5. Verify that the [Coding guidelines](#coding-guidelines) are respected
6. Verify that the [automated tests](#running-tests) are passing
7. Make a commit and push it to your fork
8. From github, create the pull request. Automated tests from GitHub actions
and codecov will then automatically run the tests and check the code coverage
9. If other modifications are needed, you are free to create more commits and
push them on your branch. They'll get added to the PR automatically.

Once the Pull Request is accepted and merged, you can safely
delete the branch (and the forked repo if no more development is needed).
