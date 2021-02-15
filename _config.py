# pylint: disable=C0103,C0301,C0111
"""
    C0103: Invalid %s name
    C0301: Line too long
    C0111: Missing docstring
"""

from ConfigParser import SafeConfigParser

class ConfigObject(object):
    def __init__(self, filepath='./', filename='app.ini'):
        parser = SafeConfigParser()
        parser.read(filepath+filename)
        self.filepath = filepath
        self.filename = filename

        group = 'setting'
        self.mode = parser.get(group, 'mode')
        self.log_level = parser.get(group, 'log_level')
        self.version = parser.get(group, 'version')
        self.worker_processes = parser.getint(group, 'worker_processes')
        self.max_tasks = parser.getint(group, 'max_tasks')
        self.session_timeout = parser.getint(group, 'session_timeout_secs')

        group = 'task'
        self.isMP3 = parser.getboolean(group, 'mp3_backup')
        self.err_path = None if not parser.get(group, 'error_backup_path') else parser.get(group, 'error_backup_path')

        group = 'directory'
        self.dir_srcpath = None if not parser.get(group, 'audio_source_path') else parser.get(group, 'audio_source_path')
        self.dir_cvtpath = None if not parser.get(group, 'audio_convert_path') else parser.get(group, 'audio_convert_path')
        self.dir_interval = parser.getint(group, 'scan_interval_secs')

        group = 'server'
        self.ip = parser.get(group, 'ip')
        self.port = parser.getint(group, 'port')

        group = 'webhook'
        self.url = None if not parser.get(group, 'url') else parser.get(group, 'url')

        group = 'db'
        self.db_ip = parser.get(group, 'ip')
        self.db_port = parser.getint(group, 'port')
        self.db_user = parser.get(group, 'user')
        self.db_pass = parser.get(group, 'password')
        self.db_name = parser.get(group, 'name')

    def __str__(self):
        import operator
        parser = SafeConfigParser()
        parser.read(self.filepath+self.filename)
        retstr = '\n\n\n=========== ini file ===================\n'
        for section_name in parser.sections():
            parser.options(section_name)
            for name, value in parser.items(section_name):
                retstr += '[{}] {} = {}\n'.format(section_name, name, value)

        retstr += '\n=========== config =====================\n'
        sorted_dic = sorted(vars(self).iteritems(), key=operator.itemgetter(0))
        for name, value in sorted_dic:
            if name != 'parser':
                retstr += '{} = {}\n'.format(name, value)

        return retstr

    def getLogger(self, name):
        import logging
        import logging.handlers
        import os
        if self.log_level == 'debug':
            level = logging.DEBUG
        elif self.log_level == 'info':
            level = logging.INFO
        elif self.log_level == 'warning':
            level = logging.WARNING
        elif self.log_level == 'error':
            level = logging.ERROR
        elif self.log_level == 'critical':
            level = logging.CRITICAL
        else:
            level = logging.NOTSET

        logger = logging.getLogger(name)
        logger.setLevel(level)

        if self.mode == 'TEST':
            path = '{}logs'.format(self.filepath)
            if os.access(path, os.F_OK) is False:
                os.makedirs(path, 0755)

            path = '{}records'.format(self.filepath)
            if os.access(path, os.F_OK) is False:
                os.makedirs(path, 0755)

            path = '{}records/webhook'.format(self.filepath)
            if os.access(path, os.F_OK) is False:
                os.makedirs(path, 0755)

            handler = logging.FileHandler('{}logs/app.log'.format(self.filepath))

        else:
            path = '/home/rootdev/workcpp/servicemanager/records'
            if os.access(path, os.F_OK) is False:
                os.makedirs(path, 0755)

            path = '/home/rootdev/workcpp/servicemanager/records/webhook'
            if os.access(path, os.F_OK) is False:
                os.makedirs(path, 0755)

            logpath = '/home/rootdev/workcpp/servicemanager/logs'
            if os.access(logpath, os.F_OK) is False:
                os.makedirs(logpath, 0755)

            handler = logging.handlers.TimedRotatingFileHandler('{}/{}.log'.format(logpath, name), when='D', backupCount=31)

        handler.setLevel(level)

        formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        return logger

    @classmethod
    def getProcessID(cls, procname='python2.7'):
        import subprocess
        arg = 'ps -ef | grep \"' + procname + '\" | grep -v \"grep\"'
        ret = subprocess.Popen(arg, shell=True, stdout=subprocess.PIPE)
        data = ret.communicate()[0].split('\n')

        for line in data:
            psline = []
            for word in line.split(' '):
                if word:
                    psline.append(word)
            if len(psline) > 3 and int(psline[2]) == 1: # PPID
                return int(psline[1]) # PID
        return 0
