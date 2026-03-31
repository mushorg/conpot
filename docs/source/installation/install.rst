Installation on a host
========================

This guide covers running Conpot directly on your machine (outside Docker). Conpot requires **Python 3.12 or newer** (see ``requires-python`` in ``pyproject.toml``).

System packages (Debian / Ubuntu)
---------------------------------

Install build dependencies for lxml, gevent, and cryptography:

::

    $ sudo apt-get install gcc libxslt1-dev python3-dev libevent-dev libffi-dev libssl-dev

Other distributions need the equivalent development headers and a compiler.

Install uv (recommended for development)
------------------------------------------

For working from a git checkout, `uv <https://docs.astral.sh/uv/>`_ manages dependencies and a local virtual environment. Follow the `official installation instructions <https://docs.astral.sh/uv/getting-started/installation/>`_ for your platform.

Install from source with uv
^^^^^^^^^^^^^^^^^^^^^^^^^^^

::

    $ git clone https://github.com/mushorg/conpot.git
    $ cd conpot
    $ uv sync --group dev

This creates ``.venv`` in the project directory, installs Conpot in editable form, and adds development tools (for example pytest).

Run Conpot:

::

    $ uv run conpot --template default -f

Run tests:

::

    $ uv run pytest

The project ``Makefile`` targets ``install``, ``test``, and ``format`` call uv the same way.

Updating dependencies (maintainers and contributors): edit ``pyproject.toml``, run ``uv lock``, and commit the updated ``uv.lock`` so CI stays reproducible.

Install the release from PyPI with pip
--------------------------------------

If you only want a released version and already use ``pip`` with a virtual environment, you can install Conpot from PyPI as before:

::

    $ python3 -m venv conpot-env
    $ source conpot-env/bin/activate
    $ pip install conpot

Install from source with pip (without uv)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you prefer not to install uv, you can build from a git clone using a PEP 517–compatible installer:

::

    $ python3 -m venv conpot-env
    $ source conpot-env/bin/activate
    $ pip install ./path/to/conpot

Optional test dependencies (pytest, pytest-cov) are listed in the ``dev`` dependency group in ``pyproject.toml``; with uv, use ``uv sync --group dev``. With pip alone, install those packages manually if you need them.

Classic virtualenv workflow
---------------------------

You can still combine ``virtualenv`` (or ``python -m venv``) with ``pip install conpot`` or ``pip install .`` from a source tree; uv is optional but recommended for contributors because it respects the lockfile.
