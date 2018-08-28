Virtualenv
==========

A generic way to keep Python installations separate is using `virtualenv <https://pypi.python.org/pypi/virtualenv>`_. This way you can run conpot on your machine without littering your machine. This guides assumes you have Python 3.5 installed and running on your computer.


Installation
------------

Install dependencies:
::

    apt-get install git libsmi2ldbl smistrip libxslt1-dev python3.5-dev libevent-dev default-libmysqlclient-dev

Create the virtualenv
::

    virtualenv --python=python3.5 conpot

Activate the environment
::

    source conpot/bin/activate

Upgrade any basic tools in the environment and deps
::

    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install cffi

Install the table version of Conpot from PyPI:
::

    pip install conpot
