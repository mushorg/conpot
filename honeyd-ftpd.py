# (Version 0.1, Venkat Pothamsetty, vpothams@cisco.com)

# This  program is free software; you may redistribute and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; Version 2.
# This guarantees your right to use, modify, and redistribute
# this software under certain conditions This program is distributed
# in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details at http://www.gnu.org/copyleft/gpl.html .
# The authors or our employer, will not be liable for any direct,
# indirect, special or consequential damages from the use of or
# failure to use of improper use of this tool.

import re
import string
import time
import sys


ListCommandResponse = "150 Opening BINARY mode data connection\ndrwx------  1 user          ftp\n"
SystResponse = "215 UNIX Type: BlahWorks\r\n"
HelpResponse = """214-The following commands are recognized (* =>'s unimplemented).\n USER    PORT    STOR    MSAM*   RNTO    NLST    MKD     CDUP\n PASS    PASV    APPE    MRSQ*   ABOR    SITE    XMKD    XCUP\n ACCT*   TYPE    MLFL*   MRCP*   DELE    SYST    RMD     STOU\n SMNT*   STRU    MAIL*   ALLO    CWD     STAT    XRMD    SIZE\n REIN*   MODE    MSND*   REST    XCWD    HELP    PWD     MDTM\n QUIT    RETR    MSOM*   RNFR    LIST    NOOP    XPWD\n"""
QuitResponse = "221 Goodbye.\r"
PermissionDenied = "550 Permission denied\r\n"
UnKnownResponse = "502 command not implemented.\r"
CWD = "root"


class HoneyFTPd:

    logFile = "scadahoneynet.log"
    def startFTP(self):

        sys.stdout.write('220 FTP server (VxWorks version 5.3.2) ready.\r\n')
        sys.stdout.flush()

        while 1:
            data=sys.stdin.readline()
            self.implementCommands(data)

    def implementCommands(self,data):
    # If the client sends USER command
        if re.compile('user', re.IGNORECASE).search(data):

            self.writeLog("Got a user command")
            sys.stdout.write('331 Guest login ok, send your complete e-mail address as a password.\r\n')  # Send Login OK, which means the client will ask the user for
            sys.stdout.flush()
            return
        
        elif re.compile('pass', re.IGNORECASE).search(data):  # Password

            self.writeLog("Got the password")
            # The client will send the PASS command next
            sys.stdout.write('230 User Logged in\r\n')  # The command says the the username and password are OK
            sys.stdout.flush()
            return

        elif re.compile('help', re.IGNORECASE).search(data):  # Password

            self.writeLog("Got the help command")
            # The client will send the PASS command next
            sys.stdout.write(HelpResponse)
            sys.stdout.flush()
            return
    
        elif re.compile('list', re.IGNORECASE).search(data):  # Password

            # Without the IP address knowledge, you cannot open up the
            # data port, which you can with the stand alone script.
            self.writeLog("Got a list command")
            sys.stdout.write("425 Cant build data connection: Connection Timeout\r\n")
            sys.stdout.flush()
            sys.exit()
            #conn.send('250 Changed directory \r\n')# The command says the the username and password are OK
            return

        elif re.compile('cwd', re.IGNORECASE).search(data):  # Password
            self.writeLog("Got a cwd command")
            f=string.splitfields(data, ' ')
            directory = f[1]
            sys.stdout.write('250 Changed directory %s \r\n' % directory)  # The command says the the username and password are OK
            sys.stdout.flush()
            return

        elif re.compile('port', re.IGNORECASE).search(data):  # Password
            # sys.stdout.write('200 Port set OK\r\n')
            # After this you need to connect back to the port and listen for a command.
            # Convert each of the last numbers to hex and combine the two hexnumbers, convert the combined hex number
            # to decimal and you should get the port number.#m,n=(hex(int(f[4])),hex(int(f[5]))
            sys.stdout.write("425 Cant build data connection: Connection Timeout\r\n")
            sys.stdout.flush()
            f = string.splitfields(data, ',')
            m, n = (hex(int(f[4])), hex(int(f[5])))
            x, y = (string.splitfields(m, 'x'), string.splitfields(n, 'x'))
            s = '0x' + x[1] + y[1]
            port = int(s, 16)
            self.PORTport = port
            return
            
        elif re.compile('quit', re.IGNORECASE).search(data):  # QUIT
            self.writeLog("Got a QUIT command")
            sys.stdout.write("")
            sys.stdout.flush(QuitResponse)
            return

        elif re.compile('syst', re.IGNORECASE).search(data):
            self.writeLog("Got a syst command")
            sys.stdout.write(SystResponse)
            sys.stdout.flush()
            return
            
        else:
            self.writeLog("Got a unkown command:%s" %(data))
            sys.stdout.write(UnKnownResponse)
            sys.stdout.flush()
            sys.exit()
            return
        
    def writeLog(self,string):    
        fileobject = open(self.logFile, 'a')
        fileobject.write("Scadahoneynet, FTP Log" + ":" + (time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()) +
                                                           ":" + string + "\n"))
        fileobject.close()

    def main(self):
        self.startFTP()

HoneyFTPd().main()
