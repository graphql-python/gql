# Contributing

Thanks for helping to make gql awesome!

We welcome all kinds of contributions:

- Bug fixes
- Documentation improvements
- New features
- Refactoring & tidying


## Getting started

If you have a specific contribution in mind, be sure to check the [issues](https://github.com/graphql-python/gql/issues) and [pull requests](https://github.com/graphql-python/gql/pulls) in progress - someone could already be working on something similar and you can help out.


## Project setup

After cloning this repo, ensure dependencies are installed by running:

```sh
make dev-setup
```

## Running tests

After developing, the full test suite can be evaluated by running:

```sh
make tests
```

## Development on Conda

In order to run `tox` command on conda, you must create a new env (e.g. `gql-dev`) with the following command:

```sh
conda create -n gql-dev python=3.8
```

Then activate the environment with `conda activate gql-dev` and install [tox-conda](https://github.com/tox-dev/tox-conda):

```sh
conda install -c conda-forge tox-conda
```

Uncomment the `requires = tox-conda` line on `tox.ini` file and that's it! Run `tox` and you will see all the environments being created and all passing tests. :rocket:

