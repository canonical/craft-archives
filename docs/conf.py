import datetime
import os
import textwrap

# Configuration for the Sphinx documentation builder.
# All configuration specific to your project should be done in this file.

# Project name
project = "Craft Archives"

# Author name; used in the default copyright statement in the page footer
author = "Canonical Ltd."

# Format the product name and version for the TOC and HTML title
# release = <starcraft>.__version__
# if ".post" in release:
#     release = "dev"
# else:
#     major, minor, *_ = release.split(".")
#     release = f"{major}.{minor}"

# The year in the copyright statement
copyright = f"2023-{datetime.date.today().year}"

# Sidebar documentation title
# To disable the title, set it to an empty string.
html_title = project + " documentation"

# Documentation website URL
ogp_site_url = "https://canonical-craft-archives.readthedocs-hosted.com/"

# Preview name of the documentation website
ogp_site_name = project

# Preview image URL
ogp_image = "https://assets.ubuntu.com/v1/cc828679-docs_illustration.svg"

# Dictionary of values to pass into the Sphinx context for all pages:
# https://www.sphinx-doc.org/en/master/usage/configuration.html#confval-html_context
html_context = {
    # Product page URL; can be different from product docs URL
    "product_page": "github.com/canonical/craft-archives",
    # Your Mattermost channel URL
    "mattermost": "",
    # Your Matrix channel URL
    "matrix": "",
    # Your documentation GitHub repository URL.
    "github_url": "https://github.com/canonical/craft-archives",
    # Docs branch in the repo; used in links for viewing the source files
    "repo_default_branch": "main",
    # Docs location in the repo; used in links for viewing the source files
    "repo_folder": "/docs/",
    # List contributors on individual pages
    "display_contributors": False,
    # Required for feedback button
    "github_issues": "enabled",
    # Passes the top-level 'author' value to the theme
    "author": author,
    # Documentation license information
    "license": {
        "name": "LGPL-3.0-or-later",
        "url": "https://github.com/canonical/craft-archives/blob/main/LICENSE",
    },
}

# Edit button on pages
html_theme_options = {
  "source_edit_link": "https://github.com/canonical/craft-archives",
}

# Sitemap configuration
html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "/")

# sphinx-sitemap uses html_baseurl to generate the full URL for each page:
sitemap_url_scheme = "{link}"

# Pages excluded from the sitemap:
sitemap_excludes = [
    "404/",
    "genindex/",
    "search/",
]

# Redirects
rediraffe_redirects = "redirects.txt"
rediraffe_dir_only = True

# sphinx-llm configuration
llms_txt_description = textwrap.dedent(
    """\
    This is the documentation for Craft Archives, a Python package to manage
    interaction with software package repositories on behalf of tools using the
    Craft Parts library.
    """
)

# The base URL for references built by sphinx-markdown-builder.
if os.environ.get("READTHEDOCS"):
    markdown_http_base = html_baseurl

# Link checker exceptions
linkcheck_ignore = [
    r"^https://github.com",
    r"^https://www.gnu.org/",
    r"^https://crates.io/",
    r"^https://([\w-]*\.)?npmjs.org",
    r"^https://rsync.samba.org",
    r"^https://ubuntu.com",
    r"^https://matrix.to/#",
    r"^https://gitlab.gnome.org",
]

# Give linkcheck multiple tries on failure
linkcheck_retries = 20

# Report timeouts as 'timeout' instead of 'broken'
linkcheck_report_timeouts_as_broken = False


# Configuration extras
extensions = [
    "canonical_sphinx",
    "notfound.extension",
    "sphinx_design",
    "sphinx_rerediraffe",
    "sphinxext.opengraph",
    "sphinx_llm.txt",
    "sphinx_related_links",
    "sphinx.ext.intersphinx",
    "sphinx_sitemap",
    # Custom Craft extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.viewcode",
]

# Excludes files or directories from processing
exclude_patterns = [
    "README.md",  # Docs README
    "reuse",
    "tutorials",  # No tutorials yet, so just hide the category
]

# Specifies a reST snippet to be prepended to each .rst file
rst_prolog = """
.. role:: center
   :class: align-center
.. role:: h2
    :class: hclass2
.. role:: woke-ignore
    :class: woke-ignore
.. role:: vale-ignore
    :class: vale-ignore
"""

# Add configuration for intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "starflow": ("https://documentation.ubuntu.com/starflow/latest", None),
}

# Block Intersphinx from looking up external sources with internal references.
intersphinx_disabled_reftypes = ["std:*"]


##############################
# Custom Craft configuration #
##############################

# Type hints configuration
set_type_checking_flag = True
typehints_fully_qualified = False
always_document_param_types = True

# Github config
github_username = "canonical"
github_repository = "craft-archives"
