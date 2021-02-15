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

