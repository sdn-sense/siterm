#!/bin/sh
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
# Title 			: SiteRM-FE
# Author			: Justas Balcas
# Email 			: justas.balcas (at) cern.ch
# @Copyright	  	        : Copyright (C) 2016 California Institute of Technology
# Date		        	: 2017/09/26
# =============================================================================
##H fresh-siterm-fe-install.sh [OPTIONS]
##H
##H Deploy all needed stuff for dtn-rm site-fe, called sensei
##H
##H Possible options:
##H  -R DIR         ROOT directory for installation;
##H  -T DIR         TMP Directory for temporary data;
##H  -H HOST        Hostname of this node; By default uses `hostname -f` output
##H  -G GITREPO     Git Repo to use for installation. default siterm
##H  -O GITORG      Git Organization or user. default sdn-sense
##H  -B GITBR       Git Branch to use. default master
##H  -D anyvalue    this flag tells that this is docker installation. It will skip copying config files
##H  -h             Display this help.

# TODO also force to specify TSDB parameters it should get from FE.
# TODO. data directory should come from configuration parameter
datadir=/opt/config/
workdir=`pwd`
packages="git autoconf sudo libcurl-devel libffi-devel openssl-devel automake curl gcc libuuid-devel lm_sensors make nc pkgconfig wget zlib-devel python3-devel httpd httpd-devel python3-mod_wsgi mod_ssl cronie python3-pip python38 python3-pyOpenSSL mariadb-server python38-pyyaml python3-mysql mariadb-devel fetch-crl"
# Check if release is supported.

while [ $# -ge 1 ]; do
  case $1 in
    -R ) rootdir="$2"; shift; shift ;;
    -T ) tmpdir="$2"; shift; shift;;
    -H ) hostname="$2"; shift; shift;;
    -G ) gitr="$2"; shift; shift;;
    -O ) gito="$2"; shift; shift;;
    -B ) gitb="$2"; shift; shift;;
    -D ) docker="$2"; shift; shift;;
    -h ) perl -ne '/^##H/ && do { s/^##H ?//; print }' < $0 1>&2; exit 1 ;;
    -* ) echo "$0: unrecognized option $1, use -h for help" 1>&2; exit 1 ;;
    *  ) break ;;
  esac
done

# =======================================================================
# Do all checks and if all needed parameters are specified.
if [ X"$rootdir" = X ]; then
  echo "Usage: fresh-siterm-fe-install.sh [OPTIONS] (use -h for help)" 1>&2
  exit 1
fi

if [ X"$tmpdir" = X ]; then
    tmpdir=/tmp/foo/
fi

if [ X"$hostname" = X ]; then
    hostname=`hostname -f`
fi

if [ X"$gitr" = X ]; then
  echo "WARNING: Git Repo not set. using default siterm is not specified." 1>&2
  gitr=siterm
fi

if [ X"$gito" = X ]; then
  echo "WARNING: Git Organization not set. using default sdn-sense is not specified." 1>&2
  gito=sdn-sense
fi

if [ X"$gitb" = X ]; then
  echo "WARNING: Git Branch not set. using default master is not specified." 1>&2
  gitb=master
fi

# =======================================================================
# Checking if running as root
echo '==================================================================='
echo 'Checking if running as root'
if [[ $(id -u) -ne 0 ]] ; then echo "Please run this script as root" ; exit 1 ; fi

# =======================================================================
# Installing packages.
echo '==================================================================='
echo 'Installing required packages through yum.'
echo "Packages: $packages"
yum install -y epel-release
yum install -y $packages

# Make sure root directory is there
[ -d $rootdir ] || mkdir -p $rootdir || exit $?
# Also make a tmp directory
[ -d $tmpdir ] || mkdir -p $tmpdir || exit $?

echo "==================================================================="
echo "We need latest setuptools to be able to install dtnrm package. Updating setuptools"
pip3 install --upgrade setuptools

echo "==================================================================="
echo "Cloning siterm and installing it"
cd $rootdir
rm -rf $gitr
git clone -b $gitb https://github.com/$gito/$gitr

cd $gitr

if [ X"$docker" = X ]; then
  python3 setup-sitefe.py install || exit $?
else
  python3 setup-sitefe.py install --docker || exit $?
fi

  echo "==================================================================="
  echo "Modifying ownership and permission rules for Site FE directories"
  echo "-------------------------------------------------------------------"

  # Remove ssl.conf - we have all defined inside the sitefe-httpd.conf
  rm -f /etc/httpd/conf.d/ssl.conf
  # Ownership
  echo "1. Making apache as owner of $datadir"
  chown apache:apache -R $datadir
  cd $datadir
  # File permissions, recursive
  echo "2. Recursive file permissions to 0644 in $datadir"
  find . -type f -exec chmod 0644 {} \;
  # Dir permissions, recursive
  echo "3. Recursive directory permissions to 0755 in $datadir"
  find . -type d -exec chmod 0755 {} \;

if [ X"$docker" = X ]; then
  # SELinux serve files off Apache, resursive
  echo "4. Apply SELinux rule to allow Apache serve files from $datadir"
  chcon -t httpd_sys_content_t $datadir -R
  # Allow write only to specific dirs
  chcon -t httpd_sys_rw_content_t $datadir -R
  echo "5. Applying mod_proxy policy change so that it can write remotely."
  echo "   More details: http://sysadminsjourney.com/content/2010/02/01/apache-modproxy-error-13permission-denied-error-rhel/"
  /usr/sbin/setsebool -P httpd_can_network_connect 1
fi

echo "==================================================================="
echo "==================================================================="
echo "==================================================================="
echo "                       INSTALLATION DONE                           "
echo "==================================================================="
echo "Please check the following things:"
echo "   1. Configuration changes:"
echo "      Your configuration is correct on GIT Repo."
echo "   2. Start httpd service"
echo "   3. Execute all services and see if they work (While it is fresh install, just see if there is no obvious errors):"
echo "        a) LookUpService-update: MRML template preparation about all DTNs and Switches. "
echo "        b) PolicyService-update: That deltas are accepted and it works"
echo "        c) ProvisioningService-Update: That provisions deltas."
echo "   4. Make sure firewalld has port 443/tcp"
exit 0
