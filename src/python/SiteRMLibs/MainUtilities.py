#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Everything goes here when they do not fit anywhere else.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import ast
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
import pwd
import shlex
import shutil
import socket
import subprocess
import sys
import time
import uuid

# Custom exceptions imports
import pycurl
import requests
import simplejson as json
from past.builtins import basestring
from rdflib import Graph
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.CustomExceptions import (
    FailedInterfaceCommand,
    NoOptionError,
    NoSectionError,
    NotFoundError,
    NotSupportedArgument,
    TooManyArgumentalValues,
    WrongInputError,
)
from SiteRMLibs.DBBackend import dbinterface
from SiteRMLibs.HTTPLibrary import Requests
from yaml import safe_load as yload


def dictSearch(key, var, ret):
    """Search item in dictionary"""
    if isinstance(var, dict):
        for k, v in var.items():
            if k == key:
                ret.append(v)
            elif isinstance(v, dict):
                ret = dictSearch(key, v, ret)
            elif isinstance(v, list):
                for d in v:
                    ret = dictSearch(key, d, ret)
    elif isinstance(var, list):
        for d in var:
            ret = dictSearch(key, d, ret)
    return ret


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
    """Output from the server needs to be evaluated."""
    if not inputDict:
        return {}
    if isinstance(inputDict, (list, dict)):
        return inputDict
    try:
        out = ast.literal_eval(inputDict)
    except ValueError:
        out = json.loads(inputDict)
    except SyntaxError as ex:
        raise WrongInputError(
            f"SyntaxError: Failed to literal eval dict. Err:{ex} "
        ) from ex
    return out


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
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb=verb, data=json.dumps(inputDict))
    except http.client.HTTPException as ex:
        return ex.reason, ex.status, "FAILED", True
    except pycurl.error as ex:
        return ex.args[1], ex.args[0], "FAILED", False
    return out


def getDataFromSiteFE(inputDict, host, url):
    """Get data from Site FE."""
    req = Requests(host, {})
    try:
        out = req.makeRequest(url, verb="GET", data=inputDict)
    except http.client.HTTPException as ex:
        return ex.reason, ex.status, "FAILED", True
    except pycurl.error as ex:
        return ex.args[1], ex.args[0], "FAILED", False
    return out


def getWebContentFromURL(url):
    """GET from URL"""
    out = requests.get(url)
    return out


def postWebContentToURL(url, **kwargs):
    """POST to URL"""
    response = requests.post(url, **kwargs)
    return response


def reCacheConfig(prevHour=None, prevDay=None):
    """Return prevHour == currentHour, currentHour and used in Service Object
    re-initiation."""
    datetimeNow = datetime.datetime.now()
    currentHour = datetimeNow.strftime("%H")
    currentDay = datetimeNow.strftime("%d")
    return prevHour == currentHour, currentDay == prevDay, currentHour, currentDay


class GitConfig:
    """Git based configuration class."""

    def __init__(self):
        self.config = {}
        self.defaults = {
            "SITENAME": {"optional": False},
            "GIT_REPO": {"optional": True, "default": "sdn-sense/rm-configs"},
            "GIT_URL": {
                "optional": True,
                "default": "https://raw.githubusercontent.com/",
            },
            "GIT_BRANCH": {"optional": True, "default": "master"},
            "MD5": {"optional": True, "default": generateMD5(getHostname())},
        }

    @staticmethod
    def gitConfigCache(name):
        """Get Config file from tmp dir"""
        filename = f"/tmp/siterm-link-{name}.yaml"
        if os.path.isfile(filename):
            with open(filename, "r", encoding="utf-8") as fd:
                output = yload(fd.read())
        else:
            raise Exception(f"Config file {filename} does not exist.")
        return output

    def getFullGitUrl(self, customAdds=None):
        """Get Full Git URL."""
        urlJoinList = [
            self.config["GIT_URL"],
            self.config["GIT_REPO"],
            self.config["GIT_BRANCH"],
            self.config["SITENAME"],
        ]
        if customAdds:
            for item in customAdds:
                urlJoinList.append(item)
        return "/".join(urlJoinList)

    def getLocalConfig(self):
        """Get local config for info where all configs are kept in git."""
        if not os.path.isfile("/etc/siterm.yaml"):
            print("Config file /etc/siterm.yaml does not exist.")
            raise Exception("Config file /etc/siterm.yaml does not exist.")
        with open("/etc/siterm.yaml", "r", encoding="utf-8") as fd:
            self.config = yload(fd.read())
        for key, requirement in list(self.defaults.items()):
            if key not in list(self.config.keys()):
                # Check if it is optional or not;
                if not requirement["optional"]:
                    print(
                        "Configuration /etc/siterm.yaml missing non optional config parameter %s",
                        key,
                    )
                    raise Exception(
                        f"Configuration /etc/siterm.yaml missing non optional config parameter {key}"
                    )
                self.config[key] = requirement["default"]

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
        defConfig = {
            "MAIN": {
                "general": {
                    "logDir": "/var/log/siterm-agent/",
                    "logLevel": "INFO",
                    "privatedir": "/opt/siterm/config/",
                },
                "agent": {"norules": False, "rsts_enabled": "ipv4,ipv6"},
                "qos": {
                    "policy": "default-not-set",
                    "qos_params": "mtu 9000 mpu 9000 quantum 200000 burst 300000 cburst 300000 qdisc sfq balanced",
                    "class_max": True,
                    "interfaces": [],
                },
            }
        }
        self.__addDefaults(defConfig)
        self.__generatevlaniplists()

    def __generatevlaniplists(self):
        """Generate list for vlans and ips. config might have it in str"""
        for key, _ in list(self.config["MAIN"].items()):
            for subkey, subval in list(self.config["MAIN"][key].items()):
                self.generateIPList(key, subkey, subval)
                self.generateVlanList(key, subkey, subval)

    def getGitAgentConfig(self):
        """Get Git Agent Config."""
        if self.config["MAPPING"]["type"] == "Agent":
            self.config["MAIN"] = self.gitConfigCache("Agent-main")
            self.presetAgentDefaultConfigs()

    @staticmethod
    def __genValFromItem(inVal):
        """Generate int value from vlan range item"""
        if isinstance(inVal, int):
            return [inVal]
        retVals = []
        tmpvals = inVal.split("-")
        if len(tmpvals) == 2:
            # Need to loop as it is range;
            # In case second val is bigger than 1st - raise Exception
            if int(tmpvals[0]) >= int(tmpvals[1]):
                raise Exception(
                    f"Configuration Error. Vlan Range equal or lower. Vals: {tmpvals}"
                )
            for i in range(int(tmpvals[0]), int(tmpvals[1]) + 1):
                retVals.append(i)
        else:
            retVals.append(int(tmpvals[0]))
        return retVals

    def __genVlansRange(self, vals):
        """Generate Vlans Range"""
        retVals = []
        tmpVals = vals
        if isinstance(vals, int):
            return [vals]
        if not isinstance(vals, list):
            tmpVals = vals.split(",")
        for val in tmpVals:
            for lval in self.__genValFromItem(val):
                retVals.append(int(lval))
        return list(set(retVals))

    def generateVlanList(self, key1, key2, vals):
        """Generate Vlan List. which can be separated by comma, dash"""

        def _addToAll(vlanlist):
            """Add to all vlan list"""
            self.config["MAIN"][key1].setdefault("all_vlan_range_list", [])
            for vlanid in vlanlist:
                if vlanid not in self.config["MAIN"][key1].get(
                    "all_vlan_range_list", []
                ):
                    self.config["MAIN"][key1].setdefault(
                        "all_vlan_range_list", []
                    ).append(vlanid)

        # Default list is a must! Will be done checked at config preparation/validation
        if "vlan_range" not in self.config["MAIN"][key1]:
            return
        if "vlan_range_list" not in self.config["MAIN"][key1]:
            newvlanlist = self.__genVlansRange(self.config["MAIN"][key1]["vlan_range"])
            self.config["MAIN"][key1]["vlan_range_list"] = newvlanlist
            _addToAll(newvlanlist)
        if key2 == "ports":
            for portname, portvals in self.config["MAIN"][key1][key2].items():
                if "vlan_range" in portvals:
                    newvlanlist = self.__genVlansRange(portvals["vlan_range"])
                    self.config["MAIN"][key1][key2][portname][
                        "vlan_range_list"
                    ] = newvlanlist
                    _addToAll(newvlanlist)
                # Else we set default
                else:
                    self.config["MAIN"][key1][key2][portname][
                        "vlan_range"
                    ] = self.config["MAIN"][key1]["vlan_range"]
                    self.config["MAIN"][key1][key2][portname][
                        "vlan_range_list"
                    ] = self.config["MAIN"][key1]["vlan_range_list"]

    def generateIPList(self, key1, key2, vals):
        """Split by command and return list"""
        if key2 in [
            "ipv4-address-pool",
            "ipv6-address-pool",
            "ipv4-subnet-pool",
            "ipv6-subnet-pool",
        ]:
            if isinstance(vals, list) and vals:
                self.config["MAIN"][key1][f"{key2}-list"] = vals
            else:
                vals = list(set(list(filter(None, vals.split(",")))))
                self.config["MAIN"][key1][f"{key2}-list"] = vals

    def presetFEDefaultConfigs(self):
        """Preset default config parameters for FE"""
        defConfig = {
            "MAIN": {
                "general": {
                    "logDir": "/var/log/siterm-site-fe/",
                    "logLevel": "INFO",
                    "privatedir": "/opt/siterm/config/",
                },
                "ansible": {
                    "private_data_dir": "/opt/siterm/config/ansible/sense/",
                    "inventory": "/opt/siterm/config/ansible/sense/inventory/inventory.yaml",
                    "inventory_host_vars_dir": "/opt/siterm/config/ansible/sense/inventory/host_vars/",
                    "rotate_artifacts": 100,
                    "ignore_logging": False,
                    "verbosity": 0,
                    "debug": False,
                    "private_data_dir_singleapply": "/opt/siterm/config/ansible/sense/",
                    "inventory_singleapply": "/opt/siterm/config/ansible/sense/inventory_singleapply/inventory.yaml",
                    "inventory_host_vars_dir_singleapply": "/opt/siterm/config/ansible/sense/inventory_singleapply/host_vars/",
                    "rotate_artifacts_singleapply": 100,
                    "ignore_logging_singleapply": False,
                    "verbosity_singleapply": 0,
                    "debug_singleapply": False,
                },
                "prefixes": {
                    "mrs": "http://schemas.ogf.org/mrs/2013/12/topology#",
                    "nml": "http://schemas.ogf.org/nml/2013/03/base#",
                    "owl": "http://www.w3.org/2002/07/owl#",
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                    "schema": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "sd": "http://schemas.ogf.org/nsi/2013/12/services/definition#",
                    "site": "urn:ogf:network",
                    "xml": "http://www.w3.org/XML/1998/namespace#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#",
                },
                "snmp": {
                    "mibs": [
                        "ifDescr",
                        "ifType",
                        "ifMtu",
                        "ifAdminStatus",
                        "ifOperStatus",
                        "ifHighSpeed",
                        "ifAlias",
                        "ifHCInOctets",
                        "ifHCOutOctets",
                        "ifInDiscards",
                        "ifOutDiscards",
                        "ifInErrors",
                        "ifOutErrors",
                        "ifHCInUcastPkts",
                        "ifHCOutUcastPkts",
                        "ifHCInMulticastPkts",
                        "ifHCOutMulticastPkts",
                        "ifHCInBroadcastPkts",
                        "ifHCOutBroadcastPkts",
                    ]
                },
            }
        }
        self.__addDefaults(defConfig)
        # Generate list vals - not in a str format. Needed in delta checks
        self.__generatevlaniplists()

    def getGitFEConfig(self):
        """Get Git FE Config."""
        if self.config["MAPPING"]["type"] == "FE":
            self.config["MAIN"] = self.gitConfigCache("FE-main")
            self.config["AUTH"] = self.gitConfigCache("FE-auth")
            self.presetFEDefaultConfigs()

    def getGitConfig(self):
        """Get git config from configured github repo."""
        if not self.config:
            self.getLocalConfig()
        mapping = self.gitConfigCache("mapping")
        if self.config["MD5"] not in list(mapping.keys()):
            msg = f"Configuration is not available for this MD5 {self.config['MD5']} tag in GIT REPO {self.config['GIT_REPO']}"
            print(msg)
            raise Exception(msg)
        self.config["MAPPING"] = copy.deepcopy(mapping[self.config["MD5"]])
        self.getGitFEConfig()
        self.getGitAgentConfig()

    def __getitem__(self, item):
        """Subscripable item lookup"""
        if item in ["MAIN", "AUTH"]:
            return self.config[item]
        return self.config["MAIN"][item]

    def get(self, key, subkey):
        """Custom get from dictionary in a way like configparser"""
        if key not in self.config["MAIN"]:
            raise NoSectionError(f"{key} is not available in configuration.")
        if subkey not in self.config["MAIN"][key]:
            raise NoOptionError(
                f"{subkey} is not available under {key} section in configuration."
            )
        return self.config["MAIN"].get(key, {}).get(subkey, {})

    def getraw(self, key):
        """Get RAW DICT of key"""
        return self.config.get(key, {})

    def getboolean(self, key, subkey):
        """Return boolean"""
        val = self.get(key, subkey)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("yes", "true", "1")

    def getint(self, key, subkey):
        """Return int from config"""
        return int(self.get(key, subkey))

    def has_section(self, key):
        """Check if section available"""
        if self.config["MAIN"].get(key, {}):
            return True
        return False

    def has_option(self, key, subkey):
        """Check if option available"""
        if not self.config["MAIN"].get(key, {}):
            raise NoSectionError(f"{key} section is not available in configuration.")
        if subkey in self.config["MAIN"][key]:
            return True
        return False


def getGitConfig():
    """Wrapper before git config class. Returns dictionary."""
    gitConf = GitConfig()
    gitConf.getGitConfig()
    return gitConf


def getFileContentAsJson(inputFile):
    """Get file content as json."""
    out = {}
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


class contentDB:
    """File Saver, loader class."""

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
        out[tmpItem[0].decode("utf-8")] = tmpItem[1].decode("utf-8")
    return out


def read_input_data(environ):
    """Read input data from environ, which can be used for PUT or POST."""
    length = int(environ.get("CONTENT_LENGTH", 0))
    if length == 0:
        raise WrongInputError("Content input length is 0.")
    if sys.version.startswith("3."):
        body = io.BytesIO(environ["wsgi.input"].read(length))
    else:
        body = io.StringIO(environ["wsgi.input"].read(length))
    outjson = {}
    try:
        outjson = evaldict(body.getvalue())
    except ValueError as ex:
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


def getHostname():
    """Return running server hostname"""
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
                        f"Server does not support parameter {param['key']}={outVals[0]}. Supported: param['options']"
                    )
            outParams[param["key"]] = outVals[0]
        elif not outVals:
            outParams[param["key"]] = param["default"]
    print(outParams)
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
    return int(time.mktime(dat.timetuple()))


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
    if hasattr(cls, "config"):
        config = cls.config
    else:
        config = getGitConfig()
    for sitename in config["MAIN"]["general"]["sites"] + ["MAIN"]:
        if hasattr(cls, "dbI"):
            if hasattr(cls.dbI, sitename):
                # DB Object is already in place!
                continue
        dbConn[sitename] = dbinterface(serviceName, config, sitename)
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
