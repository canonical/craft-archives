.. py:currentmodule:: craft_archives.repo.installer

Modify the default package repositories
=======================================

Read the existing repositories
------------------------------

Reading the default repositories from a given root as is simple as calling
:py:func:`get_default_repos`:

.. code-block:: python

    from craft_archives.repo import installer
    repos = installer.get_default_repos(root=my_root)

If ``root`` is not specified, the current running system will be modified.

Create a new list of repositories
---------------------------------

A ``PackageRepository`` object is frozen, so the new repositories must be generated as
model copies from the old repositories. For example, for an end-of-life Ubuntu release,
the URLs can be changed as follows:

.. code-block:: python

    new_repos = [
        repo.model_copy(update={"url": "http://old-releases.ubuntu.com/ubuntu"}),
        for repo in repos
    ]

Write default repositories
--------------------------

Once you have a new list of repositories to set as the defaults, they can be written
to the appropriate sources file using :py:func:`set_default_repos`:

.. code-block:: python

    installer.set_default_repos(new_repos, root=my_root)

Whether these are written to ``/etc/apt/sources.list`` or
``/etc/apt/sources.list.d/ubuntu.sources`` depends on the existence of the latter file.
