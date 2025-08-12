*********
Changelog
*********

See the `Releases page`_ on Github for a complete list of commits that are
included in each version.

2.2.0 (2025-08-12)
------------------

Features

* Add :py:func:`~craft_archives.defaults.use_old_releases`, which changes a
  system's default repositories to those hosted on ``old-releases.ubuntu.com``.

2.1.0 (2025-Feb-24)
-------------------

Features

* Allow installing apt packages for foreign architectures. This is supported
  in Ubuntu 24.04 or newer or on Ubuntu systems where the default sources file
  ``ubuntu.sources`` is in the `deb822`_ format.

2.0.2 (2024-Dec-04)
-------------------

* Fix an issue where declaring a package-repository to an Ubuntu archive
  using the "https" scheme would cause an error in a later ``apt update``
  when in Noble.

2.0.1 (2024-Oct-21)
-------------------

* Fix an issue where declaring a package-repository to an Ubuntu archive (for
  example, to add an architecture) would cause an error in a later ``apt
  update`` when in Noble.

2.0.0 (2024-08-08)
------------------

* Update minimum Python version to 3.10
* Require Pydantic 2

1.2.0 (2024-07-05)
------------------

* Support "series" and "pocket" in Apt package repositories.
* Support key-ids in PPAs.
* Add missing py.typed file.

1.1.3 (2023-08-04)
------------------

This release addresses a regression where package repository definitions
with declared ``architectures`` would cause an error when calling
``install()``. The fix also changes the behavior to only call
``dpkg --add-architecture`` when the target architecture is "compatible"
with the host's, meaning ``i386`` on ``amd64`` and ``armhf`` on ``amd64``.


1.1.2 (2023-07-12)
------------------

This release addresses a regression where local filepaths were no longer
accepted for the ``url`` property of an deb-type repository.

1.1.1 (2023-06-30)
------------------

This release addresses a regression where asset files with multiple
fingerprints (either from multiple keys or subkeys) were no longer accepted.

1.1.0 (2023-05-30)
------------------

- Add support for configuring Apt repositories in non-default roots

1.0.0 (2023-05-24)
------------------

This release marks the stability of craft-archives' API. Most of the work
has been on internal refactorings and tooling.

- Add support for Ubuntu Cloud Archive repositories
- Unify package repositories representations

.. _deb822: https://manpages.debian.org/unstable/apt/sources.list.5.en.html
.. _Releases page: https://github.com/canonical/craft-archives/releases
