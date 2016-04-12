#!/usr/bin/env python
# -*- coding:utf-8 -*-


"""
   Life's short, Python more.
"""

import sys
import os
import json
import uuid
import signal
import time
import subprocess
from optparse import OptionParser


##begin cli & help logic
def getOptionParser():
    parser = OptionParser(usage = getUsage())
    #rdbms reader and writer
    parser.add_option('-r', '--reader', action='store', dest='reader', help='trace datasource read performance with specified !json! string')
    parser.add_option('-w', '--writer', action='store', dest='writer', help='trace datasource write performance with specified !json! string')

    parser.add_option('-c', '--channel',  action='store', dest='channel', default='1', help='the number of concurrent sync thread, the default is 1')
    parser.add_option('-f', '--file',   action='store', help='existing datax configuration file, include reader and writer params')
    parser.add_option('-t', '--type',   action='store', default='reader', help='trace which side\'s performance, cooperate with -f --file params, need to be reader or writer')
    parser.add_option('-d', '--delete',   action='store', default='true', help='delete temporary files, the default value is true')
    return parser

def getUsage():
    return '''

The following params are available for -r --reader:
    [these params is for rdbms reader, used to trace rdbms read performance, it's like datax's key]
    *datasourceType: datasource type, may be mysql|drds|oracle|ads|sqlserver|postgresql|db2 etc...
    *jdbcUrl:        datasource jdbc connection string, mysql as a example: jdbc:mysql://ip:port/database
    *username:       username for datasource
    *password:       password for datasource
    *table:          table name for read data
    column:          column to be read, the default value is ['*']
    splitPk:         the splitPk column of rdbms table
    where:           limit the scope of the performance data set
    fetchSize:       how many rows to be fetched at each communicate

    [these params is for stream reader, used to trace rdbms write performance]
    reader-sliceRecordCount:how man test data to mock(each channel), the default value is 10000
    reader-column          :stream reader while generate test data(type supports: string|long|date|double|bool|bytes; support constant value and random mixup function)，demo: [{"type":"string","value":"abc"},{"type":"string","mixup":"random(10,20)"}]

The following params are available for -w --writer:
    [these params is for rdbms writer, used to trace rdbms write performance, it's like datax's key]
    datasourceType:  datasource type, may be mysql|drds|oracle|ads|sqlserver|postgresql|db2|ads etc...
    *jdbcUrl:        datasource jdbc connection string, mysql as a example: jdbc:mysql://ip:port/database
    *username:       username for datasource
    *password:       password for datasource
    *table:          table name for write data
    column:          column to be writed, the default value is ['*']
    batchSize:       how many rows to be storeed at each communicate, the default value is 512
    preSql:          prepare sql to be executed before write data, the default value is ''
    postSql:         post sql to be executed end of write data, the default value is ''
    url:             required for ads, pattern is ip:port
    schme:           required for ads, ads database name

    [these params is for stream writer, used to trace rdbms read performance]
    writer-print:           true means print data read from source datasource, the default value is false

The following params are available global control:
    -c --channel:        the number of concurrent tasks, the default value is 1
    -f --file:           existing completely dataX configuration file path
    -t --readerOrWriter: test read or write performance for a datasource, couble be reader or writer, in collaboration with -f --file

some demo:
dtrace.py --channel=10 --reader='{"jdbcUrl":"jdbc:mysql://127.0.0.1:3306/database", "username":"", "password":"", "table": "", "where":"", "splitPk":"", "writer-print":"false"}'
dtrace.py --channel=10 --writer='{"jdbcUrl":"jdbc:mysql://127.0.0.1:3306/database", "username":"", "password":"", "table": "", "reader-column": [{"type":"string","value":"abc"},{"type":"string","mixup":"random(10,20)"}]}'
dtrace.py --file=/tmp/datax.job.json --type=reader

some example jdbc url pattern, may help:
jdbc:oracle:thin:@ip:port:database
jdbc:mysql://ip:port/database
jdbc:sqlserver://ip:port;DatabaseName=database
jdbc:postgresql://ip:port/database
warn: ads is ip:port
'''

def printCopyright():
    DATAX_VERSION = 'UNKNOWN_DATAX_VERSION'
    print '''
DataX (%s), From Alibaba !
Copyright (C) 2010-2015, Alibaba Group. All Rights Reserved.
''' % DATAX_VERSION
    sys.stdout.flush()


def yesNoChoice():
    yes = set(['yes','y', 'ye', ''])
    no = set(['no','n'])
    choice = raw_input().lower()
    if choice in yes:
        return True
    elif choice in no:
        return False
    else:
        sys.stdout.write("Please respond with 'yes' or 'no'")
##end cli & help logic


##begin process logic
def suicide(signum, e):
    global childProcess
    print >> sys.stderr, "[Error] Receive unexpected signal %d, starts to suicide." % (signum)
    if childProcess:
        childProcess.send_signal(signal.SIGQUIT)
        time.sleep(1)
        childProcess.kill()
    print >> sys.stderr, "DataX Process was killed ! you did ?"
    sys.exit(-1)


def registerSignal():
    global childProcess
    signal.signal(2, suicide)
    signal.signal(3, suicide)
    signal.signal(15, suicide)


def fork(command, isShell=False):
    global childProcess
    childProcess = subprocess.Popen(command, shell = isShell)
    registerSignal()
    (stdout, stderr) = childProcess.communicate()
    #阻塞直到子进程结束
    childProcess.wait()
    return childProcess.returncode
##end process logic


##begin datax json generate logic
#warn: if not '': -> true;   if not None: -> true
def notNone(obj, context):
    if not obj:
        raise Exception("Configuration property [%s] could not be blank!" % (context))

def attributeNotNone(obj, attributes):
    for key in attributes:
        notNone(obj.get(key), key)

def isBlank(value):
    if value is None or len(value.strip()) == 0:
        return True
    return False

def parsePluginName(jdbcUrl, pluginType):
    import re
    #warn: drds
    name = 'pluginName'
    mysqlRegex = re.compile('jdbc:(mysql)://.*')
    if (mysqlRegex.match(jdbcUrl)):
        name = 'mysql'
    postgresqlRegex = re.compile('jdbc:(postgresql)://.*')
    if (postgresqlRegex.match(jdbcUrl)):
        name = 'postgresql'
    oracleRegex = re.compile('jdbc:(oracle):.*')
    if (oracleRegex.match(jdbcUrl)):
        name = 'oracle'
    sqlserverRegex = re.compile('jdbc:(sqlserver)://.*')
    if (sqlserverRegex.match(jdbcUrl)):
        name = 'sqlserver'
    db2Regex = re.compile('jdbc:(db2)://.*')
    if (db2Regex.match(jdbcUrl)):
        name = 'db2'
    return "%s%s" % (name, pluginType)

def renderDataXJson(paramsDict, readerOrWriter = 'reader', channel = 1):
    dataxTemplate = {
        "job": {
            "setting": {
                "speed": {
                    "channel": 1
                }
            },
            "content": [
                {
                    "reader": {
                        "name": "",
                        "parameter": {
                            "username": "",
                            "password": "",
                            "column": [
                                "*"
                            ],
                            "connection": [
                                {
                                    "table": [],
                                    "jdbcUrl": []
                                }
                            ]
                        }
                    },
                    "writer": {
                        "name": "",
                        "parameter": {
                            "print": "false",
                            "connection": [
                                {
                                    "table": [],
                                    "jdbcUrl": ''
                                }
                            ]
                        }
                    }
                }
            ]
        }
    }
    dataxTemplate['job']['setting']['speed']['channel'] = channel
    dataxTemplateContent = dataxTemplate['job']['content'][0]

    pluginName = ''
    if paramsDict.get('datasourceType'):
        pluginName = '%s%s' % (paramsDict['datasourceType'], readerOrWriter)
    elif paramsDict.get('jdbcUrl'):
        pluginName = parsePluginName(paramsDict['jdbcUrl'], readerOrWriter)
    elif paramsDict.get('url'):
        pluginName = 'adswriter'

    theOtherSide = 'writer' if readerOrWriter == 'reader' else 'reader'
    dataxPluginParamsContent = dataxTemplateContent.get(readerOrWriter).get('parameter')
    dataxPluginParamsContent.update(paramsDict)

    dataxPluginParamsContentOtherSide = dataxTemplateContent.get(theOtherSide).get('parameter')

    if readerOrWriter == 'reader':
        dataxTemplateContent.get('reader')['name'] = pluginName
        dataxTemplateContent.get('writer')['name'] = 'streamwriter'
        if paramsDict.get('writer-print'):
            dataxPluginParamsContentOtherSide['print'] = paramsDict['writer-print']
            del dataxPluginParamsContent['writer-print']
        del dataxPluginParamsContentOtherSide['connection']
    if readerOrWriter == 'writer':
        dataxTemplateContent.get('reader')['name'] = 'streamreader'
        dataxTemplateContent.get('writer')['name'] = pluginName
        if paramsDict.get('reader-column'):
            dataxPluginParamsContentOtherSide['column'] = paramsDict['reader-column']
            del dataxPluginParamsContent['reader-column']
        if paramsDict.get('reader-sliceRecordCount'):
            dataxPluginParamsContentOtherSide['sliceRecordCount'] = paramsDict['reader-sliceRecordCount']
            del dataxPluginParamsContent['reader-sliceRecordCount']
        del dataxPluginParamsContentOtherSide['connection']

    if paramsDict.get('jdbcUrl'):
        if readerOrWriter == 'reader':
            dataxPluginParamsContent['connection'][0]['jdbcUrl'].append(paramsDict['jdbcUrl'])
        else:
            dataxPluginParamsContent['connection'][0]['jdbcUrl'] = paramsDict['jdbcUrl']
    if paramsDict.get('table'):
        dataxPluginParamsContent['connection'][0]['table'].append(paramsDict['table'])


    traceJobJson = json.dumps(dataxTemplate, indent = 4)
    return traceJobJson


def parseJson(strConfig, context):
    try:
        return json.loads(strConfig)
    except Exception, e:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        print >> sys.stderr, '%s %s need in line with json syntax' % (context, strConfig)
        sys.exit(-1)

def convert(options, args):
    traceJobJson = ''
    if options.file:
        fileopen = open(options.file, 'r')
        traceJobJson = fileopen.read()
        traceJobDict = parseJson(traceJobJson, '%s content' % options.file)
        if options.type == 'reader':
            traceJobDict['job']['content'][0]['writer']['name'] = 'streamwriter'
            traceJobDict['job']['content'][0]['writer']['parameter']['print'] = 'false'
        else:
            #do nothing
            pass
        return json.dumps(traceJobDict, indent = 4)
    elif options.reader:
        traceReaderDict = parseJson(options.reader, 'reader config')
        return renderDataXJson(traceReaderDict, 'reader', options.channel)
    elif options.writer:
        traceReaderDict = parseJson(options.writer, 'writer config')
        return renderDataXJson(traceReaderDict, 'writer', options.channel)
    else:
        raise Exception('type params should be reader or writer')
    #dataxParams = {}
    #for opt, value in options.__dict__.items():
    #    dataxParams[opt] = value
##end datax json generate logic


if __name__ == "__main__":
    printCopyright()
    parser = getOptionParser()

    options, args = parser.parse_args(sys.argv[1:])
    #print options, args
    dataxTraceJobJson = convert(options, args)

    #由MAC地址、当前时间戳、随机数生成,可以保证全球范围内的唯一性
    dataxJobPath = os.path.join(os.getcwd(), "perftrace-" + str(uuid.uuid1()))
    jobConfigOk = True
    if os.path.exists(dataxJobPath):
        print "file already exists, truncate and rewrite it? %s" % dataxJobPath
        if yesNoChoice():
            jobConfigOk = True
        else:
            print "exit failed, because of file conflict"
            sys.exit(-1)
    fileWriter = open(dataxJobPath, 'w')
    fileWriter.write(dataxTraceJobJson)
    fileWriter.close()


    print "trace environments:"
    print "dataxJobPath:  %s" % dataxJobPath
    dataxHomePath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print "dataxHomePath: %s" % dataxHomePath

    dataxCommand = "%s %s" % (os.path.join(dataxHomePath, "bin", "datax.py"), dataxJobPath)
    print "dataxCommand:  %s" % dataxCommand

    returncode = fork(dataxCommand, True)
    if options.delete == 'true':
        os.remove(dataxJobPath)
    sys.exit(returncode)
