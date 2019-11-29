Internal Interface
-------------------

Internal interface was a feature developed for advanced users. Basically every attribute of a class that is decorated by `@conpot_protocol` decorator can be accessed. This can be very powerful in case we want to emulate a system-wide phenomenon. Like for example we want to emulate a system restart (kamstrup management protocol ;-) we can set a counter and freeze access to all protocols.

Some other uses include timing the last attack. This can be done by tracking the handle method for every protocol. Again can be easily done, without even touching the protocol implementation :-)

For more details refer to PR related to this issue: https://github.com/mushorg/conpot/pull/375