import codecs
import logging
import struct

from pymodbus.constants import ExcCodes

from conpot.protocols.modbus.slave import MBSlave, ModbusInvalidRequestError

logger = logging.getLogger(__name__)


class SlaveBase(object):
    """Slave table. Unit ids 0..255 are allowed; pymodbus' own context stops at 247."""

    def __init__(self, template):
        self._slaves = {}
        self.template = template

    def add_slave(self, slave_id):
        if (slave_id < 0) or (slave_id > 255):
            raise ValueError("Invalid slave id %d" % slave_id)
        if slave_id in self._slaves:
            raise ValueError("Slave %d already exists" % slave_id)
        self._slaves[slave_id] = MBSlave(slave_id, self.template)
        return self._slaves[slave_id]

    def get_slave(self, slave_id):
        try:
            return self._slaves[slave_id]
        except KeyError:
            raise KeyError("Slave %s does not exist" % slave_id)

    def handle_request(self, request, mode):
        """
        Handle one MBAP request.

        Return value is ``(response, logdata)``. ``response`` is the bytes to
        send, or None when the peer should get nothing (empty PDU, broadcast,
        or a framing error).
        """
        slave_id = None
        function_code = None
        response_pdu = b""

        try:
            if len(request) < 7:
                raise ModbusInvalidRequestError(
                    "Request length is only %d bytes" % len(request)
                )
            _transaction, _protocol, length, slave_id = struct.unpack(
                ">HHHB", request[:7]
            )
            request_pdu = request[7:]
            if length != len(request_pdu) + 1:
                raise ModbusInvalidRequestError(
                    "MBAP length %s does not match PDU of %s bytes"
                    % (length, len(request_pdu))
                )

            if not request_pdu:
                logger.info(
                    "Discarding Modbus request with empty PDU (slave_id=%s)",
                    slave_id,
                )
                return (
                    None,
                    {
                        "request": codecs.encode(request, "hex"),
                        "slave_id": slave_id,
                        "function_code": None,
                        "response": b"",
                    },
                )

            function_code = request_pdu[0]
            logger.debug("Working mode: %s", mode)

            if mode == "tcp":
                # Serve any template-configured internal slave by unit id
                # (issue #353). UID 255 remains the conventional Modbus/TCP
                # "this device" address; other IDs map 1:1 to <slave id="...">.
                if 0 <= slave_id <= 255:
                    response_pdu = self._call_slave(slave_id, request_pdu, False)
                else:
                    response_pdu = _device_failure(function_code)
            elif mode == "serial":
                if slave_id == 0:
                    for key in self._slaves:
                        self._slaves[key].handle_request(request_pdu, broadcast=True)
                    return (
                        None,
                        {
                            "request": request_pdu.hex(),
                            "slave_id": slave_id,
                            "function_code": function_code,
                            "response": "",
                        },
                    )
                elif 0 < slave_id <= 247:
                    response_pdu = self._call_slave(slave_id, request_pdu, False)
                else:
                    response_pdu = _device_failure(function_code)
            else:
                response_pdu = _device_failure(function_code)

            if response_pdu is None:
                return (
                    None,
                    {
                        "request": codecs.encode(request, "hex"),
                        "slave_id": slave_id,
                        "function_code": function_code,
                        "response": b"",
                    },
                )
            response = _build_mbap(request, response_pdu)
        except (KeyError, OSError) as exc:
            logger.error(exc)
            response_pdu = _device_failure(function_code or 0)
            response = _build_mbap(request, response_pdu)
        except ModbusInvalidRequestError as exc:
            logger.error(exc)
            return (
                None,
                {
                    "request": codecs.encode(request, "hex"),
                    "slave_id": slave_id,
                    "function_code": function_code,
                    "response": b"",
                },
            )

        logged_function = function_code
        slave = self._slaves.get(slave_id)
        if slave is not None and slave.function_code is not None:
            logged_function = slave.function_code

        logdata = {
            "request": codecs.encode(request_pdu, "hex"),
            "slave_id": slave_id,
            "function_code": logged_function,
            "response": codecs.encode(response_pdu, "hex"),
        }
        if slave is not None and slave.event_type:
            logdata["type"] = slave.event_type
        return response, logdata

    def _call_slave(self, slave_id, request_pdu, broadcast):
        slave = self.get_slave(slave_id)
        return slave.handle_request(request_pdu, broadcast=broadcast)


def _device_failure(function_code):
    return struct.pack(">BB", (function_code or 0) + 0x80, int(ExcCodes.DEVICE_FAILURE))


def _build_mbap(request, response_pdu):
    transaction_id, protocol_id, _length, unit_id = struct.unpack(">HHHB", request[:7])
    return (
        struct.pack(
            ">HHHB", transaction_id, protocol_id, len(response_pdu) + 1, unit_id
        )
        + response_pdu
    )
