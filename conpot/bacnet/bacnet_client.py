import socket

from bacpypes.apdu import *

x = WhoIsRequest(deviceInstanceRangeLowLimit=100, deviceInstanceRangeHighLimit=600)
x.debug_contents()
y = APDU()
x.encode(y)
y.debug_contents()
z = PDU()
y.encode(z)
z.debug_contents()

print z.pduSource
print len(z.pduData)


TCP_IP = '127.0.0.1'
TCP_PORT = 9000
BUFFER_SIZE = 1024

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))
s.send(z.pduData)
data = s.recv(BUFFER_SIZE)
s.close()

print "received data:", data, type(data)