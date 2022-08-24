#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Site FE call functions.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import json
from tempfile import NamedTemporaryFile
from SiteFE.PolicyService import policyService as polS
from SiteFE.PolicyService import stateMachine as stateM
from DTNRMLibs.MainUtilities import httpdate
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getCustomOutMsg
from DTNRMLibs.MainUtilities import getAllFileContent
from DTNRMLibs.MainUtilities import convertTSToDatetime
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.CustomExceptions import DeltaNotFound
from DTNRMLibs.CustomExceptions import ModelNotFound
from DTNRMLibs.CustomExceptions import WrongDeltaStatusTransition
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import getVal


class frontendDeltaModels():
    """Delta Actions through Frontend interface."""
    def __init__(self, config=None, dbI=None):
        if config:
            self.config = config
        else:
            self.config = getConfig()
        self.logger = getLoggingObject(config=self.config, service='http-api')
        self.policer = {}
        if dbI:
            self.dbI = dbI
        else:
            self.dbI = getDBConn('REST-DELTA', self)
        self.policer = {}
        for sitename in self.config.get('general', 'sites').split(','):
            policer = polS.PolicyService(config, sitename)
            self.policer[sitename] = policer
        self.stateM = stateM.StateMachine(self.config)
        self.siteDB = contentDB(config=self.config)

    def addNewDelta(self, uploadContent, environ, **kwargs):
        """Add new delta."""
        dbobj = getVal(self.dbI, **kwargs)
        hashNum = uploadContent['id']
        if dbobj.get('deltas', search=[['uid', hashNum]], limit=1):
            # This needs to be supported as it can be re-initiated again. TODO
            msg = 'Something weird has happened... Check server logs; Same ID is already in DB'
            kwargs['http_respond'].ret_409('application/json', kwargs['start_response'], None)
            return getCustomOutMsg(errMsg=msg, errCode=409)
        tmpfd = NamedTemporaryFile(delete=False, mode="w+")
        tmpfd.close()
        self.getmodel(uploadContent['modelId'], **kwargs)
        outContent = {"ID": hashNum,
                      "InsertTime": getUTCnow(),
                      "UpdateTime": getUTCnow(),
                      "Content": uploadContent,
                      "State": "accepting",
                      "modelId": uploadContent['modelId']}
        self.siteDB.saveContent(tmpfd.name, outContent)
        out = self.policer[kwargs['sitename']].acceptDelta(tmpfd.name)
        outDict = {'id': hashNum,
                   'lastModified': convertTSToDatetime(outContent['UpdateTime']),
                   'href': f"{environ['SCRIPT_URI']}/{hashNum}",
                   'modelId': out['modelId'],
                   'state': out['State']}
        print(f"Delta was {out['State']}. Returning info {outDict}")
        if out['State'] in ['accepted']:
            kwargs['http_respond'].ret_201('application/json', kwargs['start_response'],
                                           [('Last-Modified', httpdate(out['UpdateTime'])),
                                            ('Location', outDict['href'])])
            return outDict
        kwargs['http_respond'].ret_500('application/json', kwargs['start_response'], None)
        if 'Error' not in list(out.keys()):
            out = f"Unknown Error. Dump all out content {json.dumps(out)}"
        else:
            out = json.dumps(out)
        return getCustomOutMsg(errMsg=out, exitCode=500)

    def getdelta(self, deltaID=None, **kwargs):
        """Get delta from database."""
        dbobj = getVal(self.dbI, **kwargs)
        if not deltaID:
            return dbobj.get('deltas')
        out = dbobj.get('deltas', search=[['uid', deltaID]], orderby=['insertdate', 'ASC'])
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out[0]

    def getdeltastates(self, deltaID, **kwargs):
        """Get delta states from database."""
        dbobj = getVal(self.dbI, **kwargs)
        out = dbobj.get('states', search=[['deltaid', deltaID]])
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out

    def getHostNameIDs(self, hostname, state, **kwargs):
        """Get Hostname IDs."""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('hoststates', search=[['hostname', hostname], ['state', state]])

    def getmodel(self, modelID=None, content=False, **kwargs):
        """Get all models."""
        dbobj = getVal(self.dbI, **kwargs)
        if not modelID:
            return dbobj.get('models', orderby=['insertdate', 'DESC'])
        model = dbobj.get('models', limit=1, search=[['uid', modelID]])
        if not model:
            raise ModelNotFound(f"Model with {modelID} id was not found in the system")
        if content:
            return getAllFileContent(model[0]['fileloc'])
        return model[0]

    def commitdelta(self, deltaID, newState='UNKNOWN', internal=False, hostname=None, **kwargs):
        """Change delta state."""
        dbobj = getVal(self.dbI, **kwargs)
        if internal:
            out = dbobj.get('hoststates', search=[['deltaid', deltaID], ['hostname', hostname]])
            if not out:
                msg = f'This query did not returned any host states for {deltaID} {hostname}'
                raise WrongDeltaStatusTransition(msg)
            self.stateM._stateChangerHost(dbobj, out[0]['id'], **{'deltaid': deltaID,
                                                                  'state': newState,
                                                                  'insertdate': getUTCnow(),
                                                                  'hostname': hostname})
            if newState == 'remove':
                # Remove state comes only from modify and by agent itself
                self.stateM.stateChange(dbobj, {'uid': deltaID, 'state': newState})
            return getCustomOutMsg(msg='Internal State change approved', exitCode=200)
        delta = self.getdelta(deltaID, **kwargs)
        print(f'Commit Action for delta {delta}')
        # Now we go directly to commited in case of commit
        if delta['state'] != 'accepted':
            msg = (f"Delta state in the system is not in accepted state."
                   f"State on the system: {delta['state']}. Not allowed to change.")
            print(msg)
            raise WrongDeltaStatusTransition(msg)
        self.stateM.commit(dbobj, {'uid': deltaID, 'state': 'committing'})
        return {'status': 'OK'}

    def getActiveDeltas(self, **kwargs):
        """Get all Active Deltas"""
        dbobj = getVal(self.dbI, **kwargs)
        activeDeltas = dbobj.get('activeDeltas')
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            activeDeltas['output'] = evaldict(activeDeltas['output'])
        if not activeDeltas:
            activeDeltas = {'output': {}}
        return activeDeltas
