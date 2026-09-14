Welcome to Conpot's documentation!
==================================

Conpot is an ICS honeypot with the goal to collect intelligence about the motives and
methods of adversaries targeting industrial control systems.

Installation
------------

Basic instructions on how to install Conpot:

* **Docker** — fastest way to try Conpot without a local Python stack; see :doc:`installation/quick_install`.
* **Host install** — run Conpot on your machine: install the release from PyPI with ``pip``, or clone the repository and use **uv** (recommended for development); see :doc:`installation/install`.

.. toctree::
   :maxdepth: 2

   installation/quick_install
   installation/install
   installation/configuration

Conpot concepts
---------------

.. toctree::
   :glob:

   concepts/*

Development guidelines
-----------------------

.. toctree::
   :maxdepth: 2

   development/guidelines

Usage and Frequently asked questions
------------------------------------

.. toctree::
   :maxdepth: 2

   usage/index
   faq

API reference
-------------

.. toctree::
   :maxdepth: 2

   api/index