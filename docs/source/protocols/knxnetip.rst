KNXnet/IP
=========

The ``knxnetip`` template listens for **KNXnet/IP** discovery traffic on UDP
port **3671**. Conpot emulates a KNXnet/IP tunneling interface that answers
**SEARCH_REQUEST** and **DESCRIPTION_REQUEST** with template-driven Device
Information and Supported Service Families DIBs.

CONNECT / TUNNELING, Routing Indications, and KNX IP Secure (TCP) are out of
scope for this handler; see GitHub issue `#218`.

Start the server
----------------

KNXnet/IP-only profile::

    uv run conpot --template knxnetip -f

You should see KnxnetipServer listening on ``0.0.0.0:3671``. After bind, the
server joins multicast group ``224.0.23.12`` so LAN SEARCH probes (for example
``nmap`` ``knx-gateway-discover``) can reach it.

Template configuration
----------------------

``knxnetip.toml`` is validated by the ``knxnetip`` schema in
``conpot/protocols/schemas.py``. Important keys:

.. list-table::
   :header-rows: 1
   :widths: 28 14 58

   * - Key
     - Default
     - Meaning
   * - ``enabled`` / ``host`` / ``port``
     - —
     - Bind address (shipped: ``0.0.0.0:3671``)
   * - ``friendly_name``
     - ``Conpot KNX IP``
     - Device Information DIB friendly name (30 octets max)
   * - ``individual_address``
     - ``1.1.1``
     - KNX individual address (``area.line.device``)
   * - ``serial_number``
     - ``00fa00000001``
     - 6-byte serial as hex (colons optional)
   * - ``mac_address``
     - ``00:fa:00:00:00:01``
     - 6-byte MAC as hex
   * - ``manufacturer_id``
     - ``250``
     - Stored in template identity (fixture only)
   * - ``medium``
     - ``2`` (TP1)
     - KNX medium code in Device Information DIB
   * - ``device_status`` / ``project_installation_id``
     - ``0`` / ``0``
     - Device Information DIB fields
   * - ``multicast_group``
     - ``224.0.23.12``
     - Discovery group joined after bind

Do not paste real organization serial numbers or MAC addresses into templates.

Probe with the standard library
-------------------------------

Send a DESCRIPTION_REQUEST and print the friendly name::

    import socket
    from conpot.protocols.knxnetip import knxip_codec as knxip

    body = knxip.pack_hpai("127.0.0.1", 3671)
    req = knxip.pack_header(knxip.SERVICE_DESCRIPTION_REQUEST, 6 + len(body)) + body
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2)
    sock.sendto(req, ("127.0.0.1", 3671))
    data, _ = sock.recvfrom(1024)
    sock.close()
    print(knxip.extract_friendly_name(data))
