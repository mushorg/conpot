CentOS installation 7.3
======================================

Validated to work on CentOS version 7.3-1611 & Conpot 0.5.1 (may also work on other CentOS versions)

1. Login via ssh with an account with sufficient system privileges (e.g root)
-----------------------------------------------------------------------------
2. Upgrade the system
---------------------
::

$ sudo yum -y update


3. Install needed packages and libs
-----------------------------------
::

$ sudo yum -y install libxslt-devel libxml2-devel python-pip python
$ sudo yum -y install mariadb-server mysql-connector-python.noarch mariadb-devel
$ sudo yum -y install git python-lxml.x86_64 python-devel
$ sudo yum -y groupinstall "Development tools"
$ wget https://bootstrap.pypa.io/get-pip.py && sudo python ./get-pip.py

Upgrade `lxml`
::

$ sudo pip install -U lxml

4. Start mysql server
------------------------
::

$ sudo chkconfig mariadb on
$ sudo service mariadb start

Sugestions to mysql secure installation are to change the root password and accect to removing anonymous users, test database and disallow root login.
::

$ sudo mysql_secure_installation

5. CONPOT installation
----------------------
::

$ git clone https://github.com/mushorg/conpot
$ cd conpot/
$ sudo python setup.py install

6. Open ports in firewalld : 80 , 102, 161 and 502
---------------------------------------------------
::

$ firewall-cmd --permanent --add-port=80/tcp
$ firewall-cmd --permanent --add-port=102/tcp
$ firewall-cmd --permanent --add-port=161/tcp
$ firewall-cmd --permanent --add-port=502/tcp
$ firewall-cmd --reload


7. Start the Conpot honeypot
-----------------------------

::

$ conpot --template default

8. Check if it's running and you can access it from remote (in browser)
-----------------------------------------------------------------------

::

$ lynx http://YOUR_IP/
