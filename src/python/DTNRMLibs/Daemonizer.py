#!/usr/bin/env python3
"""This part of code is taken from:

https://web.archive.org/web/20160305151936/http://www.jejik.com/articles/2007/02/a_simple_unix_linux_daemon_in_python/
Please respect developer (Sander Marechal) and always keep a reference to URL and also as kudos to him
Changes applied to this code:
    Dedention (Justas Balcas 07/12/2017)
    pylint fixes: with open, split imports, var names, old style class (Justas Balcas 07/12/2017)
"""
from __future__ import print_function
import os
import sys
import time
import atexit
import psutil
from DTNRMLibs.MainUtilities import getConfig, getLoggingObject
from DTNRMLibs.MainUtilities import reCacheConfig
from DTNRMLibs.MainUtilities import pubStateRemote

class Daemon():
    """A generic daemon class.

    Usage: subclass the Daemon class and override the run() method.
    """

    ALLCMD = ['start', 'stop', 'restart', 'startforeground', 'status']

    def __init__(self, component, logType='TimedRotatingFileHandler',
                 stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.component = component
        self.pidfile = '/tmp/end-site-rm-%s.pid' % component
        self.config = getConfig()
        self.logger = getLoggingObject("%s/%s/" % (self.config.get('general', 'logDir'), component),
                                self.config.get('general', 'logLevel'), logType=logType)
        self.availableCommands = ['start', 'stop', 'restart', 'startforeground', 'status']

    def _refreshConfig(self):
        self.config = getConfig()

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
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
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
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.stdin, 'r', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stdin.fileno())
        with open(self.stdout, 'a+', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stdout.fileno())
        with open(self.stderr, 'a+', encoding='utf-8') as fd:
            os.dup2(fd.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        with open(self.pidfile, 'w+', encoding='utf-8') as fd:
            fd.write("%s\n" % pid)

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

    def __kill(self, pid):
        """ Kill process using psutil lib """
        process = psutil.Process(pid)
        for proc in process.children(recursive=True):
            proc.kill()
        process.kill()

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
        try:
            while 1:
                self.__kill(pid)
                time.sleep(0.1)
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print(str(err))
                sys.exit(1)

    def restart(self):
        """Restart the daemon."""
        self.stop()
        self.start()

    def status(self):
        """Daemon status."""
        try:
            with open(self.pidfile, 'r', encoding='utf-8') as fd:
                pid = int(fd.read().strip())
                print('Application info: PID %s' % pid)
        except IOError:
            print('Is application running?')
            sys.exit(1)

    def command(self, command):
        """Execute a specific command to service."""
        if command == 'start':
            self.start()
        elif command == 'stop':
            self.stop()
        elif command == 'restart':
            self.restart()
        elif command == 'startforeground':
            self.run()
        elif command == 'status':
            self.status()
        else:
            print("Unknown command")
            sys.exit(2)
        sys.exit(0)

    def run(self):
        """ Run main execution """
        timeeq, currentHour = reCacheConfig(None)
        runThreads = self.getThreads()
        while True:
            hadFailure = False
            try:
                for sitename, rthread in list(runThreads.items()):
                    self.logger.info('Start worker for %s site', sitename)
                    try:
                        rthread.startwork()
                        pubStateRemote(self.config, servicename=self.component, servicestate='OK', sitename=sitename)
                    except:
                        hadFailure = True
                        pubStateRemote(self.config, servicename=self.component, servicestate='FAILED', sitename=sitename)
                        excType, excValue = sys.exc_info()[:2]
                        self.logger.critical("Error details. ErrorType: %s, ErrMsg: %s", str(excType.__name__), excValue)
                time.sleep(10)
            except KeyboardInterrupt as ex:
                pubStateRemote(self.config, servicename=self.component, servicestate='KEYBOARDINTERRUPT', sitename=sitename)
                self.logger.critical("Received KeyboardInterrupt: %s ", ex)
                sys.exit(3)
            if hadFailure:
                self.logger.info('Had Runtime Failure. Sleep for 30 seconds')
                time.sleep(30)
            timeeq, currentHour = reCacheConfig(currentHour)
            if not timeeq:
                self.logger.info('Re initiating LookUp Service with new configuration from GIT')
                self._refreshConfig()
                rthread = self.getThreads()

    def getThreads(self):
        """ Overwrite this then Daemonized in your own class """
        return {}
