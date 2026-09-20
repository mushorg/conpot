"""BACnet/IP (BVLC + NPDU + APDU) encode and decode using bacpypes3.

Conpot owns the UDP socket. bacpypes3 is only the codec and object model.
"""

from bacpypes3.apdu import APDU, APCISequence
from bacpypes3.errors import DecodingError
from bacpypes3.ipv4.bvll import (
    LPCI,
    OriginalBroadcastNPDU,
    OriginalUnicastNPDU,
    pdu_types,
)
from bacpypes3.npdu import NPDU
from bacpypes3.pdu import Address, PDU


def peer_address(address):
    """Build a bacpypes3 address from a (host, port) tuple."""
    return Address("{0}:{1}".format(address[0], address[1]))


def _prepare_apdu(apdu):
    """Fill header fields bacpypes3 leaves unset so APCI.encode() can run."""
    defaults = (
        ("apduSeg", 0),
        ("apduMor", 0),
        ("apduSA", 0),
        ("apduSrv", 0),
        ("apduNak", 0),
        ("apduSeq", 0),
        ("apduWin", 0),
        ("apduMaxSegs", 0),
        ("apduMaxResp", 0),
        ("apduInvokeID", 0),
        ("apduService", 0),
        ("apduAbortRejectReason", 0),
        ("pduExpectingReply", False),
        ("pduNetworkPriority", 0),
    )
    for name, default in defaults:
        if not hasattr(apdu, name):
            setattr(apdu, name, default)
    return apdu


def _as_apdu(message):
    # Request sequences (WhoIsRequest, ReadPropertyACK, ...) encode their tags
    # into a plain APDU. APDU subclasses such as RejectPDU are already headers.
    if isinstance(message, APCISequence):
        apdu = message.encode()
    elif isinstance(message, APDU):
        apdu = message
    else:
        raise TypeError("BACnet APDU expected, got {0}".format(type(message).__name__))
    return _prepare_apdu(apdu)


def encode_bacnet_ip(message):
    """Wrap a bacpypes3 request or APDU in a BACnet/IP datagram."""
    apdu = _as_apdu(message)
    encoded_apdu = apdu.encode()

    npdu = NPDU()
    npdu.pduExpectingReply = apdu.pduExpectingReply
    npdu.pduNetworkPriority = apdu.pduNetworkPriority
    npdu.put_data(encoded_apdu.pduData)
    encoded_npdu = npdu.encode()

    destination = getattr(message, "pduDestination", None)
    if destination is not None and destination.addrType in (
        Address.localBroadcastAddr,
        Address.globalBroadcastAddr,
    ):
        link_pdu = OriginalBroadcastNPDU(encoded_npdu.pduData)
    else:
        link_pdu = OriginalUnicastNPDU(encoded_npdu.pduData)
    return bytes(link_pdu.encode().pduData)


def decode_bacnet_ip(data, address):
    """Decode a BACnet/IP datagram down to an APDU (not a service sequence)."""
    pdu = PDU(bytearray(data), source=peer_address(address))
    lpci = LPCI.decode(pdu)
    try:
        link_class = pdu_types[lpci.bvlciFunction]
    except KeyError:
        raise DecodingError("unsupported BVLC function: {0}".format(lpci.bvlciFunction))
    link_pdu = link_class.decode(pdu)
    npdu = NPDU.decode(PDU(link_pdu.pduData))
    return APDU.decode(PDU(npdu.pduData))
