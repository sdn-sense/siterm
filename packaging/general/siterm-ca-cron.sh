#!/bin/sh

TMP_DIR=$(mktemp -d)
GIT_REPO=`cat /etc/dtnrm.yaml | grep 'GIT_REPO' | awk '{print $2}' | tr -d '"' | tr -d "'"`
CA_DIR=/etc/grid-security/certificates

cd $TMP_DIR
git clone https://github.com/$GIT_REPO .

cd $TMP_DIR/CAs/
for fname in `ls *.pem`; do
  cp $fname $CA_DIR/
  hash=$(openssl x509 -hash -in "$CA_DIR/$fname" |head -n 1)
  ln -sf $CA_DIR/$fname $CA_DIR/$hash.0
done
