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


# The default response.
HelpResponse = "help                           Print this list\nioHelp                         Print I/O utilities help info\ndbgHelp                        Print debugger help info\nnfsHelp                        Print nfs help info\nnetHelp                        Print network help info\nspyHelp                        Print task histogrammer help info\ntimexHelp                      Print execution timer help info\nh         [n]                  Print (or set) shell history\ni         [task]               Summary of tasks' TCBs\nti        task                 Complete info on TCB for task\nsp        adr,args...          Spawn a task, pri=100, opt=0, stk=20000\ntaskSpawn name,pri,opt,stk,adr,args... Spawn a task\ntd        task                 Delete a task\nts        task                 Suspend a task\n"


class HoneyTelnetd:
    PWD = ""
    logFile = "/var/log/scadahoneynet.log"
    CommandLine = 'Hostname'
    Prompt="#"
    def startDump(self):
        
        while 1:
            CommandLine = self.CommandLine+self.Prompt
                    
            sys.stdout.write(CommandLine)
            sys.stdout.flush()
            
            data=sys.stdin.readline()
            self.implementCommands(data)

    
    # Send responses to commands: The commands supported are ls, cd.
    def implementCommands(self,data):

        if(re.compile('ls', re.IGNORECASE).search(data)):
            self.writeLog("Got a ls command")
            sys.stdout.write('-rw-r--r--    1 root     root           33 Mar  5 18:06 gw\r\n') 
            sys.stdout.flush()
        
        elif (re.compile('cd', re.IGNORECASE).search(data)):#Password
            self.writeLog("Got a cd command")
            f=string.splitfields(data,' ')
            PWD = f[1]
            self.CommandLine=string.rstrip(self.CommandLine+" " + PWD)
            return
        
        if(re.compile('help', re.IGNORECASE).search(data)):
            self.writeLog("Got a help command")
            sys.stdout.write(HelpResponse) 
            sys.stdout.flush()
            
        else:
            self.writeLog("Got a RET or unkknown command")
            sys.stdout.write('Shell: Command not found\r\n')
            sys.stdout.flush()
            return
    
    # Write the attacker's responses into a log file.
    def writeLog(self,string):    
        fileobject = open(self.logFile, 'a')
        fileobject.write("Scadahoneynet, Telnet Log" +":"+(time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()) +":"+ string +"\n"))
        fileobject.close()
        
    def main(self):
        self.startDump()

HoneyTelnetd().main()
