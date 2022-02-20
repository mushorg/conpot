# Copyright (C) 2014  Andrea De Pasquale <andrea@de-pasquale.name>
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

import logging

import conpot.core as conpot_core

logger = logging.getLogger(__name__)


class BaseCommand(object):
    HELP_MESSAGE = ""
    CMD_OUTPUT = ""
    INVALID_PARAMETER = (
        "\r\n"
        "? Invalid parameter.\r\n"
        "Try 'H cmd' for specific help.\r\n"
        " Ie: H !SC\r\n"
    )

    def help(self):
        return self.HELP_MESSAGE

    def run(self, params=None):
        return self.CMD_OUTPUT


class HelpCommand(BaseCommand):
    CMD_OUTPUT = (
        "==============================================================================\r\n"
        "Service Menu\r\n"
        "==============================================================================\r\n"
        "H:   Help [cmd].\r\n"
        "Q:   Close connection.\r\n"
        "!AC: Access control.\r\n"
        "!AS: Alarm Server.\r\n"
        "!GC: Get Config.\r\n"
        "!GV: Software version.\r\n"
        "!SA: Set KAP Server IP and port (*1).\r\n"
        "!SB: Set 2nd KAP Server IP and port.\r\n"
        "!SC: Set Config (*1).\r\n"
        "!SD: Set device name (*1).\r\n"
        "!SH: Set KAP Server lookup (DNS or DHCP)\r\n"
        "!SI: Set IP (enter either valid IP or 0 to force DHCP)(*1).\r\n"
        "!SK: Set KAP watchdog timeout(WDT).\r\n"
        "!SN: Set IP for DNS Name servers to use.\r\n"
        "!SP: Set IP Ports\r\n"
        "!SS: Set Serial Settings.\r\n"
        "!RC: Request connect\r\n"
        "!RR: Request restart (*1).\r\n"
        "!WM: Wink module.\r\n"
        "==============================================================================\r\n"
        "(*1) Forces system restart\r\n"
        "==============================================================================\r\n"
        "Kamstrup (R)\r\n"
    )

    def __init__(self, commands):
        self.commands = commands

    def run(self, params=None):
        if params is None:
            return self.CMD_OUTPUT

        c = params[0:3]
        if c in list(self.commands.keys()):
            return self.commands[c].help()

        return self.INVALID_PARAMETER


class AccessControlCommand(BaseCommand):
    HELP_MESSAGE = (
        "!AC: Access control.\r\n"
        "     Used for simple IP address firewall filtering.\r\n"
        "     If enabled only the listed IP's can assess this module.\r\n"
        "      Format:  !AC [En/Dis [ID IP]]\r\n"
        "      Example: !AC\r\n"
        "               Lists the setup.\r\n"
        "      Example: !AC 0\r\n"
        "               Disables the filter allowing everybody to access.\r\n"
        "      Example: !AC 0 1 192.168.1.211\r\n"
        "               !AC 0 2 10.0.0.1\r\n"
        "               !AC 0 3 195.215.168.45\r\n"
        "               !AC 1\r\n"
        "               Only connections from 192.168.1.211, \r\n"
        "               10.0.0.1 or 195.215.168.45 are possible.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "{access_control_status} \r\n"
        " [1] {access_control_1}\r\n"
        " [2] {access_control_2}\r\n"
        " [3] {access_control_3}\r\n"
        " [4] {access_control_4}\r\n"
        " [5] {access_control_5}\r\n"
    )

    def set_access_ip(self, number, ip_string):
        databus = conpot_core.get_databus()
        if ip_string.count(".") == 3:
            if any(x in number for x in ["1", "2", "3", "4", "5"]):
                acl_number = int(number)
                final_ip = parse_ip(ip_string)
                databus.set_value("access_control_{0}".format(acl_number), final_ip)

    def run(self, params=None):
        databus = conpot_core.get_databus()
        cmd_output = ""
        if params:
            # return is always OK apparently...
            cmd_output = "\r\nOK\r\n"
            if len(params) == 1 and params == "0":
                databus.set_value("access_control_status", "DISABLED")
            elif len(params) == 1 and params == "1":
                databus.set_value("access_control_status", "ENABLED")
            elif len(params.split(" ")) == 3:
                cmd, acl_number, ip_address = params.split(" ")
                if cmd == "0":
                    self.set_access_ip(acl_number, ip_address)

        return cmd_output + self.CMD_OUTPUT.format(
            access_control_status=databus.get_value("access_control_status"),
            access_control_1=databus.get_value("access_control_1"),
            access_control_2=databus.get_value("access_control_2"),
            access_control_3=databus.get_value("access_control_3"),
            access_control_4=databus.get_value("access_control_4"),
            access_control_5=databus.get_value("access_control_5"),
        )


class AlarmServerCommand(BaseCommand):
    HELP_MESSAGE = (
        "!AS: Alarm Server.\r\n"
        "     Used to set IP and port of server to handle alarm notifications.\r\n"
        "      Format:  !AS [SrvIP [SrvPort]]\r\n"
        "      Example: !AS 195.215.168.45 \r\n"
        "               Alarms are sent to 195.215.168.45.\r\n"
        "      Example: !AS 195.215.168.45 4000\r\n"
        "               Alarms are sent to to port 4000 on 195.215.168.45.\r\n"
        "      Example: !AS 0.0.0.0\r\n"
        "               Alarm reporting is disabled.\r\n"
    )

    CMD_OUTPUT = "\r\n" "Alarm server:  {alarm_server_output} "  # no CRLF

    def run(self, params=None):
        databus = conpot_core.get_databus()
        output_prefix = ""
        output_postfix = ""
        if not params:
            if databus.get_value("alarm_server_status") == "DISABLED":
                output = "DISABLED"
            else:
                output = "{0}:{1}".format(
                    databus.get_value("alarm_server_ip"),
                    databus.get_value("alarm_server_port"),
                )
        else:
            output_prefix = "\r\nOK"
            # in this case the command has CRLF... really funky...
            output_postfix = "\r\n"
            databus.set_value("alarm_server_status", "ENABLED")
            params_split = params.split(" ")
            databus.set_value("alarm_server_ip", parse_ip(params_split[0]))
            # port provided also
            if len(params_split) > 1:
                port = parse_port(params_split[1])
                if port != 0:
                    databus.set_value("alarm_server_port", port)
            output = "{0}:{1}".format(
                databus.get_value("alarm_server_ip"),
                databus.get_value("alarm_server_port"),
            )
        return (
            output_prefix
            + self.CMD_OUTPUT.format(alarm_server_output=output)
            + output_postfix
        )


class GetConfigCommand(BaseCommand):
    HELP_MESSAGE = "!GC: Get Config.\r\n" "     Returns the module configuration.\r\n"

    CMD_OUTPUT = (
        "Device Name         : {device_name}\r\n"
        "Use DHCP            : {use_dhcp}\r\n"
        "IP addr.            : {ip_addr}\r\n"
        "IP Subnet           : {ip_subnet}\r\n"
        "Gateway addr.       : {ip_gateway}\r\n"
        "Service server addr.: {service_server_ip}\r\n"
        "Service server hostname.: {service_server_host}\r\n"
        "DNS Server No. 1: {nameserver_1}\r\n"
        "DNS Server No. 2: {nameserver_2}\r\n"
        "DNS Server No. 3: {nameserver_3}\r\n"
        "MAC addr. (HEX)     : {mac_address}\r\n"
        # TODO: i think was can get these from the other protocol also
        "Channel A device meterno.: {channel_a_meternumber}\r\n"
        "Channel B device meterno.: {channel_b_meternumber}\r\n"
        # TODO: these...
        "Keep alive timer (flash setting): ENABLED 10\r\n"
        "Keep alive timer (current setting): ENABLED 10\r\n"
        "Has the module received acknowledge from the server: {kap_ack_server}\r\n"
        "KAP Server port: {kap_a_server_port}\r\n"
        "KAP Local port: {kap_local_port}\r\n"
        # TODO: This, read from other proto also?
        "Software watchdog: ENABLED 3600\r\n"
    )

    def run(self, params=None):
        databus = conpot_core.get_databus()
        return self.CMD_OUTPUT.format(
            device_name=databus.get_value("device_name"),
            nameserver_1=databus.get_value("nameserver_1"),
            nameserver_2=databus.get_value("nameserver_2"),
            nameserver_3=databus.get_value("nameserver_3"),
            mac_address=databus.get_value("mac_address"),
            use_dhcp=databus.get_value("use_dhcp"),
            ip_addr=databus.get_value("ip_addr"),
            ip_subnet=databus.get_value("ip_subnet"),
            ip_gateway=databus.get_value("ip_gateway"),
            service_server_ip=databus.get_value("kap_a_server_ip"),
            service_server_host=databus.get_value("kap_a_server_hostname"),
            channel_a_meternumber=databus.get_value("channel_a_meternumber"),
            channel_b_meternumber=databus.get_value("channel_b_meternumber"),
            kap_ack_server=databus.get_value("kap_ack_server"),
            kap_a_server_port=databus.get_value("kap_a_server_port"),
            kap_local_port=databus.get_value("kap_local_port"),
        )


class SoftwareVersionCommand(BaseCommand):
    HELP_MESSAGE = (
        "!GV: Software version.\r\n"
        "     Returns the software revision of the module.\r\n"
    )

    CMD_OUTPUT = "\r\n" "Software Version: {software_version}\r\n"

    def run(self, params=None):
        return self.CMD_OUTPUT.format(
            software_version=conpot_core.get_databus().get_value("software_version")
        )


class SetKap1Command(BaseCommand):
    HELP_MESSAGE = (
        "!SA: Set KAP Server IP and port (*1).\r\n"  # restart is not forced...
        "     Used for setting the IP of the Server to receive KAP-pacakeges.\r\n"
        "     UDP port on server can be provided optionally.\r\n"
        "      Format:  !SA SrvIP [SrvPort]\r\n"
        "      Example: !SA 195215168045 \r\n"
        "               KAP packages are hereafter sent to 195.215.168.45.\r\n"
        "      Example: !SA 195.215.168.45 \r\n"
        '               Same result as "!SA 195215168045".\r\n'
        "      Example: !SA 192168001002 61000\r\n"
        "               KAP packages are hereafter sent to 192.168.1.2:61000\r\n"
        "               from module port 8000.\r\n"
        "      Example: !SA 0.0.0.0 \r\n"
        "               Disables KAP.\r\n"
    )

    CMD_OUTPUT = "\r\n" "Service server addr.: {kap_a_output}\r\n"

    def run(self, params=None):
        databus = conpot_core.get_databus()
        if params:
            output_prefix = "\r\nOK"
            params_split = params.split(" ")
            databus.set_value("kap_a_server_ip", parse_ip(params_split[0]))
            # TODO: The meter might do a lookup on the ip, and the result of that
            # lookup might be stored in a_server_host...
            databus.set_value("kap_a_server_hostname", "0 - none")
            # port provided also
            if len(params_split) > 1:
                port = parse_port(params_split[1])
                if port != 0:
                    databus.set_value("kap_a_server_port", port)
        else:
            output_prefix = "\r\n"
        output = "{0}:{1}".format(
            databus.get_value("kap_a_server_ip"), databus.get_value("kap_a_server_port")
        )
        return output_prefix + self.CMD_OUTPUT.format(kap_a_output=output)


class SetKap2Command(BaseCommand):
    HELP_MESSAGE = (
        "!SB: Set 2nd KAP Server IP and port.\r\n"
        "     Used for redundancy with two KAP servers.\r\n"
        "     When enabled every second KAP is send to the IP defined by !SB.\r\n"
        "     NB: The KAP interval to each individual server is half of KAPINT\r\n"
        "         defined by !SK.\r\n"
        "     NB: !SA must be enabled (not 0.0.0.0) \r\n"
        "      Format:  !SB SrvIP [SrvPort]\r\n"
        "      Example: !SB 195.215.168.45 \r\n"
        "               KAP packages are hereafter also sent to 195.215.168.45.\r\n"
        "      Example: !SB 0.0.0.0 \r\n"
        "               Disabled.\r\n"
        "      Example: !SB 192.168.1.2 61000\r\n"
        "               KAP packages are hereafter sent to 192.168.1.2:61000\r\n"
        "               from module port 8000.\r\n"
    )

    CMD_OUTPUT_SINGLE = (
        "\r\n" "{}\r\n" "Service server addr.: {}:{} (from DNS)\r\n" "No redundancy."
    )

    CMD_OUTPUT_DOUBLE = (
        "\r\n"
        "{}\r\n"
        "Service server addr.: {}:{} (from DNS)\r\n"
        "and fallback KAP to:  {}:{}\r\n"
    )

    def run(self, params=None):
        databus = conpot_core.get_databus()
        cmd_ok = ""
        if params:
            cmd_ok = "OK"
            params_split = params.split(" ")
            databus.set_value("kap_b_server_ip", parse_ip(params_split[0]))
            if len(params_split) > 1:
                port = parse_port(params_split[1])
                if port != 0:
                    databus.set_value("kap_b_server_port", params_split[1])

        if databus.get_value("kap_b_server_ip") == "0.0.0.0":
            return self.CMD_OUTPUT_SINGLE.format(
                cmd_ok,
                databus.get_value("kap_a_server_ip"),
                databus.get_value("kap_a_server_port"),
            )
        return self.CMD_OUTPUT_DOUBLE.format(
            cmd_ok,
            databus.get_value("kap_a_server_ip"),
            databus.get_value("kap_a_server_port"),
            databus.get_value("kap_b_server_ip"),
            databus.get_value("kap_b_server_port"),
        )


class SetConfigCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SC: Set Config (*1).\r\n"
        "     Configures the module.\r\n"
        "      Format:  !SC DHCP IP SUB GW DNS1 DNS2 DNS3 SRV_IP DEVICENAME SRV_DNS\r\n"
        "               DHCP        1 for DHCP, 0 for static IP.\r\n"
        "               IP..        Static IP settings.\r\n"
        "               SRV_IP      IP of remote server (Only if SRV_DNS is 0).\r\n"
        "               DEVICENAME  User label for for individual naming.\r\n"
        "               SRV_DNS     DNS name of remote server (0 to disable DNS lookup)\r\n"
    )

    CMD_OUTPUT = "\r\n" "Service server hostname.: {}\r\n"

    def run(self, params=None):
        databus = conpot_core.get_databus()
        if params:
            params_split = params.split(" ")
            if len(params_split) >= 10:

                if params_split[0] == "1":
                    databus.set_value("use_dhcp", "YES")
                else:
                    databus.set_value("use_dhcp", "NO")
                    databus.set_value("ip_addr", parse_ip(params_split[1]))
                    databus.set_value("ip_subnet", parse_ip(params_split[2]))
                    databus.set_value("ip_gateway", parse_ip(params_split[3]))

                databus.set_value("nameserver_1", parse_ip(params_split[4]))
                databus.set_value("nameserver_2", parse_ip(params_split[5]))
                databus.set_value("nameserver_3", parse_ip(params_split[6]))

                if params_split[9] == "0":
                    databus.set_value("kap_a_server_ip", parse_ip(params_split[7]))
                    databus.set_value("kap_a_server_hostname", "0 - none")
                else:
                    databus.set_value("kap_a_server_hostname", params_split[9])
                    # FIXME: server IP should be resolved from the hostname
                    # using nameserver_1, nameserver_2, nameserver_3
                    databus.set_value("kap_a_server_ip", parse_ip(params_split[7]))

                device_name = params_split[8]
                if len(device_name) > 20:
                    device_name = device_name[0:20]
                databus.set_value("device_name", device_name)

        databus.set_value("reboot_signal", 1)


class SetDeviceNameCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SD: Set device name (*1).\r\n"
        "     Option for individual naming of the module (0-20 chars).\r\n"
    )

    def run(self, params=None):
        if params is None:
            params = ""

        if len(params) > 20:
            params = params[0:20]
            output = ""
        else:
            output = "\r\nOK"

        databus = conpot_core.get_databus()
        databus.set_value("device_name", params)
        databus.set_value("reboot_signal", 1)
        return output


class SetLookupCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SH: Set KAP Server lookup (DNS or DHCP)\r\n"
        "     Used for setting the DNS name of the Server to receive KAP-pacakeges.\r\n"
        '     Using the keyword "DHCP_OPTION:xxx" makes the module request the IP using DHCP option xxx.\r\n'
        "     The settings are first activated when the module is reset (using !RR).\r\n"
        "      Example: !SH 0 \r\n"
        "               Lookup Disabled.\r\n"
        "               The module will send KAP to the IP listed by !SA. \r\n"
        "      Example: !SH hosting.kamstrup_meter.dk \r\n"
        "               Use DNS lookup.\r\n"
        "               The module will send KAP to the IP listed by !SA until it resolves the DNS,\r\n"
        "               hereafter the KAP will be sent to hosting.kamstrup_meter.dk\r\n"
        "      Example: !SH DHCP_OPTION:129\r\n"
        "               Use DHCP Option.\r\n"
        "               The module will send KAP to the IP provided by DHCP (in this case option 129).\r\n"
        "               The module uses the IP provided by !SA if the DHCP offer dos not include option xxx data.\r\n"
    )

    def run(self, params=None):
        if params is None:
            params = ""

        output = "\r\n"

        databus = conpot_core.get_databus()
        # no, i am not making this up... this is actually how it is implemented on the Kamstrup meter..
        if len(params) == 1:
            databus.set_value("kap_server_lookup", "0 - none")
            output = "\r\nOK" + output
        elif len(params) > 1:
            databus.set_value("kap_server_lookup", params)
            output = "\r\nOK" + output

        output += "Service server hostname.: {0}\r\n"
        return output.format(databus.get_value("kap_server_lookup"))


class SetIPCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SI: Set IP (enter either valid IP or 0 to force DHCP)(*1).\r\n"
        "     Used for changing the module IP.\r\n"
        "     (Use !SC if you need to change subnet/Gateway too).\r\n"
        "     Entering a '0' will enable DHCP.\r\n"
        "      Format:  !SI IP\r\n"
        "      Example: !SI 0\r\n"
        "               The module will reboot and acuire the IP settings using DHCP.\r\n"
        "      Example: !SI 192168001200\r\n"
        "               The module will reboot using static IP addr 192.168.1.200.\r\n"
        "               (SUB, GW and DNS unchanged)\r\n"
        "      Example: !SI 192.168.1.200\r\n"
        "               Same as !SI 192168001200.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "Use DHCP            : {use_dhcp}\r\n"
        "\r\n"
        "IP addr.            : {ip_addr}\r\n"
    )

    def run(self, params=None):
        databus = conpot_core.get_databus()
        if params:
            ip_addr = parse_ip(params)
            if ip_addr == "0.0.0.0":
                if databus.get_value("use_dhcp") == "NO":
                    databus.set_value("use_dhcp", "YES")
                    databus.set_value("ip_addr", databus.get_value("ip_addr_dhcp"))
                    databus.set_value(
                        "ip_gateway", databus.get_value("ip_gateway_dhcp")
                    )
                    databus.set_value("ip_subnet", databus.get_value("ip_subnet_dhcp"))
                    databus.set_value("reboot_signal", 1)
            else:
                databus.set_value("use_dhcp", "NO")
                databus.set_value("ip_addr", ip_addr)
                databus.set_value("reboot_signal", 1)

        return self.CMD_OUTPUT.format(
            use_dhcp=databus.get_value("use_dhcp"), ip_addr=databus.get_value("ip_addr")
        )


class SetWatchdogCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SK: Set KAP watchdog timeout(WDT).\r\n"
        "     Used for setting KeepAlive watchdog timing.\r\n"
        "      Format:  !SK [WDT] [MISSING] [KAPINT]\r\n"
        "      Example: !SK\r\n"
        "      Example: !SK 3600\r\n"
        "      Example: !SK 3600 60 10\r\n"
        "               WDT     The module reboots after WDT?KAPINT seconds\r\n"
        "                       without an ACK from the server.\r\n"
        "                       0 = disable WDT.\r\n"
        "               MISSING After MISSING?KAPINT seconds without an ACK,\r\n"
        "                       the Err LED starts blinking.\r\n"
        "                       (Used for indication of missing link to the server)\r\n"
        "               KAPINT  Interval in seconds for how often KeepAlivePackages\r\n"
        "                       are send to the KAP server.\r\n"
        "     The WDT and MISSING timeout counts are both reset by an ACK from the server.                       \r\n"
    )

    CMD_OUTPUT = (
        "Software watchdog: {0}\r\n"
        "KAP Missing warning: {1}\r\n"
        "Keep alive timer (flash setting): {2}\r\n"
    )

    def run(self, params=None):
        output = "\r\n"
        databus = conpot_core.get_databus()

        if params is not None:
            params_split = params.split(" ")

            if len(params_split) > 0:
                # meh, actually the real value is non-existing. If you supply a larger value the smart meter
                # just overwrite memory and starts writing to the next memory location - yep, you heard it here first!
                watchdog_value = str(
                    try_parse_uint(params_split[0], min_value=5, max_value=4294967295)
                )
                databus.set_value("software_watchdog", watchdog_value)
                if len(params_split) > 1:
                    kap_missing = str(
                        try_parse_uint(
                            params_split[1], min_value=0, max_value=4294967295
                        )
                    )
                    databus.set_value("kap_missing_warning", kap_missing)
                if len(params_split) > 2:
                    keep_alive_timer = str(
                        try_parse_uint(
                            params_split[2], min_value=0, max_value=4294967295
                        )
                    )
                    databus.set_value("keep_alive_timer", keep_alive_timer)
                output = "\r\nOK" + output

        return_values = [
            databus.get_value("software_watchdog"),
            databus.get_value("kap_missing_warning"),
            databus.get_value("keep_alive_timer"),
        ]

        for i in range(0, len(return_values)):
            if return_values[i] == "0":
                return_values[i] = "DISABLED {0}".format(return_values[i])
            else:
                return_values[i] = "ENABLED {0}".format(return_values[i])

        output += SetWatchdogCommand.CMD_OUTPUT.format(
            return_values[0], return_values[1], return_values[2]
        )

        return output.format(databus.get_value("kap_server_lookup"))


class SetNameserverCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SN: Set IP for DNS Name servers to use.\r\n"
        "      Format:  !SN DNS1 DNS2 DNS3\r\n"
        "      Example: !SN 192168001200 192168001201 000000000000\r\n"
        "      Example: !SN 172.16.0.83 172.16.0.84 0.0.0.0\r\n"
    )

    def run(self, params=None):
        if params is None:
            return self.INVALID_PARAMETER

        nameservers = params.split(" ")
        if len(nameservers) != 3:
            return self.INVALID_PARAMETER

        databus = conpot_core.get_databus()
        databus.set_value("nameserver_1", parse_ip(nameservers[0]))
        databus.set_value("nameserver_2", parse_ip(nameservers[1]))
        databus.set_value("nameserver_3", parse_ip(nameservers[2]))
        return "\r\nOK"


class SetPortsCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SP: Set IP Ports\r\n"
        "      Format:  !SP [KAP CHA CHB CFG]\r\n"
        "      Example: !SP 333\r\n"
        "               KAP packages are hereafter sent to port 333 on the server.\r\n"
        "      Example: !SP 50 1025 1026 50100\r\n"
        "               KAP packages are sent to port 50.\r\n"
        "               Direct connections to UART channel A is on port 1025, B on 1026.\r\n"
        "               Config connection on port 50100.\r\n"
        "               (default values)\r\n"
        "      Example: !SP 0 0 80\r\n"
        "               UART channel B is on port 80 (KAP and ChA is ingored - unchanged).\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "{}\r\n"
        "KAP on server: {}\r\n"
        "ChA on module: {}\r\n"
        "ChB on module: {}\r\n"
        "Cfg on module: {}\r\n"
    )

    def run(self, params=None):
        databus = conpot_core.get_databus()
        cmd_ok = ""
        if params:
            params_split = params.split(" ")
            cmd_ok = "OK"

            kap_port = parse_port(params_split[0])
            if kap_port != 0:
                databus.set_value("kap_a_server_port", kap_port)

            if len(params_split) > 1:
                cha_port = parse_port(params_split[1])
                if cha_port != 0:
                    databus.set_value("channel_a_port", cha_port)

            if len(params_split) > 2:
                chb_port = parse_port(params_split[2])
                if chb_port != 0:
                    databus.set_value("channel_b_port", chb_port)

            # FIXME: how do we change the port we are connected to?
            # if len(params_split) > 3:
            # cfg_port = parse_port(params_split[3])
            # if cfg_port != 0:
            # databus.set_value("", cfg_port)

        return self.CMD_OUTPUT.format(
            cmd_ok,
            databus.get_value("kap_a_server_port"),
            databus.get_value("channel_a_port"),
            databus.get_value("channel_b_port"),
            50100,
        )  # FIXME: see above


class SetSerialCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SS: Set Serial Settings.\r\n"
        "     Used for setting the serial interface for channel A or B.\r\n"
        "      Format:  !SS [Channel Baud,DataBits,Parity,StopBits[,Ctrl]]\r\n"
        "      Example: !SS A Auto\r\n"
        "      Example: !SS A 9600,8,N,2\r\n"
        "      Example: !SS B 115200,8,E,1\r\n"
        "      Example: !SS B 115200,8,E,1,I\r\n"
        "      Example: !SS B 115200,8,E,1,L\r\n"
        "     The ctrl flag can be 'C'(check), 'I' (ignore framing errors) or 'L' (Link, ChB only).\r\n"
        "     Chanel A supports auto mode (Also enables load profile logger in old E-Meters).\r\n"
    )

    def run(self, params=None):
        databus = conpot_core.get_databus()
        invalid_message = "\r\nInvalid data!\r\n\r\n"
        if params:
            params_split = params.split(" ")
            if len(params_split) == 2:
                output = "\r\nOK\r\n"
                if params_split[0] == "A":
                    databus.set_value("serial_settings_a", params_split[1])
                elif params_split[0] == "B":
                    databus.set_value("serial_settings_b", params_split[1])
                else:
                    return invalid_message
            else:
                return invalid_message
        else:
            output = "\r\n" "UART A setup : {0}\r\n" "UART B setup : {1}\r\n"

        return output.format(
            databus.get_value("serial_settings_a"),
            databus.get_value("serial_settings_b"),
        )


class RequestConnectCommand(BaseCommand):
    HELP_MESSAGE = (
        "!RC: Request connect\r\n"
        "     Makes the module crate a ChA or ChB socket to a remote server.\r\n"
        "      Format:  !RC Action [IP [Port]]\r\n"
        "      Example: !RC A 195.215.168.45 200\r\n"
        "      Example: !RC B 195.215.168.45 201\r\n"
        "      Example: !RC D\r\n"
        "               Disconnects both A and B if open.\r\n"
        "      Example: !RC\r\n"
        "               Status only.\r\n"
    )

    def run(self, params):
        databus = conpot_core.get_databus()
        # TODO: Further investigations needed... How does this remote socket work? How should copot react?
        output = "Status: 0100\r\n"
        if params:
            params_split = params.split(" ")
            output = "\r\nOK\r\n" + output
            if len(params_split) == 1 and params_split[0] == "D":
                pass
            elif len(params_split) == 2:
                channel, value = params_split
                if channel == "A":
                    # TODO: figure out how these are parsed when meter is online again
                    databus.set_value("channel_a_connect_socket", value)
                elif channel == "B":
                    databus.set_value("channel_b_connect_socket", value)
                else:
                    return self.INVALID_PARAMETER
            else:
                return self.INVALID_PARAMETER
        else:
            output = "\r\n" + output

        return output


class RequestRestartCommand(BaseCommand):
    HELP_MESSAGE = "!RR: Request restart (*1).\r\n"

    def run(self, params=None):
        conpot_core.get_databus().set_value("reboot_signal", 1)
        return


class WinkModuleCommand(BaseCommand):
    HELP_MESSAGE = (
        "!WM: Wink module.\r\n"
        "     Causes the WINK LED on the module to blink for physical identification.\r\n"
    )

    # no other output
    CMD_OUTPUT = "\r\n" "\r\n" "OK\r\n"


def parse_ip(ip_string):
    default = "0.0.0.0"
    if "." in ip_string:
        octets = ip_string.split(".")
    else:
        octets = [int(ip_string[i : i + 3]) for i in range(0, len(ip_string), 3)]

    if len(octets) != 4:
        return default
    for octet in octets:
        if int(octet) < 0 or int(octet) > 255:
            return default
    return ".".join(list(map(str, octets)))


def parse_port(port_string):
    try:
        port = int(port_string)
        if 0 < port < 65536:
            return port
        return 0
    except ValueError:
        return 0


def try_parse_uint(uint_string, min_value=0, max_value=254):
    try:
        value = int(uint_string)
        if value < min_value or value > max_value:
            value = 0
    except ValueError:
        value = "0"
    return value
