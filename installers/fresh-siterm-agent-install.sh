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
# Title             : dtnrm
# Author            : Justas Balcas
# Email             : justas.balcas (at) cern.ch
# @Copyright        : Copyright (C) 2016 California Institute of Technology
# Date            : 2017/09/26
# =============================================================================
##H fresh-siterm-agent-install.sh [OPTIONS]
##H
##H Deploy all needed stuff for dtn-rm
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

workdir=`pwd`
packages="git autoconf automake sudo libcurl-devel libffi-devel python3-lxml openssl-devel curl gcc traceroute libuuid-devel lm_sensors ipset make nc pkgconfig python38 python38-pyyaml zlib-devel python3-devel wget tcpdump jq iproute cronie python3-pip wireshark iperf3 iproute-tc diffutils fetch-crl procps-ng mariadb-devel"

while [ $# -ge 1 ]; do
  case $1 in
    -R ) rootdir="$2"; shift; shift ;;
    -T ) tmpdir="$2"; shift; shift;;
    -H ) hostname="$2"; shift; shift;;
    -G ) gitr="$2"; shift; shift;;
    -O ) gito="$2"; shift; shift;;
    -B ) gitb="$2"; shift; shift;;
    -D ) docker="$2": shift; shift;;
    -h ) perl -ne '/^##H/ && do { s/^##H ?//; print }' < $0 1>&2; exit 1 ;;
    -* ) echo "$0: unrecognized option $1, use -h for help" 1>&2; exit 1 ;;
    *  ) break ;;
  esac
done

# =======================================================================
# Do all checks and if all needed parameters are specified.
if [ X"$rootdir" = X ]; then
  echo "Usage: fresh-siterm-agent-install.sh [OPTIONS] (use -h for help)" 1>&2
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
  python3 setup-agent.py install || exit $?
else
  python3 setup-agent.py install --docker || exit $?
fi

for x in iprange firehol
do
    if [ ! -d /usr/src/${x}.git ]
        then
        echo "Downloading (git clone) ${x}..."
        git clone https://github.com/firehol/${x}.git /usr/src/${x}.git || exit 1
    else
        echo "Downloading (git pull) ${x}..."
        cd /usr/src/${x}.git || exit 1
        git pull || exit 1
    fi
done

echo
echo "Building iprange..."
cd /usr/src/iprange.git || exit 1
./autogen.sh || exit 1
./configure --prefix=/usr CFLAGS="-O2" --disable-man || exit 1
make clean
make || exit 1
make install || exit 1

echo
echo "Building firehol..."
cd /usr/src/firehol.git || exit 1
./autogen.sh || exit 1
./configure --prefix=/usr --sysconfdir=/etc --localstatedir=/var --disable-man --disable-doc || exit 1
make clean
make || exit 1
make install || exit 1

touch /etc/firehol/fireqos.conf

echo "==================================================================="
echo "==================================================================="
echo "==================================================================="
echo "                       INSTALLATION DONE                           "
echo "==================================================================="
echo "Please check the following things:"
echo "   1. Make sure your GIT Config is ok in official GIT Repo"
echo "   2. Service to start:"
echo "         a) 'dtnrmagent-update start' which updates about all information of DTN"
echo "         b) 'dtnrm-ruler start' which looks for new requests and applies rules"
echo "         c) 'dtnrm-nettester start' (OPTIONAL) This is network tester which will start transfers automatically"
echo "             This requires to define correct secrets.sh file for communicating with Orchestrator. Location /opt/sense-client/"
exit 0
