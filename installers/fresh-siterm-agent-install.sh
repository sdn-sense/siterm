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
##H  -P PORT        Time Series database repository port. No default;
##H  -I IP          Time Series database IP or hostname. No default;
##H  -U PROTOCOL    Time Series database protocol. By default tcp
##H  -G GITREPO     Git Repo to use for installation. default sdn-sense
##H  -D anyvalue    this flag tells that this is docker installation. It will skip copying config files
##H  -h             Display this help.

# TODO also force to specify FE URL, FE Port; TSDB parameters it should get from FE.
# Other configuration users have to specify by himself.
workdir=`pwd`
packages="git autoconf automake curl gcc traceroute libmnl-devel libuuid-devel lm_sensors ipset make MySQL-python nc pkgconfig python python-psycopg2 PyYAML zlib-devel python-devel wget vconfig tcpdump jq iproute"
# Check if release is supported.
# TODO. Support other releases also.
case $(uname) in
  Linux  ) linuxmajor=$(egrep -o 'release [0-9]+{1}\.' /etc/redhat-release|cut -d" " -f2|tr -d .)
           case $linuxmajor in
             6 ) arch=slc6_amd64_gcc481 ;;
             7 ) arch=slc7_amd64_gcc630 ;;
           esac
           xargsr="xargs -r"
           ;;
  *      ) echo "unsupported architecture" 1>&2; exit 1 ;;
esac

while [ $# -ge 1 ]; do
  case $1 in
    -R ) rootdir="$2"; shift; shift ;;
    -T ) tmpdir="$2"; shift; shift;;
    -N ) netdatarelease="$2"; shift; shift;;
    -H ) hostname="$2"; shift; shift;;
    -P ) tsdport="$2"; shift; shift;;
    -I ) tsdip="$2"; shift; shift;;
    -U ) tsdp="$2"; shift; shift;;
    -G ) gitr="$2"; shift; shift;;
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

if [ X"$netdatarelease" = X ]; then
    netdatarelease=1.8.0
fi

if [ X"$hostname" = X ]; then
    hostname=`hostname -f`
fi

HISTORYDB=true
if [ X"$tsdport" = X ]; then
  HISTORYDB=false
  echo "WARNING: Repository port is not specified." 1>&2
fi

if [ X"$tsdp" = X ]; then
  tsdp=tcp
fi

if [ X"$tsdip" = X ]; then
  HISTORYDB=false
  echo "WARNING: Repository ip is not specified." 1>&2
fi

if [ X"$gitr" = X ]; then
  echo "WARNING: Git Repo not set. using default sdn-sense is not specified." 1>&2
  gitr=sdn-sense
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

echo 'Installing and upgrading pip.'
cd $tmpdir
wget https://bootstrap.pypa.io/get-pip.py
python get-pip.py

# Check if netdata is already installed. If it is skip re-installing
service netdata status
netdataExit=$?
if [ "$netdataExit" -ne 0 ]; then
  echo "==================================================================="
  echo "Installing netdata release $netdatarelease"
  # Receive netdata release and also untar it
  rm -rf $tmpdir/netdata-$netdatarelease
  cd $tmpdir
  [ -f netdata-$netdatarelease.tar.gz ] || wget https://github.com/firehol/netdata/releases/download/v$netdatarelease/netdata-$netdatarelease.tar.gz || exit $?
  tar -xf netdata-$netdatarelease.tar.gz -C $tmpdir || exit $?
  cd $tmpdir/netdata-$netdatarelease
  ./netdata-installer.sh --dont-wait --install $rootdir || exit $?
  cd ..
  rm -rf $tmpdir/netdata-$netdatarelease
  # Append few configs so that netdata consumes less memory
  echo 1 >/sys/kernel/mm/ksm/run
  echo 1000 >/sys/kernel/mm/ksm/sleep_millisecs
else
  echo "Netdata is already installed. Skipping re-installation"
fi

echo "==================================================================="
echo "We need latest setuptools to be able to install dtnrm package. Updating setuptools"
pip install --upgrade setuptools

echo "==================================================================="
echo "Cloning siterm and installing it"
cd $rootdir
rm -rf siterm
git clone https://github.com/$gitr/siterm
cd siterm
if [ X"$docker" = X ]; then
  python setup-agent.py install || exit $?
else
  python setup-agent.py install --docker || exit $?
fi

echo "==================================================================="
if [ "$HISTORYDB" = true ] ; then
  echo "Copying netdata configuration file and modifying it"
  netdataconf=$rootdir/netdata/etc/netdata/netdata.conf
  if [ -f $netdataconf ]; then
    echo "Current config file:"
    cat $netdataconf
    echo ""
    echo "-------------------------------------------------------------------"
  fi
  if [ -f packaging/netdata.conf ]; then
    echo "Overwriting with temporary config file:"
    cat packaging/netdata.conf
    cp packaging/netdata.conf $netdataconf
    echo ""
    echo "-------------------------------------------------------------------"
  fi
  perl -pi -e "s/##HOSTNAME##/$hostname/g" $netdataconf
  perl -pi -e "s/##REPOPORT##/$tsdport/g" $netdataconf
  perl -pi -e "s/##REPOIP##/$tsdip/g" $netdataconf
  perl -pi -e "s/##REPOPROT##/$tsdp/g" $netdataconf
  echo "Final configuration file:"
  cat $netdataconf
  echo ""
  echo "==================================================================="
  echo "Restarting netdata"
  # SLC6 is still missing this: https://github.com/firehol/netdata/pull/2805
  sudo service netdata restart
else
  echo "WARNING: Netdata configuration was not modified. you will have to do it by hand."
  echo "-------------------------------------------------------------------"
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
echo "   1. /etc/dtnrm/main.conf file and that all parameters are correct. For more information on parameters see:"
echo "        https://github.com/sdn-sense/siterm-agent/wiki/SiteRM-Agent-Configuration-parameters"
echo "   2. $netdataconf file and that all backend parameters are correct if want to backup endhost metrics."
echo "      It should report only to sensedtn opentsdb listener"
echo "   3. Service to start:"
echo "         a) 'dtnrmagent-update start' which updates about all information of DTN"
echo "         b) 'dtnrm-ruler start' which looks for new requests and applies rules"
echo "         c) 'dtnrm-nettester start' (OPTIONAL) This is network tester which will start transfers automatically"
echo "             This requires to define correct secrets.sh file for communicating with Orchestrator. Location /opt/sense-client/"
exit 0
