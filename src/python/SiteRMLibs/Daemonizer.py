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

import psutil
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.MainUtilities import (
    getDataFromSiteFE,
    getDBConn,
    getFullUrl,
    getGitConfig,
    getHostname,
    getLoggingObject,
    getUTCnow,
    getVal,
    publishToSiteFE,
    reCacheConfig,
)


def getParser(description):
    """Returns the argparse parser."""
    oparser = argparse.ArgumentParser(description=description,
                                      prog=os.path.basename(sys.argv[0]), add_help=True)
    oparser.add_argument('--action', dest='action', default='',
                         help='Action - start, stop, status, restart service.')
    oparser.add_argument('--foreground', action='store_true',
                         help="Run program in foreground. Default no")
    oparser.set_defaults(foreground=False)
    oparser.add_argument('--logtostdout', action='store_true',
                         help="Log to stdout and not to file. Default false")
    oparser.add_argument('--onetimerun', action='store_true',
                         help="Run once and exit from loop (Only for start). Default false")
    oparser.add_argument('--noreporting', action='store_true',
                         help="Do not report service Status to FE (Only for start/restart). Default false")
    oparser.add_argument('--runnum', dest='runnum', default='1',
                         help="Run Number. Default 1. Used only for multi thread debugging purpose. No need to specify manually")
    oparser.set_defaults(logtostdout=False)
    return oparser

def validateArgs(inargs):
    """Validate arguments."""
        # Check port
    if inargs.action not in ['start', 'stop', 'status', 'restart']:
        raise Exception(f"Action '{inargs.action}' not supported. Supported actions: start, stop, status, restart")


class DBBackend():
    """DB Backend class."""
    # pylint: disable=E1101,E0203,W0201
    def _loadDB(self, component):
        """Load DB connection."""
        if self.dbI or not self.config:
            return
        if self.config.get('MAPPING', {}).get('type', None) == 'FE':
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
                "updatedate": getUTCnow(),
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
            print(
                "Error details in reportServiceStatus. ErrorType: %s, ErrMsg: %s",
                str(excType.__name__),
                excValue,
            )
            reported = False
        return reported

    def _pubStateRemote(self, **kwargs):
        """Publish state from remote services."""
        # pylint: disable=W0703
        if self._reportServiceStatus(**kwargs):
            return
        try:
            fullUrl = getFullUrl(self.config, kwargs["sitename"])
            fullUrl += "/sitefe"
            dic = {
                "servicename": kwargs["servicename"],
                "servicestate": kwargs["servicestate"],
                "sitename": kwargs["sitename"],
                "runtime": kwargs["runtime"],
                "hostname": getHostname(),
                "version": runningVersion,
            }
            publishToSiteFE(dic, fullUrl, "/json/frontend/servicestate")
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(
                f"Error details in pubStateRemote. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}"
            )

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
                dbOut = [["id", action['id']]]
                dbobj.delete("serviceaction", dbOut)
            return True
        return False

    def _autoRefreshAPI(self, **kwargs):
        pass
        """Auto Refresh via API check"""
        # pylint: disable=W0703
        refresh = False
        try:
            hostname = getFullUrl(self.config, kwargs["sitename"])
            url = "/sitefe/json/frontend/serviceaction"
            kwargs['servicename'] = self.component
            kwargs['hostname'] = getHostname()
            actions = getDataFromSiteFE(kwargs, hostname, url)
            # Config Fetcher is not allowed to delete other services refresh.
            if actions[0] and self.component == "ConfigFetcher":
                return True
            for action in actions[0]:
                publishToSiteFE({'id': action['id'], 'servicename': self.component}, hostname, url, verb="DELETE")
                refresh = True
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(
                f"Error details in _autoRefreshAPI. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}"
            )
        return refresh




class Daemon(DBBackend):
    """A generic daemon class.

    Usage: subclass the Daemon class and override the run() method.
    """
    # pylint: disable=R0902

    def __init__(self, component, inargs, getGitConf=True):
        logType = 'TimedRotatingFileHandler'
        if inargs.logtostdout:
            logType = 'StreamLogger'
        self.component = component
        self.inargs = inargs
        self.dbI = None
        self.runCount = 0
        self.pidfile = f"/tmp/end-site-rm-{component}-{self.inargs.runnum}.pid"
        self.config = None
        self.logger = None
        self.runThreads = {}
        if getGitConf:
            self.config = getGitConfig()
            self.logger = getLoggingObject(config=self.config,
                                           logfile=f"{self.config.get('general', 'logDir')}/{component}/",
                                           logLevel=self.config.get('general', 'logLevel'), logType=logType,
                                           service=self.component)
        else:
            self.logger = getLoggingObject(logFile=f"/var/log/{component}-",
                                           logLevel='DEBUG', logType=logType,
                                           service=self.component)
        self.sleepTimers = {'ok': 10, 'failure': 30}
        self.totalRuntime = 0
        self._loadDB(component)

    def _refreshConfig(self):
        """Config refresh call"""
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
        with open('/dev/null', 'r', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stdin.fileno())
        with open('/dev/null', 'a+', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stdout.fileno())
        with open('/dev/null', 'a+', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+', encoding='utf-8') as fd:
            fd.write(f"{pid}\n")

    def delpid(self):
        """Remove pid file."""
        os.remove(self.pidfile)

    def start(self):
        """Start the daemon."""
        # Check for a pidfile to see if the daemon already runs
        pid = None
        try:
            directory = os.path.dirname(self.pidfile)
            if not os.path.exists(directory):
                os.makedirs(directory)
            with open(self.pidfile, 'r', encoding='utf-8') as fd:
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
            with open(self.pidfile, 'r', encoding='utf-8') as fd:
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
            with open(self.pidfile, 'r', encoding='utf-8') as fd:
                pid = int(fd.read().strip())
                psutil.Process(pid)
                print(f'Application info: PID {pid}')
        except psutil.NoSuchProcess:
            print(f'PID lock present, but process not running. Remove lock file {self.pidfile}')
            sys.exit(1)
        except IOError:
            print(f'Is application running? No Lock file {self.pidfile}')
            sys.exit(1)

    def command(self):
        """Execute a specific command to service."""
        if self.inargs.action == 'start' and self.inargs.foreground:
            self.start()
        elif self.inargs.action == 'start' and not self.inargs.foreground:
            self.run()
        elif self.inargs.action == 'stop':
            self.stop()
        elif self.inargs.action == 'restart':
            self.restart()
        elif self.inargs.action == 'status':
            self.status()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)

    def reporter(self, state, sitename, stwork):
        """Report Service State to FE"""
        if not self.inargs.noreporting:
            runtime = int(getUTCnow()) - stwork
            self._pubStateRemote(servicename=self.component,
                                 servicestate=state, sitename=sitename,
                                 version=runningVersion, runtime=runtime)

    def autoRefreshDB(self, **kwargs):
        """Auto Refresh if there is a DB request to do so."""
        # pylint: disable=W0703
        refresh = False
        try:
            if self.dbI:
                refresh = self._autoRefreshDB(**kwargs)
            elif self.config:
                refresh = self._autoRefreshAPI(**kwargs)
        except Exception:
            excType, excValue = sys.exc_info()[:2]
            print(
                f"Error details in autoRefreshDB. ErrorType: {str(excType.__name__)}, ErrMsg: {excValue}"
            )
            return False
        return refresh

    def runLoop(self):
        """Return True if it is not onetime run."""
        if self.inargs.onetimerun and self.runCount == 0:
            return True
        if self.inargs.onetimerun and self.runCount > 0:
            return False
        return True

    def refreshThreads(self, houreq, dayeq):
        """Refresh threads"""
        # pylint: disable=W0702
        while True:
            try:
                self.getThreads(houreq, dayeq)
                return
            except SystemExit:
                exc = traceback.format_exc()
                self.logger.critical("SystemExit!!! Error details:  %s", exc)
                sys.exit(1)
            except:
                exc = traceback.format_exc()
                self.logger.critical("Exception!!! Error details:  %s", exc)
                time.sleep(self.sleepTimers['failure'])

    def run(self):
        """Run main execution"""
        # pylint: disable=W0702
        houreq, dayeq, currentHour, currentDay = reCacheConfig(None, None)
        self.refreshThreads(houreq, dayeq)
        while self.runLoop():
            self.runCount += 1
            hadFailure = False
            refresh = False
            stwork = int(getUTCnow())
            try:
                for sitename, rthread in list(self.runThreads.items()):
                    stwork = int(getUTCnow())
                    refresh = self.autoRefreshDB(**{"sitename": sitename})
                    self.logger.info('Start worker for %s site', sitename)
                    try:
                        self.preRunThread(sitename, rthread)
                        rthread.startwork()
                        self.postRunThread(sitename, rthread)
                        self.reporter('OK', sitename, stwork)
                    except:
                        hadFailure = True
                        self.reporter('FAILED', sitename, stwork)
                        exc = traceback.format_exc()
                        self.logger.critical("Exception!!! Error details:  %s", exc)
                if self.runLoop():
                    time.sleep(self.sleepTimers['ok'])
            except KeyboardInterrupt as ex:
                self.reporter('KEYBOARDINTERRUPT', sitename, stwork)
                self.logger.critical("Received KeyboardInterrupt: %s ", ex)
                sys.exit(3)
            if hadFailure:
                self.logger.info('Had Runtime Failure. Sleep for 30 seconds')
                if self.runLoop():
                    time.sleep(self.sleepTimers['failure'])
                else:
                    sys.exit(4)
            if self.totalRuntime != 0 and self.totalRuntime <= int(getUTCnow()):
                self.logger.info('Total Runtime expired. Stopping Service')
                sys.exit(0)
            houreq, dayeq, currentHour, currentDay = reCacheConfig(currentHour, currentDay)
            if not houreq:
                self.logger.info('Re-initiating Service with new configuration from GIT')
                self._refreshConfig()
                self.refreshThreads(houreq, dayeq)
            elif refresh:
                self.logger.info('Re-initiating Service with new configuration from GIT. Forced by DB')
                self.cleaner()
                self._refreshConfig()
                self.refreshThreads(houreq, dayeq)

    @staticmethod
    def getThreads(_houreq, _dayeq):
        """Overwrite this then Daemonized in your own class"""
        return {}

    @staticmethod
    def cleaner():
        """Clean files from /tmp/ directory"""
        # Only one service overrides it, and it is ConfigFetcher
        # So if anyone else calls it - we sleep for 30 seconds
        print("Due to DB Refresh - sleep for 30 seconds until ConfigFetcher is done")
        time.sleep(30)


    @staticmethod
    def preRunThread(_sitename, _rthread):
        """Call before thread runtime in case something needed to be done by Daemon"""

    @staticmethod
    def postRunThread(_sitename, _rthread):
        """Call after thread runtime in case something needed to be done by Daemon"""
