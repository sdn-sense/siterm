#!/usr/bin/env python3
"""Utilities which are used in any setup script.

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
Title                   : siterm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
"""
import os
import sys

# IMPORTANT Be aware if you update version here, please update it also in:
# setupUtilities.py
# src/python/__init__.py
# src/python/SiteFE/__init__.py
# src/python/SiteRMAgent/__init__.py
# src/python/SiteRMLibs/__init__.py
VERSION = '1.3.0'


def get_path_to_root(appendLocation=None):
    """Work out the path to the root from where the script is being run.

    Allows for calling setup.py env from sub directories and directories
    outside the main dir
    """
    fullPath = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(), sys.argv[0])))
    if appendLocation:
        return "%s/%s" % (fullPath, appendLocation)
    return fullPath


def list_packages(packageDirs=None, recurse=True, ignoreThese=None, pyFiles=False):
    """Take a list of directories and return a list of all packages under those
    directories, Skipping 'CVS', '.svn', 'svn', '.git', '', 'sitermagent.egg-
    info' files."""
    if not packageDirs:
        packageDirs = []
    if not ignoreThese:
        ignoreThese = set(['CVS', '.svn', 'svn', '.git', '', 'sitermagent.egg-info'])
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
                if not list(set(pathelements) & ignoreThese):
                    relPath = os.path.relpath(dirpath, get_path_to_root())
                    relPath = relPath.split('/')[2:]
                    if not pyFiles:
                        packages.append('.'.join(relPath))
                    else:
                        for fileName in dummyFilenames:
                            if fileName.startswith('__init__.') or \
                               fileName.endswith('.pyc') or \
                               not fileName.endswith('.py'):
                                continue
                            relName = fileName.rsplit('.', 1)
                            modules.append("%s.%s" % ('.'.join(relPath), relName[0]))
                else:
                    continue
        else:
            relPath = os.path.relpath(aDir, get_path_to_root())
            relPath = relPath.split('/')[2:]
            packages.append('.'.join(relPath))
    if pyFiles:
        return modules
    return packages


def get_py_modules(modulesDirs):
    """Get py modules for setup.py."""
    return list_packages(modulesDirs, pyFiles=True)


def get_web_files(rootdir='/var/www/html'):
    """Get all files to copy to html dir"""
    maindir = os.path.abspath(os.getcwd())
    htmldir = os.path.join(maindir, 'src/html/')
    htmldirs = [htmldir]
    out = []
    for dirN in htmldirs:
        allFiles = []
        for fName in os.listdir(dirN):
            newpath = os.path.join(dirN, fName)
            if os.path.isdir(newpath):
                htmldirs.append(newpath)
                continue
            fPath = newpath[len(maindir)+1:]
            allFiles.append(fPath)
        out.append((os.path.join(rootdir, dirN[len(htmldir):]), allFiles))
    return out
