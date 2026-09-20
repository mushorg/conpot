Protocols
=========

Conpot ships the protocol handlers listed below (keys in
``conpot.protocols.name_mapping``). Ports are the values used in the
shipped templates; override them in your profile.

.. list-table::
   :header-rows: 1
   :widths: 22 10 28 12

   * - Handler
     - Port
     - Typical template
     - Docs
   * - ``bacnet``
     - 47808
     - ``default``
     - —
   * - ``enip``
     - 44818
     - ``default``
     - :doc:`enip`
   * - ``ftp``
     - 2121
     - ``default``
     - —
   * - ``guardian_ast``
     - 10001
     - ``guardian_ast``
     - —
   * - ``http``
     - 8800
     - ``default``
     - :doc:`http`
   * - ``IEC104``
     - 2404
     - ``IEC104``
     - —
   * - ``ipmi``
     - 6230
     - ``default`` (``623`` in ``ipmi``)
     - —
   * - ``kamstrup_management``
     - 50100
     - ``kamstrup_382``
     - —
   * - ``kamstrup_meter``
     - 1025
     - ``kamstrup_382``
     - —
   * - ``modbus``
     - 5020
     - ``default``, ``plc_modbus``
     - :doc:`modbus`
   * - ``s7comm``
     - 10201
     - ``default``
     - :doc:`s7comm`
   * - ``snmp``
     - 16100
     - ``default``, ``snmp``
     - :doc:`snmp`
   * - ``tftp``
     - 6969
     - ``default``
     - —

Only handlers with existing documentation have a dedicated page. Cross-cutting
CPU stop/restart probes are summarized in :doc:`../usage/stop_restart`.

.. toctree::
   :maxdepth: 1

   enip
   http
   modbus
   s7comm
   snmp
