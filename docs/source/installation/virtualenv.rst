Virtualenv
==========

A generic way to keep Python installations separate is using `virtualenv <https://pypi.python.org/pypi/virtualenv>`_. This way you can run conpot on your machine without littering your machine. This guides assumes you have Python 2 installed and running on your computer.


Installation
------------

Install dependencies:
::

    apt-get install git libsmi2ldbl smistrip libxslt1-dev python-dev libevent-dev

Create the virtualenv
::

    virtualenv --python=python2 venv

Activate the environment
::

    source venv/bin/activate

Upgrade any basic tools in the environment
::

    pip install --upgrade pip
    pip install --upgrade setuptools

Install the table version of Conpot from PyPI:
::

    pip install conpot


References
----------
* `The Hitchhickers Guide to Python: Virtual Environments <http://docs.python-guide.org/en/latest/dev/virtualenvs/>`_
