Frequently Asked Questions
==========================

Sharing Data
------------

**With whom do we share?**

Everyone who is interested and potentially shares data, results or helps improving the tool.

**What's the data volume?**

Conpot has build-in support for HPFeeds, a generic data sharing
protocol we are using in the Honeynet Project. This means that
potentially we are going to get all the data from every sensor with
HPFeeds enabled.

Right now there is only a very small number of deployed sensors.
HPFeeds is not enabled by default and probably nobody is using a HMI
to attract adversaries yet. So if you are lucky you will see an event
every other day. We know that with a HMI the traffic will be significantly
higher as your sensor will be found using search engines.

**What is the data format?**

Raw data in JSON formatting.

**How do I get the data?**

There is a Python `client <https://github.com/mushorg/conpot/blob/master/bin/conpot_hpf_client>`_
which uses the HPFeeds library. About 40 lines of code. From there it's
quite easy to write the data to a database.
You can find an explanation on how it works
`here <http://heipei.github.io/2013/05/11/Using-hpfriends-the-social-data-sharing-platform/>`_.

**What do I have to do?**

If you want to have access to the Conpot data, you have to create a
`HPFriends <http://hpfriends.honeycloud.net/>`_ account. As soon as you accept
the share, you can create an authkey. You can modify the client with
the auth keys credentials. The client should be self explaining. You
can extend the client so it fits your needs (e.g. logging to a database).

**How do I test this?**

As soon as you have Conpot set-up it should be easy to create some traffic for testing.
