#!/usr/bin/env python
"""
Forwarding Service creates apache config file.
    a)Reads configuration file and get information where the FE is running.
    b)Get's a list of all hosts.
    c)Checks which one it already prepared and which one needs to add again.
    d)Append all of this with ProxyReserve rules and restart apache

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
from shutil import copy2
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import readFile
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getFullUrl
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import externalCommand
from DTNRMLibs.MainUtilities import getDataFromSiteFE
from DTNRMLibs.CustomExceptions import FailedToParseError

CONFIG = getConfig(["/etc/dtnrm-site-fe.conf"])
COMPONENT = 'ForwardingService'
LOGGER = getLogger("%s/%s/" % (CONFIG.get('general', 'logDir'), COMPONENT), CONFIG.get(COMPONENT, 'logLevel'))


def checkConsistency(inputDict, currentHttpdConf, start, end):
    """Check current config and information from Site FE. Append what is missing."""
    newConfig = []
    changed = False
    print 'Appending the beginning %s lines' % start
    for lineNum in range(0, start):
        newConfig.append(currentHttpdConf[lineNum])
    print 'Starting to check current configuration with what we received from DB'
    newConfig.append("### HERE STARTS PROXYREWRITERULES")
    for lineNum in range(start, end):
        if lineNum == start or lineNum == end:
            continue
        if currentHttpdConf[lineNum].strip().startswith("# PROXYRULE"):
            inLine = currentHttpdConf[lineNum].split("|")  # # PROXYRULE|HOST|1.2.3.4|PORT|19999
            if inLine[2] in inputDict['nodes'].keys() and int(inputDict['nodes'][inLine[2]]['port']) == int(inLine[4]):
                print 'This host is already defined... Just copy next 3 lines'
                for i in range(3):
                    newConfig.append(currentHttpdConf[lineNum + i])
                del inputDict['nodes'][inLine[2]]
            else:
                print 'Something does not match and this host is not anymore in the list...'
                changed = True
                # If host is not there it will take ~N minutes after it to re-appear again.
                # I do not foresee any issue as server now provides data from a file, not memory, so
                # it is always up to date.
    print 'Finished to check current configuration with what we received from DB'
    print 'Checking what is left in server configuration and appending to config file'
    print 'Currently there is still %s hosts left' % inputDict['nodes'].keys()
    for ipv4, values in inputDict['nodes'].items():
        changed = True
        newConfig.append('# PROXYRULE|HOST|%s|PORT|%s' % (ipv4, values['port']))
        newConfig.append('ProxyPass "/nodemonitoring/%s/" "http://%s:%s/" connectiontimeout=15 timeout=30' % (ipv4, ipv4, values['port']))
        newConfig.append('ProxyPassReverse "/nodemonitoring/%s/" "http://%s:%s/"' % (ipv4, ipv4, values['port']))
    newConfig.append("### HERE ENDS PROXYREWRITERULES")
    print 'Appending the ending %s lines' % int(len(currentHttpdConf) - end)
    for lineNum in range(end + 1, len(currentHttpdConf)):
        newConfig.append(currentHttpdConf[lineNum])
    return newConfig, changed


def prepareNewHTTPDConfig(inputDict, currentHttpdConf):
    """Check if needed start end tags are available.
       If not consistent or was modified, file will append new config between tags"""
    start, end = -1, -1
    # Get the start and the end. In the automatic preparation it will 3 lines defined:
    # # PROXYRULE|HOST|1.2.3.4|PORT|19999
    # ProxyPass "/nodemonitoring/1.2.3.4/" "http://1.2.3.4:19999/" connectiontimeout=15 timeout=30
    # ProxyPassReverse "/nodemonitoring/1.2.3.4/" "http://1.2.3.4:19999/"
    for lineNum in range(len(currentHttpdConf)):
        print currentHttpdConf[lineNum]
        if currentHttpdConf[lineNum].strip().startswith("### HERE STARTS PROXYREWRITERULES"):
            print 'start'
            start = lineNum
        elif currentHttpdConf[lineNum].strip().startswith("### HERE ENDS PROXYREWRITERULES"):
            print 'end'
            end = lineNum
    if start == -1 or end == -1 or start == end:
        print 'Do not do any change as there is no start or end.... ERROR!'
        return None, None
    diff = end - start
    if diff != 1:
        diff = float(diff - 1) / 3
        intDiff = int(diff)
        floatDiff = float(diff)
        if intDiff != floatDiff:
            # Make sure there is 3 lines defined. Even it is automatic, we can`t be sure that admins will not mess it up.
            print 'There is not an equal number of lines, and agent does not know how to prepare it...'
            print 'Will skip all information and will prepare a totally new file'
    newOutConfig, wasChanged = checkConsistency(inputDict, currentHttpdConf, start, end)
    if not wasChanged:
        print 'Configuration looks the same what is available on FE. No point of changing restarting...'
    return newOutConfig, wasChanged


def writeNewConfig(newInConfig, workDir):
    """ Write and print new configuration file"""
    newFileName = workDir + "httpd-new.conf"
    print 'Writing new configuration file here: %s' % newFileName
    print '=' * 40
    with open(newFileName, 'w+b') as fd:
        for line in newInConfig:
            print line
            fd.write("%s\n" % line)
    print '=' * 40
    return


def startwork(config=None, logger=None):
    """Main start """
    fullURL = getFullUrl(config)
    agents = getDataFromSiteFE({}, fullURL, "/sitefe/json/frontend/ips")
    if agents[2] != 'OK':
        print 'Received a failure getting information from Site Frontend %s' % str(agents)
        return
    workDir = config.get('frontend', 'privatedir') + "/forwardingService/"
    createDirs(workDir)
    copy2("/etc/httpd/conf.d/sitefe-httpd.conf", str(workDir + "httpd-copy.conf"))
    httpdCopy = readFile(str(workDir + "httpd-copy.conf"))
    try:
        newDict = evaldict(agents[0])
    except FailedToParseError as ex:
        print 'Server returned not a json loadable object. Raising error. Output %s. Errors: %s' % (str(agents), ex)
        return
    if not newDict:
        print 'Seems server returned empty dictionary. Exiting.'
        return
    newOut, changed = prepareNewHTTPDConfig(newDict, httpdCopy)
    if changed:
        writeNewConfig(newOut, workDir)
        copy2(str(workDir + "httpd-new.conf"), "/etc/httpd/conf.d/sitefe-httpd.conf")
        stdout = externalCommand("service httpd restart")
        print stdout
        # Restart apache...
    return

def execute():
    """ Main execution """
    startwork(CONFIG, LOGGER)


if __name__ == '__main__':
    execute()
