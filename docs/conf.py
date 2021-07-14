# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = "range-streams"
copyright = "2021, Louis Maddox"
author = "Louis Maddox"

# The full version, including alpha/beta/rc tags
release = ""


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.doctest",
    # "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "myst_nb",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "python-ranges": ("https://python-ranges.readthedocs.io/en/latest/", None),
}

suppress_warnings = [
    #   'ref.citation',  # Many duplicated citations in numpy/scipy docstrings.
    #   'ref.footnote',  # Many unreferenced footnotes in numpy/scipy docstrings
    "files.*",
    "rest.*",
    "app.add_node",
    "app.add_directive",
    "app.add_role",
    "app.add_generic_role",
    "app.add_source_parser",
    "download.not_readable",
    "image.not_readable",
    "ref.term",
    "ref.ref",
    "ref.numref",
    "ref.keyword",
    "ref.option",
    "ref.citation",
    "ref.footnote",
    "ref.doc",
    "ref.python",
    "misc.highlighting_failure",
    "toc.circular",
    "toc.secnum",
    "epub.unknown_project_files",
    "epub.duplicated_toc_entry",
    "autosectionlabel.*",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# Note: if both md and ipynb copies of each notebook exist (as they do when
# using jupytext) then listing ipynb before md ensures Myst will convert the
# notebook. Notebooks which are not executed have outputs as ipynb but not md,
# so the ipynb must be converted
source_suffix = [".rst", ".ipynb", ".md"]

main_doc = "index"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

autosummary_generate = True
# https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
napolean_use_rtype = False

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

# -- Options for myst ----------------------------------------------
jupyter_execute_notebooks = "force"
execution_allow_errors = False
execution_fail_on_error = (
    True  # Requires https://github.com/executablebooks/MyST-NB/pull/296
)
nb_render_priority = {
    "html": (
        "application/vnd.jupyter.widget-view+json",
        "application/javascript",
        "text/html",
        "image/svg+xml",
        "image/png",
        "image/jpeg",
        "text/markdown",
        "text/latex",
        "text/plain",
    )
}
nb_render_priority["doctest"] = nb_render_priority["html"]

# Notebook cell execution timeout; defaults to 30.
execution_timeout = 100

# List of patterns, relative to source directory, that match notebook
# files that will not be executed.
execution_excludepatterns = []
