ADS
===

The ``ads`` template listens for **Beckhoff ADS** over AMS/TCP on port
**48898** and answers TwinCAT broadcast search on UDP port **48899**.
Conpot emulates a TwinCAT-style ADS endpoint that answers device info, ADS
state, and index-group read/write requests, plus the UDP Identify banner
(hostname, AMS NetId, TwinCAT and OS version) used by internet scanners.
Secure ADS, notifications, symbolic get-handle / read-by-name, and UDP
AddRoute are out of scope for this handler; see GitHub issue `#277`.

Start the server
----------------

ADS-only profile::

    uv run conpot --template ads -f

You should see AdsServer listening on ``0.0.0.0:48898`` and AdsDiscovery on
``0.0.0.0:48899``.

Template configuration
----------------------

``ads.toml`` is validated by the ``ads`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:48898``)
   * - ``timeout``
     - ``5``
     - Idle recv timeout in seconds (issue `#441`)
   * - ``ams_net_id``
     - ``192.168.1.1.1.1``
     - Local AMS NetId advertised in responses
   * - ``ams_port``
     - ``851``
     - TwinCAT 3 PLC runtime AMS port
   * - ``device_name``
     - ``Conpot TwinCAT``
     - 16-octet ReadDeviceInfo name
   * - ``version_major`` / ``version_minor`` / ``version_build``
     - ``3`` / ``1`` / ``0``
     - Device version fields in ReadDeviceInfo
   * - ``ads_state`` / ``device_state``
     - ``5`` / ``0``
     - Values returned by ReadState (``5`` = RUN)
   * - ``symbols``
     - —
     - Index-group table (``name``, ``index_group``, ``index_offset``, ``value_hex``)
   * - ``discovery_enabled`` / ``discovery_port``
     - ``true`` / ``48899``
     - UDP broadcast-search listener
   * - ``hostname``
     - ``CX-CONPOT``
     - ComputerName in the UDP Identify reply
   * - ``tc_version_major`` / ``tc_version_minor`` / ``tc_version_build``
     - ``3`` / ``1`` / ``4024``
     - TwinCAT version in the UDP Identify reply
   * - ``os_platform`` / ``os_major`` / ``os_minor`` / ``os_build``
     - ``2`` / ``10`` / ``0`` / ``19045``
     - OS version (``2`` = Windows NT)
   * - ``os_service_pack``
     - empty
     - UTF-16 service-pack string in the OS version blob

Do not paste real plant AMS NetIds or production symbol tables into templates.

Supported commands
------------------

* ADS Read Device Info (1)
* ADS Read (2) — by ``index_group`` / ``index_offset``
* ADS Write (3) — updates matching symbol bytes in memory
* ADS Read State (4)
* ADS Write Control (5) — mocked success

Unknown command IDs return an ADS error result and are still logged.

UDP discovery
-------------

Port **48899** answers AMS/UDP **Identify** (service 1, magic ``0x71146603``).
The reply sets the response bit (``0x80000001``), advertises ``ams_net_id``
with system-service port **10000**, and puts ComputerName in the first TLV.
**AddRoute** (service 6) is logged by service id only and is not accepted.

Probe Identify (stdlib only)::

    import socket
    import struct

    netid = bytes(int(p) for p in "10.0.0.1.1.1".split("."))
    req = struct.pack("<III6sHI", 0x71146603, 0, 1, netid, 10000, 0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    sock.sendto(req, ("127.0.0.1", 48899))
    data, _addr = sock.recvfrom(2048)
    tag, length = struct.unpack_from("<HH", data, 24)
    name = data[28 : 28 + length].split(b"\x00", 1)[0]
    print(name)
    sock.close()

Probe with a raw AMS/TCP client
-------------------------------

A minimal Read Device Info exchange (stdlib only)::

    import socket
    import struct

    def ams_net_id(s):
        return bytes(int(p) for p in s.split("."))

    target = ams_net_id("192.168.1.1.1.1")
    source = ams_net_id("10.0.0.1.1.1")
    # AMS header: target NetId/port, source NetId/port, cmd=1, flags=4, len=0, err=0, invoke=1
    ams = struct.pack(
        "<6sH6sHHHIII",
        target, 851, source, 32905, 1, 0x0004, 0, 0, 1,
    )
    frame = struct.pack("<HI", 0, len(ams)) + ams

    sock = socket.create_connection(("127.0.0.1", 48898), timeout=2)
    sock.sendall(frame)
    header = sock.recv(6)
    length = struct.unpack_from("<HI", header, 0)[1]
    body = sock.recv(length)
    # device name starts 8 bytes into the ADS response payload
    name = body[32 + 8 : 32 + 24].split(b"\x00", 1)[0]
    print(name)
    sock.close()

Session events
--------------

Each TCP session logs ``NEW_CONNECTION``, per-frame ``REQUEST`` (command name,
AMS NetIds, invoke id), and ``CONNECTION_LOST`` on close, idle timeout, or peer
reset. Each UDP discovery datagram logs the same trio with the service name
(``IDENTIFY`` or ``ADD_ROUTE``). AddRoute payloads are not stored.
