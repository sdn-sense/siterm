#!/usr/bin/env python3
"""Function profiler to check/print memory usage. This is just an example"""
import time
import os
import psutil
import inspect
from SiteFE.LookUpService import lookup as LS
from SiteRMLibs.MainUtilities import getGitConfig


def elapsedSince(start):
    """Find elapsed time"""
    elapsed = time.time() - start
    if elapsed < 1:
        return str(round(elapsed*1000, 2)) + "ms"
    if elapsed < 60:
        return str(round(elapsed, 2)) + "s"
    if elapsed < 3600:
        return str(round(elapsed/60, 2)) + "min"
    return str(round(elapsed / 3600, 2)) + "hrs"


def getProcessMemory():
    """Get process memory info"""
    process = psutil.Process(os.getpid())
    memInf = process.memory_info()
    return memInf.rss, memInf.vms, memInf.shared


def formatBytes(inVal):
    """Format bytes"""
    if abs(inVal) < 1000:
        return str(bytes)+"B"
    if abs(inVal) < 1e6:
        return str(round(inVal/1e3, 2)) + "kB"
    if abs(inVal) < 1e9:
        return str(round(inVal / 1e6, 2)) + "MB"
    return str(round(inVal / 1e9, 2)) + "GB"


def profile(func, *args, **kwargs):
    """Profiler decorator"""
    def wrapper(*args, **kwargs):
        """Profiler wrapper"""
        rssBefore, vmsBefore, sharedBefore = getProcessMemory()
        start = time.time()
        result = func(*args, **kwargs)
        elapsedTime = elapsedSince(start)
        rssAfter, vmsAfter, sharedAfter = getProcessMemory()
        print("Profiling: {:>20}  RSS: {:>8} | VMS: {:>8} | SHR {"
              ":>8} | time: {:>8}"
             .format("<" + func.__name__ + ">",
                     formatBytes(rssAfter - rssBefore),
                     formatBytes(vmsAfter - vmsBefore),
                     formatBytes(sharedAfter - sharedBefore),
                     elapsedTime))
        return result
    if inspect.isfunction(func):
        return wrapper
    if inspect.ismethod(func):
        return wrapper(*args, **kwargs)


class MyDaemon():
    """My own Deamon override"""

    @profile
    def __init__(self):
        self.config = getGitConfig()

    @profile
    def getThreads(self):
        """Multi threading. Allow multiple sites under single FE"""
        outThreads = {}
        for sitename in self.config.get('general', 'sites'):
            thr = LS.LookUpService(self.config, sitename)
            outThreads[sitename] = thr
        return outThreads

    @profile
    def runcustom(self, runThreads):
        """Custom run"""
        i = 0
        while i < 5:
            for sitename, rthread in list(runThreads.items()):
                print(f'Run thread for {sitename}')
                rthread.startwork()
            i += 1


if __name__ == "__main__":
    DAEMON = MyDaemon()
    while True:
        threads = DAEMON.getThreads()
        DAEMON.runcustom(threads)
