#!/bin/bash

# TODO, check that openssl library is installed;
# TODO, check that letsencrypt certbot is installed;

while [ $# -ge 1 ]; do
  case $1 in
    --certissuer ) certissuer="$2"; shift; shift;;
    --docker ) docker="$2"; shift; shift;;
    -h ) perl -ne '/^##H/ && do { s/^##H ?//; print }' < $0 1>&2; exit 1 ;;
    -* ) echo "$0: unrecognized option $1, use -h for help" 1>&2; exit 1 ;;
    *  ) break ;;
  esac
done

# =======================================================================
if [ X"$certissuer" = X ]; then
  echo "--certissuer option is required. How do you want to request certificate?"
  echo "1) Using OpenSSL and creating own Root CA and Self Signed certificate?"
  echo "2) Using LetsEncrypt? This requires port 443 open on the host."
  echo "3) Other... (Manually installed certificate)"  
  read n
  case $n in
    1) certissuer="openssl";;
    2) certissuer="letsencrypt";;
    3) certissuer="other";;
    *) echo "invalid option";;
  esac
fi

if [ X"$docker" = X ]; then
  echo "--docker option is required. Is this certificate request for docker container?"
  echo "1) yes"
  echo "2) no"
  read n
  case $n in
    1) docker=yes;;
    2) docker=no;;
    *) echo "invalid option";;
  esac
fi


echo "---------------------------------------"
echo "Install type: $certissuer"
echo "For Service type: $docker"
echo "---------------------------------------"

if [ "$certissuer" = "openssl" ]; then
  # make directories to work from
  echo "What is the hostname of this endhost?"
  read FQDN
  echo 'To generate certificate, it requires you to enter few inputs, like:'
  echo 'O: Organization'
  echo 'L: Locality'
  echo 'ST: State'
  echo 'C: CountryName'
  echo "IMPORTANT: There is no validation done for your input."
  echo "Please enter C: CountryName (e.g.: US):"
  read countryname
  echo "Please enter ST: State (e.g.: California):"
  read statename
  echo "Please enter L: Locality (e.g.: Pasadena):"
  read localityname
  echo "Please enter O: Organization (e.g.: Caltech):"
  read organizationname

  mkdir -p certs/{server,client,ca,tmp}

  # Create your very own Root Certificate Authority
  openssl genrsa \
    -out certs/ca/my-root-ca.key.pem \
    2048

  # Self-sign your Root Certificate Authority
  # Since this is private, the details can be as bogus as you like
  openssl req \
    -x509 \
    -new \
    -nodes \
    -key certs/ca/my-root-ca.key.pem \
    -days 1024 \
    -out certs/ca/my-root-ca.crt.pem \
    -subj "/C=$countryname/ST=$statename/L=$localityname/O=$organizationname/CN=$FQDN"

  # Create a Device Certificate for each domain,
  # such as example.com, *.example.com, awesome.example.com
  # NOTE: You MUST match CN to the domain name or ip address you want to use
  openssl genrsa \
    -out certs/server/privkey.pem \
    2048

  # Create a request from your Device, which your Root CA will sign
  openssl req -new \
    -key certs/server/privkey.pem \
    -out certs/tmp/csr.pem \
    -subj "/C=${countryname}/ST=${statename}/L=${localityname}/O=${organizationname}/CN=${FQDN}"

  # Sign the request from Device with your Root CA
  # -CAserial certs/ca/my-root-ca.srl
  openssl x509 \
    -req -in certs/tmp/csr.pem \
    -CA certs/ca/my-root-ca.crt.pem \
    -CAkey certs/ca/my-root-ca.key.pem \
    -CAcreateserial \
    -out certs/server/cert.pem \
    -days 500

  # Create a public key, for funzies
  # see https://gist.github.com/coolaj86/f6f36efce2821dfb046d
  openssl rsa \
    -in certs/server/privkey.pem \
    -pubout -out certs/client/pubkey.pem

  # Put things in their proper place
  rsync -a certs/ca/my-root-ca.crt.pem certs/server/chain.pem
  rsync -a certs/ca/my-root-ca.crt.pem certs/client/chain.pem
  cat certs/server/cert.pem certs/server/chain.pem > certs/server/fullchain.pem
  if [ "$docker" = "yes" ]; then
    echo "What is the docker configuration directory? If you run this script from downloaded git repo, it is ../fe-docker/ or ../agent-docker/"
    read dockerdir
    echo "Copying certificated to $dockerdir"
    mkdir -p $dockerdir/conf/etc/httpd/certs/
    mkdir -p $dockerdir/conf/etc/grid-security/
    cp certs/server/* $dockerdir/conf/etc/httpd/certs/
    cp certs/server/cert.pem $dockerdir/conf/etc/grid-security/hostcert.pem
    cp certs/server/privkey.pem $dockerdir/conf/etc/grid-security/hostkey.pem
    python cert-checker.py $dockerdir/conf/etc/httpd/certs/cert.pem
  else
    mkdir -p /etc/httpd/certs/
    mkdir -p /etc/grid-security/
    cp certs/server/* /etc/httpd/certs/
    cp certs/server/cert.pem /etc/grid-security/hostcert.pem
    cp certs/server/privkey.pem /etc/grid-security/hostkey.pem
    python cert-checker.py /etc/httpd/certs/cert.pem
  fi
elif [ "$certissuer" = "letsencrypt" ]; then
    echo "Please refer to certbot documentation to install certbot: https://certbot.eff.org"
    echo "What is the hostname of this endhost?"
    read FQDN
    sudo certbot certonly --standalone -d $FQDN
    if [ "$docker" = "yes" ]; then
      echo "What is the docker configuration directory? If you run this script from downloaded git repo, it is ../fe-docker/ or ../agent-docker/"
      read dockerdir
      echo "Copying certificated to $dockerdir"
      mkdir -p $dockerdir/conf/etc/httpd/certs/
      mkdir -p $dockerdir/conf/etc/grid-security/
      cp -L /etc/letsencrypt/live/$FQDN/* $dockerdir/conf/etc/httpd/certs/
      cp -L /etc/letsencrypt/live/$FQDN/cert.pem $dockerdir/conf/etc/grid-security/hostcert.pem
      cp -L /etc/letsencrypt/live/$FQDN/privkey.pem $dockerdir/conf/etc/grid-security/hostkey.pem
      python cert-checker.py $dockerdir/conf/etc/httpd/certs/cert.pem
    else
      mkdir -p /etc/httpd/certs/
      mkdir -p /etc/grid-security/
      cp -L /etc/letsencrypt/live/$FQDN/* /etc/httpd/certs/
      cp -L /etc/letsencrypt/live/$FQDN/cert.pem /etc/grid-security/hostcert.pem
      cp -L /etc/letsencrypt/live/$FQDN/privkey.pem /etc/grid-security/hostkey.pem
      python cert-checker.py /etc/httpd/certs/cert.pem
   fi
fi
