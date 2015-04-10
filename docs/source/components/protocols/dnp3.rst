====
DNP3
====

Installation
------------

1) Fetch DNP3 2.0.x branch from https://github.com/automatak/dnp3
git clone https://github.com/automatak/dnp3.git

2) Install the prerequisites: 
http://dnp3.github.io/doc/2.0.x/building/prerequisites.html

Get ASIO from here: http://think-async.com/ and install it (./configure/make/make install)

3) Before building dnp3 change the following file: 
dnp3/cpp/examples/master/DemoMain.cpp

Change the port on line 54 from 20000 to 20001, so that it becomes:
	auto pChannel = manager.AddTCPClient("tcpclient", FILTERS, TimeDuration::Seconds(2), TimeDuration::Seconds(5), "127.0.0.1", "0.0.0.0", 20001);

4) Follow the build instructions: http://dnp3.github.io/doc/2.0.x/building/building-linux.html
5) Run conpot with the proxy i.e. conpot -t dnp3_proxy.xml
6) Run ``outstationdemo`` and ``masterdemo``. 

Note: If you build before the modification (step 3) proceed with the following:

1) Run: find /your/dir -type f -exec touch {} +
2) Run: make clean
3) Continue with steps 4 to 6 above.

If you get a warning concerning a clock skew while running these additional steps, you may ignore it since you're running a clean build.
