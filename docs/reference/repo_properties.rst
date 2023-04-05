
Package Repository Properties
*****************************

.. _ppa-properties:

PPA properties
==============

The following properties are supported for PPA-type repositories:

- type
   - Type: enum[string]
   - Description: Specifies type of package-repository, must currently be
     ``apt``
   - Examples: ``type: apt``
- ppa
   - Type: string
   - Description: PPA shortcut string
   - Format: <ppa-owner>/<ppa-name>
   - Examples:
      - ``ppa: snappy-devs/snapcraft-daily``
      - ``ppa: mozillateam/firefox-next``

.. _uca-properties:

The following properties are supported for UCA-type repositories:

- type
   - Type: enum[string]
   - Description: Specifies type of package-repository, must currently be
     ``apt``
   - Examples: ``type: apt``
- cloud
   - Type: string
   - Description: UCA release name
   - Format: <uca-release>
   - Examples:
      - ``cloud: antelope``
      - ``cloud: zed``
- pocket
   - Type: enum[string]
   - Description: Pocket to get packages from, must be either ``updates``
     or ``proposed``
   - Default: If unspecified, pocket is assumed to be ``updates``
   - Examples:
      - ``pocket: updates``
      - ``pocket: proposed``

.. _deb-properties:

Deb properties
==============

The following properties are supported for Deb-type repositories:

- architectures
   - Type: list[string]
   - Description: Architectures to enable, or restrict to, for this repository
   - Default: If unspecified, architectures is assumed to match the host's
     architecture only (even for multi-arch builds)
   - Examples:
      - ``architectures: [i386]``
      - ``architectures: [i386, amd64]``
- components
   - Type: list[string]
   - Description: Apt repository components to enable: e.g.
     ``main``, ``multiverse``, ``unstable``
   - Examples:
       - ``components: [main]``
       - ``components: [main, multiverse, universe, restricted]``
- formats
   - Type: list[string]
   - Description: List of deb types to enable
   - Default: If unspecified, format is assumed to be ``deb``, i.e. ``[deb]``
   - Examples:
       - ``formats: [deb]``
       - ``formats: [deb, deb-src]``
- key-id
   - Type: string
   - Description: 40 character GPG key identifier ("long-form thumbprint" or
     "fingerprint"). The Craft Application will first look for the corresponding
     key at: ``<project>/snap/keys/<key-id[-8:]>.asc``. If the key is not found,
     the key will be fetched from the ``key-server``. To determine a key-id from
     a given key file with gpg, type the following:
     ``gpg --import-options show-only --import <file>``
   - Format: alphanumeric, dash ``-`` , and underscores ``_`` permitted.
   - Examples:
       - ``key-id: 590CA3D8E4826565BE3200526A634116E00F4C82``

         The Application will look for a corresponding key at
         ``<project>/snap/keys/E00F4C82.asc``
- key-server
   - Type: string
   - Description: Key server to fetch key ``<key-id>`` from
   - Default: If unspecified, The Craft Application will attempt to fetch a
     specified key from keyserver.ubuntu.com
   - Format: Key server URL supported by ``gpg --keyserver``
   - Examples:
       - ``key-server: keyserver.ubuntu.com``
       - ``key-server: hkp://keyserver.ubuntu.com:80``
- path
   - Type: string
   - Description: Absolute path to repository (from ``url``). Cannot be used
     with ``suites`` and ``components``
   - Format: Path starting with ``/``
   - Examples:
       - ``path: /``
       - ``path: /my-repo``
- suites
   - Type: string
   - Description: Repository suites to enable
   - Notes: If your deb URL does not look like it has a suite defined, it is
     likely that the repository uses an absolute URL. Consider using ``path``
   - Examples:
       - ``suites: [xenial]``
       - ``suites: [xenial, xenial-updates]``
- type
   - Type: enum[string]
   - Description: Specifies type of package-repository
   - Notes: Must be ``apt``
   - Examples:
       - ``type: apt``
- url
   - Type: string
   - Description: Repository URL.
   - Examples:
       - ``url: http://archive.canonical.com/ubuntu``
       - ``url: https://apt-repo.com/stuff``

Examples
========

PPA repository using "ppa" property
-----------------------------------

.. code-block:: yaml

   package-repositories:
     - type: apt
       ppa: snappy-dev/snapcraft-daily

UCA repository using "cloud" property
-------------------------------------

.. code-block:: yaml
   package-repositories:
     - type: apt
       cloud: antelope

UCA repository using "pocket" property
--------------------------------------

.. code-block:: yaml
   package-repositories:
     - type: apt
       cloud: antelope
       pocket: updates

Typical apt repository with components and suites
-------------------------------------------------

.. code-block:: yaml

   package-repositories:
     - type: apt
       components: [main]
       suites: [xenial]
       key-id: 78E1918602959B9C59103100F1831DDAFC42E99D
       url: http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu

Apt repository enabling deb sources
-----------------------------------

.. code-block:: yaml

   package-repositories:
     - type: apt
       formats: [deb, deb-src]
       components: [main]
       suites: [xenial]
       key-id: 78E1918602959B9C59103100F1831DDAFC42E99D
       url: http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu

Absolute path repository with implied root path "/"
---------------------------------------------------

.. code-block:: yaml

   package-repositories:
     - type: apt
       key-id: AE09FE4BBD223A84B2CCFCE3F60F4B3D7FA2AF80
       url: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64

Absolute path repository with explicit path and formats
-------------------------------------------------------

.. code-block:: yaml

   package-repositories:
     - type: apt
       formats: [deb]
       path: /
       key-id: AE09FE4BBD223A84B2CCFCE3F60F4B3D7FA2AF80
       url: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu1804/x86_64`
