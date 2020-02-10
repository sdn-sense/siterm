#!/usr/bin/env python
"""
Everything goes here when they do not fit anywhere else

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
import os
import os.path
import cgi
import pwd
import shutil
import ast
import time
import shlex
import uuid
import json
import copy
import httplib
import base64
import datetime
import subprocess
import email.utils as eut
import ConfigParser
from cStringIO import StringIO
import logging
from logging import StreamHandler
from logging.handlers import TimedRotatingFileHandler
# Custom exceptions imports
import pycurl
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import WrongInputError
from DTNRMLibs.CustomExceptions import FailedToParseError
from DTNRMLibs.CustomExceptions import NoSectionError
from DTNRMLibs.CustomExceptions import NoOptionError
from DTNRMLibs.CustomExceptions import TooManyArgumentalValues
from DTNRMLibs.CustomExceptions import NotSupportedArgument
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand
from DTNRMLibs.HTTPLibrary import Requests

def getUTCnow():
    now = datetime.datetime.utcnow()
    timestamp = int(time.mktime(now.timetuple()))
    return timestamp

def getVal(conDict, **kwargs):
    """ Get value from configuration """
    if 'sitename' in kwargs.keys():
        if kwargs['sitename'] in conDict.keys():
            return conDict[kwargs['sitename']]
        else:
            raise Exception('This SiteName is not configured on the Frontend. Contact Support')
    else:
        print kwargs
        raise Exception('This Call Should not happen. Contact Support')


def getFullUrl(config, sitename=None):
    """ Prepare full URL from Config """
    webdomain = config.get('general', 'webdomain')
    if not sitename:
        sitename = config.get('general', 'sitename')
    if not webdomain.startswith("http"):
        webdomain = "http://" + webdomain
    return "%s/%s" % (webdomain, sitename)


def getStreamLogger(logLevel='DEBUG'):
    """ Get Stream Logger """
    levels = {'FATAL': logging.FATAL,
              'ERROR': logging.ERROR,
              'WARNING': logging.WARNING,
              'INFO': logging.INFO,
              'DEBUG': logging.DEBUG}
    logger = logging.getLogger()
    handler = StreamHandler()
    formatter = logging.Formatter("%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
                                  datefmt="%a, %d %b %Y %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(levels[logLevel])
    return logger

def getLogger(logFile='', logLevel='DEBUG', logOutName='api.log', rotateTime='midnight', backupCount=10):
    """ Get new Logger for logging """
    levels = {'FATAL': logging.FATAL,
              'ERROR': logging.ERROR,
              'WARNING': logging.WARNING,
              'INFO': logging.INFO,
              'DEBUG': logging.DEBUG}
    logger = logging.getLogger()
    createDirs(logFile)
    logFile += logOutName
    handler = TimedRotatingFileHandler(logFile, when=rotateTime, backupCount=backupCount)
    formatter = logging.Formatter("%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
                                  datefmt="%a, %d %b %Y %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(levels[logLevel])
    return logger


def evaldict(inputDict):
    """Output from the server needs to be evaluated"""
    out = {}
    try:
        out = ast.literal_eval(str(inputDict).encode('utf-8'))
    except ValueError as ex:
        print "Failed to literal eval dict. Err:%s " % ex
    except SyntaxError as ex:
        print "Failed to literal eval dict. Err:%s " % ex
    return out


def readFile(fileName):
    """Read all file lines to a list and rstrips the ending"""
    try:
        with open(fileName) as fd:
            content = fd.readlines()
        content = [x.rstrip() for x in content]
        return content
    except IOError:
        # File does not exist
        return []

def externalCommand(command, communicate=True):
    """Execute External Commands and return stdout and stderr"""
    command = shlex.split(str(command))
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if communicate:
        return proc.communicate()
    return proc


def execute(command, logger, raiseError=True):
    """ Execute interfaces commands. """
    logger.info('Asked to execute %s command' % command)
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    msg = 'Command: %s, Out: %s, Err: %s, ReturnCode: %s' % (command, out.rstrip(), err.rstrip(), cmdOut.returncode)
    logger.info(command)
    if cmdOut.returncode != 0 and raiseError:
        raise FailedInterfaceCommand(msg)
    elif cmdOut.returncode != 0:
        return False
    return True


def createDirs(fullDirPath):
    """ Create Directories on fullDirPath"""
    if not os.path.isdir(fullDirPath):
        try:
            os.makedirs(fullDirPath)
        except OSError as ex:
            print 'Received exception creating %s directory. Exception: %s' % (fullDirPath, ex)
    return


def publishToSiteFE(inputDict, host, url):
    """Put JSON to the Site FE"""
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb='PUT', data=json.dumps(inputDict))
    except httplib.HTTPException as ex:
        return (ex.message, ex.status, 'FAILED', True)
    except pycurl.error as ex:
        return (ex.args[1], ex.args[0], 'FAILED', False)
    return out

def getDataFromSiteFE(inputDict, host, url):
    """Get data from Site FE"""
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb='GET', data=inputDict)
    except httplib.HTTPException as ex:
        return (ex.message, ex.status, 'FAILED', True)
    except pycurl.error as ex:
        return (ex.args[1], ex.args[0], 'FAILED', False)
    return out

def getConfig(locations):
    """ Get parsed configuration """
    tmpCp = ConfigParser.ConfigParser()
    for fileName in locations:
        if os.path.isfile(fileName):
            tmpCp.read(fileName)
            return tmpCp
    return None


def getValueFromConfig(configPars, section, valName):
    """ Return value if available, else return None"""
    try:
        return configPars.get(section, valName)
    except ConfigParser.NoOptionError:
        msg = 'Configuration files does not have option %s in section %s defined' % (valName, section)
        raise NoOptionError(msg)
    except ConfigParser.NoSectionError:
        msg = 'Configuration files does not have section %s defined' % section
        raise NoSectionError(msg)
    return None


def getFileContentAsJson(inputFile):
    """ Get file content as json """
    out = {}
    if os.path.isfile(inputFile):
        with open(inputFile, 'r') as fd:
            try:
                out = json.load(fd)
            except ValueError:
                print fd.seek(0)
                out = evaldict(fd.read())
    return out


def getAllFileContent(inputFile):
    """ Get all file content as a string """
    if os.path.isfile(inputFile):
        with open(inputFile, 'r') as fd:
            return fd.read()
    raise NotFoundError('File %s was not found on the system.' % inputFile)

def getUsername():
    """Return current username"""
    return pwd.getpwuid(os.getuid())[0]

class contentDB(object):
    """ File Saver, loader class """
    def __init__(self, logger=None, config=None):
        self.config = config
        self.logger = logger


    def getFileContentAsJson(self, inputFile):
        """ Get file content as json """
        return getFileContentAsJson(inputFile)

    def getHash(self, inputText):
        newuuid4 = str(uuid.uuid4())
        return str(newuuid4 + inputText)

    def dumpFileContentAsJson(self, outFile, content, newHash=None):
        """ Dump File content with locks """
        tmpoutFile = outFile + '.tmp'
        with open(tmpoutFile, 'w+') as fd:
            json.dump(content, fd)
        shutil.move(tmpoutFile, outFile)
        return True

    def saveContent(self, destFileName, outputDict):
        """ Saves all content to a file """
        newHash = self.getHash("This-to-replace-with-date-and-Service-Name")
        return self.dumpFileContentAsJson(destFileName, outputDict, newHash)

    def removeFile(self, fileLoc):
        """ Remove file """
        if os.path.isfile(fileLoc):
            os.unlink(fileLoc)
            return True
        return False


def delete(inputObj, delObj):
    """ Delete function which covers exceptions"""
    if isinstance(inputObj, list):
        tmpList = copy.deepcopy(inputObj)
        try:
            tmpList.remove(delObj)
        except ValueError as ex:
            print 'Delete object %s is not in inputObj %s list. Err: %s' % (delObj, tmpList, ex)
        return tmpList
    elif isinstance(inputObj, dict):
        tmpDict = copy.deepcopy(inputObj)
        try:
            del tmpDict[delObj]
        except KeyError as ex:
            print 'Delete object %s is not in inputObj %s dict. Err: %s' % (delObj, tmpList, ex)
        return tmpDict
    # This should not happen
    raise WrongInputError('Provided input type is not available for deletion. Type %s' % type(inputObj))


def read_input_data(environ):
    """Read input data from environ, which can be used for PUT or POST"""
    length = int(environ.get('CONTENT_LENGTH', 0))
    if length == 0:
        raise WrongInputError('Content input length is 0.')
    body = StringIO(environ['wsgi.input'].read(length))
    outjson = {}
    try:
        outjson = json.loads(body.getvalue())
    except ValueError as ex:
        errMsg = 'Failed to parse json input: %s, Err: %s. Did caller used json.dumps?' % (body.getvalue(), ex)
        print errMsg
        raise WrongInputError(errMsg)
    return outjson

VALIDATION = {"addhost": [{"key": "hostname", "type": basestring},
                          {"key": "ip", "type": basestring},
                          {"key": "port", "type": int},
                          {"key": "insertTime", "type": int},
                          {"key": "updateTime", "type": int},
                          {"key": "status", "type": basestring, "values": ["benchmark", "maintenance", "operational"]},
                          {"key": "desc", "type": basestring}],
              "updatehost": [{"key": "ip", "type": basestring},
                             {"key": "port", "type": int},
                             {"key": "updateTime", "type": int},
                             {"key": "status", "type": basestring,
                              "values": ["benchmark", "maintenance", "operational"]}]}


def validateInput(inputDict, validationKey):
    """Validate input with VALIDATION predefined config.
       In case of issue raises NotFoundError or WrongInputError"""
    return


def configOut(location, mandatoryOptions=None):
    """ Check configuration if all needed options are defined """
    defaults = [{"varName": "logdir", "varType": str, "varDefault": "/var/log/dtnrm/"},
                {"varName": "loglevel", "varType": str, "varDefault": "DEBUG"},
                {"varName": "logmaxbytes", "varType": int, "varDefault": 2000000},
                {"varName": "logbackupCount", "varType": int, "varDefault": 5}]
    config = getConfig(location)
    if not config:
        raise Exception("Configuration file is not available... Please refer to documentation")
    # Check config file if all options are available
    if not mandatoryOptions:
        return config
    for section, optionsList in mandatoryOptions.items():
        if not config.has_section(section):
            msg = "Configuration file does not have %s section defined. Please refer to documentation" % section
            raise Exception(msg)
        for option in optionsList:
            if not config.has_option(section, option):
                msg = "Configuration file does not have %s option defined. Please refer to documentation" % option
                raise Exception(msg)
    for section in config.sections():
        for default in defaults:
            if default['varName'] not in config.options(section):
                config.set(section, default['varName'], str(default['varDefault']))
            else:
                try:
                    if default['varType'] == str:
                        config.get(section, default['varName'])
                    elif default['varType'] == int:
                        config.getint(section, default['varName'])
                    elif default['varType'] == bool:
                        config.getboolean(section, default['varName'])
                except ValueError as ex:
                    raise ValueError(ex)
    return config


def generateHash(inText):
    """ Generate unique using uuid """
    del inText
    return str(uuid.uuid1())

def getCustomOutMsg(errMsg=None, errCode=None, msg=None, exitCode=None):
    """ Create custom return dictionary """
    newOut = {}
    if errMsg:
        newOut['error_description'] = errMsg
    if errCode:
        newOut['error'] = errCode
    if msg:
        newOut['msg'] = msg
    if exitCode:
        newOut['exitCode'] = exitCode
    return newOut

def getDefaultConfigAgent(componentName='api', configIn=None, loggerIn=None, confloc=None, streamLogger=False):
    """ Get default configuration and logger for agents """
    if confloc:
        configIn = configOut([confloc])
    else:
        configIn = configOut(['/etc/dtnrm/main.conf', 'dtnrmagent.conf'])
    createDirs("%s/%s/" % (configIn.get('general', 'logDir'), componentName))
    if not loggerIn:
        if streamLogger:
            loggerIn = getStreamLogger(configIn.get('general', 'logLevel'))
        else:
            loggerIn = getLogger("%s/%s/" % (configIn.get('general', 'logDir'), componentName),
                                 configIn.get('general', 'logLevel'),
                                 '%s.log' % componentName,
                                 configIn.get('general', 'rotate'),
                                 configIn.get('general', 'logbackupCount'))
    return configIn, loggerIn

def getUrlParams(environ, paramsList):
    """ Get URL parameters and return them in dictionary """
    if not paramsList:
        return {}
    if environ['REQUEST_METHOD'].upper() in ['POST']:
        # POST will handle by himself
        # TODO. It should set back the correct methods and input so that multiple places can use it.
        return {}
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
    outParams = {}
    for param in paramsList:
        # {"key": "summary", "default": True, "type": bool},
        # {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}
        outVals = form.getlist(param['key'])
        if len(outVals) > 1:
            raise TooManyArgumentalValues("Parameter %s has too many defined values" % param['key'])
        if len(outVals) == 1:
            if param['type'] == bool:
                if outVals[0] in ['true', 'True']:
                    outParams[param['key']] = True
                elif outVals[0] in ['false', 'False']:
                    outParams[param['key']] = False
                else:
                    raise NotSupportedArgument("Parameter %s value is not acceptable. Allowed options: [tT]rue,[fF]alse" % param['key'])
            elif param['type'] == str:
                if outVals[0] not in param['options']:
                    raise NotSupportedArgument("Server does not support parameter %s=%s. Supported: %s" % (param['key'], outVals[0], param['options']))
        elif not outVals:
            outParams[param['key']] = param['default']
    print outParams
    return outParams

def getHeaders(environ):
    """ Get all Headers and return them back as dictionary """
    headers = {}
    for key in environ.keys():
        if key.startswith('HTTP_'):
            headers[key[5:]] = environ.get(key)
    return headers

def convertTSToDatetime(inputTS):
    """ Convert timestamp to datetime """
    return datetime.datetime.fromtimestamp(int(inputTS)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def httpdate(timestamp):
    """
    Return a string representation of a date according to RFC 1123 (HTTP/1.1).
    """
    dat = datetime.datetime.fromtimestamp(int(timestamp))
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dat.weekday()]
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
             "Oct", "Nov", "Dec"][dat.month - 1]
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dat.day, month, dat.year,
                                                    dat.hour, dat.minute, dat.second)

def httptimestamp(inhttpdate):
    """
    Return timestamp from RFC1123 (HTTP/1.1).
    """
    dat = datetime.datetime(*eut.parsedate(inhttpdate)[:5])
    return int(time.mktime(dat.timetuple()))

def getModTime(headers):
    """ Get modification time from the headers """
    modTime = 0
    if 'IF_MODIFIED_SINCE' in headers:
        modTime = httptimestamp(headers['IF_MODIFIED_SINCE'])
    return modTime


def encodebase64(inputStr, encodeFlag=True):
    """ Encode str to base64 """
    if encodeFlag and inputStr:
        return base64.b64encode(inputStr)
    return inputStr


def decodebase64(inputStr, decodeFlag=True):
    """ Decode base64 to real format """
    if decodeFlag and inputStr:
        return base64.b64decode(inputStr)
    return inputStr

def mergeTwoDicts(inDict1, inDict2):
    originCopy = inDict1.copy()   # start with x's keys and values
    originCopy.update(inDict2)    # modifies z with y's keys and values & returns None
    return originCopy
