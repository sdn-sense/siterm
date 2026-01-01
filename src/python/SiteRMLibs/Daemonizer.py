#!/usr/bin/env python3
"""This part of code is taken from:

https://web.archive.org/web/20160305151936/http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
Please respect developer (Sander Marechal) and always keep a reference to URL and also as kudos to him
Changes applied to this code:
    Dedention (Justas Balcas 07/12/2017)
    pylint fixes: with open, split imports, var names, old style class (Justas Balcas 07/12/2017)
"""
import argparse
import atexit
import os
import sys
import time
import traceback
import tracemalloc

import psutil
from deepdiff import DeepDiff
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.CustomExceptions import (
    HTTPServerNotReady,
    NoOptionError,
    NoSectionError,
    ServiceWarning,
)
from SiteRMLibs.DefaultParams import GIT_CONFIG_REFRESH_TIMEOUT
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import (
    HOSTSERVICES,
    contentDB,
    createDirs,
    getDBConn,
    getFullUrl,
    getHostname,
    getLoggingObject,
    getSiteNameFromConfig,
    getTempDir,
    getUTCnow,
    getVal,
    loadEnvFile,
    timeout,
)


def getParser(description):
    """Returns the argparse parser."""
    oparser = argparse.ArgumentParser(description=description, prog=os.path.basename(sys.argv[0]), add_help=True)
    oparser.add_argument(
        "--action",
        dest="action",
        default="",
        help="Action - start, stop, status, restart service.",
    )
    oparser.add_argument(
        "--foreground",
        action="store_true",
        help="Run program in foreground. Default no",
    )
    oparser.set_defaults(foreground=False)
    oparser.add_argument(
        "--logtostdout",
        action="store_true",
        help="Log to stdout and not to file. Default false",
    )
    oparser.add_argument(
        "--onetimerun",
        action="store_true",
        help="Run once and exit from loop (Only for start). Default false",
    )
    oparser.add_argument(
        "--noreporting",
        action="store_true",
        help="Do not report service Status to FE (Only for start/restart). Default false",
    )
    oparser.add_argument(
        "--runnum",
        dest="runnum",
        default="1",
        help="Run Number. Default 1. Used only for multi thread debugging purpose. No need to specify manually",
    )
    oparser.add_argument(
        "--sleeptimeok",
        dest="sleeptimeok",
        default="10",
        help="Sleep time in seconds when everything is ok. Default 10",
    )
    oparser.add_argument(
        "--sleeptimefailure",
        dest="sleeptimefailure",
        default="10",
        help="Sleep time in seconds when there is a failure. Default 10",
    )
    oparser.add_argument(
        "--devicename",
        dest="devicename",
        default="",
        help="Device name to start the process. Only for SwitchWorker process.",
    )
    oparser.add_argument(
        "--bypassstartcheck",
        action="store_true",
        help="Bypass start check. Default false",
        default=False,
    )
    oparser.add_argument(
        "--forceremovepid",
        action="store_true",
        help="Force remove PID file during status action if process is dead. Default false",
    )
    oparser.set_defaults(forceremovepid=False)
    # Add config param for debug level
    oparser.add_argument("--loglevel", dest="loglevel", default=None, help="Log level. Default None")
    oparser.set_defaults(logtostdout=False)
    return oparser


def validateArgs(inargs):
    """Validate arguments."""
    # Check port
    if inargs.action not in ["start", "stop", "status", "restart"]:
        raise Exception(f"Action '{inargs.action}' not supported. Supported actions: start, stop, status, restart")


class DBBackend:
    # pylint: disable=too-few-public-methods
    """DB Backend class."""

    # pylint: disable=E1101,E0203,W0201
    def _loadDB(self, component):
        """Load DB connection."""
        if self.dbI or not self.config:
            return
        if self.config.getraw("MAPPING").get("type", None) == "FE":
            try:
                self.dbI = getDBConn(component, self)
            except KeyError:
                self.dbI = None

    def _reportServiceStatus(self, **kwargs):
        """Report service state to DB."""
        # pylint: disable=W0703
        if not self.dbI:
            return False
        reported = True
        try:
            dbOut = {
                "hostname": kwargs.get("hostname", "default"),
                "servicestate": kwargs.get("servicestate", "UNSET"),
                "servicename": kwargs.get("servicename", "UNSET"),
                "runtime": kwargs.get("runtime", -1),
                "version": kwargs.get("version", runningVersion),
                "insertdate": getUTCnow(),
                "updatedate": getUTCnow(),
                "exc": str(kwargs.get("exc", "No Exception provided by service"))[:4095],
            }
            dbobj = getVal(self.dbI, **{"sitename": kwargs.get("sitename", "UNSET")})
            services = dbobj.get(
                "servicestates",
                search=[
                    ["hostname", dbOut["hostname"]],
                    ["servicename", dbOut["servicename"]],
                ],
            )
            if not services:
                dbobj.insert("servicestates", [dbOut])
            else:
                dbobj.update("servicestates", [dbOut])
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(f"Error details in reportServiceStatus. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")
            reported = False
        return reported

    def _pubStateRemote(self, **kwargs):
        """Publish state from remote services."""
        # pylint: disable=W0703
        if self._reportServiceStatus(**kwargs):
            return
        try:
            dic = {
                "servicename": kwargs["servicename"],
                "servicestate": kwargs["servicestate"],
                "sitename": kwargs["sitename"],
                "runtime": kwargs["runtime"],
                "hostname": getHostname(self.config, self.component),
                "version": runningVersion,
                "exc": kwargs.get("exc", "No Exception provided by service")[:4095],
            }
            self.handlers[kwargs["sitename"]].makeHttpCall("POST", f"/api/{kwargs['sitename']}/servicestates", data=dic, useragent="Daemonizer")
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(f"Error details in pubStateRemote. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")
            print(f"Full traceback: {traceback.format_exc()}")

    def _autoRefreshDB(self, **kwargs):
        """Auto Refresh if there is a DB request to do so."""
        search = [["hostname", "default"], ["servicename", self.component]]
        if self.component == "ConfigFetcher":
            search = [["hostname", "default"]]
        dbobj = getVal(self.dbI, **{"sitename": kwargs.get("sitename", "UNSET")})
        actions = dbobj.get("serviceaction", search=search)
        if actions:
            # Config Fetcher is not allowed to delete other services refresh.
            if self.component == "ConfigFetcher":
                return True
            for action in actions:
                dbOut = [["id", action["id"]]]
                dbobj.delete("serviceaction", dbOut)
            return True
        return False

    def _autoRefreshAPI(self, **kwargs):
        """Auto Refresh via API check"""
        # pylint: disable=W0703
        refresh = False
        try:
            kwargs["servicename"] = self.component
            kwargs["hostname"] = getHostname(self.config, self.component)
            url = f"/api/{kwargs['sitename']}/serviceaction?hostname={kwargs['hostname']}&servicename={self.component}"
            # If handler not available, skip
            if kwargs["sitename"] not in self.handlers:
                return False
            actions = self.handlers[kwargs["sitename"]].makeHttpCall("GET", url, raiseEx=False, useragent="Daemonizer")
            # Config Fetcher is not allowed to delete other services refresh.
            if actions[1] == 404:
                self.logger.debug("No service actions found for %s", kwargs["sitename"])
                return False
            if actions[1] != 200:
                self.logger.error("Failed to get service actions for %s: %s", kwargs["sitename"], actions[0])
                return False
            if self.component == "ConfigFetcher":
                return True
            if not actions:
                self.logger.debug("No actions found for %s", kwargs["sitename"])
                return False
            for action in actions[0]:
                self.handlers[kwargs["sitename"]].makeHttpCall("DELETE", url, data={"id": action["id"], "servicename": self.component, "action": action["action"]}, useragent="Daemonizer")
                refresh = True
        except Exception:
            exc = traceback.format_exc()
            excType, excValue = sys.exc_info()[:2]
            print(f"Error details in _autoRefreshAPI. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")
            print(f"Traceback details: {exc}")
        return refresh


class Daemon(DBBackend):
    """A generic daemon class.

    Usage: subclass the Daemon class and override the run() method.
    """

    # pylint: disable=R0902

    def __init__(self, component, inargs, getGitConf=True):
        """Initialize the daemon."""
        loadEnvFile()
        logType = "TimedRotatingFileHandler"
        if inargs.logtostdout:
            logType = "StreamLogger"
        self.component = component
        self.inargs = inargs
        self.dbI = None
        self.runCount = 0
        self.pidfile = f"{getTempDir()}/end-site-rm-{component}-{self.inargs.runnum}.pid"
        if self.inargs.devicename:
            self.pidfile = f"{getTempDir()}/end-site-rm-{component}-{self.inargs.runnum}-{self.inargs.devicename}.pid"
        self.config = None
        self.logger = None
        self.firstInitDone = False
        self.runThreads = {}
        self.contentDB = contentDB()
        self.getGitConf = getGitConf
        if self.getGitConf:
            self._refreshConfig()
            self.logger = getLoggingObject(
                config=self.config,
                logfile=f"{self.config.get('general', 'logDir')}/{component}/",
                logLevel=self._getLogLevel(),
                logType=logType,
                service=self.component,
            )
        else:
            self.logger = getLoggingObject(
                logFile=f"/var/log/{component}-",
                logLevel=self._getLogLevel(),
                logType=logType,
                service=self.component,
            )
        self.sleepTimers = {
            "ok": int(self.inargs.sleeptimeok),
            "failure": int(self.inargs.sleeptimefailure),
        }
        self.totalRuntime = 0
        self.lastRefresh = getUTCnow()
        self._loadDB(component)
        self.memdebug = False
        if os.getenv("SITERM_MEMORY_DEBUG"):
            self.memdebug = True
        self.handlers = {}
        self._getHandlers()

    def _getHandlers(self):
        """Get handlers for all sites."""
        # pylint: disable=W0702
        if not self.getGitConf:
            return
        sitename = getSiteNameFromConfig(self.config)
        fullURL = getFullUrl(self.config)
        self.handlers[sitename] = Requests(url=fullURL, logger=self.logger)

    def _getLogLevel(self):
        """Get log level."""
        if self.inargs.loglevel:
            return self.inargs.loglevel
        if not self.config:
            return "DEBUG"
        return self.config.get("general", "logLevel", "DEBUG")

    def startready(self):
        """Check if the startup is ready"""
        retval = True
        if self.inargs.bypassstartcheck:
            return retval
        if os.path.exists(f"{getTempDir()}/siterm-mariadb-init"):
            try:
                self.logger.info("Database init/upgrade started at:")
                with open(f"{getTempDir()}/siterm-mariadb-init", "r", encoding="utf-8") as fd:
                    self.logger.info(fd.read())
            except IOError:
                pass
            self.logger.info("Database not ready. See details above. If continous, check the mariadb and mariadb_init process.")
            retval = False
        if not os.path.exists(f"{getTempDir()}/config-fetcher-ready") and not self.firstInitDone:
            self.logger.info("Config Fetcher not ready. See details above. If continous, check the config-fetcher process.")
            retval = False
        return retval

    def startreadyloop(self):
        """Check if the database is ready"""
        while not self.startready():
            time.sleep(5)
        self.firstInitDone = True

    def _refreshConfigAfterFailure(self):
        """Config refresh call after failure"""
        if self.getGitConf:
            self.logger.info("Refreshing Config after failure after 10 second sleep")
            time.sleep(10)
            self.config = getGitConfig()

    def _refreshConfig(self):
        """Config refresh call"""
        if self.getGitConf:
            self.config = getGitConfig()

    def daemonize(self):
        """do the UNIX double-fork magic, see Stevens' "Advanced Programming in
        the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16."""
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"fork #1 failed: {e.errno} ({e.strerror})\n")
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(f"fork #2 failed: {e.errno} ({e.strerror})\n")
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        with open("/dev/null", "r", encoding="utf-8") as fd:
            os.dup2(fd.fileno(), sys.stdin.fileno())
        with open("/dev/null", "a+", encoding="utf-8") as fd:
            os.dup2(fd.fileno(), sys.stdout.fileno())
        with open("/dev/null", "a+", encoding="utf-8") as fd:
            os.dup2(fd.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        self.writepid()

    def delpid(self):
        """Remove pid file."""
        os.remove(self.pidfile)

    def writepid(self):
        """Write pid file."""
        pid = str(os.getpid())
        with open(self.pidfile, "w+", encoding="utf-8") as fd:
            fd.write(f"{pid}\n")

    def start(self):
        """Start the daemon."""
        self.startreadyloop()
        # Check for a pidfile to see if the daemon already runs
        pid = None
        try:
            directory = os.path.dirname(self.pidfile)
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(self.pidfile, "r", encoding="utf-8") as fd:
                pid = int(fd.read().strip())
        except IOError:
            pid = None

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    @staticmethod
    def __kill(pid):
        """Kill process using psutil lib"""

        def processKill(procObj):
            """Kill a process object."""
            try:
                procObj.kill()
            except psutil.NoSuchProcess:
                pass

        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        for proc in process.children(recursive=True):
            processKill(proc)
        processKill(process)

    def stop(self):
        """Stop the daemon."""
        # Get the pid from the pidfile
        pid = None
        try:
            with open(self.pidfile, "r", encoding="utf-8") as fd:
                pid = int(fd.read().strip())
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # not an error in a restart

        # Try killing the daemon process
        self.__kill(pid)
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

    def restart(self):
        """Restart the daemon."""
        self.stop()
        self.start()

    def status(self):
        """Daemon status."""
        try:
            with open(self.pidfile, "r", encoding="utf-8") as fd:
                pid = int(fd.read().strip())
                psutil.Process(pid)
                print(f"Application info: PID {pid}")
        except psutil.NoSuchProcess:
            if self.inargs.forceremovepid:
                print(f"PID lock present, but process not running. Removing lock file {self.pidfile}")
                os.remove(self.pidfile)
                sys.exit(1)
            print(f"PID lock present, but process not running. Remove lock file {self.pidfile}")
            sys.exit(1)
        except IOError:
            print(f"Is application running? No Lock file {self.pidfile}")
            sys.exit(1)

    def command(self):
        """Execute a specific command to service."""
        if self.inargs.action == "start" and self.inargs.foreground:
            self.start()
        elif self.inargs.action == "start" and not self.inargs.foreground:
            # Register pid file deletion on exit and write pid file
            atexit.register(self.delpid)
            self.writepid()
            self.run()
        elif self.inargs.action == "stop":
            self.stop()
        elif self.inargs.action == "restart":
            self.restart()
        elif self.inargs.action == "status":
            self.status()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)

    def reporter(self, state, sitename, stwork, exc=None):
        """Report Service State to FE"""
        if not self.inargs.noreporting:
            runtime = int(getUTCnow()) - stwork
            exc = exc if exc else "No Exception provided by service"
            self._pubStateRemote(
                servicename=self.component,
                servicestate=state,
                sitename=sitename,
                version=runningVersion,
                runtime=runtime,
                exc=exc,
            )
            # Log state also to local file
            createDirs(f"{getTempDir()}/siterm-states/")
            fname = f"{getTempDir()}/siterm-states/{self.component}.json"
            if self.inargs.devicename:
                fname = f"{getTempDir()}/siterm-states/{self.component}-{self.inargs.devicename}.json"
            self.contentDB.dumpFileContentAsJson(
                fname,
                {
                    "state": state,
                    "sitename": sitename,
                    "component": self.component,
                    "runtime": runtime,
                    "version": runningVersion,
                    "exc": exc,
                },
            )

    def autoRefreshDB(self, **kwargs):
        """Auto Refresh if there is a DB request to do so."""
        # pylint: disable=W0703
        # Minimize queries to this and do this only every 5 minutes
        if int(getUTCnow()) - self.lastRefresh < GIT_CONFIG_REFRESH_TIMEOUT:
            return False
        self.lastRefresh = int(getUTCnow())
        refresh = False
        if self.component not in HOSTSERVICES:
            return refresh
        # Do a diff check with current configuration and config obtained from GIT
        newconf = getGitConfig()
        diff = DeepDiff(self.config.config, newconf.config, ignore_order=True)
        if diff:
            self.logger.info(f"Configuration change detected: {diff}")
            refresh = True
        try:
            if self.dbI:
                refresh = self._autoRefreshDB(**kwargs) or refresh
            elif self.config:
                refresh = self._autoRefreshAPI(**kwargs) or refresh
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(f"Error details in autoRefreshDB. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}")
            print(f"Full traceback: {traceback.format_exc()}")
            return refresh
        return refresh

    def runLoop(self):
        """Return True if it is not onetime run."""
        self.startreadyloop()
        if self.inargs.onetimerun and self.runCount == 0:
            return True
        if self.inargs.onetimerun and self.runCount > 0:
            return False
        return True

    def timeToExit(self):
        """Return True if it is time to exit."""
        if self.totalRuntime > 0 and self.totalRuntime <= int(getUTCnow()):
            return True
        return False

    def refreshThreads(self):
        """Refresh threads"""
        # pylint: disable=W0702
        while True:
            try:
                self.getThreads()
                return
            except SystemExit:
                exc = traceback.format_exc()
                self.logger.critical(f"SystemExit!!! Error details:  {exc}")
                raise
            except (NoOptionError, NoSectionError) as ex:
                exc = traceback.format_exc()
                self.logger.critical(f"Exception!!! Traceback details: {exc}, Catched Exception: {ex}")
                time.sleep(self.sleepTimers["failure"])
                self._refreshConfigAfterFailure()
            except Exception as ex:
                exc = traceback.format_exc()
                self.logger.critical(f"Exception!!! Error details: {ex}. Traceback details: {exc}")
                time.sleep(self.sleepTimers["failure"])

    def __run(self, rthread):
        """Run main execution and record memory usage (if env variable memdebug is set)"""
        if self.memdebug:
            if not tracemalloc.is_tracing():
                tracemalloc.start()
            self.logger.debug("Started Memory Usage Tracking")
            self.logger.debug("Memory usage: %s", tracemalloc.get_traced_memory())
        try:
            return rthread.startwork()
        finally:
            if self.memdebug:
                snapshot = tracemalloc.take_snapshot()
                self.logger.debug("Snapshot taken after rthread startwork attempt")
                for stat in snapshot.statistics("lineno")[:10]:
                    self.logger.debug("MEM_STAT: %s", stat)
                self.logger.debug("Final Memory usage: %s", tracemalloc.get_traced_memory())
                self.logger.debug("=" * 50)

    def run(self):
        """Run main execution"""
        # pylint: disable=W0702,too-many-branches
        self.refreshThreads()
        while self.runLoop():
            self.runCount += 1
            hadFailure = False
            refresh = False
            speedup = False
            stwork = int(getUTCnow())
            self.logger.debug("Daemonizer main loop start. Run count: %s", self.runCount)
            try:
                for sitename, rthread in list(self.runThreads.items()):
                    stwork = int(getUTCnow())
                    refresh = self.autoRefreshDB(**{"sitename": sitename})
                    self.logger.debug("Start worker for %s site", sitename)
                    try:
                        self.preRunThread(sitename, rthread)
                        with timeout(180):
                            speedup = self.__run(rthread)
                        self.reporter("OK", sitename, stwork)
                    except ServiceWarning as ex:
                        exc = traceback.format_exc()
                        self.reporter("WARNING", sitename, stwork, str(ex))
                        self.logger.warning("Service Warning!!! Error details:  %s", ex)
                        self.logger.warning("Service Warning!!! Traceback details:  %s", exc)
                        self.logger.warning("It is not fatal error. Continue to run normally.")
                    except HTTPServerNotReady as ex:
                        exc = traceback.format_exc()
                        self.logger.error("HTTP Server Not Ready!!! Error details:  %s", ex)
                        self.logger.error("HTTP Server Not Ready!!! Traceback details:  %s", exc)
                        self.logger.error("Look at SiteRM Frontend logs for more details.")
                    except Exception as ex:
                        hadFailure = True
                        self.reporter("FAILED", sitename, stwork, str(ex))
                        exc = traceback.format_exc()
                        self.logger.critical(f"Exception!!! Error details:  {ex}. Traceback details: {exc}")
                    finally:
                        self.postRunThread(sitename, rthread)
                        self.logger.debug("Finished worker for %s site", sitename)
                if self.runLoop():
                    time.sleep(self.sleepTimers["ok"] // 2 if speedup else self.sleepTimers["ok"])
            except KeyboardInterrupt as ex:
                self.reporter("KEYBOARDINTERRUPT", sitename, stwork)
                self.logger.critical("Received KeyboardInterrupt: %s ", ex)
                sys.exit(3)
            if hadFailure:
                self.logger.info(f"Had Runtime Failure. Sleep for {self.sleepTimers['failure']} seconds")
                if self.runLoop():
                    time.sleep(self.sleepTimers["failure"])
                else:
                    sys.exit(4)
            if self.timeToExit():
                self.logger.info("Total Runtime expired. Stopping Service")
                sys.exit(0)
            if refresh:
                self.logger.info("Re-initiating Service with new configuration from GIT. Forced by DB")
                self._refreshConfig()
                self.refreshThreads()
            self.logger.debug("Daemonizer main loop end. Run count: %s", self.runCount)

    @staticmethod
    def getThreads():
        """Overwrite this then Daemonized in your own class"""
        return {}

    @staticmethod
    def preRunThread(_sitename, _rthread):
        """Call before thread runtime in case something needed to be done by Daemon"""

    @staticmethod
    def postRunThread(_sitename, _rthread):
        """Call after thread runtime in case something needed to be done by Daemon"""
