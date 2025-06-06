.. _explanation-cryptographic-technology:

Cryptographic technology in Craft Archives
==========================================

.. This includes: Encryption/decryption, hashing, and digital signatures.

Craft Archives uses cryptographic processes to parse public keys and optionally
retrieve them from remote servers. It does not directly implement its own cryptography,
but depends on `GNU Privacy Guard (GPG)`_ to do so.

A declaration of a package repository includes a mandatory ``key-id`` field that
specifies the fingerprint of the repository's public key. This public key can either be
stored locally or automatically fetched by Craft Archives.

If the key file is located as part of the project's assets, Craft Archives uses the
GPG as provided by the official Ubuntu archives to ensure that the file
matches the declared fingerprint. If the key file is not present locally, Craft Archives
uses GPG in conjunction with `dirmngr`_ (also from the Ubuntu archives) to fetch the key
from the OpenPGP keyserver ``keyserver.ubuntu.com``.

In either scenario, Craft Archives then creates an APT data source for the package
repository referencing the identified key. It does not validate that the remote
repository is in fact signed by the key, as APT itself does it as part of its normal
operation.

.. _GNU Privacy Guard (GPG): https://gnupg.org/
.. _dirmngr: https://manpages.ubuntu.com/manpages/noble/man8/dirmngr.8.html
