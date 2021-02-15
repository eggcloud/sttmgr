# pylint: disable=C0103,C0301,C0111
"""
    C0103: Invalid %s name
    C0301: Line too long
    C0111: Missing docstring
"""

import datetime
import pymysql
import os

class MYSQL(object):
    def __init__(self, cfg):
        try:
            self.connection = pymysql.connect(host=cfg.db_ip, port=cfg.db_port, user=cfg.db_user, password=cfg.db_pass, db=cfg.db_name, charset='utf8')
            self.cursor = self.connection.cursor(pymysql.cursors.DictCursor)
        except Exception:
            raise

    def close(self):
        self.connection.close()

    def commit(self):
        self.connection.commit()

    def execute(self, query, args={}):
        self.cursor.execute(query, args)

    def executeOne(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchone()
        return row

    def executeAll(self, query, args={}):
        self.cursor.execute(query, args)
        row = self.cursor.fetchall()
        return row

    def makeInsertSql(self, tname, data):
        if tname == "TB_STT_INFO_RECORD":
            sql  = "INSERT INTO TB_STT_INFO_RECORD ("
            sql += "SEQ"
            sql += ", TC_CALL_ID"
            sql += ", TC_CALL_STARTDATE"
            sql += ", TC_CALL_STARTTIME"
            sql += ", TC_CALL_ENDDATE"
            sql += ", TC_CALL_ENDTIME"
            sql += ", TC_DOMAIN_CODE"
            sql += ", TC_DOMAIN_NAME"
            sql += ", TC_AGENT_ID"
            sql += ", TC_AGENT_NAME"
            sql += ", TC_AGENT_EXTNO"
            sql += ", TC_AGENT_PHONENO"
            sql += ", TC_CUSTOMER_ID"
            sql += ", TC_CUSTOMER_NAME"
            sql += ", TC_CUSTOMER_PHONENO"
            sql += ", TC_FILE_ID"
            sql += ", TC_FILE_NAME"
            sql += ", TC_FILE_ORG_PATH"
            sql += ", TC_DOMAIN_SEQ"
            sql += ") VALUES (fn_get_seq('stt')"
            sql += ", '"+data.sid+"'"
            sql += ", '"+datetime.datetime.now().strftime("%Y-%m-%d")+"'"
            sql += ", '"+datetime.datetime.now().strftime("%H:%M:%S")+"'"
            sql += ", '"+datetime.datetime.now().strftime("%Y-%m-%d")+"'"
            sql += ", '"+datetime.datetime.now().strftime("%H:%M:%S")+"'"
            sql += ", '"+data.dcode+"'"
            sql += ", '"+data.dname+"'"
            sql += ", 'AID001'"
            sql += ", 'UNAME'"
            sql += ", '001'"
            sql += ", '5678'"
            sql += ", 'CID001'"
            sql += ", 'CNAME'"
            sql += ", '01023456789'"
            sql += ", '"+data.fid+"'"
            sql += ", '"+data.fname+"'"
            sql += ", '"+data.fpath+"'"
            sql += ", (SELECT SEQ FROM TB_CS_INFO_DOMAIN WHERE TC_DOMAIN_CODE='"+data.dcode+"')"
            sql += ") ;"
        else:
            raise Exception('unknown table name: {}'.format(tname))
        return sql

    def makeSelectSql(self, tname, data):
        if tname == "TB_STT_INFO_RECORD":
            sql  ="SELECT SEQ FROM TB_STT_INFO_RECORD";
            sql +=" WHERE TC_CALL_ID = '"+ data.sid + "';";

        elif tname == "TB_CS_INFO_DOMAIN":
            sql  ="SELECT SEQ FROM TB_CS_INFO_DOMAIN";
            sql +=" WHERE TC_USEYN = 1 AND TC_DOMAIN_CODE = '"+ data.dcode + "'";
            sql +=" ORDER BY SEQ DESC LIMIT 0, 1;"

        elif tname == "TB_CS_INFO_SVR_CONFIG":
            sql  ="SELECT SEQ FROM TB_CS_INFO_SVR_CONFIG";
            sql +=" WHERE TC_USEYN = 1 AND TC_DELETED = 0 AND TC_DOMAIN_SEQ = %d" % (data.msg["domainSeq"])
            sql +=" ORDER BY SEQ DESC LIMIT 0, 1;"

        else:
            raise Exception('unknown table name: {}'.format(tname))
        return sql

    def makeUpdateSql(self, tname, data, value=0):
        if tname == "TB_STT_CSCONN STATUS":
            sql  = "UPDATE TB_STT_CSCONN"
            sql += " SET TC_WORKSTATUS = %d" % (value)
            sql += " WHERE SEQ = %d;" % (data.msg['seq'])

        elif tname == "TB_STT_INFO_RECORD DELETE":
            sql  = "UPDATE TB_STT_INFO_RECORD"
            sql += " SET TC_FILE_DELETED = 1"
            sql += " WHERE SEQ = %d;" % (data.msg['seq'])

        elif tname == "TB_STT_INFO_RECORD MEDIA":
            sql  = "UPDATE TB_STT_INFO_RECORD"
            sql += " SET TC_FILE_WAV_NAME = '%s'" % (data.msg['audioWAV'])
            sql += ", TC_SERVER_SEQ = %d" % (data.msg['serverSeq'])
            sql += ", TC_DOMAIN_SEQ = %d" % (data.msg['domainSeq'])
            sql += ", TC_FILE_WAV_PATH = '%s'" % (data.msg['audioPath'])
            sql += " WHERE SEQ = %d;" % (data.msg['seq'])

        elif tname == "TB_STT_CSCONN MEDIA":
            sql  = "UPDATE TB_STT_CSCONN"
            sql += " SET TC_WORKSTATUS = %d" % (value)
            sql += ", TC_WORKMEDIA = '%s'" % (data.msg['audioMP3'])
            sql += ", TC_MEDIATYPE = 'S16LE'"
            sql += ", TC_STARTTIME = '%s'" % (datetime.datetime.now().strftime("%H:%M:%S.%f")[:12])
            sql += ", TC_SERVER_SEQ = %d" % (data.msg['serverSeq'])
            sql += ", TC_DOMAIN_SEQ = %d" % (data.msg['domainSeq'])
            sql += ", TC_IMAGE_SEQ = %d" % (data.msg['imageSeq'])
            sql += " WHERE SEQ = %d;" % (data.msg['seq'])
        else:
            raise Exception('unknown table name: {}'.format(tname))
        return sql
