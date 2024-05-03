#!/usr/bin/env python3
"""
    Debug Service

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/22
"""
import os
import traceback
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
            out['stderr'].append(traceback.format_exc())
            exitCode = 501
            newstate = "failed"
        self.logger.debug(f"Finish check of process on debug action {item['id']}. ExitCode: {exitCode} NewState: {newstate}")
        if exitCode == -1 and newstate == 'unknown':
            # We skip this as it is up to the process to decide what to do.
            return

        out = {'id': item['id'],
               'state': newstate,
               'output': jsondumps(out),
               'updatedate': getUTCnow()}
        self.logger.debug(f"Updating state of debug: {out['id']} to {newstate}")
        self.logger.debug(f"Output of process: {out}")
        self.publishToFE(out)

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
        out = self.diragent.getFileContentAsJson(fname)
        out['output'] = evaldict(out.get('output', {}))
        return out

    def _runCmd(self, inputDict, action, foreground):
        """Start execution of new requests"""
        retOut = {'processOut': [], 'stdout': [], 'stderr': [], 'jsonout': {}, 'exitCode': -1}
        command = f"siterm-bgprocess --action {action} --noreporting --runnum {inputDict['id']}"
        if foreground:
            command += " --foreground"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
        retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
        retOut['processOut'] += self._getOut(inputDict['id'], 'process')
        retOut['jsonout'] = self._getOutjson(inputDict['id'], 'jsonout')
        retOut['exitCode'] = cmdOut.returncode
        return retOut

    def _clean(self, inputDict):
        """Clean up after process is finished"""
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.json")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stdout")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stderr")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.process")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.jsonout")

    def run(self, inputDict):
        """Run a specific debug service in a separate thread"""
        inputDict['requestdict'] = evaldict(inputDict['requestdict'])
        self.logger.debug(f"Check background process: {inputDict}")
        # Check Status first
        retOut = self._runCmd(inputDict, 'status', False)

        # If this first start, then start it.
        if retOut['exitCode'] != 0 and inputDict['state'] == 'new':
            self.logger.info(f"Starting background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'start', True)
            retOut['processOut'].append(f"Starting background process: {inputDict['id']}")
            return retOut, 0, "active"

        # If it is active, and process is active, then get output from it.
        if retOut['exitCode'] == 0 and inputDict['state'] == 'active':
            self.logger.info(f"Checking background process: {inputDict['id']}")
            retOut['processOut'].append(f"Checking background process: {inputDict['id']}")
            return retOut, 0, "active"

        # If it is active, but process exited, then it failed.
        if retOut['exitCode'] != 0 and inputDict['state'] == 'active':
            self.logger.info(f"Force stoping background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, 'stop', True)
            retOut['processOut'].append(f"Force stoping background process: {inputDict['id']}")
            if retOut['jsonout'].get('output', {}).get('exitCode', -1) == 0:
                self._clean(inputDict)
                return retOut, 2, "finished"
            # In case failed, we keep logs remaining. Not best practice, but we keep it for now.
            return retOut, 1, "failed"

        self.logger.warning(f"Unknown state for background process: {inputDict['id']}")
        self.logger.warning(f"Return Out of Process: {retOut}")
        return retOut, -1, "unknown"
