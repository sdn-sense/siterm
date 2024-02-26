#!/usr/bin/env python3
"""
    Push local prometheus stats to a remote gateway.

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


class DebugService:
    """Debug Service Class"""
    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
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
            out = {'processOut': [], 'stdout': [], 'stderr': [], 'exitCode': 501}
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
            self.diragent.removeFile(fname)
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

    @staticmethod
    def _runCmd(self, inputDict, action):
        """Start execution of new requests"""
        command = f"siterm-bgprocess --action {action} --runnum {inputDict['id']}"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        return out, err, cmdOut

    def _getOut(self, pid, logtype):
        fname = self.workDir + f"/background-process-{pid}.{logtype}"
        out = ["Output for {logtype} for {pid}", "="*80, ""]
        if os.path.isfile(fname):
            with open(fname, 'r', encoding='utf-8') as fd:
                out += fd.readlines()
        return out

    def run(self, inputDict):
        """Run a specific debug service in a separate thread"""
        inputDict['requestdict'] = evaldict(inputDict['requestdict'])
        self.logger.debug(f"Check background process: {inputDict}")
        retOut = {'processOut': [], 'stdout': [], 'stderr': [], 'exitCode': -1}
        utcNow = int(getUTCnow())
        # Check Status first
        out, err, cmdOut = self._runCmd(inputDict, 'status')

        # If this first start, then start it.
        if cmdOut.returncode != 0 and inputDict['state'] == 'new':
            self.logger.info(f"Starting background process: {inputDict['id']}")
            out, err, cmdOut = self._runCmd(inputDict, 'start')
            retOut['processOut'].append(f"Starting background process: {inputDict['id']}")
            retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
            retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
            retOut['exitCode'] = cmdOut.returncode
            return retOut, cmdOut.returncode, "active"

        # If it is active, but process exited, then restart it (if time still allows that).
        if cmdOut.returncode != 0 and inputDict['state'] == 'active' and int(inputDict['requestdict']['runtime']) > utcNow:
            self.logger.info(f"Restarting background process: {inputDict['id']}")
            out, err, cmdOut = self._runCmd(inputDict, 'restart')
            retOut['processOut'].append(f"Restarting background process: {inputDict['id']}")
            retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
            retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
            retOut['exitCode'] = cmdOut.returncode
            return retOut, cmdOut.returncode, "active"

        # If it is active, and process is active, then get output from it.
        if cmdOut.returncode == 0 and inputDict['state'] == 'active' and int(inputDict['requestdict']['runtime']) > utcNow:
            self.logger.info(f"Checking background process: {inputDict['id']}")
            retOut['processOut'].append(f"Checking background process: {inputDict['id']}")
            retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
            retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
            retOut['exitCode'] = cmdOut.returncode
            return retOut, cmdOut.returncode, "active"

        # if it is active, process is active, and time ran out, then stop it.
        if cmdOut.returncode == 0 and inputDict['state'] == 'active' and int(inputDict['requestdict']['runtime']) <= utcNow:
            self.logger.info(f"Stopping background process: {inputDict['id']}")
            out, err, cmdOut = self._runCmd(inputDict, 'stop')
            retOut['processOut'].append(f"Stopping background process: {inputDict['id']}")
            retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
            retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
            retOut['exitCode'] = cmdOut.returncode
            return retOut, 3, "finished"

        # If any other unknown state - we stop process and set it to failed
        if cmdOut.returncode != 0 and (inputDict['state'] != 'new' or inputDict['state'] != 'active'):
            self.logger.info(f"Stopping background process (unknown): {inputDict['id']}")
            out, err, cmdOut = self._runCmd(inputDict, 'stop')
            retOut['processOut'].append(f"Stopping background process: {inputDict['id']}")
            retOut['stdout'] += out.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stdout')
            retOut['stderr'] += err.decode("utf-8").split('\n') + self._getOut(inputDict['id'], 'stderr')
            retOut['exitCode'] = cmdOut.returncode
            return retOut, cmdOut.returncode, "failed"
        return retOut, 501, "unknown"
