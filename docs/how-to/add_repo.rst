Add a Package Repository
************************

It's possible to add your own apt repositories as sources for build-packages and
stage-packages, including those hosted on a PPA, the Personal Package Archive,
which serves personally hosted non-standard packages, and those hosted on the
UCA, the Ubuntu Cloud Archive.

Third-party repositories can be added to the project file of a Craft Application
(like Snapcraft, Rockcraft, or Charmcraft) by using the top-level
``package-repositories`` keyword with either a PPA-type repository, an UCA-type
repository or a deb-type repository:

PPA-type repository:

.. code-block:: yaml

   package-repositories:
    - type: apt
      ppa: snappy-dev/snapcraft-daily

UCA-type repository:

.. code-block:: yaml

   package-repositories:
    - type: apt
      cloud: antelope
      pocket: updates

deb-type repository:

.. code-block:: yaml

   package-repositories:
     - type: apt
       components: [main]
       suites: [xenial]
       key-id: 78E1918602959B9C59103100F1831DDAFC42E99D
       url: http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu

As shown above, PPA-type repositories, UCA-type repositories and traditional
deb-type each require a different set of properties.

* :ref:`PPA-type properties <ppa-properties>`
* :ref:`UCA-type properties <uca-properties>`
* :ref:`deb-type properties <deb-properties>`

Once configured, packages provided by these repositories will become available
via ``stage-packages`` and ``build-packages``.
