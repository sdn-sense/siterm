#!/usr/bin/env python3
"""Certificate validity checker."""
import sys
import subprocess
try:
    from OpenSSL import crypto
except ImportError as ex:
    print('Failed to import OpenSSL. Will use command line to check cert validity')


def printInfo(inDict):
    """Print Certificate information to stdout."""
    inDict['fullDN'] = "%s%s" % (inDict['issuer'], inDict['subject'])
    print('Cert Info: %s' % inDict)
    print('Certificate Subject:     ', inDict['subject'])
    print('Certificate Valid From:  ', inDict['notAfter'])
    print('Certificate Valid Until: ', inDict['notBefore'])
    print('Certificate Issuer:      ', inDict['issuer'])
    print('Certificate Full DN:     ', inDict['fullDN'])
    print('-'*80)
    print('INFO: Please ensure that Certificate full DN is entered in GIT Repo for the Frontend.')
    print('INFO: In case it is custom certificate, you will need to put ca in Fronend to trust local issued certificate')
    print('-'*80)

def getCertInfoCMD(certLocation):
    """Get Certificate information using openssl command line."""
    cmd = "openssl x509 -in %s -subject -issuer -noout -dates" % certLocation
    proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    out = {}
    for line in stdout.split("\n"):
        if not line: continue
        vars = line.split("=", 1)
        out[vars[0].strip()] = vars[1].strip()
    printInfo(out)

def getCertInfoOpenSSL(certLocation):
    """Get Certificate information using OpenSSL Library."""
    out = {}
    certF=open(certLocation, 'rt').read()
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, certF)
    subject = cert.get_subject()
    out['subject'] = "".join("/{0:s}={1:s}".format(name.decode(), value.decode()) for name, value in subject.get_components())
    out['notAfter'] = cert.get_notAfter()
    out['notBefore'] = cert.get_notBefore()
    out['issuer'] = "".join("/{0:s}={1:s}".format(name.decode(), value.decode()) for name, value in cert.get_issuer().get_components())
    printInfo(out)

if __name__ == '__main__':
    print('Argument must be certificate file. Passed arguments %s' % sys.argv)
    if 'OpenSSL.crypto' not in sys.modules:
        getCertInfoCMD(sys.argv[1])
    else:
        getCertInfoOpenSSL(sys.argv[1])
