import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto("foo", ("127.0.0.1", 161))
print repr(s.recv(1024))
