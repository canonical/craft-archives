# Contributing to Craft Archives

We welcome contributions to Craft Archives! Craft Archives is open source and part of the Canonical family.

## Code of Conduct

This project is governed by the [Ubuntu Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct). We expect good conduct and excellence from every member.

## Contributor License Agreement

Before we can accept your pull requests, you must sign the [Canonical Contributor License Agreement](http://www.ubuntu.com/legal/contributors).

## Reporting Issues

Please report bugs or suggest features on our [GitHub Issues page](https://github.com/canonical/craft-archives/issues).

## Development Setup

Craft Archives uses [uv](https://docs.astral.sh/uv/) for dependency and virtual environment management.

To set up your local development environment:

```bash
make setup
```

### Running Tests

To run the fast tests:

```bash
make test-fast
```

To run the full test suite (including unit and integration tests):

```bash
make test
```

### Formatting and Linting

Before pushing your changes, please run formatters and linters:

```bash
make format
make lint
```

## Creating a Pull Request

1. Fork the repository on GitHub.
2. Create a feature branch (named `work/<description>` or `issue-<number>-<description>`).
3. Commit your changes using [Conventional Commits](https://www.conventionalcommits.org/).
4. Push your branch to your fork and open a Pull Request against the `main` branch.
