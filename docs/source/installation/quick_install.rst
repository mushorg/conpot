Quick Installation using Docker
===============================

|Docker Build Status| |Docket Image Size| |Docker Pulls|

Via a pre-built image
^^^^^^^^^^^^^^^^^^^^^

1. Install `Docker`_
2. Run ``docker pull honeynet/conpot``
3. Run
   ``docker run -it -p 80:8800 -p 102:10201 -p 502:5020 -p 161:16100/udp --network=bridge honeynet/conpot``

Navigate to ``http://MY_IP_ADDRESS`` to confirm the setup.

Build docker image from source
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Install `Docker`_
2. Clone this repo with ``git clone https://github.com/mushorg/conpot.git``
3. Run ``sudo make build-docker``
4. Run ``sudo make run-docker``

Navigate to ``http://MY_IP_ADDRESS`` to confirm the setup.

Build from source and run with docker-compose
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Install `docker-compose`_
2. Clone this repo with
   ``git clone https://github.com/mushorg/conpot.git`` and
   ``cd conpot``
3. Build the image with ``docker-compose build``
4. Test if everything is running correctly with ``docker-compose up``
5. Permanently run as a daemon with ``docker-compose up -d``

Sample output
-------------

::

   # conpot --template default
                        _
    ___ ___ ___ ___ ___| |_
   |  _| . |   | . | . |  _|
   |___|___|_|_|  _|___|_|
               |_|

   Version 0.6.0
   MushMush Foundation

   2018-08-09 19:13:15,085 Initializing Virtual File System at ConpotTempFS/__conpot__ootc_k3j. Source specified : tar://conpot-0.6.0-py3.6/conpot/data.tar
   2018-08-09 19:13:15,100 Please wait while the system copies all specified files
   2018-08-09 19:13:15,172 Fetched x.x.x.x as external ip.
   201

.. _Docker: https://docs.docker.com/engine/installation/
.. _docker-compose: https://docs.docker.com/compose/install/

.. |Docker Build Status| image:: https://img.shields.io/docker/build/honeynet/conpot.svg
   :target: https://hub.docker.com/r/honeynet/conpot
.. |Docket Image Size| image:: https://img.shields.io/microbadger/image-size/honeynet/conpot.svg
   :target: https://hub.docker.com/r/honeynet/conpot
.. |Docker Pulls| image:: https://img.shields.io/docker/pulls/honeynet/conpot.svg
   :target: https://hub.docker.com/r/honeynet/conpot
