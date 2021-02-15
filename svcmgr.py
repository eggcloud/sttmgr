#-*- coding: utf-8 -*-
# pylint: disable=C0103,C0301,C0111,C0302,R0902,R0912,R0914,R0915
"""
   C0103: Invalid %s name
   C0301: Line too long
   C0111: Missing docstring
   C0302: Too many lines in module
   R0902: Too many instance attributes
   R0912: Too many branches
   R0914: Too many local variables
   R0915: Too many statements
"""

from __future__ import print_function

import multiprocessing
import Queue
import json
import threading
import time
import sys
import os
import signal
import socket
import select
import datetime

import requests
import _config
import _database

# Block InsecurePlatformWarning
requests.packages.urllib3.disable_warnings()

reload(sys)
sys.setdefaultencoding('utf-8')

# Define ENGINE
STT_ENGINE = 'sttengine'

# Define Record State
REC_TRANSCRIBE_BEGIN = 'TRANSCRIBE_BEGIN'
REC_WORKER_PUT = 'WORKER_PUT'
REC_WORKER_GET = 'WORKER_GET'
REC_STTENGINE_SEND = 'STT_SEND'
REC_STTENGINE_RECV = 'STT_RECV'
REC_TRANSCRIBE_END = 'TRANSCRIBE_END'

# Define Packet
PKT_HEADER_LEN = 12

# Define Packet Type
PKT_LOGIN_REQ = '1001'
PKT_LOGIN_RES = '2001'
PKT_RECOGNIZE_REQ = '3001'
PKT_RECOGNIZE_RES = '4001'
PKT_TRANSCRIBE_REQ = '1002'
PKT_TRANSCRIBE_RES = '2002'
PKT_MONITOR_REQ = '1003'
PKT_MONITOR_RES = '2003'

# Define Json Key
KEY_RESULT = 'result'
KEY_TYPE = 'type'
KEY_SPEECHID = 'speechID'
KEY_DOMAINCODE = 'domainCode'
KEY_DOMAINNAME = 'domainName'
KEY_FILEID = 'fileID'
KEY_FILENAME = 'fileName'
KEY_FILEPATH = 'filePath'
KEY_AUDIOPATH = 'audioPath'
KEY_SOCK = 'socket'
KEY_FILE = 'file'
KEY_STATE = 'state'

# Define Result
RET_SUCCEED = 0
RET_ALREADY = 1
RET_UNSUPPORTED = 2
RET_UNAVAILABLE = 3
RET_NOTFOUND = 4
RET_TIMEOUT = 5
RET_TOOMANY = 6
RET_BADREQ = 7
RET_DISCONNECT = 8
RET_ERROR = 9

# Define Task State
STATE_NONE = 'NONE'
STATE_INIT = 'INIT'
STATE_NOFILE_ID = 'NOFILE_ID'
STATE_NOFILE_WAV = 'NOFILE_WAV'
STATE_NOFILE_MP3 = 'NOFILE_MP3'
STATE_UNKNOWN_FORMAT = 'UNKNOWN_FORMAT'
STATE_ERROR = 'ERROR'
STATE_DONE = 'DONE'

# Queue Object
class TaskObject(object):
    def __init__(self, message):
        try:
            self.msg = json.loads(message)
            self.sid = self.msg[KEY_SPEECHID]
            self.dcode = self.msg[KEY_DOMAINCODE]
            self.dname = self.msg[KEY_DOMAINNAME]
            self.fid = self.msg[KEY_FILEID]
            self.fname = self.msg[KEY_FILENAME]
            self.fpath = self.msg[KEY_FILEPATH]
            self.apath = self.msg[KEY_AUDIOPATH]
            self.state = STATE_DONE
        except Exception:
            raise

# Worker Processes
class Worker(multiprocessing.Process):
    def __init__(self, app_config, queues):
        multiprocessing.Process.__init__(self)
        self.cfg = app_config
        self.log = self.cfg.getLogger(self.name)
        self.task_queue, self.agent_queue = queues

    def runShellCommand(self, cmd):
        import subprocess
        self.log.info('###### {}'.format(cmd))
        ret = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        return  ret.communicate()

    def pushAgentQueue(self, task):
        try:
            self.log.info('@@@@@ putQueue [%s]', task.sid)
            self.agent_queue.put_nowait(task)
        except Queue.Full:
            self.log.critical('????? Agent Queue Full.')
        except Exception as e:
            self.log.error('????? TaskObject Error: {}'.format(e))

    def run(self):
        self.log.info('<Start>')

        while True:
            task = self.task_queue.get()
            self.log.info('@@@@@ getQueue [%s] [%s/%s] [%s]', task.sid, task.dcode, task.dname, os.path.join(task.fpath, task.fname))

            try:
                mydb = _database.MYSQL(self.cfg)

                # 음성파일에 대한 정보를 STT Engine 에 전달하기 전에 필요한 전처리를 여기서 한다.

                sql = mydb.makeInsertSql("TB_STT_INFO_RECORD", task)
                mydb.execute(sql)
                mydb.commit()
                self.log.info("speechID[{}] SQL Insert records into Table. TB_STT_INFO_RECORD".format(task.sid))

                sql = mydb.makeSelectSql("TB_STT_INFO_RECORD", task)
                rows = mydb.executeOne(sql)
                if rows is None:
                    raise Exception('no data found. TB_STT_INFO_RECORD <= speechID[{}]'.format(task.sid))
                self.log.info("speechID[{}] SQL Select records from Table. TB_STT_INFO_RECORD => SEQ[{}]".format(task.sid, rows['SEQ']))
                task.msg['seq'] = rows['SEQ']

                sql = mydb.makeSelectSql("TB_CS_INFO_DOMAIN", task)
                rows = mydb.executeOne(sql)
                if rows is None:
                    raise Exception('no data found. TB_CS_INFO_DOMAIN <= speechID[{}]'.format(task.sid))
                self.log.info("speechID[{}] SQL Select records from Table. TB_CS_INFO_DOMAIN => domain SEQ[{}]".format(task.sid, rows['SEQ']))
                task.msg['domainSeq'] = rows['SEQ']

                sql = mydb.makeSelectSql("TB_CS_INFO_SVR_CONFIG", task)
                rows = mydb.executeOne(sql)
                if rows is None:
                    raise Exception('no data found. TB_CS_INFO_SVR_CONFIG <= speechID[{}]'.format(task.sid))
                self.log.info("speechID[{}] SQL Select records from Table. TB_CS_INFO_SVR_CONFIG => image SEQ[{}]".format(task.sid, rows['SEQ']))
                task.msg['imageSeq'] = rows['SEQ']

                sql = mydb.makeUpdateSql("TB_STT_CSCONN STATUS", task, 1)
                mydb.execute(sql)
                mydb.commit()
                self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN STATUS 1".format(task.sid))

                if not os.path.exists(task.apath):
                    os.makedirs(task.apath)

                channels = 0
                task.msg['serverSeq'] = 1
                path_fid = os.path.join(task.fpath, task.fid)
                path_wav = os.path.join(task.apath, ''.join(os.path.splitext(task.fid)[:-1])+'.wav')
                path_mp3 = os.path.join(task.apath, ''.join(os.path.splitext(task.fid)[:-1])+'.mp3')

                self.log.info("speechID[{}] Set Paths\nID path[{}]\nWAV path[{}]\nMP3 path[{}]".format(task.sid, path_fid, path_wav, path_mp3))

                self.log.info("speechID[{}] convert audio to wav".format(task.sid))
                if os.path.exists(path_fid):
                    self.runShellCommand('ffmpeg -nostats -loglevel 0 -y -i {} -ar 8000 {}'.format(path_fid, path_wav))
                    task.msg['audioWAV'] = os.path.basename(path_wav)
                else:
                    task.state = STATE_NOFILE_ID
                    sql = mydb.makeUpdateSql("TB_STT_CSCONN STATUS", task, 11)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN STATUS 11".format(task.sid))
                    raise Exception('not exist id file. speechID[{}]'.format(task.sid))

                self.log.info("speechID[{}] convert wav to mp3".format(task.sid))
                if os.path.exists(path_wav):
                    os.remove(path_fid)
                    sql = mydb.makeUpdateSql("TB_STT_INFO_RECORD DELETE", task)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_INFO_RECORD DELETE org".format(task.sid))

                    if self.cfg.isMP3:
                        self.runShellCommand('ffmpeg -nostats -loglevel 0 -y -i {} -vn -ab 64k -ar 8000 -f mp3 {}'.format(path_wav, path_mp3))
                        task.msg['audioMP3'] = os.path.basename(path_mp3)
                        if os.path.exists(path_mp3) is False:
                            task.state = STATE_NOFILE_MP3
                            sql = mydb.makeUpdateSql("TB_STT_CSCONN STATUS", task, 14)
                            mydb.execute(sql)
                            mydb.commit()
                            self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN STATUS 14".format(task.sid))
                            raise Exception('not exist mp3 file. speechID[{}]'.format(task.sid))

                    sql = mydb.makeUpdateSql("TB_STT_INFO_RECORD MEDIA", task)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_INFO_RECORD PATH".format(task.sid))

                else:
                    if self.cfg.err_path is None:
                        os.remove(path_fid)
                    else:
                        if not os.path.exists(self.cfg.err_path):
                            os.makedirs(self.cfg.err_path)
                        self.log.info("speechID[{}] rename [{}] to [{}]".format(task.sid, path_fid, os.path.join(self.cfg.err_path, task.fid)))
                        os.rename(path_fid, os.path.join(self.cfg.err_path, task.fid))

                    task.state = STATE_NOFILE_WAV
                    sql = mydb.makeUpdateSql("TB_STT_CSCONN STATUS", task, 12)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN STATUS 12".format(task.sid))
                    raise Exception('not exist wav file. speechID[{}]'.format(task.sid))

                self.log.info("speechID[{}] check wave file".format(task.sid))
                # ffmpeg -i <file_wav> 2>&1 | grep 'Hz'
                import wave
                fw = wave.open(path_wav)
                channels = fw.getnchannels()
                fw.close()

                task.msg['channels'] = channels
                if channels == 1 or channels == 2:
                    if channels == 2:
                        path_wav1 = ''.join(os.path.splitext(path_wav)[:-1])+"_A"+os.path.splitext(path_wav)[-1]
                        path_wav2 = ''.join(os.path.splitext(path_wav)[:-1])+"_B"+os.path.splitext(path_wav)[-1]
                        self.runShellCommand('ffmpeg -nostats -loglevel 0 -y -i {} -map_channel 0.0.0 {} -map_channel 0.0.1 {}'.format(path_wav, path_wav1, path_wav2))
                        os.remove(path_wav)

                    sql = mydb.makeUpdateSql("TB_STT_CSCONN MEDIA", task, 2)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN MEDIA".format(task.sid))
                else:
                    task.state = STATE_UNKNOWN_FORMAT
                    sql = mydb.makeUpdateSql("TB_STT_CSCONN STATUS", task, 13)
                    mydb.execute(sql)
                    mydb.commit()
                    self.log.info("speechID[{}] SQL Update records of Table. TB_STT_CSCONN STATUS 13".format(task.sid))
                    raise Exception('unknown wav file. speechID[{}]'.format(task.sid))

                mydb.close()
            except Exception as e:
                self.log.error('????? Database Error: {}'.format(e))
                if task.state == STATE_DONE:
                    task.state = STATE_ERROR

            self.pushAgentQueue(task)
        return


class PacketAgent(multiprocessing.Process):
    def __init__(self, app_config, queues):
        multiprocessing.Process.__init__(self)
        self.cfg = app_config
        self.log = self.cfg.getLogger(self.name)
        self.task_queue, self.worker_queue = queues
        self.http_queue = None
        self.speechmap = {} # { SpeechID : { "socket" : Socket, "state" : STATE_INIT, "startTime" : DateTime , "processInterval" : [], "data" : {} }  }
        self.filemap = {} # { fullpath : { "isRunning" : false , "mTime" : modification time } }
        self.stt_sock = None

    def sendMessage(self, sock, msg):
        ret = True
        try:
            sock.send(msg)
        except Exception as e:
            self.log.error('????? send fd({}) error: {}'.format(sock.fileno(), e))
            ret = False
        return ret

    def run(self):
        # 서버 초기화
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.cfg.ip, self.cfg.port))
        server_sock.listen(5)

        # webhook url 주소가 등록되어 있으면, HTTP 처리를 위한 스레드를 생성한다.
        if self.cfg.url is not None:
            self.http_queue = Queue.Queue()
            thd = threading.Thread(target=self.httpHandler)
            #thd.daemon = True
            thd.start()

        # agent_queue 로 수신된 메세지를 처리하는 스레드를 생성한다.
        thd = threading.Thread(target=self.workerHandler)
        #thd.daemon = True
        thd.start()

        self.log.info('<Start Server>')
        connList = [server_sock]

        while True:
            readable, _, _ = select.select(connList, [], [], 3)

            # select timeout
            if len(readable) <= 0:
                self.checkSession(connList)
                self.checkDirectory()

                mmsg = ""
                for sock in connList:
                    mmsg += "{}".format(sock.fileno())
                    if server_sock == sock:
                        mmsg += "(SVR)"
                    if self.stt_sock == sock:
                        mmsg += "(STT)"
                    mmsg += " "
                if len(mmsg) > 0:
                    self.log.debug('............Connection List : {}'.format(mmsg))
                mmsg = ""

            # readable socket
            for sock in readable:
                if sock == server_sock:
                    try:
                        (client_sock, addr) = server_sock.accept()
                        connList.append(client_sock)
                        self.log.info('@@@@@ accept fd({}) address{}'.format(client_sock.fileno(), addr))
                    except Exception as e:
                        self.log.error('????? accept error: {}'.format(e))
                else:
                    rmsg = None
                    header = None
                    pkt_type = None
                    try:
                        header = sock.recv(PKT_HEADER_LEN)
                        if len(header) > 0:
                            if header[4:].strip().isdigit():
                                rmsg = sock.recv(int(header[4:].strip()))
                                pkt_type = header[:4]
                                self.log.info('@@@@@ recv fd({}): header[{}] body[{}]'.format(sock.fileno(), header, rmsg))
                            else:
                                self.log.warning('????? unknown header[{}]'.format(header))
                                continue
                    except Exception as e:
                        self.log.error('????? recv error: {}'.format(e))

                    if rmsg is None:
                        self.log.info('@@@@@ close fd({})'.format(sock.fileno()))
                        if self.stt_sock == sock:
                            self.log.info('@@@@@ {} disconnected.'.format(STT_ENGINE))
                            self.stt_sock = None
                            # 엔진 연결이 중단되면 요청이 완료되지 않은 것들은 바로 종료한다.
                            for sid in self.speechmap.keys():
                                self.log.warning('????? speechID({}) stop'.format(sid))
                                ssock = None
                                if KEY_SOCK in self.speechmap[sid]:
                                    ssock = self.speechmap[sid][KEY_SOCK]
                                self.recordState(sid, REC_TRANSCRIBE_END, None, RET_UNAVAILABLE)
                                if ssock is not None:
                                    connList.remove(ssock)
                                    ssock.close()
                        else:
                            for sid in self.speechmap.keys():
                                if KEY_SOCK in self.speechmap[sid] and self.speechmap[sid][KEY_SOCK] == sock:
                                    self.recordState(sid, REC_TRANSCRIBE_END, None, RET_DISCONNECT)
                        connList.remove(sock)
                        sock.close()

                    else:
                        if pkt_type == PKT_LOGIN_REQ:
                            smsg = '{}{:8}'.format(PKT_LOGIN_RES, 1)
                            if rmsg.strip() == STT_ENGINE:
                                if self.stt_sock is None:
                                    self.stt_sock = sock
                                    smsg += str(RET_SUCCEED)
                                else:
                                    smsg += str(RET_ALREADY)
                            else:
                                smsg += str(RET_UNSUPPORTED)
                            self.log.info('@@@@@ send fd({})\n{}\n{}'.format(sock.fileno(), "Login Response", smsg[PKT_HEADER_LEN:]))
                            self.sendMessage(sock, smsg)

                        elif pkt_type == PKT_TRANSCRIBE_REQ:
                            self.transcribeRequest(rmsg, sock)

                        elif pkt_type == PKT_RECOGNIZE_RES:
                            self.recognizeResponse(rmsg, sock)

                        elif pkt_type == PKT_MONITOR_REQ:
                            self.monitorRequest(rmsg, sock)

                        else:
                            self.log.warning('????? unknown packet type: header[{}] body[{}]'.format(header, rmsg))

        self.log.info('<End Server>')
        for sock in connList:
            sock.close()
        return

    def checkSession(self, connList):
        for sid in self.speechmap.keys():
            if KEY_SOCK in self.speechmap[sid]:
                delta = datetime.datetime.now() - datetime.datetime.strptime(self.speechmap[sid]["startTime"], "%Y.%m.%d %H:%M:%S.%f")
                if self.cfg.session_timeout <= delta.total_seconds():
                    sock = self.speechmap[sid][KEY_SOCK]
                    self.log.warning('????? session timeout {} secs : close fd({}) speechID({})'.format(delta.total_seconds(), sock.fileno(), sid))
                    self.recordState(sid, REC_TRANSCRIBE_END, None, RET_TIMEOUT)
                    connList.remove(sock)
                    sock.close()
        return

    def checkDirectory(self):
        # 지정된 디렉토리에서 파일을 처음 발견하면 파일속성을 저장한다.
        # 일정시간이 경과한 후에 파일속성에서 변경이력이 없으면 완료된 것으로 판단하여 변환 처리를 요청한다.

        def scan(dname, fmap):
            fid = None
            mtime = None
            try:
                files = os.listdir(dname)
                for fn in files:
                    ff = os.path.join(dname, fn)
                    if os.path.isdir(ff):
                        scan(ff, fmap)
                    elif len(os.path.splitext(ff)[-1]) > 0 and ff not in fmap:
                        fid = ff
                        mtime = os.path.getmtime(ff)
                        break
            except Exception as e:
                self.log.error('????? error: {}'.format(e))
            return (fid, mtime)

        if self.cfg.dir_srcpath is None:
            return
        elif self.stt_sock is None:
            return
        elif len(self.speechmap) > self.cfg.max_tasks:
            return

        if os.path.exists(self.cfg.dir_srcpath):
            (fid, mtime) = scan(self.cfg.dir_srcpath, self.filemap)
            if fid is not None:
                self.filemap[fid] = {"isRunning": False, "mTime": mtime}

        for fid in self.filemap.keys():
            if self.filemap[fid]["isRunning"]:
                continue

            delta = time.time() - self.filemap[fid]["mTime"]
            if self.cfg.dir_interval <= delta:
                self.log.info('@@@@@ Discovered File ({})'.format(fid))

                if os.path.exists(fid) is False:
                    del self.filemap[fid]
                elif self.filemap[fid]["mTime"] == os.path.getmtime(fid):
                    sid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")

                    fname = sid+os.path.splitext(fid)[-1]
                    apath = ""
                    os.rename(fid, os.path.join(self.cfg.dir_srcpath, sid+os.path.splitext(fid)[-1]));
                    if self.cfg.dir_cvtpath is None:
                        apath = os.path.join(self.cfg.dir_srcpath, "rec_mp3/{}".format(sid.split('_')[0]))
                    else:
                        apath = os.path.join(self.cfg.dir_cvtpath, sid.split('_')[0])

                    fmsg = '{"%s":"%s",' % (KEY_SPEECHID, sid)
                    fmsg += ' "%s":"%s",' % (KEY_DOMAINCODE, "SG0001")
                    fmsg += ' "%s":"%s",' % (KEY_DOMAINNAME, "SGDefault")
                    fmsg += ' "%s":"%s",' % (KEY_FILEID, fname)
                    fmsg += ' "%s":"%s",' % (KEY_FILENAME, os.path.basename(fid))
                    fmsg += ' "%s":"%s",' % (KEY_FILEPATH, os.path.dirname(fid))
                    fmsg += ' "%s":"%s"}' % (KEY_AUDIOPATH, apath)

                    try:
                        task = TaskObject(fmsg)
                        self.log.info('@@@@@ putQueue [%s]', task.sid)
                        self.worker_queue.put_nowait(task)
                        self.log.info('@@@@@ file path({})\n{}\n{}'.format(fid, "Transcribe Start", json.dumps(task.msg, indent=4, ensure_ascii=False)))
                        sid = task.sid
                        self.speechmap[sid] = {KEY_FILE: fid}
                        self.recordState(sid, REC_TRANSCRIBE_BEGIN, task.msg)
                        self.recordState(sid, REC_WORKER_PUT, task.msg)
                        self.filemap[fid]["isRunning"] = True
                    except Queue.Full:
                        self.log.critical('????? Worker Queue Full.')
                        del self.filemap[fid]
                    except Exception as e:
                        self.log.error('????? TaskObject Error: {}'.format(e))
                        del self.filemap[fid]
                else:
                    self.filemap[fid] = os.path.getmtime(fid)
        return

    def transcribeRequest(self, rmsg, sock):
        ret = None
        if len(self.speechmap) > self.cfg.max_tasks:
            self.log.critical('????? Too Many Requests.')
            ret = RET_TOOMANY
        elif self.stt_sock is None:
            self.log.critical('????? Not Connected Engine')
            ret = RET_UNAVAILABLE
        else:
            try:
                task = TaskObject(rmsg)
                sid = task.sid
                self.log.info('@@@@@ putQueue [%s]', sid)
                self.worker_queue.put_nowait(task)
                self.log.info('@@@@@ socket fd({})\n{}\n{}'.format(sock.fileno(), "Transcribe Request", json.dumps(task.msg, indent=4, ensure_ascii=False)))
                self.speechmap[sid] = {KEY_SOCK: sock}
                self.recordState(sid, REC_TRANSCRIBE_BEGIN, task.msg)
                self.recordState(sid, REC_WORKER_PUT, task.msg)
            except Queue.Full:
                self.log.critical('????? Worker Queue Full.')
                ret = RET_UNAVAILABLE
            except Exception as e:
                self.log.error('????? TaskObject Error: {}'.format(e))
                ret = RET_BADREQ

        if ret is not None:
            if rmsg[-1] == '}':
                smsg = ',"%s":"%d","%s":"%s"}' % (KEY_RESULT, ret, KEY_STATE, STATE_NONE)
                smsg = rmsg[:-1] + smsg
            else:
                smsg = '{"%s":"%d","%s":"%s"}' % (KEY_RESULT, ret, KEY_STATE, STATE_NONE)
            smsg = '{}{:8}'.format(PKT_TRANSCRIBE_RES, len(smsg)) + smsg
            self.log.info('@@@@@ send fd({})\n{}\n{}'.format(sock.fileno(), "Transcribe Response", smsg[PKT_HEADER_LEN:]))
            self.sendMessage(sock, smsg)
        return

    def recognizeResponse(self, rmsg, sock):
        jdata = None
        sid = None
        try:
            jdata = json.loads(rmsg)
            sid = jdata[KEY_SPEECHID]
            self.log.info('@@@@@ socket fd({})\n{}\n{}'.format(sock.fileno(), "Recognize Response", json.dumps(jdata, indent=4, ensure_ascii=False)))
            self.recordState(sid, REC_STTENGINE_RECV, jdata)
        except Exception as e:
            self.log.error('????? JsonLoads Error: {}'.format(e))

        if sid is not None:
            if sid in self.speechmap:
                self.recordState(sid, REC_TRANSCRIBE_END, jdata)
            else:
                self.log.warning('????? already disconnnected. speechID[%s]', sid)
        return

    def monitorRequest(self, rmsg, sock):
        # rmsg 에서 type == cpu / memory / disk / task / engine 분류해서 보내도록 추가 가능하다.

        import collections
        import psutil
        def obj2dict(obj):
            if isinstance(obj, (collections.OrderedDict, dict)):
                res = {}
                for k, v in obj.items():
                    res[k] = obj2dict(v)
                return res
            elif isinstance(obj, list):
                return [obj2dict(item) for item in obj]
            return obj

        jdata = {}
        jdata["version"] = self.cfg.version
        jdata["engine"] = {STT_ENGINE : self.stt_sock is not None}
        jdata["task"] = []
        for sid in self.speechmap.keys():
            tmp = {}
            tmp[KEY_SPEECHID] = sid
            tmp["startTime"] = self.speechmap[sid]["startTime"]
            tmp[KEY_STATE] = self.speechmap[sid][KEY_STATE]
            jdata["task"].append(tmp)
        jdata["cpu"] = obj2dict(vars(psutil.cpu_times_percent(interval=0.3, percpu=False)))
        jdata["memory"] = obj2dict(vars(psutil.virtual_memory()))
        if "available" in jdata["memory"]:
            jdata["memory"]["availableB2H"] = psutil._common.bytes2human(jdata["memory"]["available"])
        if "total" in jdata["memory"]:
            jdata["memory"]["totalB2H"] = psutil._common.bytes2human(jdata["memory"]["total"])
        jdata["disk"] = []
        for part in psutil.disk_partitions(all=False):
            if os.name == 'nt':
                if 'cdrom' in part.opts or part.fstype == '':
                    continue
            usage = psutil.disk_usage(part.mountpoint)
            tmp = {}
            tmp["device"] = part.device
            tmp["total"] = psutil._common.bytes2human(usage.total)
            tmp["used"] = psutil._common.bytes2human(usage.used)
            tmp["free"] = psutil._common.bytes2human(usage.free)
            tmp["percent"] = int(usage.percent)
            tmp["type"] = part.fstype
            tmp["mount"] = part.mountpoint
            jdata["disk"].append(tmp)

        smsg = json.dumps(jdata, ensure_ascii=False)
        smsg = '{}{:8}'.format(PKT_MONITOR_RES, len(smsg)) + smsg
        self.log.info('@@@@@ send fd({})\n{}\n{}'.format(sock.fileno(), "Monitor Response", json.dumps(jdata, indent=4, ensure_ascii=False)))
        self.sendMessage(sock, smsg)

    def workerHandler(self):
        self.log.info('<Start Thread workerHandler>')

        while True:
            task = self.task_queue.get()
            self.log.info('@@@@@ getQueue [%s] [%s/%s] [%s]', task.sid, task.dcode, task.dname, os.path.join(task.fpath, task.fname))

            if task.sid in self.speechmap:
                ret = RET_SUCCEED
                sid = task.sid
                self.recordState(sid, REC_WORKER_GET, task.msg)
                self.speechmap[sid][KEY_STATE] = task.state

                if self.stt_sock is None:
                    self.log.critical('????? Not Connected Engine.')
                    ret = RET_UNAVAILABLE
                elif task.state == STATE_DONE:
                    smsg = json.dumps(task.msg, ensure_ascii=False)
                    smsg = '{}{:8}'.format(PKT_RECOGNIZE_REQ, len(smsg)) + smsg
                    self.log.info('@@@@@ send fd({})\n{}\n{}'.format(self.stt_sock.fileno(), "Recognize Request", json.dumps(task.msg, indent=4, ensure_ascii=False)))
                    if self.sendMessage(self.stt_sock, smsg):
                        self.recordState(sid, REC_STTENGINE_SEND, task.msg)
                    else:
                        ret = RET_UNAVAILABLE
                elif task.state == STATE_NOFILE_ID:
                    ret = RET_NOTFOUND
                else:
                    ret = RET_ERROR

                if ret > RET_SUCCEED:
                    self.log.warning('????? cannot recognize request : speechID[{}] state[{}] result[{}]'.format(sid, task.state, ret))
                    self.recordState(sid, REC_TRANSCRIBE_END, None, ret)
            else:
                self.log.warning('????? already disconnnected. speechID[%s]', sid)
        return

    def httpHandler(self):
        self.log.info('<Start Thread httpHandler>')

        while True:
            rt = None
            jdata = self.http_queue.get()

            try:
                sid = jdata[KEY_SPEECHID]
                rt = requests.post(self.cfg.url, data=json.dumps(jdata, ensure_ascii=False), headers={"Content-Type" : "application/json"})
                self.log.info('speechID[{}] HTTP_POST[{}] => RESPONSE[{}]'.format(sid, rt.url, rt.status_code))
            except requests.exceptions.RequestException as e:
                self.log.error('????? requests error: {}'.format(e))
            except Exception as e:
                self.log.error('????? json error: {}'.format(e))

            if rt is None or rt.status_code > 202:
                with open(self.cfg.filepath+'records/webhook/'+sid, 'w') as f:
                    json.dump(jdata, f, ensure_ascii=False)
                    self.log.info('file created. [{}]'.format(self.cfg.filepath+'records/webhook/'+sid))
        return

    def recordState(self, sid, rstate, msg, ret=RET_SUCCEED):
        if sid in self.speechmap:
            if rstate == REC_TRANSCRIBE_BEGIN:
                self.speechmap[sid]["startTime"] = datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S.%f")
                self.speechmap[sid]["processInterval"] = []
                self.speechmap[sid]["data"] = {}
                self.speechmap[sid][KEY_STATE] = STATE_INIT

            if msg is not None:
                self.speechmap[sid]["data"] = msg
            delta = datetime.datetime.now() - datetime.datetime.strptime(self.speechmap[sid]["startTime"], "%Y.%m.%d %H:%M:%S.%f")
            self.speechmap[sid]["processInterval"].append("{} < {}".format(delta.total_seconds(), rstate))

            if rstate == REC_TRANSCRIBE_END:
                # 작업을 마무리한다.
                if KEY_SOCK in self.speechmap[sid]:
                    sock = self.speechmap[sid][KEY_SOCK]
                    if ret == RET_DISCONNECT:
                        self.log.info('@@@@@ fd({}) speechID({}) disconnected.'.format(sock.fileno(), sid))
                    else:
                        if msg is None:
                            smsg = '{"%s":"%d","%s":"%s","%s":"%s"}' % (KEY_RESULT, ret, KEY_SPEECHID, sid, KEY_STATE, self.speechmap[sid][KEY_STATE])
                            smsg = '{}{:8}'.format(PKT_TRANSCRIBE_RES, len(smsg)) + smsg
                            self.log.info('@@@@@ send fd({})\n{}\n{}'.format(sock.fileno(), "Transcribe Response", smsg[PKT_HEADER_LEN:]))
                        else:
                            msg[KEY_STATE] = self.speechmap[sid][KEY_STATE]
                            smsg = json.dumps(msg, ensure_ascii=False)
                            smsg = '{}{:8}'.format(PKT_TRANSCRIBE_RES, len(smsg)) + smsg
                            self.log.info('@@@@@ send fd({})\n{}\n{}'.format(sock.fileno(), "Transcribe Response", json.dumps(msg, indent=4, ensure_ascii=False)))
                        self.sendMessage(sock, smsg)
                else:
                    fid = self.speechmap[sid][KEY_FILE]
                    self.log.info('@@@@@ file path({})\nspeechID({}) {}'.format(fid, sid, "Transcribe Finish"))
                    if fid in self.filemap:
                        del self.filemap[fid]

                # records 폴더에 사용기록을 남긴다.
                wmsg = self.speechmap[sid]["data"]
                if KEY_SOCK in self.speechmap[sid]:
                    self.speechmap[sid][KEY_SOCK] = self.speechmap[sid][KEY_SOCK].fileno()
                with open(self.cfg.filepath+'records/{}'.format(datetime.datetime.now().strftime("%Y%m%d.json")), 'a') as f:
                    json.dump(self.speechmap[sid], f, indent=4, ensure_ascii=False)
                del self.speechmap[sid]

                # webhook 처리하도록 Queue에 넣는다.
                if self.http_queue is not None and msg is not None:
                    try:
                        self.log.info('@@@@@ httpQueue [%s]', sid)
                        self.http_queue.put_nowait(wmsg)
                    except Exception as e:
                        self.log.error('????? httpQueue Error: {}'.format(e))
                        with open(self.cfg.filepath+'records/webhook/'+sid, 'w') as f:
                            json.dump(wmsg, f, ensure_ascii=False)
                            self.log.info('file created. [{}]'.format(self.cfg.filepath+'records/webhook/'+sid))
        else:
            self.log.warning('????? not found in speechmap. speechID[%s]', sid)
        return

def main(homepath):
    sys.stdout.write('\n\n================[ Program Start ]============================= {}\n'.format(datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")))
    sys.stdout.write('Service Manager Daemon started with pid {}\n'.format(os.getpid()))
    sys.stdout.flush()

    # Application Config
    cfg = _config.ConfigObject(homepath)
    log = cfg.getLogger('Main')
    log.info(cfg)

    # Database
    try:
        mydb = _database.MYSQL(cfg)
        log.info('Database Connection')
    except Exception as e:
        log.error('????? database error: {}'.format(e))
        return

    # Queue Init
    agent_queue = multiprocessing.Queue()
    worker_queue = multiprocessing.Queue()

    # Process Init
    agent_proc = PacketAgent(cfg, (agent_queue, worker_queue))
    workers = [Worker(cfg, (worker_queue, agent_queue)) for _ in xrange(cfg.worker_processes)]

    # Daemon Flag Set
    agent_proc.daemon = True
    for proc in workers:
        proc.daemon = True

    # Process start
    agent_proc.start()
    for proc in workers:
        proc.start()

    # Process join
    agent_proc.join()
    for proc in workers:
        proc.join()

    mydb.close()

    sys.stdout.write('================[ Program End ]============================= {}\n'.format(datetime.datetime.now().strftime("%Y.%m.%d %H:%M:%S")))
    sys.stdout.flush()

def daemonize(pidno, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
    if pidno > 0:
        raise RuntimeError('Already running')

    # First fork (detaches from parent)
    try:
        if os.fork() > 0:
            raise SystemExit(0) # Parent exit
    except OSError:
        raise RuntimeError('fork #1 failed.')

    os.chdir('/')
    os.umask(0)
    os.setsid()

    # Second fork (relinquish session leadership)
    try:
        if os.fork() > 0:
            raise SystemExit(0)
    except OSError:
        raise RuntimeError('fork #2 failed.')

    # Flush I/O buffers
    sys.stdout.flush()
    sys.stderr.flush()

    # Replace file descriptors for stdin, stdout, and stderr
    with open(stdin, 'rb', 0) as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open(stdout, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open(stderr, 'ab', 0) as f:
        os.dup2(f.fileno(), sys.stderr.fileno())

    # Write the PID file
    #with open(pidfile, 'w') as f:
        #print(os.getpid(), file=f)

    # Arrange to have the PID file removed on exit/signal
    #import atexit
    #atexit.register(lambda: os.remove(pidfile))

    # Signal handler for termination (required)
    def sigterm_handler(signo, frame):
        print('sigterm_handler {} {}'.format(signo, frame), file=sys.stderr)
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, sigterm_handler)

if __name__ == '__main__':
    HOMEPATH = os.getcwd()+'/'
    LOGFILE = HOMEPATH+'psout.log'
    PID = _config.ConfigObject.getProcessID()

    if len(sys.argv) != 2:
        print('Usage: {} [start|stop]'.format(sys.argv[0]), file=sys.stderr)
        raise SystemExit(1)

    # Program Start
    if sys.argv[1] == 'start':
        try:
            daemonize(PID, stdout=LOGFILE, stderr=LOGFILE)
        except RuntimeError as err:
            print(err, file=sys.stderr)
            raise SystemExit(1)

        main(HOMEPATH)

    # Program Stop
    elif sys.argv[1] == 'stop':
        if PID > 0:
            os.kill(PID, signal.SIGTERM)
        else:
            print('Not running', file=sys.stderr)
            raise SystemExit(1)

    else:
        print('Unknown command {!r}'.format(sys.argv[1]), file=sys.stderr)
        raise SystemExit(1)
