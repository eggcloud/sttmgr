#-*-coding:utf-8-*-

import socket
import time
import json


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('localhost', 9999))

# login request
smsg = '{}{:8}{}'.format(1001, 9, "sttengine")
print "sendmsg", smsg
sock.send(smsg)

data = sock.recv(1024)
print "recvmsg", data

data = sock.recv(1024)
print "recvmsg", data

# recognize response
jdata = { "speechID": "uuid", "result": "0", "transcript": "고기고기" }
smsg = json.dumps(jdata, ensure_ascii=False)
smsg = '{}{:8}'.format(4001, len(smsg)) + smsg
print "sendmsg", smsg
sock.send(smsg)

sock.close()
