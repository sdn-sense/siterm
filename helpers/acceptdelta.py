#!/usr/bin/env python3
"""Change delta state to activating."""
import sys
import tempfile
import ast
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger
from DTNRMLibs.FECalls import getDBConn
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteFE.PolicyService import policyService as polS

CONFIG = getConfig()
LOGGER = getStreamLogger()
STATEMACHINE = StateMachine(LOGGER)


def getdeltaAll(sitename, deltaUID):
    """Get all deltas for specific Site.

    INPUT: sitename  - str mandatory
           deltaUID  - str mandatory
    """
    siteDB = contentDB(logger=LOGGER, config=CONFIG)
    policer = polS.PolicyService(CONFIG, LOGGER)
    delta, dbObj = getdeltainfo(sitename, deltaUID)
    tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
    tmpFile.close()
    outContent = {"ID": delta['uid'],
                  "InsertTime": delta['insertdate'],
                  "UpdateTime": delta['updatedate'],
                  "Content": ast.literal_eval(str(delta['content'])),
                  "State": "accepting",
                  "modelId": delta['modelid']}
    siteDB.saveContent(tmpFile.name, outContent)

    policer.acceptDelta(tmpFile.name, sitename)
    delta, dbObj = getdeltainfo(sitename, deltaUID)
    STATEMACHINE.stateChangerDelta(dbObj, 'activating', **delta)


def getdeltainfo(sitename, deltaUID):
    """Get all delta information.

    INPUT: sitename  - str mandatory
           deltaUID  - str mandatory
    """
    dbI = getDBConn('acceptdelta')
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        if delta['uid'] != deltaUID:
            continue
        delta['addition'] = evaldict(delta['addition'])
        delta['reduction'] = evaldict(delta['reduction'])
        LOGGER.info('=' * 80)
        LOGGER.info('Delta UID  :  %s', delta['uid'])
        LOGGER.info('Delta RedID:  %s', delta['reductionid'])
        LOGGER.info('Delta State:  %s', delta['state'])
        LOGGER.info('Delta ModAdd: %s', delta['modadd'])
        LOGGER.info('Delta InsDate: %s', delta['insertdate'])
        LOGGER.info('Delta Update:  %s', delta['updatedate'])
        LOGGER.info('Delta Model:  %s', delta['modelid'])
        LOGGER.info('Delta connID:  %s', delta['connectionid'])
        LOGGER.info('Delta Deltatype: %s', delta['deltat'])
        LOGGER.info('-' * 20)
        LOGGER.info('Delta times')
        for deltatimes in dbobj.get('states', search=[['deltaid', delta['uid']]]):
            LOGGER.info('State: %s Date: %s', deltatimes['state'], deltatimes['insertdate'])
        if delta['deltat'] in ['reduction', 'addition']:
            for hostname in list(delta[delta['deltat']]['hosts'].keys()):
                LOGGER.info('-' * 20)
                LOGGER.info('Host States %s', hostname)
                for hoststate in dbobj.get('hoststates', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                    LOGGER.info('Host %s State %s', hostname, hoststate['state'])
                    LOGGER.info('Insertdate %s UpdateDate %s', hoststate['insertdate'], hoststate['updatedate'])
                    LOGGER.info('-' * 20)
                    LOGGER.info('Host State History')
                    for hstatehistory in dbobj.get('hoststateshistory',
                                                   search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                        LOGGER.info('State: %s, Date: %s', hstatehistory['state'], hstatehistory['insertdate'])
        return delta, dbobj

if __name__ == "__main__":
    getdeltaAll(sys.argv[1], sys.argv[2])
