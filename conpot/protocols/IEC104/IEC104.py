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
import gevent
import natsort
from conpot.protocols.IEC104.DeviceDataController import addr_in_hex, inro_response
from conpot.protocols.IEC104.i_frames_check import *
import conpot.core as conpot_core
from .frames import *

logger = logging.getLogger(__name__)


class IEC104(object):
    def __init__(self, device_data_controller, sock, address, session_id):
        self.sock = sock
        self.address = address
        self.session_id = session_id
        self.T_1 = conpot_core.get_databus().get_value("T_1")
        self.timeout_t1 = gevent.Timeout(self.T_1, gevent.Timeout)
        self.T_2 = conpot_core.get_databus().get_value("T_2")
        self.w = conpot_core.get_databus().get_value("w")
        self.device_data_controller = device_data_controller
        self.ssn = 0
        self.rsn = 0
        self.ack = 0
        self.allow_DT = False
        self.t2_caller = None
        self.telegram_count = 0
        self.sentmsgs = list()
        self.send_buffer = list()

    # === u_frame
    def handle_u_frame(self, frame):
        container = u_frame(frame)
        try:
            # check if valid u_frame (length, rest bits)
            if len(frame) == 6 and container.getfieldval("LenAPDU") == 4:
                if frame[3] == 0x00 and frame[4] == 0x00 and frame[5] == 0x00:
                    # check which type (Start, Stop, Test), only one active at same time
                    # STARTDT_act
                    if frame[2] == 0x07:
                        logger.info(
                            "%s ---> u_frame. STARTDT act. (%s)",
                            self.address,
                            self.session_id,
                        )
                        self.allow_DT = True
                        yield self.send_104frame(STARTDT_con)
                        # === If buffered data, send
                        if self.send_buffer:
                            for pkt in self.send_buffer:
                                yield self.send_104frame(pkt)
                    # STARTDT_con
                    elif frame[2] == 0x0B:
                        logger.info(
                            "%s ---> u_frame. STARTDT con. (%s)",
                            self.address,
                            self.session_id,
                        )
                        #  Station sends no STARTDT_act, so there is no STARTDT_con expected and no action performed
                        #  Can be extended, if used as Master
                    # STOPDT_act
                    elif frame[2] == 0x13:
                        logger.info(
                            "%s ---> u_frame. STOPDT act. (%s)",
                            self.address,
                            self.session_id,
                        )
                        self.allow_DT = False
                        # Send S_Frame
                        resp_frame = s_frame()
                        yield self.send_104frame(resp_frame)
                        yield self.send_104frame(STOPDT_con)
                    # STOPDT_con
                    elif frame[2] == 0x23:
                        logger.info(
                            "%s ---> u_frame. STOPDT con. (%s)",
                            self.address,
                            self.session_id,
                        )
                        self.timeout_t1.cancel()
                    # TESTFR_act
                    elif frame[2] == 0x43:
                        logger.info(
                            "%s ---> u_frame. TESTFR act. (%s)",
                            self.address,
                            self.session_id,
                        )
                        # In case of both sending a TESTFR_act.
                        if self.sentmsgs:
                            temp_list = []
                            for x in self.sentmsgs:
                                if x.name != "u_frame" or x.getfieldval("Type") != 0x43:
                                    if isinstance(x, frame_object_with_timer):
                                        temp_list.append(x)
                                else:
                                    x.cancel_t1()
                            self.sentmsgs = temp_list
                        yield self.send_104frame(TESTFR_con)
                    # TESTFR_con
                    elif frame[2] == 0x83:
                        logger.info(
                            "%s ---> u_frame. TESTFR con. (%s)",
                            self.address,
                            self.session_id,
                        )
                        if self.sentmsgs:
                            temp_list = []
                            for x in self.sentmsgs:
                                if x.name != "u_frame" or x.getfieldval("Type") != 0x43:
                                    if isinstance(x, frame_object_with_timer):
                                        temp_list.append(x)
                                else:
                                    x.cancel_t1()
                            self.sentmsgs = temp_list
                    else:
                        raise InvalidFieldValueException(
                            "Invalid u_frame packet, more than 1 bit set!  (%s)",
                            self.session_id,
                        )
                else:
                    raise InvalidFieldValueException(
                        "Control field octet 2,3 or 4 not 0x00! (%s)", self.session_id
                    )
            else:
                raise InvalidFieldValueException(
                    "Wrong length for u_frame packet! (%s)", self.session_id
                )
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s. (%s)", ex, self.session_id)

    # === s_frame
    def handle_s_frame(self, frame):
        container = s_frame(frame)
        try:
            # check if valid u_frame (length, rest bits)
            if len(frame) == 6 and container.getfieldval("LenAPDU") == 4:
                if frame[2] & 0x01 and frame[3] == 0x00:
                    recv_snr = container.getfieldval("RecvSeq")
                    logger.info(
                        "%s ---> s_frame receive nr: %s. (%s)",
                        self.address,
                        str(recv_snr),
                        self.session_id,
                    )
                    if recv_snr <= self.ssn:
                        self.ack = recv_snr
                    if self.sentmsgs:
                        temp_list = []
                        for x in self.sentmsgs:
                            if (
                                x.name != "i_frame"
                                or x.getfieldval("SendSeq") >= self.ack
                            ):
                                if isinstance(x, frame_object_with_timer):
                                    temp_list.append(x)
                            else:
                                x.cancel_t1()
                        self.sentmsgs = temp_list
                        self.show_send_list()

                else:
                    raise InvalidFieldValueException(
                        "Control field octet 1 in 's_frame' not 0x01 or 2 not 0x00! "
                        "(%s)",
                        self.session_id,
                    )
            else:
                raise InvalidFieldValueException(
                    "Wrong length for s_frame packet! (%s)", self.session_id
                )
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s. (%s)", ex, self.session_id)

    # === i_frame
    def handle_i_frame(self, frame):
        container = i_frame(frame)

        request_string = " ".join(hex(n) for n in frame)
        logger.debug(
            "%s ---> i_frame %s. (%s)", self.address, request_string, self.session_id
        )
        logger.info(
            "%s ---> i_frame %s  (%s)", self.address, container.payload, self.session_id
        )

        frame_length = len(frame)
        try:
            if container.getfieldval("LenAPDU") != frame_length - 2:
                raise InvalidFieldValueException(
                    "Wrong length for i_frame packet! (%s)", self.session_id
                )
            self.telegram_count += 1
            recv_snr = container.getfieldval("RecvSeq")

            # Figure 11
            if container.getfieldval("SendSeq") == self.rsn:
                self.recvseq_increment()
            else:
                logger.error(
                    "Sequence error, send s_frame for last correct packet. Then disconnect. (%s)",
                    self.session_id,
                )
                # Better solution exists..
                if self.t2_caller:
                    gevent.kill(self.t2_caller)
                gevent.Greenlet.spawn_later(1, self.disconnect())
                return self.send_104frame(s_frame(RecvSeq=self.rsn))

            # All packets up to recv_snr-1 are acknowledged
            if self.sentmsgs:
                temp_list = []
                for x in self.sentmsgs:
                    if x.name != "i_frame" or x.getfieldval("SendSeq") >= recv_snr:
                        if isinstance(x, frame_object_with_timer):
                            temp_list.append(x)
                    else:
                        x.cancel_t1()
                self.sentmsgs = temp_list

        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s. (%s)", ex, self.session_id)

        # Send S_Frame at w telegrams or (re)start timer T2
        resp_frame = s_frame()
        if not self.t2_caller:
            self.t2_caller = gevent.Greenlet.spawn_later(
                self.T_2, self.send_frame_imm, resp_frame
            )
        if self.telegram_count >= self.w:
            return self.send_104frame(resp_frame)

        common_address = self.device_data_controller.common_address
        type_id = container.getfieldval("TypeID")
        request_coa = container.getfieldval("COA")

        # 45: Single command
        if type_id == TypeIdentification["C_SC_NA_1"] and request_coa == common_address:
            return self.handle_single_command45(container)

        # 46: Double command
        elif (
            type_id == TypeIdentification["C_DC_NA_1"] and request_coa == common_address
        ):
            return self.handle_double_command46(container)

        # 49: Setpoint command, scaled value
        elif (
            type_id == TypeIdentification["C_SE_NB_1"] and request_coa == common_address
        ):
            return self.handle_setpointscaled_command49(container)

        # 50: Setpoint command, short floating point value
        elif (
            type_id == TypeIdentification["C_SE_NC_1"] and request_coa == common_address
        ):
            return self.handle_setpointfloatpoint_command50(container)

        # 100: (General-) Interrogation command
        elif type_id == TypeIdentification["C_IC_NA_1"] and request_coa in (
            common_address,
            0xFFFF,
        ):
            return self.handle_inro_command100(container)

    def send_104frame(self, frame):
        # send s_frame
        if frame.name == "s_frame":
            frame.RecvSeq = self.rsn
            if self.t2_caller:
                gevent.kill(self.t2_caller)
            self.telegram_count = 0
            response_string = " ".join(hex(n) for n in frame.build())
            logger.info(
                "%s <--- s_frame %s  (%s)",
                self.address,
                response_string,
                self.session_id,
            )
            return frame.build()

        # send i_frame
        elif frame.name == "i_frame":
            if self.allow_DT:
                if self.t2_caller:
                    gevent.kill(self.t2_caller)
                frame.SendSeq = self.ssn
                frame.RecvSeq = self.rsn
                frame.COA = self.device_data_controller.common_address
                self.increment_sendseq()
                self.telegram_count = 0
                iframe = frame_object_with_timer(frame)
                self.sentmsgs.append(iframe)
                iframe.restart_t1()
                response_string = " ".join(hex(n) for n in frame.build())
                logger.debug(
                    "%s <--- i_frame %s  (%s)",
                    self.address,
                    response_string,
                    self.session_id,
                )
                logger.info(
                    "%s <--- i_frame %s  (%s)",
                    self.address,
                    frame.payload,
                    self.session_id,
                )
                return frame.build()

            else:
                logger.info("StartDT missing, buffer data. (%s)", self.session_id)
                # Limitation for buffer, arbitrary number
                if len(self.send_buffer) < 50:
                    self.send_buffer.append(frame)

        # send u_frame
        elif frame.name == "u_frame":
            if frame.getfieldval("Type") == 0x07 or frame.getfieldval("Type") == 0x43:
                uframe = frame_object_with_timer(frame)
                self.sentmsgs.append(uframe)
                uframe.restart_t1()
            response_string = " ".join(hex(n) for n in frame.build())
            logger.info(
                "%s <--- u_frame %s  (%s)",
                self.address,
                response_string,
                self.session_id,
            )
            return frame.build()

    def send_frame_imm(self, frame):
        # send s_frame
        if frame.name == "s_frame":
            frame.RecvSeq = self.rsn
            if self.t2_caller:
                gevent.kill(self.t2_caller)
            self.telegram_count = 0
            response_string = " ".join(hex(n) for n in frame.build())
            logger.info(
                "%s <--- s_frame %s  (%s)",
                self.address,
                response_string,
                self.session_id,
            )
            return self.sock.send(frame.build())

    def handle_single_command45(self, container):
        try:
            check_asdu_45(container, "c")
            cause_of_transmission = int(container.getfieldval("COT"))
            info_obj_addr = container.getfieldval("IOA")
            field_val = container.getfieldval("SCS")
            if cause_of_transmission == 6:
                obj = self.device_data_controller.get_object_from_reg(
                    info_obj_addr
                )  # get destination object
                if not (obj is None):  # if exists in xml-file
                    obj_cat = int(obj.category_id)  # get type (single command)
                    if obj_cat == 45:  # if object has type single command
                        # === Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(COT=7)
                            / asdu_infobj_45(IOA=info_obj_addr, SCS=field_val)
                        )
                        check_asdu_45(act_con, "m")
                        yield self.send_104frame(act_con)

                        # === Get related info object if exists
                        obj_rel_addr = obj.relation
                        if obj_rel_addr != "":  # if relation available
                            obj_rel_addr_hex = addr_in_hex(
                                obj_rel_addr
                            )  # get single point object address
                            # get the single point object
                            obj_rel = self.device_data_controller.get_object_from_reg(
                                obj_rel_addr_hex
                            )
                            obj.val = field_val  # set the value in the object to the command value
                            obj_rel.val = field_val  # set the value in the relation object to the command value
                            # test whether if it really updated the value
                            changed_val = obj_rel.val
                            single_point = (
                                i_frame()
                                / asdu_head(COT=11)
                                / asdu_infobj_1(IOA=obj_rel_addr_hex)
                            )
                            single_point.SIQ = SIQ(SPI=changed_val)
                            yield self.send_104frame(single_point)

                        # === Activation termination
                        act_term = (
                            i_frame()
                            / asdu_head(COT=10)
                            / asdu_infobj_45(IOA=info_obj_addr, SCS=field_val)
                        )
                        check_asdu_45(act_term, "m")
                        yield self.send_104frame(act_term)
                    else:  # if command type doesn't fit
                        # === neg. Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(PN=1, COT=7)
                            / asdu_infobj_45(IOA=info_obj_addr, SCS=field_val)
                        )
                        check_asdu_45(act_con, "m")
                        yield self.send_104frame(act_con)
                else:  # object doesn't exist in xml file
                    # === unknown info obj address, object not found (or no reply?)
                    bad_addr = (
                        i_frame()
                        / asdu_head(COT=47)
                        / asdu_infobj_45(IOA=info_obj_addr, SCS=field_val)
                    )
                    check_asdu_45(bad_addr, "m")
                    yield self.send_104frame(bad_addr)
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s  (%s)", ex, self.session_id)
        except AttributeError as ex:
            logger.warning(
                "Allocation for field %s not possible. (%s)", ex, self.session_id
            )

    def handle_double_command46(self, container):
        try:
            check_asdu_46(container, "c")
            cause_of_transmission = int(container.getfieldval("COT"))
            info_obj_addr = container.getfieldval("IOA")
            field_val = container.getfieldval("DCS")
            if cause_of_transmission == 6:
                obj = self.device_data_controller.get_object_from_reg(
                    info_obj_addr
                )  # get destination object
                if not (obj is None):  # if exists in xml-file
                    obj_cat = int(obj.category_id)  # get type (double command)
                    if obj_cat == 46:  # if object has type double command
                        # === Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(COT=7)
                            / asdu_infobj_46(IOA=info_obj_addr, DCS=field_val)
                        )
                        check_asdu_46(act_con, "m")
                        yield self.send_104frame(act_con)

                        # === Get related info object if exists
                        obj_rel_addr = obj.relation
                        if obj_rel_addr != "":  # if relation available
                            obj_rel_addr_hex = addr_in_hex(
                                obj_rel_addr
                            )  # get double point object address
                            # get the double point object
                            obj_rel = self.device_data_controller.get_object_from_reg(
                                obj_rel_addr_hex
                            )
                            obj.val = field_val  # set the value in the object to the command value
                            obj_rel.val = field_val  # set the value in the relation object to the command value
                            # test whether if it really updated the value
                            changed_val = obj_rel.val
                            double_point = (
                                i_frame()
                                / asdu_head(COT=11)
                                / asdu_infobj_3(IOA=obj_rel_addr_hex)
                            )
                            double_point.DIQ = DIQ(DPI=changed_val)
                            yield self.send_104frame(double_point)

                        # === Activation termination
                        act_term = (
                            i_frame()
                            / asdu_head(COT=10)
                            / asdu_infobj_46(IOA=info_obj_addr, DCS=field_val)
                        )
                        check_asdu_46(act_term, "m")
                        yield self.send_104frame(act_term)
                    else:  # if command type doesn't fit
                        # === neg. Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(PN=1, COT=7)
                            / asdu_infobj_46(IOA=info_obj_addr, DCS=field_val)
                        )
                        check_asdu_46(act_con, "m")
                        yield self.send_104frame(act_con)
                else:  # object doesn't exist in xml file
                    # === unknown info obj address, object not found
                    bad_addr = (
                        i_frame()
                        / asdu_head(COT=47)
                        / asdu_infobj_46(IOA=info_obj_addr, DCS=field_val)
                    )
                    check_asdu_46(bad_addr, "m")
                    yield self.send_104frame(bad_addr)
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s  (%s)", ex, self.session_id)
        except AttributeError as ex:
            logger.warning(
                "Allocation for field %s not possible. (%s)", ex, self.session_id
            )

    def handle_setpointscaled_command49(self, container):
        try:
            check_asdu_49(container, "c")
            cause_of_transmission = int(container.getfieldval("COT"))
            info_obj_addr = container.getfieldval("IOA")
            field_val = container.getfieldval("SVA")
            if cause_of_transmission == 6:
                obj = self.device_data_controller.get_object_from_reg(
                    info_obj_addr
                )  # get destination object
                if not (obj is None):  # if exists in xml-file
                    obj_cat = int(obj.category_id)  # get type (double command)
                    if obj_cat == 49:  # if object has type double command
                        # === Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(COT=7)
                            / asdu_infobj_49(IOA=info_obj_addr, SVA=field_val)
                        )
                        check_asdu_49(act_con, "m")
                        yield self.send_104frame(act_con)

                        # === Get related info object if exists
                        obj_rel_addr = obj.relation
                        if obj_rel_addr != "":  # if relation available
                            obj_rel_addr_hex = addr_in_hex(
                                obj_rel_addr
                            )  # get double point object address
                            # get the double point object
                            obj_rel = self.device_data_controller.get_object_from_reg(
                                obj_rel_addr_hex
                            )
                            obj.val = field_val  # set the value in the object to the command value
                            obj_rel.val = field_val  # set the value in the relation object to the command value
                            # test whether if it really updated the value
                            changed_val = obj_rel.val
                            setpoint_scaled = (
                                i_frame()
                                / asdu_head(COT=3)
                                / asdu_infobj_11(IOA=obj_rel_addr_hex, SVA=changed_val)
                            )
                            setpoint_scaled.show2()
                            yield self.send_104frame(setpoint_scaled)

                        # === Activation termination
                        act_term = (
                            i_frame()
                            / asdu_head(COT=10)
                            / asdu_infobj_49(IOA=info_obj_addr, SVA=field_val)
                        )
                        check_asdu_49(act_term, "m")
                        yield self.send_104frame(act_term)
                    else:  # if command type doesn't fit
                        # === neg. Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(PN=1, COT=7)
                            / asdu_infobj_49(IOA=info_obj_addr, SVA=field_val)
                        )
                        check_asdu_49(act_con, "m")
                        yield self.send_104frame(act_con)
                else:  # object doesn't exist in xml file
                    # === unknown info obj address, object not found
                    bad_addr = (
                        i_frame()
                        / asdu_head(COT=47)
                        / asdu_infobj_49(IOA=info_obj_addr, SVA=field_val)
                    )
                    check_asdu_49(bad_addr, "m")
                    yield self.send_104frame(bad_addr)
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s  (%s)", ex, self.session_id)
        except AttributeError as ex:
            logger.warning(
                "Allocation for field %s not possible. (%s)", ex, self.session_id
            )

    def handle_setpointfloatpoint_command50(self, container):
        try:
            check_asdu_50(container, "c")
            cause_of_transmission = int(container.getfieldval("COT"))
            info_obj_addr = container.getfieldval("IOA")
            field_val = container.getfieldval("FPNumber")
            if cause_of_transmission == 6:
                obj = self.device_data_controller.get_object_from_reg(
                    info_obj_addr
                )  # get destination object
                if not (obj is None):  # if exists in xml-file
                    obj_cat = int(obj.category_id)  # get type (double command)
                    if obj_cat == 50:  # if object has type double command
                        # === Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(COT=7)
                            / asdu_infobj_50(IOA=info_obj_addr, FPNumber=field_val)
                        )
                        check_asdu_50(act_con, "m")
                        yield self.send_104frame(act_con)

                        # === Get related info object if exists
                        obj_rel_addr = obj.relation
                        if obj_rel_addr != "":  # if relation available
                            obj_rel_addr_hex = addr_in_hex(
                                obj_rel_addr
                            )  # get double point object address
                            # get the double point object
                            obj_rel = self.device_data_controller.get_object_from_reg(
                                obj_rel_addr_hex
                            )
                            obj.val = field_val  # set the value in the object to the command value
                            obj_rel.val = field_val  # set the value in the relation object to the command value
                            # test whether if it really updated the value
                            changed_val = obj_rel.val
                            setpoint_scaled = (
                                i_frame()
                                / asdu_head(COT=3)
                                / asdu_infobj_13(
                                    IOA=obj_rel_addr_hex, FPNumber=changed_val
                                )
                            )
                            yield self.send_104frame(setpoint_scaled)

                        # === Activation termination
                        act_term = (
                            i_frame()
                            / asdu_head(COT=10)
                            / asdu_infobj_50(IOA=info_obj_addr, FPNumber=field_val)
                        )
                        check_asdu_50(act_term, "m")
                        yield self.send_104frame(act_term)
                    else:  # if command type doesn't fit
                        # === neg. Activation confirmation
                        act_con = (
                            i_frame()
                            / asdu_head(PN=1, COT=7)
                            / asdu_infobj_50(IOA=info_obj_addr, FPNumber=field_val)
                        )
                        check_asdu_50(act_con, "m")
                        yield self.send_104frame(act_con)
                else:  # object doesn't exist in xml file
                    # === unknown info obj address, object not found
                    bad_addr = (
                        i_frame()
                        / asdu_head(COT=47)
                        / asdu_infobj_50(IOA=info_obj_addr, FPNumber=field_val)
                    )
                    check_asdu_50(bad_addr, "m")
                    yield self.send_104frame(bad_addr)
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s  (%s)", ex, self.session_id)
        except AttributeError as ex:
            logger.warning(
                "Allocation for field %s not possible. (%s)", ex, self.session_id
            )

    def handle_inro_command100(self, container):
        try:
            # check_asdu_100(container, "c")
            cause_of_transmission = container.getfieldval("COT")
            qualif_of_inro = container.getfieldval("QOI")
            if cause_of_transmission == 6:
                # === Activation confirmation for inro
                act_con_inro = (
                    i_frame() / asdu_head(COT=7) / asdu_infobj_100(QOI=qualif_of_inro)
                )
                check_asdu_100(act_con_inro, "m")
                yield self.send_104frame(act_con_inro)
                # === Inro response
                if qualif_of_inro == 20:
                    reg = self.device_data_controller.get_registers()
                    sorted_reg = natsort.natsorted(list(reg.items()))

                    # get response list for certain types
                    resp1_list = inro_response(sorted_reg, 1)
                    resp3_list = inro_response(sorted_reg, 3)
                    resp5_list = inro_response(sorted_reg, 5)
                    resp7_list = inro_response(sorted_reg, 7)
                    resp9_list = inro_response(sorted_reg, 9)
                    resp11_list = inro_response(sorted_reg, 11)
                    resp13_list = inro_response(sorted_reg, 13)

                    # send each packet from each list
                    for resp1 in resp1_list:
                        yield self.send_104frame(resp1)
                    for resp3 in resp3_list:
                        yield self.send_104frame(resp3)
                    for resp5 in resp5_list:
                        yield self.send_104frame(resp5)
                    for resp7 in resp7_list:
                        yield self.send_104frame(resp7)
                    for resp9 in resp9_list:
                        yield self.send_104frame(resp9)
                    for resp11 in resp11_list:
                        yield self.send_104frame(resp11)
                    for resp13 in resp13_list:
                        yield self.send_104frame(resp13)

                # === Activation termination
                act_term = (
                    i_frame() / asdu_head(COT=10) / asdu_infobj_100(QOI=qualif_of_inro)
                )
                check_asdu_100(act_con_inro, "m")
                yield self.send_104frame(act_term)
        except InvalidFieldValueException as ex:
            logger.warning("InvalidFieldValue: %s  (%s)", ex, self.session_id)
        except AttributeError as ex:
            logger.warning(
                "Allocation for field %s not possible.  (%s)", ex, self.session_id
            )

    def restart_t1(self):
        self.timeout_t1.cancel()
        self.timeout_t1 = gevent.Timeout(self.T_1, gevent.Timeout)
        self.timeout_t1.start()

    def show_send_list(self):
        list_temp = list()
        for frm in self.sentmsgs:
            if frm.name == "u_frame":
                u_type = str(hex(frm.getfieldval("Type")))
                list_temp.append("u(" + u_list[u_type] + ")")
            elif frm.name == "s_frame":
                s_type = frm.getfieldval("RecvSeq")
                list_temp.append("s(" + str(s_type) + ")")
            elif frm.name == "i_frame":
                i_send_seq = frm.getfieldval("SendSeq")
                i_recv_seq = frm.getfieldval("RecvSeq")
                list_temp.append("i(" + str(i_send_seq) + "," + str(i_recv_seq) + ")")
        print(list_temp)

    def disconnect(self):
        self.timeout_t1.cancel()
        if self.t2_caller:
            gevent.kill(self.t2_caller)
        self.sock.close()
        self.ssn = 0
        self.rsn = 0
        self.ack = 0
        self.telegram_count = 0

    def increment_sendseq(self):
        if self.ssn < 65534:
            self.ssn = self.ssn + 2
        else:
            self.ssn = 0

    def recvseq_increment(self):
        if self.rsn < 65534:
            self.rsn = self.rsn + 2
        else:
            self.rsn = 0

    # returns object list for SQ = 0
    @staticmethod
    def get_infoobj_list(frame):
        info_obj_list = []
        number_of_objects = frame.getfieldval("NoO")
        for i in range(3, number_of_objects + 3):
            info_obj_list.append(frame.getlayer(i))
        return info_obj_list


class frame_object_with_timer:
    def __init__(self, frame):
        self.frame = frame
        self.name = frame.name
        self.T_1 = conpot_core.get_databus().get_value("T_1")
        self.__timeout_t1 = gevent.Timeout(self.T_1, gevent.Timeout)

    def restart_t1(self):
        self.__timeout_t1.cancel()
        self.__timeout_t1 = gevent.Timeout(self.T_1, gevent.Timeout)
        self.__timeout_t1.start()

    def cancel_t1(self):
        self.__timeout_t1.cancel()

    def getfieldval(self, fieldval):
        return self.frame.getfieldval(fieldval)

    def build(self):
        return self.frame.build()
