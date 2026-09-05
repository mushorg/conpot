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

Subscribe to the shared HPFeeds channels with any HPFeeds client
(for example the `hpfeeds <https://pypi.org/project/hpfeeds3/>`_ Python
library) and write the JSON payloads to a database or other sink.
You can find an explanation of HPFriends
`here <http://heipei.github.io/2013/05/11/Using-hpfriends-the-social-data-sharing-platform/>`_.

**What do I have to do?**

If you want to have access to the Conpot data, you have to create a
`HPFriends <http://hpfriends.honeycloud.net/>`_ account. As soon as you accept
the share, you can create an authkey and use those credentials with your
HPFeeds subscriber.

**How do I test this?**

As soon as you have Conpot set-up it should be easy to create some traffic for testing.
