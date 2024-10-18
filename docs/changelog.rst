*********
Changelog
*********

See the `Releases page`_ on Github for a complete list of commits that are
included in each version.

X.Y.Z (YYYY-MMM-DD)
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

.. _Releases page: https://github.com/canonical/craft-archives/releases
