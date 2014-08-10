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
        if c in self.commands.keys():
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
        "{} \r\n"
        " [1] {}\r\n"
        " [2] {}\r\n"
        " [3] {}\r\n"
        " [4] {}\r\n"
        " [5] {}\r\n"
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

    CMD_OUTPUT = (
        "\r\n"
        "Alarm server:  {} "  # no CRLF
    )


class GetConfigCommand(BaseCommand):
    HELP_MESSAGE = (
        "!GC: Get Config.\r\n"
        "     Returns the module configuration.\r\n"
    )

    CMD_OUTPUT = (
        "Device Name         : {}\r\n"
        "Use DHCP            : {}\r\n"
        "IP addr.            : {}\r\n"
        "IP Subnet           : {}\r\n"
        "Gateway addr.       : {}\r\n"
        "Service server addr.: {}\r\n"
        "Service server hostname.: {}\r\n"
        "DNS Server No. 1: {}\r\n"
        "DNS Server No. 2: {}\r\n"
        "DNS Server No. 3: {}\r\n"
        "MAC addr. (HEX)     : {}\r\n"
        "Channel A device meterno.: {}\r\n"
        "Channel B device meterno.: {}\r\n"
        "Keep alive timer (flash setting): {} {}\r\n"
        "Keep alive timer (current setting): {} {}\r\n"
        "Has the module received acknowledge from the server: {}\r\n"
        "KAP Server port: {}\r\n"
        "KAP Local port: {}\r\n"
        "Software watchdog: {} {}\r\n"
    )


class SoftwareVersionCommand(BaseCommand):
    HELP_MESSAGE = (
        "!GV: Software version.\r\n"
        "     Returns the software revision of the module.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "Software Version: {}\r\n"
    )


class SetKap1Command(BaseCommand):
    HELP_MESSAGE = (
        "!SA: Set KAP Server IP and port (*1).\r\n"
        "     Used for setting the IP of the Server to receive KAP-pacakeges.\r\n"
        "     UDP port on server can be provided optionally.\r\n"
        "      Format:  !SA SrvIP [SrvPort]\r\n"
        "      Example: !SA 195215168045 \r\n"
        "               KAP packages are hereafter sent to 195.215.168.45.\r\n"
        "      Example: !SA 195.215.168.45 \r\n"
        "               Same result as \"!SA 195215168045\".\r\n"
        "      Example: !SA 192168001002 61000\r\n"
        "               KAP packages are hereafter sent to 192.168.1.2:61000\r\n"
        "               from module port 8000.\r\n"
        "      Example: !SA 0.0.0.0 \r\n"
        "               Disables KAP.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "\r\n"
        "Service server addr.: {}:{}\r\n"
    )


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

    CMD_OUTPUT = (
        "\r\n"
        "\r\n"
        "Service server addr.: {}:{} (from DNS)\r\n"
        "No redundancy.\r\n"
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

    CMD_OUTPUT = (
        "\r\n"
        "Service server hostname.: {}\r\n"
    )


class SetDeviceNameCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SD: Set device name (*1).\r\n"
        "     Option for individual naming of the module (0-20 chars).\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "OK"
    )


class SetLookupCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SH: Set KAP Server lookup (DNS or DHCP)\r\n"
        "     Used for setting the DNS name of the Server to receive KAP-pacakeges.\r\n"
        "     Using the keyword \"DHCP_OPTION:xxx\" makes the module request the IP using DHCP option xxx.\r\n"
        "     The settings are first activated when the module is reset (using !RR).\r\n"
        "      Example: !SH 0 \r\n"
        "               Lookup Disabled.\r\n"
        "               The module will send KAP to the IP listed by !SA. \r\n"
        "      Example: !SH hosting.kamstrup.dk \r\n"
        "               Use DNS lookup.\r\n"
        "               The module will send KAP to the IP listed by !SA until it resolves the DNS,\r\n"
        "               hereafter the KAP will be sent to hosting.kamstrup.dk\r\n"
        "      Example: !SH DHCP_OPTION:129\r\n"
        "               Use DHCP Option.\r\n"
        "               The module will send KAP to the IP provided by DHCP (in this case option 129).\r\n"
        "               The module uses the IP provided by !SA if the DHCP offer dos not include option xxx data.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "Service server hostname.: {}\r\n"
    )


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
        "Use DHCP            : {}\r\n"
        "\r\n"
        "IP addr.            : {}\r\n"
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
        "\r\n"
        "Software watchdog: {} {}\r\n"
        "KAP Missing warning: {} {}\r\n"
        "Keep alive timer (flash setting): {} {}\r\n"
    )


class SetNameserverCommand(BaseCommand):
    HELP_MESSAGE = (
        "!SN: Set IP for DNS Name servers to use.\r\n"
        "      Format:  !SN DNS1 DNS2 DNS3\r\n"
        "      Example: !SN 192168001200 192168001201 000000000000\r\n"
        "      Example: !SN 172.16.0.83 172.16.0.84 0.0.0.0\r\n"
    )

    CMD_SUCCESSFUL = (
        "\r\n"
        "OK"
    )

    def run(self, params=None):
        if params is None:
            return self.INVALID_PARAMETER

        nameservers = params.split(" ")
        if len(nameservers) != 3:
            return self.INVALID_PARAMETER

        return self.CMD_SUCCESSFUL


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
        "\r\n"
        "KAP on server: {}\r\n"
        "ChA on module: {}\r\n"
        "ChB on module: {}\r\n"
        "Cfg on module: {}\r\n"
    )


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

    CMD_OUTPUT = (
        "\r\n"
        "UART A setup : {}\r\n"
        "UART B setup : {},{},{},{} {}\r\n"
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

    CMD_OUTPUT = (
        "\r\n"
        "\r\n"
        "Status: {}\r\n"
    )


class RequestRestartCommand(BaseCommand):
    HELP_MESSAGE = (
        "!RR: Request restart (*1).\r\n"
    )

    def run(self, params=None):
        conpot_core.get_databus().set_value("reboot_signal", 1)
        return


class WinkModuleCommand(BaseCommand):
    HELP_MESSAGE = (
        "!WM: Wink module.\r\n"
        "     Causes the WINK LED on the module to blink for physical identification.\r\n"
    )

    CMD_OUTPUT = (
        "\r\n"
        "\r\n"
        "OK\r\n"
    )
