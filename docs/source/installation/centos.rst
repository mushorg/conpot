Centos instalation 7.1
======================================

Validated to work on Centos version 7.1-1503 & Conpot v4 (but may likely work on other centos versions/ rpm disto.

1. login via ssh with a account with sufficient system privileges (e.g root)
----------------------------------------------------------------------------
2. Upgrade the system
---------------------
::

$ sudo yum -y update

3. Install epel repository
--------------------------

::

$ sudo rpm -iUvh http://dl.fedoraproject.org/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm

4. Install needed packages and libs
-----------------------------------
::

$ sudo yum -y install libxslt-devel libxml2-devel python-pip python-2.7.5-16.el7.x86_64
$ sudo yum -y install mariadb-server mysql-connector-python.noarch mariadb-devel-5.5.41-2.el7_0.x86_64
$ sudo yum -y install git python-lxml.x86_64 python-devel
$ sudo yum -y groupinstall "Development tools"
$ sudo easy_install -U setuptools

Below command force lxml to be version 3.3.5
::

$ sudo easy_install lxml==3.3.5

5. Starting mysql server
------------------------
::

$ sudo chkconfig mariadb on
$ sudo service mariadb start

Sugestions to mysql secure instalation are to change the root password and accect to removing anonymous users,test database and Disallow root login.
::

$ sudo mysql_secure_installation

6. CONPOT installation
----------------------
::

$ cd /usr/local/src
$ sudo git clone https://github.com/mushorg/conpot
$ cd conpot/
$ sudo python setup.py install

7. Open ports in firewalld : 80 , 102, 161 and 502
---------------------------------------------------
::

$ firewall-cmd --permanent --add-port=80/tcp
$ firewall-cmd --permanent --add-port=102/tcp
$ firewall-cmd --permanent --add-port=161/tcp
$ firewall-cmd --permanent --add-port=502/tcp
$ firewall-cmd --reload


8. temp fix as conpot currently requires the "nogroup" for the moment - raised in issue #267
--------------------------------------------------------------------------------------------
::

$ sudo groupadd nogroup

9. Start the Conpot honeypot
-----------------------------

::

$ conpot --template default

10. check if its running and you can access it from remote (in browser)
-----------------------------------------------------------------------

::

$ lynx http://YOUR_IP/
