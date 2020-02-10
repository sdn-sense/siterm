#!/usr/bin/python
"""
Utilities which are used in any setup script

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
import sys
import platform
import ConfigParser

import platform
import sys

def linuxDistr():
    """ Return linux distribution name. Otherwise Unknown """
    try:
        return platform.linux_distribution()
    except:
        return "Unknown"

def printInfo(logger=None):
    """ Print information about sytem before start setup """
    print "System Information:"
    print "-" * 100
    print "Python version: %s" % sys.version.split('\n')
    print "Dist: %s" % str(platform.dist())
    print "Linux Distribution: %s" % linuxDistr()
    print "System: %s" % platform.system()
    print "Machine: %s" % platform.machine()
    print "Platform: %s" % platform.platform()
    print 'Uname: %s' % platform.uname()
    print 'Version: %s' % platform.version()
    print 'Mac version: %s' % platform.mac_ver()


def get_path_to_root(appendLocation=None):
    """
    Work out the path to the root from where the script is being run. Allows for
    calling setup.py env from sub directories and directories outside the main dir
    """
    fullPath = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(), sys.argv[0])))
    if appendLocation:
        return "%s/%s" % (fullPath, appendLocation)
    return fullPath


def list_packages(packageDirs=None, recurse=True, ignoreThese=None, pyFiles=False):
    """
    Take a list of directories and return a list of all packages under those directories,
    Skipping 'CVS', '.svn', 'svn', '.git', '', 'dtnrmagent.egg-info' files.
    """
    if not packageDirs:
        packageDirs = []
    if not ignoreThese:
        ignoreThese = set(['CVS', '.svn', 'svn', '.git', '', 'dtnrmagent.egg-info'])
    else:
        ignoreThese = set(ignoreThese)
    packages = []
    modules = []
    # Skip the following files
    for aDir in packageDirs:
        if recurse:
            # Recurse the sub-directories
            for dirpath, dummyDirnames, dummyFilenames in os.walk('%s' % aDir, topdown=True):
                pathelements = dirpath.split('/')
                # If any part of pathelements is in the ignore_these set skip the path
                if len(set(pathelements) & ignoreThese) == 0:
                    relPath = os.path.relpath(dirpath, get_path_to_root())
                    relPath = relPath.split('/')[2:]
                    if not pyFiles:
                        packages.append('.'.join(relPath))
                    else:
                        for fileName in dummyFilenames:
                            if fileName.startswith('__init__.') or \
                               fileName.endswith('.pyc') or \
                               not fileName.endswith('.py'):
                                # print('Ignoring %s' % fileName)
                                continue
                            relName = fileName.rsplit('.', 1)
                            modules.append("%s.%s" % ('.'.join(relPath), relName[0]))
                else:
                    continue
                    # print('Ignoring %s' % dirpath)
        else:
            relPath = os.path.relpath(aDir, get_path_to_root())
            relPath = relPath.split('/')[2:]
            packages.append('.'.join(relPath))
    if pyFiles:
        return modules
    return packages


def get_py_modules(modulesDirs):
    """ Get py modules for setup.py """
    return list_packages(modulesDirs, pyFiles=True)


def readFile(fileName):
    """Read all file lines to a list and rstrips the ending"""
    with open(fileName) as fd:
        content = fd.readlines()
    content = [x.rstrip() for x in content]
    return content


def createDirs(fullDirPath):
    """Create dir if directory does not exist"""
    if not os.path.isdir(fullDirPath):
        try:
            os.makedirs(fullDirPath)
        except OSError as ex:
            print 'Received exception creating %s directory. Exception: %s' % (fullDirPath, ex)
    return

def getConfig(locations):
    """ Get parsed configuration """
    tmpCp = ConfigParser.ConfigParser()
    for fileName in locations:
        if os.path.isfile(fileName):
            tmpCp.read(fileName)
            return tmpCp
    return None

def createAllDirsFromConfig(config, mainDir):
    """ Create all directories from each configuration section: basedir, logDir, privateDir """
    for section in config.sections():
        if not config.has_option(section, 'basedir'):
            createDirs("%s/%s/" % (mainDir, section))
        for varName in ['basedir', 'logDir', 'privateDir']:
            if config.has_option(section, varName):
                createDirs(config.get(section, varName))
