#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Everything goes here when they do not fit anywhere else.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import sys
import base64
import cgi
import copy
import datetime
import email.utils as eut
import hashlib
import http.client
import io
import logging
import logging.handlers
import os
import os.path
import fcntl
import functools
import pwd
import shlex
import shutil
import socket
import subprocess
import time
import uuid
import urllib.parse
import re

# Custom exceptions imports
import pycurl
import requests
import simplejson as json
from past.builtins import basestring
from rdflib import Graph
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.CustomExceptions import FailedInterfaceCommand, WrongInputError
from SiteRMLibs.CustomExceptions import NotFoundError, NotSupportedArgument, TooManyArgumentalValues
from SiteRMLibs.DBBackend import dbinterface
from SiteRMLibs.HTTPLibrary import Requests


HOSTSERVICES = ["Agent", "Ruler", "Debugger", "LookUpService", "ProvisioningService", "SNMPMonitoring",
                "DBWorker", "PolicyService", "SwitchWorker", "Prometheus-Push", "Arp-Push", "ConfigFetcher"]

def dictSearch(key, var, ret, ignoreKeys=None):
    """Search item in dictionary"""
    if isinstance(var, dict):
        for k, v in var.items():
            if ignoreKeys and k in ignoreKeys:
                continue
            if k == key:
                ret.append(v)
            elif isinstance(v, dict):
                ret = dictSearch(key, v, ret, ignoreKeys)
            elif isinstance(v, list):
                for d in v:
                    ret = dictSearch(key, d, ret, ignoreKeys)
    elif isinstance(var, list):
        for d in var:
            ret = dictSearch(key, d, ret, ignoreKeys)
    return ret


def isValFloat(inVal):
    """Check if inVal is float"""
    try:
        float(inVal)
    except ValueError:
        return False
    return True


def getUTCnow(**kwargs):
    """Get UTC Time."""
    # In case kwargs are passed, we need to return time in the future.
    # check all parameters passed and ensure we take only valid ones.
    if kwargs:
        # Generate new dictionary with only valid keys.
        validKeys = ["seconds", "minutes", "hours", "days", "weeks", "months", "years"]
        newKwargs = {k: v for k, v in kwargs.items() if k in validKeys}
        # years and months are not supported by timedelta, so we need to calculate them manually.
        if "years" in newKwargs:
            newKwargs["days"] = newKwargs.get("days", 0) + newKwargs["years"] * 365
            del newKwargs["years"]
        if "months" in newKwargs:
            newKwargs["days"] = newKwargs.get("days", 0) + newKwargs["months"] * 30
            del newKwargs["months"]
        delta = datetime.timedelta(**newKwargs)
        return int((datetime.datetime.now(datetime.timezone.utc) + delta).timestamp())
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def getVal(conDict, **kwargs):
    """Get value from configuration."""
    if "sitename" in kwargs:
        if kwargs["sitename"] in list(conDict.keys()):
            return conDict[kwargs["sitename"]]
        raise Exception(
            "This SiteName is not configured on the Frontend. Contact Support"
        )
    raise Exception("This Call Should not happen. Contact Support")


def getFullUrl(config, sitename=None):
    """Prepare full URL from Config."""
    webdomain = config.get("general", "webdomain")
    if not sitename:
        sitename = config.get("general", "sitename")
    if not webdomain.startswith("http"):
        webdomain = "http://" + webdomain
    return f"{webdomain}/{sitename}"


def checkLoggingHandler(**kwargs):
    """Check if logging handler is present and return True/False"""
    if logging.getLogger(kwargs.get("service", __name__)).hasHandlers():
        for handler in logging.getLogger(kwargs.get("service", __name__)).handlers:
            if isinstance(handler, kwargs["handler"]):
                return handler
    return None


LEVELS = {
    "FATAL": logging.FATAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
}


def getStreamLogger(**kwargs):
    """Get Stream Logger."""
    kwargs["handler"] = logging.StreamHandler
    handler = checkLoggingHandler(**kwargs)
    logger = logging.getLogger(kwargs.get("service", __name__))
    if not handler:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
            datefmt="%a, %d %b %Y %H:%M:%S",
        )
        handler.setFormatter(formatter)
    if not logger.handlers:
        logger.addHandler(handler)
    logger.setLevel(LEVELS[kwargs.get("logLevel", "DEBUG")])
    return logger


def getLoggingObject(**kwargs):
    """Get logging Object, either Timed FD or Stream"""
    if kwargs.get("logType", "TimedRotatingFileHandler") == "TimedRotatingFileHandler":
        return getTimeRotLogger(**kwargs)
    return getStreamLogger(**kwargs)


def getTimeRotLogger(**kwargs):
    """Get new Logger for logging."""
    kwargs["handler"] = logging.handlers.TimedRotatingFileHandler
    handler = checkLoggingHandler(**kwargs)
    if "logFile" not in kwargs:
        if "config" in kwargs:
            kwargs[
                "logFile"
            ] = f"{kwargs['config'].get('general', 'logDir')}/{kwargs.get('service', __name__)}/"
        else:
            print("No config passed, will log to StreamLogger... Code issue!")
            return getStreamLogger(**kwargs)
    logFile = kwargs.get("logFile", "") + kwargs.get("logOutName", "api.log")
    logger = logging.getLogger(kwargs.get("service", __name__))
    if not handler:
        createDirs(logFile)
        handler = logging.handlers.TimedRotatingFileHandler(
            logFile,
            when=kwargs.get("rotateTime", "midnight"),
            backupCount=kwargs.get("backupCount", 5),
        )
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
            datefmt="%a, %d %b %Y %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.setLevel(LEVELS[kwargs.get("logLevel", "DEBUG")])
        logger.addHandler(handler)
    logger.setLevel(LEVELS[kwargs.get("logLevel", "DEBUG")])
    return logger


def evaldict(inputDict):
    """Safely evaluate input to dict/list."""
    if not inputDict:
        return {}
    if isinstance(inputDict, (list, dict)):
        return inputDict
    # Decode if it is bytes
    if isinstance(inputDict, bytes):
        try:
            inputDict = inputDict.decode('utf-8')
        except UnicodeDecodeError as ex:
            raise WrongInputError(f"Input bytes could not be decoded. Error: {ex}") from ex
    # At this stage, if not string, raise error.  list/dict is checked in previous if
    if not isinstance(inputDict, str):
        raise WrongInputError("Input must be a string or dict/list.")
    try:
        return json.loads(inputDict)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass  # fall back
    # Try to fix common issues:
    fixedInput = re.sub(r"'", r'"', inputDict)
    # Remove trailing commas (optional)
    fixedInput = re.sub(r",(\s*[}\]])", r"\1", fixedInput)
    try:
        return json.loads(fixedInput)
    except (json.JSONDecodeError, TypeError, ValueError) as ex:
        raise WrongInputError(
            f"Input looks like JSON but could not be parsed even after fixup. Error: {ex}") from ex


def jsondumps(inputDict):
    """Dump JSON to string"""
    return json.dumps(inputDict)


def readFile(fileName):
    """Read all file lines to a list and rstrips the ending."""
    try:
        with open(fileName, "r", encoding="utf-8") as fd:
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

def externalCommandStdOutErr(command, stdout, stderr):
    """Execute External Commands and return stdout and stderr."""
    command = shlex.split(str(command))
    with open(stdout, "w", encoding='utf-8') as outFD, open(stderr, "w", encoding='utf-8') as errFD:
        with subprocess.Popen(command, stdout=outFD, stderr=errFD) as proc:
            return proc.communicate()

def execute(command, logger, raiseError=True):
    """Execute interfaces commands."""
    logger.info(f"Asked to execute {command} command")
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    msg = f"Command: {command}, Out: {out.rstrip()}, Err: {err.rstrip()}, ReturnCode: {cmdOut.returncode}"
    if cmdOut.returncode != 0 and raiseError:
        raise FailedInterfaceCommand(msg)
    if cmdOut.returncode != 0:
        logger.debug(
            f"RaiseError is False, but command failed. Only logging Errmsg: {msg}"
        )
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
            print(f"Received exception creating {dirname} directory. Exception: {ex}")
            if not os.path.isdir(dirname):
                raise
    return


def publishToSiteFE(inputDict, host, url, verb="PUT"):
    """Put JSON to the Site FE."""
    retries = 3
    while retries > 0:
        retries -= 1
        req = Requests(host, {})
        try:
            out = req.makeRequest(url, verb=verb, data=json.dumps(inputDict))
            return out
        except http.client.HTTPException as ex:
            print(f"Got HTTPException: {ex}. Will retry {retries} more times.")
            if retries == 0:
                return ex.reason, ex.status, "FAILED", True
            time.sleep(1)
        except pycurl.error as ex:
            print(f"Got PyCurl HTTPException: {ex}. Will retry {retries} more times.")
            if retries == 0:
                return ex.args[1], ex.args[0], "FAILED", False
            time.sleep(1)


def getDataFromSiteFE(inputDict, host, url):
    """Get data from Site FE. (Retries 3 times with 1 sec delay)"""
    retries = 3
    while retries > 0:
        retries -= 1
        req = Requests(host, {})
        try:
            out = req.makeRequest(url, verb="GET", data=inputDict)
            return out
        except http.client.HTTPException as ex:
            print(f"Got HTTPException: {ex}. Will retry {retries} more times.")
            if retries == 0:
                return ex.reason, ex.status, "FAILED", True
            time.sleep(1)
        except pycurl.error as ex:
            print(f"Got PyCurl HTTPException: {ex}. Will retry {retries} more times.")
            if retries == 0:
                return ex.args[1], ex.args[0], "FAILED", False
            time.sleep(1)


def getWebContentFromURL(url, raiseEx=True, params=None):
    """GET from URL"""
    retries = 3
    out = {}
    while retries > 0:
        retries -= 1
        try:
            if params:
                out = requests.get(url, params=params, timeout=60)
            else:
                out = requests.get(url, timeout=60)
            return out
        except requests.exceptions.RequestException as ex:
            print(f"Got requests.exceptions.RequestException: {ex}. Retries left: {retries}")
            if raiseEx and retries == 0:
                raise
            out = {}
            out['error'] = str(ex)
            out['status_code'] = -1
            time.sleep(1)
    return out


def postWebContentToURL(url, **kwargs):
    """POST to URL"""
    raiseEx = bool(kwargs.get('raiseEx', True))
    retries = 3
    out = {}
    while retries > 0:
        retries -= 1
        try:
            out = requests.post(url, timeout=60, **kwargs)
            return out
        except requests.exceptions.RequestException as ex:
            print(f"Got requests.exceptions.RequestException: {ex}. Retries left: {retries}")
            if raiseEx and retries == 0:
                raise
            out = {}
            out['error'] = str(ex)
            out['status_code'] = -1
            time.sleep(1)
    return out


def getFileContentAsJson(inputFile):
    """Get file content as json."""
    out = {}
    if not inputFile:
        return out
    if os.path.isfile(inputFile):
        with open(inputFile, "r", encoding="utf-8") as fd:
            try:
                out = json.load(fd)
            except ValueError:
                print(fd.seek(0))
                out = evaldict(fd.read())
    return out


def getAllFileContent(inputFile):
    """Get all file content as a string."""
    if os.path.isfile(inputFile):
        with open(inputFile, "r", encoding="utf-8") as fd:
            return fd.read()
    raise NotFoundError(f"File {inputFile} was not found on the system.")


def getUsername():
    """Return current username."""
    return pwd.getpwuid(os.getuid())[0]


def fileLock(func):
    """Decorator to create a lock file and wait if another process holds it."""
    @functools.wraps(func)
    def wrapper(outFile, *args, **kwargs):
        lockfile = f"{outFile}.lock"
        os.makedirs(os.path.dirname(lockfile), exist_ok=True)
        for _ in range(10):
            try:
                with open(lockfile, "w", encoding="utf-8") as lock_fd:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    try:
                        return func(outFile, *args, **kwargs)
                    finally:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                        os.remove(lockfile)
            except BlockingIOError:
                time.sleep(0.5)
        raise TimeoutError(f"Could not acquire lock for {outFile} after 10 seconds")
    return wrapper

class contentDB:
    """File Saver, loader class."""

    @staticmethod
    def getFileContentAsJson(inputFile):
        """Get file content as json."""
        return getFileContentAsJson(inputFile)

    @staticmethod
    def getFileContentAsList(inputFile):
        """Get file content as list."""
        return readFile(inputFile)

    @staticmethod
    def getHash(inputText):
        """Get UUID4 hash."""
        newuuid4 = str(uuid.uuid4())
        return str(newuuid4 + inputText)

    @staticmethod
    @fileLock
    def dumpFileContentAsJson(outFile, content):
        """Dump File content with locks."""
        tmpoutFile = outFile + ".tmp"
        with open(tmpoutFile, "w+", encoding="utf-8") as fd:
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
            raise Exception(f"File {sourcefile} does not exist")
        if sourcefile.startswith(destdir):
            # We dont want to move if already in dest dir
            return sourcefile
        destFile = os.path.join(destdir, self.getHash(".json"))
        shutil.move(sourcefile, destFile)
        return destFile


def delete(inputObj, delObj):
    """Delete function which covers exceptions."""
    if isinstance(inputObj, list):
        tmpList = copy.deepcopy(inputObj)
        try:
            tmpList.remove(delObj)
        except ValueError as ex:
            print(
                f"Delete object {delObj} is not in inputObj {tmpList} list. Err: {ex}"
            )
        return tmpList
    if isinstance(inputObj, dict):
        tmpDict = copy.deepcopy(inputObj)
        try:
            del tmpDict[delObj]
        except KeyError as ex:
            print(
                f"Delete object {delObj} is not in inputObj {tmpList} dict. Err: {ex}"
            )
        return tmpDict
    # This should not happen
    raise WrongInputError(
        f"Provided input type is not available for deletion. Type {type(inputObj)}"
    )


def parse_gui_form_post(inputVal):
    """Parse GUI Form Post and return dict."""
    out = {}
    for item in inputVal.split(b"&"):
        tmpItem = item.split(b"=")
        out[tmpItem[0].decode("utf-8")] = urllib.parse.unquote(tmpItem[1].decode("utf-8"))
    return out


def read_input_data(environ):
    """Read input data from environ, which can be used for PUT or POST."""
    length = int(environ.get("CONTENT_LENGTH", 0))
    if length == 0:
        raise WrongInputError("Content input length is 0.")
    body = io.BytesIO(environ["wsgi.input"].read(length))
    outjson = {}
    try:
        outjson = evaldict(body.getvalue())
    except (ValueError, WrongInputError) as ex:
        outjson = parse_gui_form_post(body.getvalue())
        if not outjson:
            errMsg = f"Failed to parse json input: {body.getvalue()}, Err: {ex}."
            print(errMsg)
            raise WrongInputError(errMsg) from ex
    return outjson


VALIDATION = {
    "addhost": [
        {"key": "hostname", "type": basestring},
        {"key": "ip", "type": basestring},
        {"key": "port", "type": int},
        {"key": "insertTime", "type": int},
        {"key": "updateTime", "type": int},
        {
            "key": "status",
            "type": basestring,
            "values": ["benchmark", "maintenance", "operational"],
        },
        {"key": "desc", "type": basestring},
    ],
    "updatehost": [
        {"key": "ip", "type": basestring},
        {"key": "port", "type": int},
        {"key": "updateTime", "type": int},
        {
            "key": "status",
            "type": basestring,
            "values": ["benchmark", "maintenance", "operational"],
        },
    ],
}


def generateMD5(inText):
    """Generate MD5 from provided str"""
    hashObj = hashlib.md5(inText.encode())
    return hashObj.hexdigest()


def getHostname(config=None):
    """Return running server hostname"""
    # In case of FE, we need to return hostname as default
    if config and  config.getraw('MAPPING').get('type', None) == 'FE':
        return "default"
    return socket.gethostname()


def generateHash(inText):
    """Generate unique using uuid."""
    return str(uuid.uuid1(len(inText)))


def getCustomOutMsg(errMsg=None, errCode=None, msg=None, exitCode=None):
    """Create custom return dictionary."""
    newOut = {}
    if errMsg:
        newOut["error_description"] = errMsg
    if errCode:
        newOut["error"] = errCode
    if msg:
        newOut["msg"] = msg
    if exitCode:
        newOut["exitCode"] = exitCode
    return newOut


def getUrlParams(environ, paramsList):
    """Get URL parameters and return them in dictionary."""
    if not paramsList:
        return {}
    if environ["REQUEST_METHOD"].upper() in ["POST", "DELETE"]:
        # POST, DELETE will handle by himself
        return {}
    form = cgi.FieldStorage(fp=environ["wsgi.input"], environ=environ)
    outParams = {}
    for param in paramsList:
        outVals = form.getlist(param["key"])
        if len(outVals) > 1:
            raise TooManyArgumentalValues(
                f"Parameter {param['key']} has too many defined values"
            )
        if len(outVals) == 1:
            if param["type"] == bool:
                if outVals[0] in ["true", "True"]:
                    outParams[param["key"]] = True
                elif outVals[0] in ["false", "False"]:
                    outParams[param["key"]] = False
                else:
                    raise NotSupportedArgument(
                        f"Parameter {param['key']} value not acceptable. Allowed options: [tT]rue,[fF]alse"
                    )
            elif param["type"] == str and 'options' in param:
                if  outVals[0] not in param["options"]:
                    raise NotSupportedArgument(
                        f"Server does not support parameter {param['key']}={outVals[0]}. Supported: {param['options']}"
                    )
                outParams[param["key"]] = outVals[0]
            else:
                outParams[param["key"]] = outVals[0]
        elif not outVals:
            outParams[param["key"]] = param["default"]
    return outParams


def getHeaders(environ):
    """Get all Headers and return them back as dictionary."""
    headers = {}
    for key in list(environ.keys()):
        if key.startswith("HTTP_"):
            headers[key[5:]] = environ.get(key)
    return headers


def convertTSToDatetime(inputTS):
    """Convert timestamp to datetime."""
    dtObj = datetime.datetime.fromtimestamp(int(inputTS))
    return dtObj.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def httpdate(timestamp):
    """Return a string representation of a date according to RFC 1123
    (HTTP/1.1)."""
    dat = datetime.datetime.fromtimestamp(int(timestamp))
    weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dat.weekday()]
    month = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ][dat.month - 1]
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
        weekday,
        dat.day,
        month,
        dat.year,
        dat.hour,
        dat.minute,
        dat.second,
    )


def httptimestamp(inhttpdate):
    """Return timestamp from RFC1123 (HTTP/1.1)."""
    dat = datetime.datetime(*eut.parsedate(inhttpdate)[:5])
    return int(dat.timestamp())


def getModTime(headers):
    """Get modification time from the headers."""
    modTime = 0
    if "IF_MODIFIED_SINCE" in headers:
        modTime = httptimestamp(headers["IF_MODIFIED_SINCE"])
    return modTime


def encodebase64(inputStr, encodeFlag=True):
    """Encode str to base64."""
    if encodeFlag and inputStr:
        if isinstance(inputStr, bytes):
            return base64.b64encode(inputStr.encode("UTF-8"))
        return base64.b64encode(bytes(inputStr.encode("UTF-8")))
    return inputStr


def decodebase64(inputStr, decodeFlag=True):
    """Decode base64 to real format."""
    if decodeFlag and inputStr:
        return base64.b64decode(inputStr)
    return inputStr


def getDBConn(serviceName="", cls=None):
    """Get database connection."""
    dbConn = {}
    sites = ["MAIN"] + cls.config["MAIN"].get("general", {}).get("sites", [])
    for sitename in sites:
        if hasattr(cls, "dbI"):
            if hasattr(cls.dbI, sitename):
                # DB Object is already in place!
                continue
        dbConn[sitename] = dbinterface(serviceName, cls.config, sitename)
    return dbConn



def getCurrentModel(cls, raiseException=False):
    """Get Current Model from DB."""
    currentModel = cls.dbI.get("models", orderby=["insertdate", "DESC"], limit=1)
    currentGraph = Graph()
    if currentModel:
        try:
            currentGraph.parse(currentModel[0]["fileloc"], format="turtle")
        except IOError as ex:
            if raiseException:
                raise NotFoundError(
                    f"Model failed to parse from DB. Error {ex}"
                ) from IOError
            currentGraph = Graph()
    elif raiseException:
        raise NotFoundError("There is no model in DB. LookUpService is running?")
    return currentModel, currentGraph


def getAllHosts(dbI):
    """Get all hosts from database."""
    jOut = {}
    for site in dbI.get("hosts"):
        jOut[site["hostname"]] = site
    return jOut


def getActiveDeltas(cls):
    """Get Active deltas from DB."""
    activeDeltas = cls.dbI.get("activeDeltas")
    if not activeDeltas:
        return {"insertdate": int(getUTCnow()), "output": {}}
    activeDeltas = activeDeltas[0]
    activeDeltas["output"] = evaldict(activeDeltas["output"])
    return activeDeltas


def writeActiveDeltas(cls, newConfig):
    """Write Active Deltas to DB"""
    activeDeltas = cls.dbI.get("activeDeltas")
    action = "update"
    if not activeDeltas:
        action = "insert"
        activeDeltas = {"insertdate": int(getUTCnow())}
    else:
        activeDeltas = activeDeltas[0]
    activeDeltas["updatedate"] = int(getUTCnow())
    activeDeltas["output"] = str(newConfig)
    if action == "insert":
        cls.dbI.insert("activeDeltas", [activeDeltas])
    elif action == "update":
        cls.dbI.update("activeDeltas", [activeDeltas])


def strtolist(intext, splitter):
    """Str To List, separated by splitter"""
    if isinstance(intext, list):
        return intext
    out = intext.split(splitter)
    return list(filter(None, out))

def getArpVals():
    """Get Arp Values from /proc/net/arp. Return generator."""
    neighs = externalCommand("ip neigh")
    for arpline in neighs[0].decode("UTF-8").splitlines():
        parts = arpline.split()
        if len(parts) < 5:
            continue
        block = {
            'IPaddress': parts[0],
            'Device': parts[2],
            'HWaddress': parts[4],
            'Flags': parts[-1]
        }
        yield block


def timedhourcheck(lockname, hours=1):
    """Timed Lock for file."""
    filename = f'/tmp/siterm-timed-lock-{lockname}'
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as fd:
            timestamp = fd.read()
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            diff = now - timestamp
            if diff.days < hours:
                return False
    else:
        try:
            with open(filename, 'w', encoding='utf-8') as fd:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fd.write(timestamp)
        except OSError as ex:
            print(f"Error creating timestamp file: {ex}. Will return False for timedhourcheck")
            return False
    return True

def checkHTTPService(config):
    """Auto Refresh via API check"""
    # If config not present, continue normally (that fails at other checks)
    if not config:
        return 0
    # This is only done on FE:
    if config.getraw('MAPPING').get('type', None) != 'FE':
        return 0
    returnvals = []
    for sitename in config.get('general', 'sites'):
        try:
            hostname = getFullUrl(config, sitename)
            url = "/sitefe/v1/models?current=true&summary=false&encode=false"
            out = getDataFromSiteFE({}, hostname, url)
            # Need to check out that it received information back
            # otherwise print error and return 1
            if out[1] != 200 or out[2] != 'OK':
                print('Was not able to receive 200 http exit code.')
                print(f'Output: {out}')
                returnvals.append(1)
            else:
                returnvals.append(0)
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(f"Error details in checkHTTPService. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")
            returnvals.append(1)
    return 0 if not returnvals else any(returnvals)
