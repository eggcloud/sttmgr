#-*-coding:utf-8-*-
import socket
import requests
import json

server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_sock.bind(("0.0.0.0", 9999))
server_sock.listen(5)

print "server listen"

(sock, address) = server_sock.accept()
print "accept", sock.fileno(), address

rmsg = sock.recv(2048)
print "recvmsg", rmsg

# login response
smsg = '{}{:8}{}'.format(2001, 1, 0)
print "sendmsg", smsg
sock.send(smsg)

# recognize request
jdata = { "speechID": "uuid", "domainCode": "abc", "domainName": "def", "fileID": "111" , "fileName": "222", "filePath": "333"}
smsg = json.dumps(jdata, ensure_ascii=False)
smsg = '{}{:8}'.format(3001, len(smsg)) + smsg
print "sendmsg", smsg
sock.send(smsg)

rmsg = sock.recv(1024)
print "recvmsg", rmsg

sock.close()
server_sock.close()
