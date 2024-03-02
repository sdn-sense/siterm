#!/usr/bin/env python3
"""
    Debug Service

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/22
"""
import os
from SiteRMLibs.MainUtilities import jsondumps
from SiteRMLibs.MainUtilities import createDirs
from SiteRMLibs.MainUtilities import externalCommand
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import publishToSiteFE
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.GitConfig import getGitConfig

class DebugService:
    """Debug Service Class"""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.fullURL = getFullUrl(self.config, sitename)
        self.sitename = sitename
        self.diragent = contentDB()
        self.logger = getLoggingObject(config=self.config, service='DebugService')
        self.workDir = self.config.get('general', 'privatedir') + "/SiteRM/background/"
        createDirs(self.workDir)

    def publishToFE(self, inDic):
        """Publish debug runtime to FE"""
        publishToSiteFE(inDic, self.fullURL, f"/sitefe/json/frontend/updatedebug/{inDic['id']}")

    def checkBackgroundProcess(self, item):
        """Start Background work on specific item"""
        fname = self.workDir + f"/background-process-{item['id']}.json"
        if not os.path.isfile(fname):
            self.diragent.dumpFileContentAsJson(fname, item)
        try:
            out, exitCode, newstate = self.run(item)
        except (ValueError, KeyError, OSError) as ex:
            out = {'processOut': [], 'stdout': [], 'stderr': [], 'jsonout': {}, 'exitCode': 501}
            out['stderr'].append(str(ex))
            exitCode = 501
            newstate = "failed"
        self.logger.debug(f"Finish work on debug: {out}")
        # 501, 1 - error - set to failed
        # 2 - active
        # 3 - finished
        if exitCode in [501, 1]:
            newstate = 'failed'
        elif exitCode == 0:
            newstate = 'active'
        elif exitCode == 3:
            newstate = 'finished'
        else:
            newstate = 'unknown'
        if item['state'] != newstate:
            item['state'] = newstate
            self.logger.info(f"Updating state of debug: {item['id']} to {newstate}")

        out = {'id': item['id'],
               'state': item['state'],
               'output': jsondumps(out),
               'updatedate': getUTCnow()}
        self.publishToFE(item)

    def _getOut(self, pid, logtype):
        """Get output from background process log file."""
        fname = self.workDir + f"/background-process-{pid}.{logtype}"
        tmpOut = self.diragent.getFileContentAsList(fname)
        out = [f"Output for {logtype} for {pid} does not exist", "="*80, ""]
        if tmpOut:
            out = [f"Output for {logtype} for {pid}", "="*80, ""]
        out += tmpOut
        return out

    def _getOutjson(self, pid, logtype):
        """Get output from background process log file."""
        fname = self.workDir + f"/background-process-{pid}.{logtype}"
        return self.diragent.getFileContentAsJson(fname, {})

    def _runCmd(self, inputDict, action, foreground):
        """Start execution of new requests"""
        retOut = {'processOut': [], 'stdout': [], 'stderr': [], 'jsonout': {}, 'exitCode': -1}
        command = f"siterm-bgprocess --action {action} --runnum {inputDict['id']}"
        if foreground:
            command += " --foreground"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
        retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
        retOut['jsonout'] = self._getOutjson(inputDict['id'], 'jsonout')
        retOut['exitCode'] = cmdOut.returncode
        return retOut

    def _clean(self, inputDict):
        """Clean up after process is finished"""
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.json")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stdout")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stderr")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.jsonout")

    def run(self, inputDict):
        """Run a specific debug service in a separate thread"""
        inputDict['requestdict'] = evaldict(inputDict['requestdict'])
        self.logger.debug(f"Check background process: {inputDict}")
        utcNow = int(getUTCnow())
        # Check Status first
        retOut = self._runCmd(inputDict, 'status', False)

        # If this first start, then start it.
        if retOut['exitCode'] != 0 and inputDict['state'] == 'new':
            self.logger.info(f"Starting background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'start', True)
            retOut['processOut'].append(f"Starting background process: {inputDict['id']}")
            return retOut, retOut['exitCode'], "active"

        # If it is active, and process is active, then get output from it.
        if retOut['exitCode'] == 0 and inputDict['state'] == 'active' and int(inputDict['requestdict'].get('runtime', 600)) > utcNow:
            self.logger.info(f"Checking background process: {inputDict['id']}")
            retOut['processOut'].append(f"Checking background process: {inputDict['id']}")
            return retOut, retOut['exitCode'], "active"

        # If it is active, but process exited, then restart it (if time still allows that).
        if retOut['exitCode'] != 0 and inputDict['state'] == 'active' and int(inputDict['requestdict'].get('runtime', 600)) > utcNow:
            self.logger.info(f"Restarting background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'restart', True)
            retOut['processOut'].append(f"Restarting background process: {inputDict['id']}")
            return retOut, retOut['exitCode'], "active"

        # if it is active, process is active, and time ran out, then stop it.
        if retOut['exitCode'] == 0 and inputDict['state'] == 'active' and int(inputDict['requestdict'].get('runtime', 600)) <= utcNow:
            self.logger.info(f"Stopping background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'stop', False)
            self._clean(inputDict)
            return retOut, 3, "finished"

        # If any other unknown state - we stop process and set it to failed
        if retOut['exitCode'] != 0 and (inputDict['state'] != 'new' or inputDict['state'] != 'active'):
            self.logger.info(f"Stopping background process (unknown): {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'stop', False)
            retOut['processOut'].append(f"Stopping background process: {inputDict['id']}")
            self._clean(inputDict)
            return retOut, retOut['exitCode'], "failed"
        return retOut, 501, "unknown"
