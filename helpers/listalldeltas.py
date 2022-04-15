#!/usr/bin/env python3
"""List all deltas inFrontend."""
from __future__ import print_function
import sys
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger
from DTNRMLibs.FECalls import getDBConn
from SiteFE.PolicyService.stateMachine import StateMachine


LOGGER = getStreamLogger()
CONFIG = getConfig()
STATEMACHINE = StateMachine(LOGGER)


def getdeltaAll(sitename):
    """Get Deltas from Database and dump to stdout"""
    dbI = getDBConn('listalldeltas')
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        delta['addition'] = evaldict(delta['addition'])
        delta['reduction'] = evaldict(delta['reduction'])
        print('='*80)
        print('Delta UID  :  ', delta['uid'])
        print('Delta RedID:  ', delta['reductionid'])
        print('Delta State:  ', delta['state'])
        print('Delta ModAdd: ', delta['modadd'])
        print('Delta InsDate:', delta['insertdate'])
        print('Delta Update: ', delta['updatedate'])
        print('Delta Model:  ', delta['modelid'])
        print('Delta connID: ', delta['connectionid'])
        print('Delta Deltatype: ', delta['deltat'])
        print('-'*20)
        print('Delta times')
        for deltatimes in dbobj.get('states', search=[['deltaid', delta['uid']]]):
            print('State: %s Date: %s' % (deltatimes['state'], deltatimes['insertdate']))
        if delta['deltat'] not in ['reduction', 'addition']:
            print('SOMETHING WRONG WITH THIS DELTA. It does not have any type defined. Was not parsed properly')
            continue
        if not isinstance(delta[delta['deltat']], list):
            conns = [delta[delta['deltat']]]
        else:
            conns = delta[delta['deltat']]
        for conn in conns:
            if 'hosts' not in list(conn.keys()):
                print('SOMETHING WRONG WITH THIS DELTA. It does not have any hosts defined.')
                continue
            for hostname in list(conn['hosts'].keys()):
                print('-'*20)
                print('Host States %s' % hostname)
                for hoststate in dbobj.get('hoststates', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                    print('Host %s State %s' % (hostname, hoststate['state']))
                    print('Insertdate %s UpdateDate %s' % (hoststate['insertdate'], hoststate['updatedate']))
                    print('-'*20)
                    print('Host State History')
                    for hstatehistory in dbobj.get('hoststateshistory', search=[['deltaid', delta['uid']], ['hostname', hostname]]):
                        print('State: %s, Date: %s' % (hstatehistory['state'], hstatehistory['insertdate']))
        print('-'*20)
        print('Connection details')
        for conn in conns:
            for dConn in dbobj.get('delta_connections', search=[['connectionid', conn['connectionID']]]):
                print(dConn)

if __name__ == "__main__":
    getdeltaAll(sys.argv[1])
