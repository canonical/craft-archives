# Copyright 2023-2024 Canonical Ltd.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License version 3 as published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import datetime

project = "Craft Archives"
author = "Canonical Group Ltd"

copyright = "2023-%s, %s" % (datetime.date.today().year, author)

# region Configuration for canonical-sphinx
ogp_site_url = "https://canonical-craft-archives.readthedocs-hosted.com/"
ogp_site_name = project

html_context = {
    "product_page": "github.com/canonical/craft-archives",
    "github_url": "https://github.com/canonical/craft-archives",
}

# Target repository for the edit button on pages
html_theme_options = {
    "source_edit_link": "https://github.com/canonical/craft-archives",
}

extensions = [
    "canonical_sphinx",
]
# endregion

# region General configuration
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions.extend(
    [
        "sphinx.ext.intersphinx",
        "sphinx.ext.viewcode",
        "sphinx.ext.coverage",
        "sphinx.ext.doctest",
        "sphinx-pydantic",
        "sphinx_toolbox",
        "sphinx_toolbox.more_autodoc",
        "sphinx.ext.autodoc",  # Must be loaded after more_autodoc
        "sphinxext.rediraffe",
    ]
)

# endregion

# region Options for extensions
# Intersphinx extension
# https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#configuration

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Type hints configuration
set_type_checking_flag = True
typehints_fully_qualified = False
always_document_param_types = True

# Github config
github_username = "canonical"
github_repository = "craft-archives"

# endregion

# Client-side page redirects.
rediraffe_redirects = "redirects.txt"
