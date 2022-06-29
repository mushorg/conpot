# Copyright (C) 2017  Patrick Reichenberger (University of Passau) <patrick.reichenberger@t-online.de>
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

from lxml import etree
from conpot.protocols.IEC104.frames import *
import conpot.core as conpot_core
from conpot.protocols.IEC104.register import IEC104Register

logger = logging.getLogger(__name__)


# Manages the devices in a dictionary with key: address in 16_8 Bit format and value: register objects
class DeviceDataController(object):
    def __init__(self, template):
        # key: IEC104 address, value: register object
        self.registers = {}
        self.common_address = int(
            conpot_core.get_databus().get_value("CommonAddress"), 0
        )

        dom = etree.parse(template)
        categories = dom.xpath("//IEC104/categories/*")

        for category in categories:
            categ_id = int(category.attrib["id"])
            for register in category:
                address = register.attrib["name"]
                splt_addr1, splt_addr2 = address.split("_")
                assert 0 <= int(splt_addr1) <= 65535 and 0 <= int(splt_addr2) <= 255, (
                    "Address %s not allowed. 0..65535_0..255" % address
                )
                databuskey = register.xpath("./value/text()")[0]
                if register.get("rel"):
                    rel = register.attrib["rel"]
                else:
                    rel = ""

                # checks if a value for that key exists in xml file
                try:
                    val = conpot_core.get_databus().get_value(databuskey)
                except AssertionError as err:
                    err.args = ("Key not found in key-value store",)
                    raise

                # simple data type checks
                assert not (
                    categ_id in (1, 2, 30, 45, 58) and val not in (0, 1)
                ), "Value for obj %s not allowed with datatype %s" % (address, categ_id)
                assert not (
                    categ_id in (3, 4, 31, 46, 59) and val not in (0, 1, 2, 3)
                ), "Value for obj %s not allowed with datatype %s" % (address, categ_id)
                assert not (
                    categ_id in (11, 12, 49, 62) and -32768 >= val >= 32767
                ), "Value for obj %s not allowed with datatype %s" % (address, categ_id)
                iec104_register = IEC104Register(categ_id, address, val, rel)
                assert address not in self.registers
                self.registers[address] = iec104_register
        self.check_registers()

    # Checks if relation (if stated) exists
    def check_registers(self):
        for elem in self.registers:
            rel = self.registers[elem].relation
            assert not (
                rel != "" and rel not in self.registers
            ), "Relation object doesn't exist"

    # Returns the object with the obj_addr from the register dictionary
    def get_object_from_reg(self, obj_addr):
        address_structured = hex_in_addr(obj_addr)
        if address_structured in self.registers:
            return self.registers[address_structured]
        else:
            return None

    # Sets the value for an object in the register list
    def set_object_val(self, obj_addr, val):
        address_hex = hex(obj_addr)
        address_structured = hex_in_addr(address_hex)
        if address_structured in self.registers:
            self.registers[address_structured].set_val(val)

    def get_registers(self):
        return self.registers


# Builds response for a certain asdu type and returns list of responses with this type
def inro_response(sorted_reg, asdu_type):
    resp_list = []
    resp = i_frame() / asdu_head(SQ=0, COT=20)
    max_frame_size = conpot_core.get_databus().get_value("MaxFrameSize")
    counter = 0
    asdu_infobj_type = "asdu_infobj_" + str(asdu_type)
    calls_dict = {
        "asdu_infobj_1": asdu_infobj_1,
        "asdu_infobj_3": asdu_infobj_3,
        "asdu_infobj_5": asdu_infobj_5,
        "asdu_infobj_7": asdu_infobj_7,
        "asdu_infobj_9": asdu_infobj_9,
        "asdu_infobj_11": asdu_infobj_11,
        "asdu_infobj_13": asdu_infobj_13,
    }
    call = calls_dict[asdu_infobj_type]
    for dev in sorted_reg:
        if dev[1].category_id == asdu_type:
            # 12 is length i_frame = 6 + length asdu_head = 6
            if counter >= int((max_frame_size - 12) / len(call())):
                resp_list.append(resp)
                counter = 0
                resp = i_frame() / asdu_head(SQ=0, COT=20)
            xaddr = addr_in_hex(dev[1].addr)

            add_info_obj = call(IOA=xaddr)  # SQ = 0
            val = dev[1].val
            if asdu_type == 1:
                add_info_obj.SIQ = SIQ(SPI=val)
                # Other possibility for allocation (certain value for whole field)
                # add_info_obj.SIQ = struct.pack("B", val)
            elif asdu_type == 3:
                add_info_obj.DIQ = DIQ(DPI=val)
            elif asdu_type == 5:
                add_info_obj.VTI = VTI(Value=val)
            elif asdu_type == 7:
                add_info_obj.BSI = val
            elif asdu_type == 9:
                add_info_obj.NVA = val
            elif asdu_type == 11:
                add_info_obj.SVA = val
            elif asdu_type == 13:
                add_info_obj.FPNumber = val
            resp /= add_info_obj
            counter += 1
            resp.NoO = counter
    if counter > 0:
        resp_list.append(resp)
    return resp_list


# Converts the address from number representation in 16_8 Bit String format with delimiter "_"
def hex_in_addr(hex_addr):
    hexa = "{0:#0{1}x}".format(hex_addr, 8)
    a1 = hexa[2:4]
    a2 = hexa[4:6]
    a3 = hexa[6:8]
    a32 = a3 + a2
    return str(int(a32, 16)) + "_" + str(int(a1, 16))


# Converts the address from 16_8 Bit String format with delimiter "_" in a number representation
def addr_in_hex(address):
    a1, a2 = address.split("_")
    hex1_temp = "{0:0{1}x}".format(int(a1), 4)
    hex1_1 = hex1_temp[0:2]
    hex1_2 = hex1_temp[2:4]
    hex1 = str(hex1_2) + str(hex1_1)
    hex2 = "{0:#0{1}x}".format(int(a2), 4)  # bec of '0x' length 4
    hex_string = str(hex2) + str(hex1)
    return int(hex_string, 16)
