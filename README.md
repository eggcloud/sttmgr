# ServiceManager

### Introduction

Batch STT Engine (sgsas_lstm) 과 연동하는 부분을 개선하여 유지보수 및 모니터링을 위한 구조 개선에 목적이 있습니다.  
상세한 설계 내용은 `Service Manager Architecture.doc` 참조하여 주시면 됩니다.

### Version History
#### 1.0  
Initial version included:
* Connecting with STT Engine
    * Messages : Transcribe, Recognize, Monitor
    * Scan directory 
* Multi-process workers
* Session timeout settings
* Max concurrent tasks setting
* Webhook settings
* MySQL client
* System monitoring
* Usage detail record

### Message Definition

| Header (12bytes) | Body |
| :-----: | :------ |
|PacketType(4bytes)+PacketLength(8bytes)| JSON DATA |

| Result | Description |
| :-----: | :------ |
| 0 | OK |
| 1 | Already Connected |
| 2 | Unsupported Service  |
| 3 | Service Unavailable |
| 4 | Not Found |
| 5 | Request Timeout |
| 6 | Too Many Requests |
| 7 | Bad Request |
| 8 | Disconnected |
| 9 | Error |

* Transcribe Request (1002)
    ```json
    {
        "speechID": "<uuid>",
        "domainName": "<domain name>",
        "domainCode": "<domain code>",
        "fileID": "<file id>",
        "fileName": "<file name>",
        "filePath": "<file path>",
        "audioPath": "<audio path>"
    }
    ```
* Transcribe Response (2002)
    ```json
    {
        "result": "0",
        "state": "DONE",
        "speechID": "<uuid>",
        "transcipt": "<text>"
    }
    ```
* Recognize Request (3001)
    ```json
    {
        "speechID": "<uuid>",
        "domainName": "<domain name>",
        "domainCode": "<domain code>",
        "fileID": "<file id>",
        "fileName": "<file name>",
        "filePath": "<file path>",
        "seq": 622923,
        "serverSeq": 1,
        "domainSeq": 1,
        "imageSeq": 4,
        "audioPath": "<audio file path>",
        "audioWAV": "<wav file name>",
        "audioMP3": "<mp3 file name>",
        "channels": 2,
    }
    ```
* Recognize Response (4001)
    ```json
    {
        "result": "0",
        "speechID": "<uuid>",
        "transcipt": "<text>"
    }
    ```
* Monitor Request (1003)
    ```json
    {
        "type": "all"
    }
    ```
* Monitor Response (2003)
    ```json
    {
        "version": "1.0",
        "engine": {
            "sttengine": true
        },
        "task": [
            {
                "speechID": "ddffeerr",
                "startTime": "2021.01.26 13:25:39.320333",
                "state": "INIT"
            }
        ],
        "disk": [
            {
                "used": "198.2G",
                "mount": "/",
                "percent": 88,
                "free": "26.7G",
                "device": "/dev/disk1s1",
                "total": "233.6G",
                "type": "apfs"
            },
            {
                "used": "8.0G",
                "mount": "/private/var/vm",
                "percent": 23,
                "free": "26.7G",
                "device": "/dev/disk1s4",
                "total": "233.6G",
                "type": "apfs"
            }
        ],
        "cpu": {
            "system": 13.2,
            "idle": 79.3,
            "user": 7.4,
            "nice": 0.0
        },
        "memory": {
            "available": 2825515008,
            "used": 5543821312,
            "percent": 67.1,
            "free": 463429632,
            "availableB2H": "2.6G",
            "inactive": 2357448704,
            "wired": 3076673536,
            "totalB2H": "8.0G",
            "active": 2467147776,
            "total": 8589934592
        }
    }
    ```

### Python Environments

 - python2.7
 - pip2.7 없다면 아래 명령으로 설치
> $ curl https://bootstrap.pypa.io/2.7/get-pip.py -o get-pip.py  
> $ sudo python2.7 get-pip.py
 - pip2 install requests
 - pip2 install pymysql
 - pip2 install psutil

### Configure
* app.ini
```ini
[setting]
mode = TEST
log_level = debug
version = 1.0
worker_processes = 1
max_tasks = 100
session_timeout_secs = 30

[task]
mp3_backup = true
error_backup_path = /home/rootdev/error

[directory]
audio_source_path = /home/rootdev/batch
audio_target_path = /home/rootdev/batch/rec_mp3
scan_interval_secs = 40

[server]
ip = 0.0.0.0
port = 9099

[webhook]
url = http://www.data.io/speech

[db]
ip = 192.168.0.241
port = 3306
user = root
password = secure
name = SGSAS2
```

### Running

* start.sh
```sh
python2.7 svcmgr.py start
```

* stop.sh
```sh
python2.7 svcmgr.py stop
```

* check.sh
```sh
#!/bin/sh

CMS_PROCESS_COUNT=`ps -ef | grep "python2.7" | grep -v 'grep' | awk '{print $2}' | wc | awk '{print $1}'`
CMS_PROCESS_PID=`ps -ef | grep "python2.7" | grep -v 'grep' | awk '{print $2}'`

#wc 명령은 count 를 세는 명령이므로 이렇게 하면 밑에 처럼 숫자로 표시 가능
echo "Operating SVCMGR Count : "$CMS_PROCESS_COUNT
if [ "$CMS_PROCESS_COUNT" = "0" ]; then
    echo "SVCMGR not found."
else
    echo "SVCMGR pid : "$CMS_PROCESS_PID
fi
```

### Logging
* logs  
TEST 모드에서는 `logs/app.log` 모든 로그가 기록되어 디버깅에 편리하도록 하며,  
다른 모드에서는 로그 경로를 지정하여 프로세스별, 일자별로 기록이 됩니다.  
관련 코드는 `_config.py`에 있으며, 적절하게 수정하시면 됩니다.
```python
if self.mode == 'TEST':
    handler = logging.FileHandler('{}logs/app.log'.format(self.filepath))
else:
    logpath = '/home/rootdev/workcpp/servicemanager/logs'
    if os.access(logpath, os.F_OK) is False:
        os.makedirs(logpath, 0755)
    handler = logging.handlers.TimedRotatingFileHandler('{}/{}.log'.format(logpath, name), when='D', backupCount=31)
```

 * records  
STT 결과 및 동작 시간을 `records/YYMMDD.json` 파일에 기록합니다.  
webhook url 주소가 등록되어 있다면, HTTP POST 응답 실패 경우에 `records/webhook/<speechID>` 파일로 STT 결과를 저장합니다.
```json
{
    "data": {
        "speechID": "ddffeerr",
        "transcript": "고기고기",
        "result": "0"
    },
    "socket": 20,
    "state": "DONE",
    "startTime": "2021.01.25 11:20:14.082971",
    "processInterval": [
        "0.000143 < TRANSCRIBE_START",
        "0.000259 < WORKER_PUT",
        "0.086758 < WORKER_GET",
        "0.087556 < STT_SEND",
        "0.304505 < STT_RECV",
        "0.305224 < TRANSCRIBE_END"
    ]
}
```

### Debugging
프로세스 시작 정보 및 처리하지 못한 예외가 발생하면 `psout.log` 파일에 기록됩니다.  
코드 변경이 이루어졌거나 동작이 멈추면 `psout.log` 파일을 확인해 보는게 좋습니다.  
아래는 예외가 발생한 예시입니다.
```
================[ Program Start ]============================= 2021.01.20 14:01:07
Service Manager Daemon started with pid 2153
Process PacketAgent-1:
Traceback (most recent call last):
  File "/System/Library/Frameworks/Python.framework/Versions/2.7/lib/python2.7/multiprocessing/process.py", line 267, in _bootstrap
    self.run()
  File "svcmgr.py", line 271, in run
    self.transcribeComplete(jdata)
  File "svcmgr.py", line 294, in transcribeComplete
    with open('./records/{}'.format(datetime.datetime.now().strftime("%Y%m%d.json")), 'a') as f:
IOError: [Errno 2] No such file or directory: './records/20210120.json'
```
