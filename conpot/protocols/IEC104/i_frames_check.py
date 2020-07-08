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


from conpot.protocols.IEC104.errors import InvalidFieldValueException


# direction either "m" for Monitor or "c" for control. Empty if irrelevant
# identical for some process information in monitor direction
def check_information_without_time(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("COT") in (2, 3, 5, 11, 12, 20):
        pass
    else:
        raise InvalidFieldValueException(
            "Invalid COT for ASDU type " + str(type_id) + "."
        )


# identical for some process information in monitor direction
def check_information_with_time(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("SQ") == 0:
        if frame.getfieldval("COT") in (3, 5, 11, 12):
            pass
        else:
            raise InvalidFieldValueException(
                "Invalid COT for ASDU type " + str(type_id) + "."
            )
    else:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )


def check_asdu_1(frame, direction):
    check_information_without_time(frame, direction)


def check_asdu_2(frame, direction):
    check_information_with_time(frame, direction)


def check_asdu_3(frame, direction):
    check_information_without_time(frame, direction)


def check_asdu_4(frame, direction):
    check_information_with_time(frame, direction)


def check_asdu_11(frame, direction):
    check_information_without_time(frame, direction)


def check_asdu_12(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("SQ") == 0:
        if frame.getfieldval("COT") in (3, 5):
            pass
        else:
            raise InvalidFieldValueException(
                "Invalid COT for ASDU type " + str(type_id) + "."
            )
    else:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )


def check_asdu_13(frame, direction):
    check_information_without_time(frame, direction)


def check_asdu_14(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("SQ") == 0:
        if frame.getfieldval("COT") in (2, 3, 5, 11, 12, 20):
            pass
        else:
            raise InvalidFieldValueException(
                "Invalid COT for ASDU type " + str(type_id) + "."
            )
    else:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )


def check_asdu_30(frame, direction):
    check_information_with_time(frame, direction)


def check_asdu_31(frame, direction):
    check_information_with_time(frame, direction)


def check_asdu_35(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("SQ") == 0:
        if frame.getfieldval("COT") in (3, 5):
            pass
        else:
            raise InvalidFieldValueException(
                "Invalid COT for ASDU type " + str(type_id) + "."
            )
    else:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )


def check_asdu_36(frame, direction):
    type_id = int(frame.getfieldval("TypeID"), 16)
    if frame.getfieldval("SQ") == 0:
        if frame.getfieldval("COT") in (2, 3, 5, 11, 12, 20):
            pass
        else:
            raise InvalidFieldValueException(
                "Invalid COT for ASDU type " + str(type_id) + "."
            )
    else:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )


# identical for process information in control direction
def check_command(frame, direction):
    type_id = int(frame.getfieldval("TypeID"))
    if frame.getfieldval("SQ") != 0:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )
    if frame.getfieldval("COT") in (6, 8) and direction == "c":
        pass
    elif frame.getfieldval("COT") in (7, 9, 10, 44, 45, 46, 47) and direction == "m":
        pass
    else:
        raise InvalidFieldValueException(
            "Invalid COT for ASDU type " + str(type_id) + "."
        )
    number_of_objects = frame.getfieldval("NoO")
    if number_of_objects != 1:
        raise InvalidFieldValueException(
            "Only one object allowed for ASDU type " + str(type_id) + "."
        )


def check_asdu_45(frame, direction):
    check_command(frame, direction)
    if direction == "c" and frame.getfieldval("LenAPDU") != 14:
        raise InvalidFieldValueException("Illogical length")


def check_asdu_46(frame, direction):
    check_command(frame, direction)


def check_asdu_47(frame, direction):
    check_command(frame, direction)


def check_asdu_48(frame, direction):
    check_command(frame, direction)


def check_asdu_49(frame, direction):
    check_command(frame, direction)


def check_asdu_50(frame, direction):
    check_command(frame, direction)


def check_asdu_51(frame, direction):
    check_command(frame, direction)


def check_asdu_100(frame, direction):
    type_id = int(frame.getfieldval("TypeID"))
    number_of_objects = frame.getfieldval("NoO")
    cause_of_transmission = frame.getfieldval("COT")
    qualif_of_inro = frame.getfieldval("QOI")
    if frame.getfieldval("SQ") != 0:
        raise InvalidFieldValueException(
            "SQ=1 not supported for ASDU type " + str(type_id) + "."
        )
    if number_of_objects != 1:
        raise InvalidFieldValueException(
            "Only one object allowed for ASDU type " + str(type_id) + "."
        )
    if cause_of_transmission in (6, 8) and direction == "c":
        pass
    elif cause_of_transmission in (7, 9, 10, 44, 45, 46, 47) and direction == "m":
        pass
    else:
        raise InvalidFieldValueException(
            "Invalid COT for ASDU type " + str(type_id) + "."
        )
    if frame.getfieldval("IOA") != 0:
        raise InvalidFieldValueException(
            "IOA not 0 for ASDU type " + str(type_id) + "."
        )
    if qualif_of_inro not in (
        0,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
    ):
        raise InvalidFieldValueException(
            "Invalid QOI "
            + str(qualif_of_inro)
            + " for ASDU type "
            + str(type_id)
            + "."
        )
