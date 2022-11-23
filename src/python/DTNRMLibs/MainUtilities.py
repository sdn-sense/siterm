#!/usr/bin/env python3
"""Everything goes here when they do not fit anywhere else.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import os
import os.path
import io
import sys
import cgi
import pwd
import shutil
import ast
import time
import shlex
import uuid
import copy
import socket
import http.client
import base64
import datetime
import subprocess
import hashlib
import email.utils as eut
import logging
import logging.handlers
from past.builtins import basestring
import simplejson as json
# Custom exceptions imports
import pycurl
import requests
from yaml import safe_load as yload
from rdflib import Graph
from DTNRMLibs import __version__ as runningVersion
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import WrongInputError
from DTNRMLibs.CustomExceptions import TooManyArgumentalValues
from DTNRMLibs.CustomExceptions import NotSupportedArgument
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand
from DTNRMLibs.CustomExceptions import NoSectionError
from DTNRMLibs.CustomExceptions import NoOptionError
from DTNRMLibs.HTTPLibrary import Requests
from DTNRMLibs.DBBackend import dbinterface


def isValFloat(inVal):
    """Check if inVal is float"""
    try:
        float(inVal)
    except ValueError:
        return False
    return True


def getUTCnow():
    """Get UTC Time."""
    now = datetime.datetime.utcnow()
    timestamp = int(time.mktime(now.timetuple()))
    return timestamp


def getVal(conDict, **kwargs):
    """Get value from configuration."""
    if 'sitename' in kwargs:
        if kwargs['sitename'] in list(conDict.keys()):
            return conDict[kwargs['sitename']]
        raise Exception('This SiteName is not configured on the Frontend. Contact Support')
    print(kwargs)
    raise Exception('This Call Should not happen. Contact Support')


def getFullUrl(config, sitename=None):
    """Prepare full URL from Config."""
    webdomain = config.get('general', 'webdomain')
    if not sitename:
        sitename = config.get('general', 'sitename')
    if not webdomain.startswith("http"):
        webdomain = "http://" + webdomain
    return f"{webdomain}/{sitename}"

def checkLoggingHandler(**kwargs):
    """Check if logging handler is present and return True/False"""
    if logging.getLogger(kwargs.get('service', __name__)).hasHandlers():
        for handler in logging.getLogger(kwargs.get('service', __name__)).handlers:
            if isinstance(handler, kwargs['handler']):
                return handler
    return None


LEVELS = {'FATAL': logging.FATAL,
          'ERROR': logging.ERROR,
          'WARNING': logging.WARNING,
          'INFO': logging.INFO,
          'DEBUG': logging.DEBUG}


def getStreamLogger(**kwargs):
    """Get Stream Logger."""
    kwargs['handler'] = logging.StreamHandler
    handler = checkLoggingHandler(**kwargs)
    logger = logging.getLogger(kwargs.get('service', __name__))
    if not handler:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
                                      datefmt="%a, %d %b %Y %H:%M:%S")
        handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(LEVELS[kwargs.get('logLevel', 'DEBUG')])
    return logger

def getLoggingObject(**kwargs):
    """Get logging Object, either Timed FD or Stream"""
    if kwargs.get('logType', 'TimedRotatingFileHandler') == 'TimedRotatingFileHandler':
        return getTimeRotLogger(**kwargs)
    return getStreamLogger(**kwargs)

def getTimeRotLogger(**kwargs):
    """Get new Logger for logging."""
    kwargs['handler'] = logging.handlers.TimedRotatingFileHandler
    handler = checkLoggingHandler(**kwargs)
    if 'logFile' not in kwargs:
        if 'config' in kwargs:
            kwargs['logFile'] = f"{kwargs['config'].get('general', 'logDir')}/{kwargs.get('service', __name__)}/"
        else:
            print('No config passed, will log to StreamLogger... Code issue!')
            return getStreamLogger(**kwargs)
    logFile = kwargs.get('logFile', '') + kwargs.get('logOutName', 'api.log')
    logger = logging.getLogger(kwargs.get('service', __name__))
    if not handler:
        createDirs(logFile)
        handler = logging.handlers.TimedRotatingFileHandler(logFile,
                                                            when=kwargs.get('rotateTime', 'midnight'),
                                                            backupCount=kwargs.get('backupCount', 5))
        formatter = logging.Formatter("%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
                                      datefmt="%a, %d %b %Y %H:%M:%S")
        handler.setFormatter(formatter)
        handler.setLevel(LEVELS[kwargs.get('logLevel', 'DEBUG')])
        logger.addHandler(handler)
    logger.setLevel(LEVELS[kwargs.get('logLevel', 'DEBUG')])
    return logger


def evaldict(inputDict):
    """Output from the server needs to be evaluated."""
    if not inputDict:
        return {}
    if isinstance(inputDict, (list, dict)):
        return inputDict
    out = {}
    try:
        out = ast.literal_eval(inputDict)
    except ValueError:
        out = json.loads(inputDict)
    except SyntaxError as ex:
        raise WrongInputError(f"SyntaxError: Failed to literal eval dict. Err:{ex} ") from ex
    return out

def readFile(fileName):
    """Read all file lines to a list and rstrips the ending."""
    try:
        with open(fileName, 'r', encoding='utf-8') as fd:
            content = fd.readlines()
        content = [x.rstrip() for x in content]
        return content
    except IOError:
        # File does not exist
        return []

def externalCommand(command, communicate=True):
    """Execute External Commands and return stdout and stderr."""
    command = shlex.split(str(command))
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if communicate:
        return proc.communicate()
    return proc

def execute(command, logger, raiseError=True):
    """Execute interfaces commands."""
    logger.info(f'Asked to execute {command} command')
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    msg = f'Command: {command}, Out: {out.rstrip()}, Err: {err.rstrip()}, ReturnCode: {cmdOut.returncode}'
    if cmdOut.returncode != 0 and raiseError:
        raise FailedInterfaceCommand(msg)
    if cmdOut.returncode != 0:
        logger.debug(f"RaiseError is False, but command failed. Only logging Errmsg: {msg}")
        return False
    return True

def createDirs(fullDirPath):
    """Create Directories on fullDirPath."""
    if not fullDirPath:
        return
    dirname = os.path.dirname(fullDirPath)
    if not os.path.isdir(dirname):
        try:
            os.makedirs(dirname)
        except OSError as ex:
            print(f'Received exception creating {dirname} directory. Exception: {ex}')
            if not os.path.isdir(dirname):
                raise
    return

def publishToSiteFE(inputDict, host, url):
    """Put JSON to the Site FE."""
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb='PUT', data=json.dumps(inputDict))
    except http.client.HTTPException as ex:
        return (ex.reason, ex.status, 'FAILED', True)
    except pycurl.error as ex:
        return (ex.args[1], ex.args[0], 'FAILED', False)
    return out

def getDataFromSiteFE(inputDict, host, url):
    """Get data from Site FE."""
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb='GET', data=inputDict)
    except http.client.HTTPException as ex:
        return (ex.reason, ex.status, 'FAILED', True)
    except pycurl.error as ex:
        return (ex.args[1], ex.args[0], 'FAILED', False)
    return out

def getWebContentFromURL(url):
    """TODO: Add some catches in future."""
    out = requests.get(url)
    return out

def reCacheConfig(prevHour=None):
    """Return prevHour == currentHour, currentHour and used in Service Object
    re-initiation."""
    datetimeNow = datetime.datetime.now()
    currentHour = datetimeNow.strftime('%H')
    return prevHour == currentHour, currentHour

class GitConfig():
    """Git based configuration class."""
    def __init__(self):
        self.config = {}
        self.defaults = {'SITENAME':   {'optional': False},
                         'GIT_REPO':   {'optional': True, 'default': 'sdn-sense/rm-configs'},
                         'GIT_URL':    {'optional': True, 'default': 'https://raw.githubusercontent.com/'},
                         'GIT_BRANCH': {'optional': True, 'default': 'master'},
                         'MD5':        {'optional': False}}

    @staticmethod
    def gitConfigCache(name):
        """Get Config file from tmp dir"""
        output = None
        filename = f'/tmp/dtnrm-link-{name}.yaml'
        if os.path.isfile(filename):
            with open(filename, 'r', encoding='utf-8') as fd:
                output = yload(fd.read())
        else:
            raise Exception(f'Config file {filename} does not exist.')
        return output

    def getFullGitUrl(self, customAdds=None):
        """Get Full Git URL."""
        urlJoinList = [self.config['GIT_URL'], self.config['GIT_REPO'],
                       self.config['GIT_BRANCH'], self.config['SITENAME']]
        if customAdds:
            for item in customAdds:
                urlJoinList.append(item)
        return "/".join(urlJoinList)

    def getLocalConfig(self):
        """Get local config for info where all configs are kept in git."""
        if not os.path.isfile('/etc/dtnrm.yaml'):
            print('Config file /etc/dtnrm.yaml does not exist.')
            raise Exception('Config file /etc/dtnrm.yaml does not exist.')
        with open('/etc/dtnrm.yaml', 'r', encoding='utf-8') as fd:
            self.config = yload(fd.read())
        for key, requirement in list(self.defaults.items()):
            if key not in list(self.config.keys()):
                # Check if it is optional or not;
                if not requirement['optional']:
                    print('Configuration /etc/dtnrm.yaml missing non optional config parameter %s', key)
                    raise Exception(f'Configuration /etc/dtnrm.yaml missing non optional config parameter {key}')
                self.config[key] = requirement['default']

    def __addDefaults(self, defaults):
        """Add default config parameters"""
        for key1, val1 in defaults.items():
            self.config.setdefault(key1, {})
            for key2, val2 in val1.items():
                self.config[key1].setdefault(key2, {})
                for key3, val3 in val2.items():
                    self.config[key1][key2].setdefault(key3, val3)

    def presetAgentDefaultConfigs(self):
        """Preset default config parameters for Agent"""
        defConfig = {'MAIN': {'general': {'logDir': '/var/log/dtnrm-agent/',
                                          'logLevel': 'INFO',
                                          'private_dir': '/opt/siterm/config/'}}}
        self.__addDefaults(defConfig)

    def getGitAgentConfig(self):
        """Get Git Agent Config."""
        if self.config['MAPPING']['type'] == 'Agent':
            self.config['MAIN'] = self.gitConfigCache('Agent-main')
            self.presetAgentDefaultConfigs()

    @staticmethod
    def __genValFromItem(inVal):
        """Generate int value from vlan range item"""
        if isinstance(inVal, int):
            return [inVal]
        retVals = []
        tmpvals = inVal.split('-')
        if len(tmpvals) == 2:
            # Need to loop as it is range;
            # In case second val is bigger than 1st - raise Exception
            if int(tmpvals[0]) >= int(tmpvals[1]):
                raise Exception(f'Configuration Error. Vlan Range equal or lower. Vals: {tmpvals}')
            for i in range(int(tmpvals[0]), int(tmpvals[1])+1):
                retVals.append(i)
        else:
            retVals.append(int(tmpvals[0]))
        return retVals

    def __generateVlanList(self, vals):
        """Generate Vlan List. which can be separated by comma, dash"""
        retVals = []
        tmpVals = vals
        if isinstance(vals, int):
            return [vals]
        if not isinstance(vals, list):
            tmpVals = vals.split(',')
        for val in tmpVals:
            for lval in self.__genValFromItem(val):
                retVals.append(int(lval))
        return retVals

    @staticmethod
    def __generateIPList(vals):
        """Split by command and return list"""
        if isinstance(vals, list):
            return vals
        return list(filter(None, vals.split(',')))

    # TODO: Move all to public function, not private. Needed for agents
    generateIPList=__generateIPList
    generateVlanList=__generateVlanList

    def __generatevlaniplists(self):
        """Generate list for vlans and ips. config might have it in str"""
        for sitename in self.config['MAIN']['general']['sites']:
            for iptype in ['ipv6', 'ipv4']:
                for key in ['subnet-pool', 'address-pool']:
                    if f"{iptype}-{key}" in self.config['MAIN'][sitename].keys():
                        nlist = self.__generateIPList(self.config['MAIN'][sitename][f"{iptype}-{key}"])
                        self.config['MAIN'][sitename][f"{iptype}-{key}-list"] = nlist
            if 'vlan_range' in self.config['MAIN'][sitename]:
                nlist = self.__generateVlanList(self.config['MAIN'][sitename]["vlan_range"])
                self.config['MAIN'][sitename]["vlan_range_list"] = nlist
            # Now we do all individual switches. If key not available;
            # Will use the default if available
            for switch in self.config['MAIN'][sitename]['switch']:
                for iptype in ['ipv6', 'ipv4']:
                    for key in ['subnet-pool', 'address-pool']:
                        if f"{iptype}-{key}" in self.config['MAIN'][switch].keys():
                            nlist = self.__generateIPList(self.config['MAIN'][switch][f"{iptype}-{key}"])
                            self.config['MAIN'][switch][f"{iptype}-{key}-list"] = nlist
                        elif f"{iptype}-{key}-list" in self.config['MAIN'][sitename]:
                            tmp = self.config['MAIN'][sitename][f"{iptype}-{key}-list"]
                            self.config['MAIN'][switch][f"{iptype}-{key}-list"] = tmp
                if 'vlan_range' in self.config['MAIN'][switch]:
                    nlist = self.__generateVlanList(self.config['MAIN'][switch]["vlan_range"])
                    self.config['MAIN'][switch]["vlan_range_list"] = nlist
                elif 'vlan_range_list' in self.config['MAIN'][sitename]:
                    self.config['MAIN'][switch]["vlan_range_list"] = self.config['MAIN'][sitename]['vlan_range_list']
                # Also review all predefined vlan_ranges for individual ports and make a list
                for key in list(self.config['MAIN'][switch].keys()):
                    if key.startswith('port_') and key.endswith('vlan_range'):
                        nlist = self.__generateVlanList(self.config['MAIN'][switch][key])
                        self.config['MAIN'][switch][f"{key}_list"] = nlist

    def presetFEDefaultConfigs(self):
        """Preset default config parameters for FE"""
        defConfig = {'MAIN': {'general': {'logDir': '/var/log/dtnrm-site-fe/',
                                          'logLevel': 'INFO',
                                          'private_dir': '/opt/siterm/config/'},
                              'ansible': {'private_data_dir': '/opt/siterm/config/ansible/sense/',
                                          'inventory': '/opt/siterm/config/ansible/sense/inventory/inventory.yaml',
                                          'rotate_artifacts': 100,
                                          'ignore_logging': False,
                                          'debug': False,
                                          'inventory_host_vars_dir': '/opt/siterm/config/ansible/sense/inventory/host_vars/'},
                              'prefixes': {'mrs': "http://schemas.ogf.org/mrs/2013/12/topology#",
                                           'nml': "http://schemas.ogf.org/nml/2013/03/base#",
                                           'owl': "http://www.w3.org/2002/07/owl#",
                                           'rdf': "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                                           'rdfs': "http://www.w3.org/2000/01/rdf-schema#",
                                           'schema': "http://schemas.ogf.org/nml/2012/10/ethernet",
                                           'sd': "http://schemas.ogf.org/nsi/2013/12/services/definition#",
                                           'site': "urn:ogf:network",
                                           'xml': "http://www.w3.org/XML/1998/namespace#",
                                           'xsd': "http://www.w3.org/2001/XMLSchema#"}}}
        self.__addDefaults(defConfig)
        # Generate list vals - not in a str format. Needed in delta checks
        self.__generatevlaniplists()

    def getGitFEConfig(self):
        """Get Git FE Config."""
        if self.config['MAPPING']['type'] == 'FE':
            self.config['MAIN'] = self.gitConfigCache('FE-main')
            self.config['AUTH'] = self.gitConfigCache('FE-auth')
            self.presetFEDefaultConfigs()

    def getGitConfig(self):
        """Get git config from configured github repo."""
        if not self.config:
            self.getLocalConfig()
        mapping = self.gitConfigCache('mapping')
        if self.config['MD5'] not in list(mapping.keys()):
            msg = 'Configuration is not available for this MD5 %s tag in GIT REPO %s' % \
                            (self.config['MD5'], self.config['GIT_REPO'])
            print(msg)
            raise Exception(msg)
        self.config['MAPPING'] = copy.deepcopy(mapping[self.config['MD5']])
        self.getGitFEConfig()
        self.getGitAgentConfig()


def getGitConfig():
    """Wrapper before git config class. Returns dictionary."""
    gitConf = GitConfig()
    gitConf.getGitConfig()
    return gitConf.config


class getConfig():
    """Get Config"""
    def __init__(self):
        self.git = GitConfig()
        self.git.getGitConfig()

    def __getitem__(self, item):
        """Subscribable item lookup"""
        return self.git.config['MAIN'][item]

    def get(self, key, subkey):
        """Custom get from dictionary in a way like configparser"""
        if key not in self.git.config['MAIN']:
            raise NoSectionError(f'{key} is not available in configuration.')
        if subkey not in self.git.config['MAIN'][key]:
            raise NoOptionError(f'{subkey} is not available under {key} section in configuration.')
        return self.git.config['MAIN'].get(key, {}).get(subkey, {})

    def getraw(self, key):
        """Get RAW DICT of key"""
        return self.git.config.get(key, {})

    def getboolean(self, key, subkey):
        """Return boolean"""
        val = self.get(key, subkey)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ('yes', 'true', '1')

    def has_section(self, key):
        """Check if section available"""
        if self.git.config['MAIN'].get(key, {}):
            return True
        return False

    def has_option(self, key, subkey):
        """Check if option available"""
        if not self.git.config['MAIN'].get(key, {}):
            raise NoSectionError(f'{key} section is not available in configuration.')
        if self.git.config['MAIN'].get(key, {}).get(subkey, {}):
            return True
        return False


def getFileContentAsJson(inputFile):
    """Get file content as json."""
    out = {}
    if os.path.isfile(inputFile):
        with open(inputFile, 'r', encoding='utf-8') as fd:
            try:
                out = json.load(fd)
            except ValueError:
                print(fd.seek(0))
                out = evaldict(fd.read())
    return out


def getAllFileContent(inputFile):
    """Get all file content as a string."""
    if os.path.isfile(inputFile):
        with open(inputFile, 'r', encoding='utf-8') as fd:
            return fd.read()
    raise NotFoundError(f'File {inputFile} was not found on the system.')


def getUsername():
    """Return current username."""
    return pwd.getpwuid(os.getuid())[0]


class contentDB():
    """File Saver, loader class."""
    def __init__(self, config=None):
        self.config = config if config else getConfig()
        self.logger = getLoggingObject(config=self.config, service='contentdb')

    @staticmethod
    def getFileContentAsJson(inputFile):
        """Get file content as json."""
        return getFileContentAsJson(inputFile)

    @staticmethod
    def getHash(inputText):
        """Get UUID4 hash."""
        newuuid4 = str(uuid.uuid4())
        return str(newuuid4 + inputText)

    @staticmethod
    def dumpFileContentAsJson(outFile, content):
        """Dump File content with locks."""
        tmpoutFile = outFile + '.tmp'
        with open(tmpoutFile, 'w+', encoding='utf-8') as fd:
            json.dump(content, fd)
        shutil.move(tmpoutFile, outFile)
        return True

    def saveContent(self, destFileName, outputDict):
        """Saves all content to a file."""
        return self.dumpFileContentAsJson(destFileName, outputDict)

    @staticmethod
    def removeFile(fileLoc):
        """Remove file."""
        if os.path.isfile(fileLoc):
            os.unlink(fileLoc)
            return True
        return False

    def moveFile(self, sourcefile, destdir):
        """Move file from sourcefile to dest dir"""
        if not os.path.isfile(sourcefile):
            raise Exception(f'File {sourcefile} does not exist')
        if sourcefile.startswith(destdir):
            # We dont want to move if already in dest dir
            return sourcefile
        destFile = os.path.join(destdir, self.getHash('.json'))
        shutil.move(sourcefile, destFile)
        return destFile

def delete(inputObj, delObj):
    """Delete function which covers exceptions."""
    if isinstance(inputObj, list):
        tmpList = copy.deepcopy(inputObj)
        try:
            tmpList.remove(delObj)
        except ValueError as ex:
            print(f'Delete object {delObj} is not in inputObj {tmpList} list. Err: {ex}')
        return tmpList
    if isinstance(inputObj, dict):
        tmpDict = copy.deepcopy(inputObj)
        try:
            del tmpDict[delObj]
        except KeyError as ex:
            print(f'Delete object {delObj} is not in inputObj {tmpList} dict. Err: {ex}')
        return tmpDict
    # This should not happen
    raise WrongInputError(f'Provided input type is not available for deletion. Type {type(inputObj)}')

def parse_gui_form_post(inputVal):
    """Parse GUI Form Post and return dict."""
    out = {}
    for item in inputVal.split(b'&'):
        tmpItem = item.split(b'=')
        out[tmpItem[0].decode("utf-8")] = tmpItem[1].decode("utf-8")
    return out

def read_input_data(environ):
    """Read input data from environ, which can be used for PUT or POST."""
    length = int(environ.get('CONTENT_LENGTH', 0))
    if length == 0:
        raise WrongInputError('Content input length is 0.')
    if sys.version.startswith('3.'):
        body = io.BytesIO(environ['wsgi.input'].read(length))
    else:
        body = io.StringIO(environ['wsgi.input'].read(length))
    outjson = {}
    try:
        outjson = json.loads(body.getvalue())
    except ValueError as ex:
        outjson = parse_gui_form_post(body.getvalue())
        if not outjson:
            errMsg = f'Failed to parse json input: {body.getvalue()}, Err: {ex}.'
            print(errMsg)
            raise WrongInputError(errMsg) from ex
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
def generateMD5(inText):
    """Generate MD5 from provided str"""
    hashObj = hashlib.md5(inText.encode())
    return hashObj.hexdigest()

def generateHash(inText):
    """Generate unique using uuid."""
    return str(uuid.uuid1(len(inText)))


def getCustomOutMsg(errMsg=None, errCode=None, msg=None, exitCode=None):
    """Create custom return dictionary."""
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
    """Get URL parameters and return them in dictionary."""
    if not paramsList:
        return {}
    if environ['REQUEST_METHOD'].upper() in ['POST']:
        # POST will handle by himself
        return {}
    form = cgi.FieldStorage(fp=environ['wsgi.input'], environ=environ)
    outParams = {}
    for param in paramsList:
        # {"key": "summary", "default": True, "type": bool},
        # {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}
        outVals = form.getlist(param['key'])
        if len(outVals) > 1:
            raise TooManyArgumentalValues(f"Parameter {param['key']} has too many defined values")
        if len(outVals) == 1:
            if param['type'] == bool:
                if outVals[0] in ['true', 'True']:
                    outParams[param['key']] = True
                elif outVals[0] in ['false', 'False']:
                    outParams[param['key']] = False
                else:
                    raise NotSupportedArgument("Parameter %s value not acceptable. Allowed options: [tT]rue,[fF]alse" %
                                               param['key'])
            elif param['type'] == str and outVals[0] not in param['options']:
                raise NotSupportedArgument("Server does not support parameter %s=%s. Supported: %s" %
                                           (param['key'], outVals[0], param['options']))
        elif not outVals:
            outParams[param['key']] = param['default']
    print(outParams)
    return outParams


def getHeaders(environ):
    """Get all Headers and return them back as dictionary."""
    headers = {}
    for key in list(environ.keys()):
        if key.startswith('HTTP_'):
            headers[key[5:]] = environ.get(key)
    return headers


def convertTSToDatetime(inputTS):
    """Convert timestamp to datetime."""
    dtObj = datetime.datetime.fromtimestamp(int(inputTS))
    return dtObj.strftime('%Y-%m-%dT%H:%M:%S.000+0000')


def httpdate(timestamp):
    """Return a string representation of a date according to RFC 1123
    (HTTP/1.1)."""
    dat = datetime.datetime.fromtimestamp(int(timestamp))
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dat.weekday()]
    month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
             "Oct", "Nov", "Dec"][dat.month - 1]
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dat.day, month, dat.year,
                                                    dat.hour, dat.minute, dat.second)


def httptimestamp(inhttpdate):
    """Return timestamp from RFC1123 (HTTP/1.1)."""
    dat = datetime.datetime(*eut.parsedate(inhttpdate)[:5])
    return int(time.mktime(dat.timetuple()))


def getModTime(headers):
    """Get modification time from the headers."""
    modTime = 0
    if 'IF_MODIFIED_SINCE' in headers:
        modTime = httptimestamp(headers['IF_MODIFIED_SINCE'])
    return modTime


def encodebase64(inputStr, encodeFlag=True):
    """Encode str to base64."""
    if encodeFlag and inputStr:
        if isinstance(inputStr, bytes):
            return base64.b64encode(inputStr.encode('UTF-8'))
        return base64.b64encode(bytes(inputStr.encode('UTF-8')))
    return inputStr


def decodebase64(inputStr, decodeFlag=True):
    """Decode base64 to real format."""
    if decodeFlag and inputStr:
        return base64.b64decode(inputStr)
    return inputStr


def getDBConn(serviceName='', cls=None):
    """Get database connection."""
    dbConn = {}
    if hasattr(cls, 'config'):
        config = cls.config
    else:
        config = getConfig()
    for sitename in config.get('general', 'sites'):
        if hasattr(cls, 'dbI'):
            if hasattr(cls.dbI, sitename):
                # DB Object is already in place!
                continue
        dbConn[sitename] = dbinterface(serviceName, config, sitename)
    return dbConn

def reportServiceStatus(**kwargs):
    """Report service state to DB."""
    reported = True
    try:
        dbOut = {'hostname': kwargs.get('hostname', 'default'),
                 'servicestate': kwargs.get('servicestate', 'UNSET'),
                 'servicename': kwargs.get('servicename', 'UNSET'),
                 'runtime': kwargs.get('runtime', -1),
                 'version': kwargs.get('version', runningVersion),
                 'updatedate': getUTCnow()}
        dbI = getDBConn(dbOut['servicename'], kwargs.get('cls', None))
        dbobj = getVal(dbI, **{'sitename': kwargs.get('sitename', 'UNSET')})
        services = dbobj.get('servicestates', search=[['hostname', dbOut['hostname']],
                                                      ['servicename', dbOut['servicename']]])
        if not services:
            dbobj.insert('servicestates', [dbOut])
        else:
            dbobj.update('servicestates', [dbOut])
    except NoOptionError:
        reported = False
    except Exception:
        excType, excValue = sys.exc_info()[:2]
        print("Error details in reportServiceStatus. ErrorType: %s, ErrMsg: %s",
               str(excType.__name__), excValue)
        reported = False
    return reported


def pubStateRemote(**kwargs):
    """Publish state from remote services."""
    reported = reportServiceStatus(**kwargs)
    if reported:
        return
    try:
        fullUrl = getFullUrl(kwargs['cls'].config, kwargs['sitename'])
        fullUrl += '/sitefe'
        dic = {'servicename': kwargs['servicename'],
               'servicestate': kwargs['servicestate'],
               'sitename': kwargs['sitename'],
               'runtime': kwargs['runtime'],
               'hostname': socket.gethostname(),
               'version': runningVersion,
               }
        publishToSiteFE(dic, fullUrl, '/json/frontend/servicestate')
    except Exception:
        excType, excValue = sys.exc_info()[:2]
        print(f"Error details in pubStateRemote. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")

def getCurrentModel(cls, raiseException=False):
    """Get Current Model from DB."""
    currentModel = cls.dbI.get('models', orderby=['insertdate', 'DESC'], limit=1)
    currentGraph = Graph()
    if currentModel:
        try:
            currentGraph.parse(currentModel[0]['fileloc'], format='turtle')
        except IOError as ex:
            if raiseException:
                raise NotFoundError(f"Model failed to parse from DB. Error {ex}") from IOError
            currentGraph = Graph()
    elif raiseException:
        raise NotFoundError("There is no model in DB. LookUpService is running?")
    return currentModel, currentGraph

def getActiveDeltas(cls):
    """Get Active deltas from DB."""
    activeDeltas = cls.dbI.get('activeDeltas')
    if not activeDeltas:
        return {'insertdate': int(getUTCnow()),
                'output': {}}
    activeDeltas = activeDeltas[0]
    activeDeltas['output'] = evaldict(activeDeltas['output'])
    return activeDeltas

def writeActiveDeltas(cls, newConfig):
    """Write Active Deltas to DB"""
    activeDeltas = cls.dbI.get('activeDeltas')
    action = 'update'
    if not activeDeltas:
        action = 'insert'
        activeDeltas = {'insertdate': int(getUTCnow())}
    else:
        activeDeltas = activeDeltas[0]
    activeDeltas['updatedate'] = int(getUTCnow())
    activeDeltas['output'] = str(newConfig)
    if action ==  'insert':
        cls.dbI.insert('activeDeltas', [activeDeltas])
    elif action == 'update':
        cls.dbI.update('activeDeltas', [activeDeltas])

def strtolist(intext, splitter):
    """Str To List, separated by splitter"""
    if isinstance(intext, list):
        return intext
    out = intext.split(splitter)
    return list(filter(None, out))
