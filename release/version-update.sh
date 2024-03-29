#!/bin/bash
# Copyright 2017 California Institute of Technology
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
# Title             : siterm
# Author            : Justas Balcas
# Email             : justas.balcas (at) cern.ch
# @Copyright        : Copyright (C) 2021 California Institute of Technology
# Date            : 2021/02/08
# =============================================================================

SOURCE="${BASH_SOURCE[0]}"
SDIR=`dirname "$SOURCE"`
FDIR="$(realpath "${SDIR}")"

if [ $# -eq 0 ]
  then
    echo "No arguments supplied. Please provide version argument in the following format: version-update.sh <NEW_VERSION_ID>"
    exit 1
fi

NEW_VERSION=$1

# Check if this version is not already released on github.
# If it is - fail
git_tag_conflict=`git tag | grep $NEW_VERSION`
if [ $git_tag_conflict -ne 0 ];
  then
    echo "This $NEW_VERSION already exists in git repo. Please make sure you create unique version";
    exit 1;
  fi;


sed -i "s/.*VERSION = .*/VERSION = '$NEW_VERSION'/" $FDIR/../setupUtilities.py
sed -i "s/.*__version__ = .*/__version__ = '$NEW_VERSION'/" $FDIR/../src/python/__init__.py
sed -i "s/.*__version__ = .*/__version__ = '$NEW_VERSION'/" $FDIR/../src/python/SiteFE/__init__.py
sed -i "s/.*__version__ = .*/__version__ = '$NEW_VERSION'/" $FDIR/../src/python/SiteRMLibs/__init__.py
sed -i "s/.*__version__ = .*/__version__ = '$NEW_VERSION'/" $FDIR/../src/python/SiteRMAgent/__init__.py

echo "IMPORTANT: Please update release_notes file with changes from previous version"
echo "Issue `git add` command and add all new version files"
echo "Issue `git commit -m 'Release of $NEW_VERSION'`"

echo "git tag -a $NEW_VERSION -F release_notes "
echo "git push origin --tags "
