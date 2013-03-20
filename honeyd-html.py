import sys
import re

GetHttpHeader = "HTTP/1.1 200 OK\n Date: Thu, 14 Jul 2005 11:26:45 GMT\n Server: Apache/1.3.33 (Debian GNU/Linux)\n Last-Modified: Thu, 02 Dec 2004 17:41:30 GMT\n ETag: ""b6e5-148a-41af53ca""\n Accept-Ranges: bytes\n Content-Length: 5258\n Content-Type: text/html; charset=iso-8859-1\n\n <!DOCTYPE HTML PUBLIC ""-//W3C//DTD HTML 4.01 Transitional//EN"">\n"

HtmlBeg = "<HTML>\n"

HeadBeg="<HEAD>\n   <META HTTP-EQUIV=""Content-Type"" CONTENT=""text/html; charset=iso-8859-1"">\n   <META NAME=""Description"" CONTENT=""The initial installation of Debian apache."">\n"

Title = "<TITLE>Placeholder page</TITLE>\n"

HeadEnd = "</HEAD>"

BodyBeg = "<BODY TEXT=""#000000"" BGCOLOR=""#FFFFFF"" LINK=""#0000EF"" VLINK=""#55188A"" ALINK=""#FF0000"">"

H1 = "<H1>PLC Web Page</H1>\n"

Diag1 = "<H1>Diagnostic Page</H1>\n"

DiagUrl = "<A HREF=""Diagnostics"">Diagnostics</A>"

Stat1 =  "<H1>Statistics Page</H1>\n"

StatUrl = "<A HREF=""Statistics"">Statistics</A>"

Prot1 =  "<H1>Protocols Supported</H1>\n"

ProtUrl = "<A HREF=""Protocols"">Protocols Supported</A>"

Form1 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py"">Temperature: \n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Temperature"" value=""70""></FORM>\n"

Form2 = "<FORM  METHOD=""GET"" ACTION=""honeyd-feedback.py"">CPU:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""CPU"" value=""70%""></FORM>\n"


Form3 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> Memory:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Memory"" value=""240M""></FORM>\n"

Form4 = "<FORM  METHOD=""GET"" ACTION=""honeyd-feedback.py"">IO:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""IO"" value=""Active""></FORM>\n"

Form5 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> Fan:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Fan"" value=""Active""></FORM>\n"


Sform1 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> Packets:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Packets"" value=""20""></FORM>\n"

Sform2 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> Devices:\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Fan"" value=""2""></FORM>\n"

Sform3 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> HTTP(Port 80):\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Fan"" value=""1000""></FORM>\n"

Sform4 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> FTP(Port 21):\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Fan"" value=""20000""></FORM>\n"

Sform5 = "<FORM METHOD=""GET"" ACTION=""honeyd-feedback.py""> Modbus(Port 502):\n<INPUT TYPE = "" SIZE=""20"" MAXLENGTH=""64"" NAME=""Fan"" value=""300""></FORM>\n"

ProtTable = "<table border=""1"">\n<tr>\n<td>Telnet</td>\n<td>Port 23 </td>\n</tr>\n<tr>\n<td>FTP </td>\n<td>Port 21</td>\n</tr>\n<tr>\n<td>HTTP</td>\n<td>Port 80</td>\n</tr>\n<tr>\n<td>Modbus</td>\n<td>Port 502</td>\n</tr>\n</table>"

Button = "<form name=""input"" action=""honeyd-feedback.py""\n method=""get"">\n<input type=""submit"" value=""Submit""></form>"

BodyHtmlEnd = "</BODY>\n</HTML>\n"


MainPage = GetHttpHeader+HtmlBeg+HeadBeg+Title+HeadEnd+BodyBeg+H1+DiagUrl+"      "+ StatUrl+"      "+ ProtUrl+BodyHtmlEnd

DiagnosticPage = GetHttpHeader+HtmlBeg+HeadBeg+Title+HeadEnd+BodyBeg+Diag1+DiagUrl+Form1+Form2+"<br>"+Form3+Form4+Button+BodyHtmlEnd

GetSlashResponse = GetHttpHeader+HtmlBeg+HeadBeg+Title+HeadEnd+BodyBeg+H1+BodyHtmlEnd

ProtocolPage = GetHttpHeader+HtmlBeg+HeadBeg+Title+HeadEnd+BodyBeg+Prot1+ProtTable+BodyHtmlEnd

StatPage = GetHttpHeader+HtmlBeg+HeadBeg+Title+HeadEnd+BodyBeg+Stat1+StatUrl+Sform1+Sform2+"<br>"+Sform3+Sform4+Button+BodyHtmlEnd


GetSlashResponse2= "HTTP/1.1 200 OK\n Date: Thu, 14 Jul 2005 11:26:45 GMT\n Server: Apache/1.3.33 (Debian GNU/Linux)\n Last-Modified: Thu, 02 Dec 2004 17:41:30 GMT\n ETag: ""b6e5-148a-41af53ca""\n Accept-Ranges: bytes\n Content-Length: 5258\n Content-Type: text/html; charset=iso-8859-1\n\n <!DOCTYPE HTML PUBLIC ""-//W3C//DTD HTML 4.01 Transitional//EN"">\n <HTML>\n <HEAD>\n   <META HTTP-EQUIV=""Content-Type"" CONTENT=""text/html; charset=iso-8859-1"">\n   <META NAME=""Description"" CONTENT=""The initial installation of Debian apache."">\n   <TITLE>Placeholder page</TITLE>\n </HEAD> \n <H1>Placeholder page</H1> <H3><A NAME=""SECRET"">The secret word</A></H3>\n<FORM METHOD=""GET"" ACTION=""http://cgi.algonet.se/htbin/cgiwrap/ug/form.py"">\n<INPUT TYPE=""PASSWORD"" NAME=""pw"" SIZE=""20"" MAXLENGTH=""64"">\n</FORM>\n</BODY>\n</HTML>"

data=sys.stdin.readline()

if re.compile('Diag', re.IGNORECASE).search(data):
    print DiagnosticPage
elif(re.compile('Prot', re.IGNORECASE).search(data)):
    print ProtocolPage
elif(re.compile('Stat', re.IGNORECASE).search(data)):
    print StatPage
else:
    print MainPage