=============
Customization
=============

The default profile
-------------------

Conpot is shipped with a default multi-protocol sample profile (``templates/default/``).
It enables bacnet, enip, ftp, http, ipmi, modbus, s7comm, snmp, and tftp so operators can
try most of the available protocol handlers from one template. See
:doc:`../protocols/index` for the full handler list and ports.

Databus identity strings in this profile still use Siemens-flavored values (for example
``Siemens, SIMATIC, S7-200``) for deception realism. Those fingerprints are independent of
the operator-facing template catalog description.

While most of the configuration takes place within the TOML profile, protocols that
need auxiliary files (for example HTTP ``htdocs`` / ``statuscodes``, or SNMP MIB sources)
keep those in a subdirectory next to the protocol config.

Per-protocol template notes
---------------------------

* Modbus slaves, blocks, and UMAS — :doc:`../protocols/modbus`
* SNMP MIBs, tarpit, and evasion — :doc:`../protocols/snmp`
* HTTP globals, htdocs, aliases, and proxy nodes — :doc:`../protocols/http`
* EtherNet/IP identity and tags — :doc:`../protocols/enip`
* S7comm CPU stop/start — :doc:`../protocols/s7comm`
* DNP3 outstation addresses and point tables — :doc:`../protocols/dnp3`
* R-GOOSE APPID, gocbRef, and publish destination — :doc:`../protocols/goose`

The ``plc_modbus`` profile adds a scan cycle behind Modbus; see
:doc:`plc_emulator`.
