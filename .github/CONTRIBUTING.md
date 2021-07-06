# How To Contribute

Firstly thank you for your interest in contributing to _range-streams_!

If anything here is unclear, don't be afraid to open an issue or share your half-finished PR.

## Workflow

- No contribution too small!
- Try to limit each pull request to one change only
- _Always_ add tests and docstrings for your code
- Make sure changes pass on CI

## Code

- Document code in docstrings
- Obey the Black code style
- Run the full tox suite before committing

## Tests

- Write your asserts as `expected == actual` to line them up nicely
  and leave an empty line before them
- To run the test suite, all you need is a recent `tox`.
  It will ensure the test suite runs with all dependencies against all Python versions
  just as it will on CI.
  - If you lack some Python versions, you can make it a non-failure using
    `tox --skip-missing-interpreters`
- Write [good test docstrings](https://jml.io/test-docstrings/)

## Documentation

- Use [semantic newlines](https://rhodesmill.org/brandon/2012/one-sentence-per-line/)
  in [reStructuredText](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
  files (files ending in `.rst`):

  ```rst
  This is a sentence.
  This is another sentence.
  ```

- If you start a new section, add two blank lines and one blank line after the header except if two
  headers follow immediately after each other:

  ```rst
  Last line of previous section.

  Header of New Top Section
  -------------------------

  Header of New Section
  ^^^^^^^^^^^^^^^^^^^^^

  First line of new section.
  ```

## Local Development Environment

You can (and should) run the test suite using [tox](https://tox.readthedocs.io/).
However, you'll probably want a more traditional environment as well.
We highly recommend to develop using the latest Python 3 release because you're more likely
to catch certain bugs earlier.

First create a virtual environment (I use the [miniconda](https://docs.conda.io/en/latest/miniconda.html)
version of [conda](https://anaconda.org/) and have attached an
[example conda env setup](docs/CONDA_SETUP.md)). This works with tox thanks to the
very cool [tox-conda](https://github.com/tox-dev/tox-conda) plugin.

Next get the latest checkout of the _range-streams_ repository:

```sh
git clone git@github.com:lmmx/range-streams.git
```

Change into the newly created directory and **after activating your virtual environment**
install an editable version of range-streams along with its tests requirements:

```sh
cd range-streams
pip install -e .[tests]
```

At this point

```sh
python -m pytest
```

should run and pass.

On the TODO list: set up pre-commit...

> To avoid committing code that violates the style guide, please install
> [pre-commit hooks](https://pre-commit.com/) (which should have installed into the virtual
> environment automatically when you ran `pip install -e .[tests]` earlier).

```sh
pre-commit install
```

> You can also run them anytime (as tox does) using:

```sh
pre-commit run --all-files
```

---

If anything here is unclear, feel free to ask for help.

Thank you for considering contribution to _range-streams_!
