#!/usr/bin/env python
""" Notification service which informs admins about any issue in agents.

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
import os
import time
import json
from DTNRMLibs.Mailing import sendMail
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import readFile
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import getDataFromSiteFE
from DTNRMLibs.CustomExceptions import FailedToParseError
from DTNRMLibs.MainUtilities import getUTCnow

# TODO: Make a class
CONFIG = getConfig(["/etc/dtnrm-site-fe.conf"])
COMPONENT = 'NotificationService'
LOGGER = getLogger("%s/%s/" % (CONFIG.get('general', 'logDir'), COMPONENT), CONFIG.get(COMPONENT, 'logLevel'))


def checkPluginErrors(ipv4, values, errors):
    """ Check for default errors which can be set by plugin """
    for pluginName, pluginOut in values.items():
        tmpError = {}
        if not isinstance(pluginOut, dict):
            continue
        for key in ['errorType', 'errorNo', 'errMsg']:
            if key in pluginOut:
                tmpError[key] = pluginOut[key]
        if tmpError:
            tmpError['plugin'] = pluginName
            tmpError['ip'] = ipv4
            errors.append(tmpError)


def checkCertLifeTime(ipv4, inDict, errors):
    """Checking certificate lifetime"""
    oneMonthAfter = getUTCnow() + 60 * 60 * 24 * 30
    if 'CertInfo' in inDict:
        if 'enddate' in inDict['CertInfo']:
            if inDict['CertInfo']['enddate'] < getUTCnow():
                errors.append({"errMsg": "Certificate expired", "errorType": "CERTFAILED", "errorNo": 100, "ip": ipv4})
            elif inDict['CertInfo']['enddate'] > oneMonthAfter:
                errors.append({"errMsg": "Certificate will expire in less than one month",
                               "errorType": "CERTRenew", "errorNo": 1, "ip": ipv4})


def warningsFromMonComponent(ip, indict, errors):
    """ For future store warnings from the Monitoring component """
    # TODO the new plugin first....
    return


def compareErrors(prevErrors, currErrors):
    """ Compare errors and return new list which are different """
    newErrors = []
    for error in currErrors:
        foundMatch = False
        for prevError in prevErrors:
            if cmp(error, prevError) == 0:
                foundMatch = True
        if not foundMatch:
            print 'This error is new %s' % error
            newErrors.append(error)
    return newErrors


def writeNewFile(errors, workDir):
    """ Write and print new configuration file"""
    newFileName = workDir + "lastRunErrors.json"
    with open(newFileName, 'w+b') as fd:
        json.dump(errors, fd)
    return


def prepareMailSend(errors, mailingSender, mailingList):
    """Prepare mail content and send email"""
    bodyText = 'There was some Failures in the Site Infrastructure\n'
    bodyText += 'Please have a look to the following issues:\n\n'
    for error in errors:
        bodyText += '-' * 50
        bodyText += '\n'
        for key, value in error.items():
            bodyText += '%s  :  %s\n' % (key, value)
        bodyText += '\n\n'
    sendMail(mailingSender, mailingList,
             '[SENSE-DTN-RM Monitoring] Failures in the Site Infrastructure',
             bodyText)
    return


def startwork(config=None, logger=None):
    """Main start """
    errors = []
    agents = getDataFromSiteFE({}, "http://localhost/", "/sitefe/json/frontend/getdata")
    if agents[2] != 'OK':
        print 'Received a failure getting information from Site Frontend %s' % str(agents)
        return
    workDir = CONFIG.get('frontend', 'privatedir') + "/notificationService/"
    mailingSender = CONFIG.get('NotificationService', 'mailingSender')
    mailingList = CONFIG.get('NotificationService', 'mailingList').split(',')
    createDirs(workDir)
    jOut = {}
    try:
        jOut = evaldict(agents[0])
    except FailedToParseError as ex:
        print 'Server returned not a json loadable object. Raising error. Output %s. Errors: %s' % (str(agents), ex)
        return
    # We start with simple error messages
    for ipaddr, values in jOut.items():
        # Check if there is any error first
        checkPluginErrors(ipaddr, values, errors)
        checkCertLifeTime(ipaddr, values, errors)
        warningsFromMonComponent(ipaddr, values, errors)
    # Compare errors with previous run and send email only if there is something new...
    lastErrors = readFile(str(workDir + "lastRunErrors.json"))
    if lastErrors:
        try:
            lastErrors = evaldict(lastErrors[0])
        except FailedToParseError as ex:
            print 'Loaded object from the system is not evaluable. Raising error. \
                   Output %s. Errors: %s' % (str(lastErrors), ex)
            print 'Ignoring and continue as there was no errors before'
            lastErrors = []
    newErrors = []
    if lastErrors and errors:
        newErrors = compareErrors(lastErrors, errors)
    elif errors:
        # Means there is no previous errors.
        print errors
    elif lastErrors and not errors:
        print 'All errors were resolved...'
    print lastErrors, errors, newErrors
    if newErrors:
        prepareMailSend(newErrors, mailingSender, mailingList)
    writeNewFile(errors, workDir)
    return

def execute():
    """Main script execution"""
    startwork(CONFIG, LOGGER)


if __name__ == '__main__':
    execute()
