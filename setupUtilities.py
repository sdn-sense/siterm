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
VERSION = '1.5.2'


def get_path_to_root(appendLocation=None):
    """Work out the path to the root from where the script is being run.

    Allows for calling setup.py env from sub directories and directories
    outside the main dir
    """
    fullPath = os.path.dirname(os.path.abspath(os.path.join(os.getcwd(), sys.argv[0])))
    if appendLocation:
        return f"{fullPath}/{appendLocation}"
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
            for dirpath, dummyDirnames, dummyFilenames in os.walk(aDir, topdown=True):
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
                            modules.append(f"{'.'.join(relPath)}.{relName[0]}")
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

# Collect all files in packaging/release_mods recursively
def collect_files(src_dir, target_dir):
    """Collect and append all files in src_dir to target_dir."""
    paths = []
    for root, _, files in os.walk(src_dir):
        for file in files:
            full_path = os.path.join(root, file)
            install_path = os.path.join(target_dir, os.path.relpath(full_path, src_dir))
            paths.append((os.path.dirname(install_path), [full_path]))
    return paths
