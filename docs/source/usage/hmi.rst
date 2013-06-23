==============================
Human Machine Interfaces (HMI)
==============================

The default HMI
---------------

Yes, Conpot comes with a default 'HMI'. If you run Conpot with the default configuration and no additional
parameters, it will serve the default page on port 80. The default page is just a plain text file which gets
the 'sysDescr' from the SNMP server. For example:
::

    System is running: Siemens, SIMATIC, S7-200


Creating your own HMI
---------------------

Manual HMI creation
~~~~~~~~~~~~~~~~~~~

The probably most painless way to customize your HMI is by modifying the default page. If you don't want to
mess with the default files ('recommended') you can create a directory holding a custom index.html. In order
to use the custom HTML page you have to start Conpot with the following parameters:
::

    # conpot -w <your new directory> -r <root page>

For example:
::

    # conpot -w www/ -r index.html

We use jinja2 as template engine. Please refer to the default HMI template (``conpot/www/index.html``) for a
minimal example.


Crawling an existing HMI
~~~~~~~~~~~~~~~~~~~~~~~~

We recommend to use the crawler only against your own applications! Usage on your own risk.
Improper usage will most likely damage the system.

In case you have access to a HTML HMI you can use to crawler to create a copy that's compatible with Conpot's
HTTP server.
::

    # hmi_crawler --target http://<taget_domain> --www <target_dir>
    # hmi_crawler -t http://localhost:80 -w dump/

This will dump a copy of the target web content into ``www``. If you run Conpot now:
::

    # conpot -w dump/ -r index.html

It will server the dumped web page as HMI.