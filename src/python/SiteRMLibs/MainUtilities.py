# pylint: disable=unknown-option-value,line-too-long,too-many-lines
#!/usr/bin/env python3
"""Everything goes here when they do not fit anywhere else.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/01/20
"""
import base64
import copy
import datetime
import email.utils as eut
import fcntl
import functools
import hashlib
import logging
import logging.handlers
import os
import os.path
import shlex
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

import simplejson as json
from rdflib import Graph
from SiteRMLibs.CustomExceptions import (
    FailedInterfaceCommand,
    NotFoundError,
    WrongInputError,
)
from SiteRMLibs.DBBackend import dbinterface
from SiteRMLibs.SqLiteBackend import SQLiteBackend
from yaml import safe_load as yload

HOSTSERVICES = [
    "Agent",
    "Ruler",
    "Debugger",
    "LookUpService",
    "ProvisioningService",
    "SNMPMonitoring",
    "DBWorker",
    "DBCleaner",
    "Validator",
    "ValidatorService",
    "PolicyService",
    "SwitchWorker",
    "ConfigFetcher",
    "MonitoringService",
]

HOSTSERVICEENUMALL = Enum("HOSTSERVICEENUMA", {name: name for name in HOSTSERVICES + ["ALL"]})


def getstartupconfig(conffile="/etc/siterm.yaml"):
    """Get local config for info where all configs are kept in git."""
    if not os.path.isfile(conffile):
        print(f"Config file {conffile} does not exist.")
        raise Exception(f"Config file {conffile} does not exist.")
    with open(conffile, "r", encoding="utf-8") as fd:
        out = yload(fd.read())
    return out


def loadEnvFile(filepath="/etc/environment"):
    """Loads environment variables from a file if"""
    if not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as fd:
            for line in fd:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
    except Exception as ex:  # pylint: disable=broad-except
        print(f"Failed to load environment file {filepath}. Error: {ex}")


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
    # pylint: disable=broad-exception-raised
    if "sitename" in kwargs:
        if kwargs["sitename"] in list(conDict.keys()):
            return conDict[kwargs["sitename"]]
        raise Exception("This SiteName is not configured on the Frontend. Contact Support")
    raise Exception("This Call Should not happen. Contact Support")


def getFullUrl(config):
    """Prepare full URL from Config."""
    webdomain = config.get("general", "webdomain")
    if not webdomain.startswith("http"):
        webdomain = "http://" + webdomain
    return f"{webdomain}/"


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
            kwargs["logFile"] = f"{kwargs['config'].get('general', 'logDir')}/{kwargs.get('service', __name__)}/"
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


def bytestoStr(inputBytes):
    """Convert bytes object to string."""
    if isinstance(inputBytes, bytes):
        try:
            return inputBytes.decode("utf-8")
        except UnicodeDecodeError as ex:
            raise WrongInputError(f"Input bytes could not be decoded. Error: {ex}") from ex
    return inputBytes


def evaldict(inputDict):
    """Safely evaluate input to dict/list."""
    if not inputDict:
        return {}
    if isinstance(inputDict, (list, dict)):
        return inputDict
    inputDict = bytestoStr(inputDict)
    # At this stage, if not string, raise error.  list/dict is checked in previous if
    if not isinstance(inputDict, str):
        raise WrongInputError("Input must be a string or dict/list.")
    try:
        return json.loads(inputDict)
    except (json.JSONDecodeError, TypeError, ValueError) as ex:
        raise WrongInputError(f"Input looks like JSON but could not be parsed. Error: {ex}") from ex


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
    # pylint: disable=consider-using-with
    command = shlex.split(str(command))
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if communicate:
        return proc.communicate()
    return proc


def externalCommandStdOutErr(command, stdout, stderr):
    """Execute External Commands and return stdout and stderr."""
    command = shlex.split(str(command))
    with open(stdout, "w", encoding="utf-8") as outFD, open(stderr, "w", encoding="utf-8") as errFD:
        with subprocess.Popen(command, stdout=outFD, stderr=errFD, text=True) as proc:
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
            print(f"Received exception creating {dirname} directory. Exception: {ex}")
            if not os.path.isdir(dirname):
                raise
    return


def firstRunCheck(firstRun, servicename):
    """Check if it is first run."""
    if firstRun:
        fname = Path(tempfile.gettempdir()) / "siterm" / f"{servicename.lower()}-first-run"
        fname.parent.mkdir(parents=True, exist_ok=True)
        if not fname.exists():
            fname.write_text(f"This is first run of {servicename}. Do not remove this file.")
    else:
        fname = Path(tempfile.gettempdir()) / "siterm" / f"{servicename.lower()}-first-run"
        if fname.exists():
            fname.unlink()


def firstRunFinished(servicename):
    """Check if first Run finished for a service."""
    fname = Path(tempfile.gettempdir()) / "siterm" / f"{servicename.lower()}-first-run"
    if fname.exists():
        return False
    return True


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


def removeFile(fileLoc):
    """Remove file."""
    if os.path.isfile(fileLoc):
        os.unlink(fileLoc)
        return True
    return False


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
                        try:
                            os.remove(lockfile)
                        except FileNotFoundError:
                            pass
            except BlockingIOError:
                time.sleep(0.5)
        raise TimeoutError(f"Could not acquire lock for {outFile} after 10 seconds")

    return wrapper


def dumpFileContentAsJson(outFile, content):
    """Dump File content with locks."""
    tmpoutFile = outFile + ".tmp"
    createDirs(tmpoutFile)
    with open(tmpoutFile, "w+", encoding="utf-8") as fd:
        json.dump(content, fd)
    shutil.move(tmpoutFile, outFile)
    return True


def saveContent(destFileName, outputDict):
    """Saves all content to a file."""
    return dumpFileContentAsJson(destFileName, outputDict)


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
    @fileLock
    def dumpFileContentAsJson(outFile, content):
        """Dump File content with locks."""
        dumpFileContentAsJson(outFile, content)

    @staticmethod
    @fileLock
    def dumpFileContent(outFile, content):
        """Dump File content with locks."""
        tmpoutFile = outFile + ".tmp"
        with open(tmpoutFile, "wb+") as fd:
            fd.write(content)
        shutil.move(tmpoutFile, outFile)
        return True

    def saveContent(self, destFileName, outputDict):
        """Saves all content to a file."""
        return self.dumpFileContentAsJson(destFileName, outputDict)

    @staticmethod
    def removeFile(fileLoc):
        """Remove file."""
        removeFile(fileLoc)

    @staticmethod
    def fileExists(fileLoc):
        """Check if file exists."""
        return os.path.isfile(fileLoc)


def delete(inputObj, delObj):
    """Delete function which covers exceptions."""
    if isinstance(inputObj, list):
        tmpList = copy.deepcopy(inputObj)
        try:
            tmpList.remove(delObj)
        except ValueError as ex:
            print(f"Delete object {delObj} is not in inputObj {tmpList} list. Err: {ex}")
        return tmpList
    if isinstance(inputObj, dict):
        tmpDict = copy.deepcopy(inputObj)
        try:
            del tmpDict[delObj]
        except KeyError as ex:
            print(f"Delete object {delObj} is not in inputObj {tmpList} dict. Err: {ex}")
        return tmpDict
    # This should not happen
    raise WrongInputError(f"Provided input type is not available for deletion. Type {type(inputObj)}")


def generateMD5(inText):
    """Generate MD5 from provided str"""
    hashObj = hashlib.md5(inText.encode())
    return hashObj.hexdigest()


def getHostname(config=None, service=None):
    """Return running server hostname"""
    # In case of FE, we need to return hostname as default
    if config and config.getraw("MAPPING").get("type", None) == "FE":
        return "default"
    # If service is Debugger, we return socket.gethostname() (as Debugger can run on multiple hosts)
    if service and service.lower() == "debugger":
        return socket.gethostname()
    # If config is provided, we return hostname from config
    if config and config.get("agent", "hostname"):
        return config.get("agent", "hostname")
    return socket.gethostname()


def generateHash(inText):
    """Generate unique using uuid."""
    return str(uuid.uuid1(len(inText)))


def generateRandomUUID():
    """Generate random UUID."""
    return str(uuid.uuid4())


def convertTSToDatetime(inputTS):
    """Convert timestamp to datetime."""
    dtObj = datetime.datetime.fromtimestamp(int(inputTS))
    return dtObj.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def httpdate(timestamp):
    """Return a string representation of a date according to RFC 1123
    (HTTP/1.1)."""
    # pylint: disable=consider-using-f-string
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
    if "if-modified-since" in headers:
        modTime = httptimestamp(headers["if-modified-since"])
    return modTime


def encodebase64(inputStr, encodeFlag=True):
    """Encode str to base64."""
    if encodeFlag and inputStr:
        return base64.b64encode(bytestoStr(inputStr))
    return inputStr


def decodebase64(inputStr, decodeFlag=True):
    """Decode base64 to real format."""
    if decodeFlag and inputStr:
        return base64.b64decode(inputStr)
    return inputStr


def getDBConn(serviceName="", cls=None):
    """Get database connection."""
    if not hasattr(cls, "dbConnMain") or cls.dbConnMain is None:
        cls.dbConnMain = {}

    dbConnMain = cls.dbConnMain.setdefault(serviceName, {})

    if dbConnMain:
        return dbConnMain

    sitename = getSiteNameFromConfig(cls.config)
    if hasattr(cls, "dbI") and hasattr(cls.dbI, sitename):
        return dbConnMain
    dbConnMain[sitename] = dbinterface(serviceName, cls.config, sitename)

    return dbConnMain


def getDBConnObj():
    """Get database connection object (no class)"""
    return dbinterface()

def getSQLiteConnObj(config):
    """Get SQLite connection object (no class)"""
    return SQLiteBackend(config)

def parseRDFFile(modelFile):
    """Parse model file and return Graph."""
    formats = ["ntriples", "turtle", "json-ld"]
    exclist = []
    if not os.path.isfile(modelFile):
        raise NotFoundError("Model file is not present on the system.")
    for fmt in formats:
        try:
            graph = Graph()
            graph.parse(modelFile, format=fmt)
            return graph
        except Exception as ex:  # pylint: disable=broad-except
            exclist.append(f"Failed to parse with format: {fmt}. Error: {ex}")
    raise NotFoundError(f"Model file {modelFile} could not be parsed with any format: {formats}. " f"Please check the file format or content. All exceptions: {exclist}")


def getCurrentModel(cls, raiseException=False):
    """Get Current Model from DB."""
    currentModel = cls.dbI.get("models", orderby=["insertdate", "DESC"], limit=1)
    currentGraph = None
    if currentModel:
        try:
            currentGraph = parseRDFFile(currentModel[0]["fileloc"])
        except NotFoundError as ex:
            if raiseException:
                raise NotFoundError(f"Model failed to parse from DB. Error: {ex}") from NotFoundError
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


def getSiteNameFromConfig(config):
    """Get sitename from config."""
    sitename = None
    if config.has_option("general", "sitename"):
        sitename = config.get("general", "sitename")
    else:
        raise ValueError("No sitename defined in config file. Fatal Failure.")
    return sitename


def normalizePipeStrings(obj):
    """Recursively walk obj (active deltas). If a string contains '|', normalize it by sorting."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = normalizePipeStrings(v)
        return obj
    if isinstance(obj, list):
        return [normalizePipeStrings(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(normalizePipeStrings(v) for v in obj)
    if isinstance(obj, str) and "|" in obj:
        parts = obj.split("|")
        return "|".join(sorted(parts))
    return obj


def getActiveDeltas(cls):
    """Get Active deltas from DB."""
    activeDeltas = cls.dbI.get("activeDeltas")
    if not activeDeltas:
        return {"insertdate": int(getUTCnow()), "output": {}}
    activeDeltas = activeDeltas[0]
    activeDeltas["output"] = evaldict(activeDeltas["output"])
    activeDeltas["output"] = normalizePipeStrings(activeDeltas["output"])
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
    activeDeltas["output"] = jsondumps(newConfig)
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
    for arpline in neighs[0].splitlines():
        parts = arpline.split()
        if len(parts) < 5:
            continue
        block = {
            "IPaddress": parts[0],
            "Device": parts[2],
            "HWaddress": parts[4],
            "Flags": parts[-1],
        }
        yield block


def timedhourcheck(lockname, hours=1):
    """Timed Lock for file."""
    filename = f"/tmp/siterm-timed-lock-{lockname}"
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as fd:
            timestamp = fd.read()
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            now = datetime.datetime.now()
            diff = now - timestamp
            if diff.days < hours:
                return False
    else:
        try:
            with open(filename, "w", encoding="utf-8") as fd:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fd.write(timestamp)
        except OSError as ex:
            print(f"Error creating timestamp file: {ex}. Will return False for timedhourcheck")
            return False
    return True


def tryConvertToNumeric(value):
    """Convert str to float or int.

    Returns what should be expected, t.y.: if str is float, int will
    fail and float will be returned; if str is int, float and int will
    succeed, returns int; if any of these fail, returns value."""
    floatVal = None
    intVal = None
    try:
        floatVal = float(value)
    except ValueError:
        return value
    try:
        intVal = int(value)
    except ValueError:
        return floatVal if floatVal else value
    return intVal


@contextmanager
def timeout(seconds):
    """Context manager that raises TimeoutError"""

    def timeout_handler(signum, frame):
        """Handle the timeout signal"""
        raise TimeoutError(f"Operation timed out after {seconds} seconds")

    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def withTimeout(timeout_seconds=60):
    """Decorator for function timeout."""

    def decorator(func):
        """Decorator that applies a timeout to the function"""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper function that applies a timeout to the decorated function"""
            with timeout(timeout_seconds):
                return func(*args, **kwargs)
        return wrapper
    return decorator
