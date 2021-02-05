#!/usr/bin/env python3
"""Print delta information."""
from __future__ import print_function
from builtins import str
import sys
import tempfile
import ast
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger
from DTNRMLibs.FECalls import getDBConn
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteFE.PolicyService import policyService as polS

CONFIG = getConfig()
LOGGER = getStreamLogger()
STATEMACHINE = StateMachine(LOGGER)


def getdeltaAll(sitename, deltaUID):
    dbI = getDBConn('analyzedelta')
    dbobj = getVal(dbI, sitename=sitename)
    policer = polS.PolicyService(CONFIG, LOGGER)
    for delta in dbobj.get('deltas'):
        if delta['uid'] != deltaUID:
            continue
        delta['addition'] = evaldict(delta['addition'])
        delta['reduction'] = evaldict(delta['reduction'])
        print('=' * 80)
        print('Delta UID  :  ', delta['uid'])
        print('Delta RedID:  ', delta['reductionid'])
        print('Delta State:  ', delta['state'])
        print('Delta ModAdd: ', delta['modadd'])
        print('Delta InsDate:', delta['insertdate'])
        print('Delta Update: ', delta['updatedate'])
        print('Delta Model:  ', delta['modelid'])
        print('Delta connID: ', delta['connectionid'])
        print('Delta Deltatype: ', delta['deltat'])
        print('-' * 20)
        import pprint
        pprint.pprint(delta)
        print('Delta times')
        for deltatimes in dbobj.get('states', search=[['deltaid', delta['uid']]]):
            print('State: %s Date: %s' % (deltatimes['state'], deltatimes['insertdate']))
        if delta['deltat'] in ['reduction', 'addition']:
            for hostname in list(delta[delta['deltat']]['hosts'].keys()):
                print('-' * 20)
                print('Host States %s' % hostname)
                for hoststate in dbobj.get('hoststates', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                    print('Host %s State %s' % (hostname, hoststate['state']))
                    print('Insertdate %s UpdateDate %s' % (hoststate['insertdate'], hoststate['updatedate']))
                    print('-' * 20)
                    print('Host State History')
                    for hstatehistory in dbobj.get('hoststateshistory', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                        print('State: %s, Date: %s' % (hstatehistory['state'], hstatehistory['insertdate']))
        toDict = ast.literal_eval(str(delta['content']))
        jOut = getAllHosts(sitename, LOGGER)
        for key in ['reduction', 'addition']:
            print(list(toDict.keys()))
            if key in toDict and toDict[key]:
                print('Got Content %s for key %s', toDict[key], key)
                tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
                try:
                    tmpFile.write(toDict[key])
                except ValueError as ex:
                    print('Received ValueError. More details %s. Try to write normally with decode', ex)
                    tmpFile.write(decodebase64(toDict["Content"][key]))
                tmpFile.close()
                # outputDict[key] = self.parseDeltaRequest(tmpFile.name, jOut)
                print("For %s this is delta location %s" % (key, tmpFile.name))
            out = policer.parseDeltaRequest(tmpFile.name, jOut)
            if not out:
                out = policer.parseDeltaRequest(tmpFile.name, jOut, sitename)
                print(out)

if __name__ == "__main__":
    getdeltaAll(sys.argv[1], sys.argv[2])
