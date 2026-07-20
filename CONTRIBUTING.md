# Contributing

Craft Archives has a community from all over the world, and the Craft Archives team
welcomes all contributions.

All contributors should become familiar with this guide. It outlines the expectations
and practices for participating in the project.

## Review the project expectations

The Starcraft team at Canonical sets the direction and priorities of Craft Archives.
They take responsibility for its stewardship and health.

Before you start work on Craft Archives, there are three documents for you to digest.

### Ubuntu Code of Conduct

Projects governed by Canonical expect good conduct and excellence from every member. The
specific principles are laid out in the [Ubuntu Code of
Conduct](https://ubuntu.com/community/ethos/code-of-conduct).

### Canonical Contributor License Agreement

As a contributor, you retain your copyright and attribution rights, provided you sign
the [Canonical Contributor License Agreement](http://www.ubuntu.com/legal/contributors).
Before committing any code, review its terms. If you agree and sign it, your code can be
incorporated into the repository.

### Open source license

Craft Archives is licensed under [LGPL-3.0](LICENSE).

## Report an issue or open a request

If you find a bug or feature gap in Craft Archives, look for it in the [project's GitHub
issues](https://github.com/canonical/craft-archives/issues) first. If you have fresh
input, add your voice to the issue.

If the bug or feature doesn't have an issue, we invite you to [open
one](https://github.com/canonical/craft-archives/issues/new/choose).

## Set up for development

See [HACKING.md](HACKING.md) for detailed instructions on setting up a development
environment, our branching and commit conventions, and how to write a changelog entry.

In short:

```bash
git clone git@github.com:<username>/craft-archives --recurse-submodules
cd craft-archives
make setup
make lint
make test
```

## Contribute a change

All significant work should be tied to an existing GitHub issue. If you don't find a
related issue, [open one](https://github.com/canonical/craft-archives/issues/new/choose)
and indicate that you're interested in taking it on.

Format commits and branch names according to the conventions in
[HACKING.md](HACKING.md#commits). Push your branch to your fork and open a PR against
`main`.

### Test the change

For low-complexity changes, run the fast tests:

```bash
make test-fast
```

For complex work, run the full test suite:

```bash
make test
```

### Document the change

Update any affected documentation under `docs/` and add an entry to the
[changelog](docs/changelog.rst) if the change is user-facing. Build the docs locally
with:

```bash
make docs
make lint-docs
```
