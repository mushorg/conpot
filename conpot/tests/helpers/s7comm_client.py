# Copyright (C) 2013  Daniel creo Haslinger <creo-conpot@blackmesa.at>
# Derived from plcscan by Dmitry Efanov (Positive Research)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from struct import pack, unpack
from optparse import OptionGroup
from conpot.helpers import str_to_bytes
import struct
import socket
import string

__FILTER = "".join(
    [" "]
    + [
        " " if chr(x) not in string.printable or chr(x) in string.whitespace else chr(x)
        for x in range(1, 256)
    ]
)


_bytes_to_str = lambda items: (
    value.decode("ascii") if isinstance(value, bytes) else value for value in items
)


def StripUnprintable(msg):
    return msg.decode("ascii").translate(__FILTER)


class TPKTPacket:
    """TPKT packet. RFC 1006"""

    def __init__(self, data=""):
        self.data = data

    def pack(self):
        return (
            pack(
                "!BBH",
                3,  # version
                0,  # reserved
                len(bytes(self.data)) + 4,  # packet size
            )
            + str_to_bytes(bytes(self.data))
        )

    def unpack(self, packet):
        try:
            header = unpack("!BBH", packet[:4])
        except struct.error:
            raise S7ProtocolError("Unknown TPKT format")

        self.data = packet[4 : 4 + header[2]]
        return self


class COTPConnectionPacket:
    """COTP Connection Request or Connection Confirm packet (ISO on TCP). RFC 1006"""

    def __init__(self, dst_ref=0, src_ref=0, dst_tsap=0, src_tsap=0, tpdu_size=0):
        self.dst_ref = dst_ref
        self.src_ref = src_ref
        self.dst_tsap = dst_tsap
        self.src_tsap = src_tsap
        self.tpdu_size = tpdu_size

    def pack(self):
        """make Connection Request Packet"""
        return pack(
            "!BBHHBBBHBBHBBB",
            17,  # size
            0xE0,  # pdu type: CR
            self.dst_ref,
            self.src_ref,
            0,  # flag
            0xC1,
            2,
            self.src_tsap,
            0xC2,
            2,
            self.dst_tsap,
            0xC0,
            1,
            self.tpdu_size,
        )

    def unpack(self, packet):
        """parse Connection Confirm Packet (header only)"""
        try:
            size, pdu_type, self.dst_ref, self.src_ref, _ = unpack("!BBHHB", packet[:7])
        except struct.error:
            raise S7ProtocolError("Wrong CC packet format")
        if len(packet) != size + 1:
            raise S7ProtocolError("Wrong CC packet size")
        if pdu_type != 0xD0:
            raise S7ProtocolError("Not a CC packet")
        return self

    def __bytes__(self):
        return self.pack()


class COTPDataPacket:
    """COTP Data packet (ISO on TCP). RFC 1006"""

    def __init__(self, data=""):
        self.data = data

    def pack(self):
        return pack("!BBB", 2, 0xF0, 0x80) + str_to_bytes(  # header len  # data packet
            bytes(self.data)
        )

    def unpack(self, packet):
        self.data = packet[packet[0] + 1 :]
        return self

    def __bytes__(self):
        return self.pack()


class S7Packet:
    """S7 packet"""

    def __init__(self, _type=1, req_id=0, parameters="", data=""):
        self.type = _type
        self.req_id = req_id
        self.parameters = parameters
        self.data = data
        self.error = 0

    def pack(self):
        if self.type not in [1, 7]:
            raise S7ProtocolError("Unknown pdu type")
        return (
            pack(
                "!BBHHHH",
                0x32,  # protocol s7 magic
                self.type,  # pdu-type
                0,  # reserved
                self.req_id,  # request id
                len(self.parameters),  # parameters length
                len(self.data),
            )
            + str_to_bytes(self.parameters)  # data length
            + str_to_bytes(self.data)
        )

    def unpack(self, packet):
        try:
            if packet[1] in [3, 2]:  # pdu-type = response
                header_size = 12
                (
                    _,
                    self.type,
                    _,
                    self.req_id,
                    parameters_length,
                    data_length,
                    self.error,
                ) = unpack("!BBHHHHH", packet[:header_size])
                if self.error:
                    raise S7Error(self.error)
            elif packet[1] in [1, 7]:
                header_size = 10
                (
                    _,
                    self.type,
                    _,
                    self.req_id,
                    parameters_length,
                    data_length,
                ) = unpack("!BBHHHH", packet[:header_size])
            else:
                raise S7ProtocolError("Unknown pdu type (%d)" % packet[1])
        except struct.error:
            raise S7ProtocolError("Wrong S7 packet format")

        self.parameters = packet[header_size : header_size + parameters_length]
        self.data = packet[
            header_size
            + parameters_length : header_size
            + parameters_length
            + data_length
        ]

        return self

    def __bytes__(self):
        return self.pack()


class S7ProtocolError(Exception):
    def __init__(self, message, packet=""):
        self.message = message
        self.packet = packet

    def __str__(self):
        return "[ERROR][S7Protocol] %s" % self.message


class S7Error(Exception):
    _errors = {
        # s7 data errors
        0x05: "Address Error",
        0x0A: "Item not available",
        # s7 header errors
        0x8104: "Context not supported",
        0x8500: "Wrong PDU size",
    }

    def __init__(self, code):
        self.code = code

    def __str__(self):
        if self.code in S7Error._errors:
            message = S7Error._errors[self.code]
        else:
            message = "Unknown error"
        return "[ERROR][S7][0x%x] %s" % (self.code, message)


def Split(ar, size):
    """split sequence into blocks of given size"""
    return [ar[i : i + size] for i in range(0, len(ar), size)]


class s7:
    def __init__(self, ip, port, src_tsap=0x200, dst_tsap=0x201, timeout=8):
        self.ip = ip
        self.port = port
        self.req_id = 0
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self.dst_ref = 0
        self.src_ref = 0x04
        self.dst_tsap = dst_tsap
        self.src_tsap = src_tsap
        self.timeout = timeout

    def Connect(self):
        """Establish ISO on TCP connection and negotiate PDU"""
        # sleep(1)
        # self.src_ref = randint(1, 20)
        self.src_ref = 10
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.settimeout(self.timeout)
        self.s.connect((self.ip, self.port))
        self.s.send(
            TPKTPacket(
                COTPConnectionPacket(
                    self.dst_ref, self.src_ref, self.dst_tsap, self.src_tsap, 0x0A
                )
            ).pack()
        )
        reply = self.s.recv(1024)
        _ = COTPConnectionPacket().unpack(TPKTPacket().unpack(reply).data)

        self.NegotiatePDU()

    def Request(self, _type, parameters="", data=""):
        """Send s7 request and receive response"""
        packet = TPKTPacket(
            COTPDataPacket(S7Packet(_type, self.req_id, parameters, data))
        ).pack()
        self.s.send(packet)
        reply = self.s.recv(1024)
        response = S7Packet().unpack(
            COTPDataPacket().unpack(TPKTPacket().unpack(reply).data).data
        )
        if self.req_id != response.req_id:
            raise S7ProtocolError("Sequence ID not correct")
        return response

    def NegotiatePDU(self, pdu=480):
        """Send negotiate pdu request and receive response. Reply no matter"""
        response = self.Request(
            0x01,
            pack(
                "!BBHHH",
                0xF0,  # function NegotiatePDU
                0x00,  # unknown
                0x01,  # max number of parallel jobs
                0x01,  # max number of parallel jobs
                pdu,
            ),
        )  # pdu length

        _, _, _, _, pdu = unpack("!BBHHH", response.parameters)
        return pdu

    def Function(self, _type, group, function, data=""):
        parameters = pack(
            "!LBBBB",
            0x00011200 + 0x04,  # parameter head (magic)  # parameter length
            0x11,  # unknown
            _type * 0x10 + group,  # type, function group
            function,  # function
            0x00,
        )  # sequence

        data = pack("!BBH", 0xFF, 0x09, len(data)) + data
        response = self.Request(0x07, parameters, data)

        code, _, _ = unpack("!BBH", response.data[:4])
        if code != 0xFF:
            raise S7Error(code)
        return response.data[4:]

    def plc_stop_function(self):
        pdu_type = 1
        request_id = 256
        stop_func_parameter = struct.pack(
            "!B5x10p", 0x29, str_to_bytes("P_PROGRAM")  # function code  # Function Name
        )
        s7packet = S7Packet(pdu_type, request_id, stop_func_parameter).pack()
        cotp_packet = COTPDataPacket(s7packet).pack()
        tpkt_packet = TPKTPacket(cotp_packet).pack()
        self.s.send(tpkt_packet)
        reply = self.s.recv(1024)
        if reply:
            return (
                S7Packet()
                .unpack(COTPDataPacket().unpack(TPKTPacket().unpack(reply).data).data)
                .data
            )
        else:
            return None

    def ReadSZL(self, szl_id):
        szl_data = self.Function(
            0x04,  # request
            0x04,  # szl-functions
            0x01,  # read szl
            pack("!HH", szl_id, 1),  # szl id
        )  # szl index

        szl_id, _, element_size, _ = unpack("!HHHH", szl_data[:8])

        return Split(szl_data[8:], element_size)


def BruteTsap(ip, port, src_tsaps=(0x100, 0x200), dst_tsaps=(0x102, 0x200, 0x201)):
    for src_tsap in src_tsaps:
        for dst_tsap in dst_tsaps:
            try:
                con = s7(ip, port)
                con.src_tsap = src_tsap
                con.dst_tsap = dst_tsap
                con.Connect()
                return src_tsap, dst_tsap

            except S7ProtocolError:
                pass

    return None


def GetIdentity(ip, port, src_tsap, dst_tsap):
    res = []

    szl_dict = {
        0x11: {
            "title": "Module Identification",
            "indexes": {1: "Module", 6: "Basic Hardware", 7: "Basic Firmware"},
            "packer": {
                (1, 6): lambda packet: "{0:s} v.{2:d}.{3:d}".format(
                    *_bytes_to_str(unpack("!20sHBBH", packet))
                ),
                (7,): lambda packet: "{0:s} v.{3:d}.{4:d}.{5:d}".format(
                    *_bytes_to_str(unpack("!20sHBBBB", packet))
                ),
            },
        },
        0x1C: {
            "title": "Component Identification",
            "indexes": {
                1: "Name of the PLC",
                2: "Name of the module",
                3: "Plant identification",
                4: "Copyright",
                5: "Serial number of module",
                6: "Reserved for operating system",
                7: "Module type name",
                8: "Serial number of memory card",
                9: "Manufacturer and profile of a CPU module",
                10: "OEM ID of a module",
                11: "Location designation of a module",
            },
            "packer": {
                (1, 2, 5): lambda packet: "%s" % packet[:24].decode("ascii"),
                (3, 7, 8): lambda packet: "%s" % packet[:32].decode("ascii"),
                (4,): lambda packet: "%s" % packet[:26].decode("ascii"),
            },
        },
    }

    con = s7(ip, port, src_tsap, dst_tsap)
    con.Connect()

    for szl_id in list(szl_dict.keys()):
        try:
            entities = con.ReadSZL(szl_id)
        except S7Error:
            continue

        packers = szl_dict[szl_id]["packer"]

        for item in entities:
            if len(item) > 2:
                (n,) = unpack("!H", item[:2])
                item = item[2:]

                try:
                    packers_keys = [i for i in list(packers.keys()) if n in i]
                    formated_item = packers[packers_keys[0]](item).strip("\x00")
                except (struct.error, IndexError):
                    formated_item = StripUnprintable(item).strip("\x00")

                res.append("%s;%s;%s" % (szl_id, n, formated_item))

    return res


def Scan(ip, port):
    res = ()
    try:
        res = BruteTsap(ip, port)
    except socket.error as e:
        print("%s:%d %s" % (ip, port, e))

    if not res:
        print(" MEH!")
        return False

    print("%s:%d S7comm (src_tsap=0x%x, dst_tsap=0x%x)" % (ip, port, res[0], res[1]))

    # sometimes unexpected exceptions occur, so try to get identity several time
    identities = []
    for attempt in [0, 1]:
        try:
            identities = GetIdentity(ip, port, res[0], res[1])
            break
        except (S7ProtocolError, socket.error) as e:
            print("Attempt {0}:  {1}".format(attempt, e))

    return identities


def AddOptions(parser):
    group = OptionGroup(parser, "S7 scanner options")
    group.add_option(
        "--src-tsap",
        help="Try this src-tsap (list) (default: 0x100,0x200)",
        type="string",
        metavar="LIST",
    )
    group.add_option(
        "--dst-tsap",
        help="Try this dst-tsap (list) (default: 0x102,0x200,0x201)",
        type="string",
        metavar="LIST",
    )
    parser.add_option_group(group)
