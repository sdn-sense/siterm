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
import requests
from yaml import load as yload
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import WrongInputError
from DTNRMLibs.CustomExceptions import TooManyArgumentalValues
from DTNRMLibs.CustomExceptions import NotSupportedArgument
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand
from DTNRMLibs.HTTPLibrary import Requests


def getUTCnow():
    """ Get UTC Time"""
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


def getWebContentFromURL(url):
    """ TODO: Add some catches in future """
    out = requests.get(url)
    return out


class GitConfig(object):
    """ Git based configuration class """
    def __init__(self):
        self.config = {}
        self.defaults = {'SITENAME':   {'optional': False},
                         'GIT_REPO':   {'optional': True, 'default': 'sdn-sense/rm-configs'},
                         'GIT_URL':    {'optional': True, 'default': 'https://raw.githubusercontent.com/'},
                         'GIT_BRANCH': {'optional': True, 'default': 'master'},
                         'MD5':        {'optional': False}}
        self.logger = getStreamLogger()

    def getFullGitUrl(self, customAdds=None):
        """ Get Full Git URL """
        urlJoinList = [self.config['GIT_URL'], self.config['GIT_REPO'],
                       self.config['GIT_BRANCH'], self.config['SITENAME']]
        if customAdds:
            for item in customAdds:
                urlJoinList.append(item)
        return "/".join(urlJoinList)

    def getLocalConfig(self):
        """ Get local config for info where all configs are kept in git """
        if not os.path.isfile('/etc/dtnrm.yaml'):
            self.logger.debug('Config file /etc/dtnrm.yaml does not exist.')
            raise Exception('Config file /etc/dtnrm.yaml does not exist.')
        with open('/etc/dtnrm.yaml', 'r') as fd:
            self.config = yload(fd.read())
        for key, requirement in self.defaults.items():
            if key not in self.config.keys():
                # Check if it is optional or not;
                if not requirement['optional']:
                    self.logger.debug('Configuration /etc/dtnrm.yaml missing non optional config parameter %s', key)
                    raise Exception('Configuration /etc/dtnrm.yaml missing non optional config parameter %s' % key)
                else:
                    self.config[key] = requirement['default']

    def getGitAgentConfig(self):
        """
        https://raw.githubusercontent.com/sdn-sense/rm-configs/master/T2_US_Caltech/Agent01/main.yaml
        """
        if self.config['MAPPING']['type'] == 'Agent':
            url = self.getFullGitUrl([self.config['MAPPING']['config'], 'main.yaml'])
            self.config['MAIN'] = yload(getWebContentFromURL(url).text)
            return

    def getGitFEConfig(self):
        """
        https://raw.githubusercontent.com/sdn-sense/rm-configs/master/T2_US_Caltech/FE/auth.yaml
        https://raw.githubusercontent.com/sdn-sense/rm-configs/master/T2_US_Caltech/FE/main.yaml
        """
        if self.config['MAPPING']['type'] == 'FE':
            url = self.getFullGitUrl([self.config['MAPPING']['config'], 'main.yaml'])
            self.config['MAIN'] = yload(getWebContentFromURL(url).text)
            url = self.getFullGitUrl([self.config['MAPPING']['config'], 'auth.yaml'])
            self.config['AUTH'] = yload(getWebContentFromURL(url).text)
            return

    def getGitConfig(self):
        """get git config from configured github repo."""
        if not self.config:
            self.getLocalConfig()
        mapping = yload(getWebContentFromURL("%s/mapping.yaml" % self.getFullGitUrl()).text)
        if self.config['MD5'] not in mapping.keys():
            msg = 'Configuration is not available for this MD5 %s tag in GIT REPO %s' % \
                            (self.config['MD5'], self.config['GIT_REPO'])
            self.logger.debug(msg)
            raise Exception(msg)
        self.config['MAPPING'] = copy.deepcopy(mapping[self.config['MD5']])
        self.getGitFEConfig()
        self.getGitAgentConfig()


def getGitConfig():
    """ Wrapper before git config class. Retirns dictionary """
    gitConf = GitConfig()
    gitConf.getGitConfig()
    return gitConf.config


def getConfig(locations=None):
    """ Get parsed configuration in ConfigParser Format.
        This is used till everyone move to YAML based config.
        TODO: Move all to getGitConfig
    """
    del locations
    config = getGitConfig()
    tmpCp = ConfigParser.ConfigParser()
    if not isinstance(config, dict):
        print('ERROR: Config from Git returned not dictionary. Malformed yaml?')
        return None
    for key, item in config['MAIN'].items():
        tmpCp.add_section(key)
        print item, key
        for key1, item1 in item.items():
            out = item1
            if isinstance(item1, list):
                out = ",".join(item1)
            tmpCp.set(key, key1, str(out))
    return tmpCp


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
        """ Get UUID4 hash """
        newuuid4 = str(uuid.uuid4())
        return str(newuuid4 + inputText)

    def dumpFileContentAsJson(self, outFile, content, newHash=None):
        """ Dump File content with locks """
        del newHash
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
                    raise NotSupportedArgument("Parameter %s value not acceptable. Allowed options: [tT]rue,[fF]alse" %
                                               param['key'])
            elif param['type'] == str:
                if outVals[0] not in param['options']:
                    raise NotSupportedArgument("Server does not support parameter %s=%s. Supported: %s" %
                                               (param['key'], outVals[0], param['options']))
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
