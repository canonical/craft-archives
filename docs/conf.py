import datetime
import os
import textwrap

# Configuration for the Sphinx documentation builder.
# All configuration specific to your project should be done in this file.
#
# A complete list of built-in Sphinx configuration values:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
#
# The Sphinx Stack uses the Canonical Sphinx theme to keep all documentation
# consistent and on brand:
# https://github.com/canonical/canonical-sphinx


#######################
# Project information #
#######################

project = "Craft Archives"
author = "Canonical Group Ltd"
copyright = f"2023-{datetime.date.today().year}, {author}"

# Sidebar documentation title
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
    "product_page": "github.com/canonical/craft-archives",
    "discourse": "",
    "mattermost": "",
    "matrix": "",
    "github_url": "https://github.com/canonical/craft-archives",
    "repo_default_branch": "main",
    "repo_folder": "/docs/",
    "display_contributors": False,
    "github_issues": "enabled",
    "author": author,
    "license": {
        "name": "LGPL-3.0",
        "url": "https://github.com/canonical/craft-archives/blob/main/LICENSE",
    },
}

html_theme_options = {
    "source_edit_link": "https://github.com/canonical/craft-archives",
}


#########################
# Sitemap configuration #
#########################

html_baseurl = os.environ.get("READTHEDOCS_CANONICAL_URL", "/")
sitemap_url_scheme = "{link}"

sitemap_excludes = [
    "404/",
    "genindex/",
    "search/",
]


################################
# Template and asset locations #
################################

templates_path = ["_templates"]


#############
# Redirects #
#############

rediraffe_redirects = "redirects.txt"
rediraffe_dir_only = True


############################
# sphinx-llm configuration #
############################

llms_txt_description = textwrap.dedent(
    """\
    This is the documentation for Craft Archives, a Python package to manage
    interaction with software package repositories on behalf of tools using the
    Craft Parts library.
    """
)

if os.environ.get("READTHEDOCS"):
    markdown_http_base = html_baseurl


###########################
# Link checker exceptions #
###########################

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

linkcheck_retries = 20
linkcheck_report_timeouts_as_broken = False


########################
# Configuration extras #
########################

extensions = [
    "canonical_sphinx",
    "notfound.extension",
    "sphinx_design",
    "sphinx_rerediraffe",
    "sphinxext.opengraph",
    "sphinx_llm.txt",
    "sphinx_related_links",
    "sphinx_roles",
    "sphinx_terminal",
    "sphinx.ext.intersphinx",
    "sphinx_sitemap",
    "sphinx.ext.viewcode",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx-pydantic",
    "sphinx_toolbox.more_autodoc.augment_defaults",
    "sphinx_toolbox.more_autodoc.typehints",
    "sphinx.ext.autodoc",  # Must be loaded after more_autodoc
]

exclude_patterns = [
    "README.md",
    "reuse",
    "explanation/documentation.rst",
]

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

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "starflow": ("https://documentation.ubuntu.com/starflow/latest", None),
}

intersphinx_disabled_reftypes = ["std:*"]


##############################
# Custom Craft configuration #
##############################

set_type_checking_flag = True
typehints_fully_qualified = False
always_document_param_types = True

github_username = "canonical"
github_repository = "craft-archives"
