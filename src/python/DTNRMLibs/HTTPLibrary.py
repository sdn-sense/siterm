#!/usr/bin/env python
"""
HTTP library for HTTP(s) communication
Parts of code are taken from dmwm/WMCore (CMS)

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
import base64
import urlparse
import urllib
from DTNRMLibs.pycurl_manager import RequestHandler
from DTNRMLibs.CustomExceptions import ValidityFailure

def argValidity(arg, aType):
    """ Argument validation """
    if not arg:
        return {} if aType == dict else []
    if aType == dict:
        if isinstance(arg, dict):
            return arg
    elif aType == list:
        if isinstance(arg, list):
            return arg
    else:
        raise ValidityFailure("Input %s != %s." % (type(arg), aType))


def check_server_url(url):
    """Check if given url starts with http tag"""
    goodName = url.startswith('http://') or url.startswith('https://')
    if not goodName:
        msg = "You must include http(s):// in your server's address, %s doesn't" % url
        raise ValueError(msg)


def sanitizeURL(url):
    """Take the url with/without username and password and return sanitized url,
       username and password in dict format
       ':' is not supported in username or password.
    """
    endpointComponents = urlparse.urlparse(url)
    if endpointComponents.port:
        netloc = '%s:%s' % (endpointComponents.hostname,
                            endpointComponents.port)
    else:
        netloc = endpointComponents.hostname
    url = urlparse.urlunparse(
        [endpointComponents.scheme,
         netloc,
         endpointComponents.path,
         endpointComponents.params,
         endpointComponents.query,
         endpointComponents.fragment])

    return {'url': url, 'username': endpointComponents.username,
            'password': endpointComponents.password}


def encodeRequest(configreq, listParams=None):
    """ Used to encode the request from a dict to a string.
    Include the code needed for transforming lists in the format
    required by the server.
    """
    if not listParams:
        listParams = []
    encodedLists = ''
    for lparam in listParams:
        if lparam in configreq:
            if len(configreq[lparam]) > 0:
                encodedLists += ('&%s=' % lparam) + ('&%s=' % lparam).join(map(urllib.quote, configreq[lparam]))
            del configreq[lparam]
    encoded = urllib.urlencode(configreq) + encodedLists
    return str(encoded)


class Requests(dict):
    """Make any type of HTTP(s) request"""
    def __init__(self, url='http://localhost', inputdict=None, config=None):
        if not inputdict:
            inputdict = {}
        # set up defaults
        self.setdefault("accept_type", 'application/json')
        self.setdefault("content_type", ' application/json')
        self.additionalHeaders = {}

        self.reqmgr = RequestHandler()
        # check for basic auth early, as if found this changes the url
        urlComponent = sanitizeURL(url)
        if urlComponent['username'] is not None:
            self.addBasicAuth(urlComponent['username'], urlComponent['password'])
            url = urlComponent['url']  # remove user, password from url

        self.setdefault("host", url)
        self.update(inputdict)
        self['endpoint_components'] = urlparse.urlparse(self['host'])

        check_server_url(self['host'])

    def addBasicAuth(self, username, password):
        """Add basic auth headers to request if user/pass is used"""
        authString = "Basic %s" % base64.encodestring('%s:%s' % (
            username, password)).strip()
        self.additionalHeaders["Authorization"] = authString

    def get(self, uri=None, data=None, incoming_headers=None,
            encode=True, decode=True, contentType=None):
        """
        GET some data
        """
        incoming_headers = argValidity(incoming_headers, dict)
        return self.makeRequest(uri, data, 'GET', incoming_headers,
                                encode, decode, contentType)

    def post(self, uri=None, data=None, incoming_headers=None,
             encode=True, decode=True, contentType=None):
        """
        POST some data
        """
        incoming_headers = argValidity(incoming_headers, dict)
        return self.makeRequest(uri, data, 'POST', incoming_headers,
                                encode, decode, contentType)

    def put(self, uri=None, data=None, incoming_headers=None,
            encode=True, decode=True, contentType=None):
        """
        PUT some data
        """
        incoming_headers = argValidity(incoming_headers, dict)
        return self.makeRequest(uri, data, 'PUT', incoming_headers,
                                encode, decode, contentType)

    def delete(self, uri=None, data=None, incoming_headers=None,
               encode=True, decode=True, contentType=None):
        """
        DELETE some data
        """
        incoming_headers = argValidity(incoming_headers, dict)
        return self.makeRequest(uri, data, 'DELETE', incoming_headers,
                                encode, decode, contentType)

    def makeRequest(self, uri=None, data=None, verb='GET', incoming_headers=None,
                    encoder=True, decoder=True, contentType=None):
        """
        Make HTTP(s) request via pycurl library. Stay complaint with
        makeRequest_httplib method.
        """
        del encoder
        incoming_headers = argValidity(incoming_headers, dict)
        ckey, cert = self.getKeyCert()
        capath = self.getCAPath()
        if not contentType:
            contentType = self['content_type']
        headers = {"Content-type": contentType,
                   "User-agent": "DTN-RM",
                   "Accept": self['accept_type']}
        for key, value in self.additionalHeaders.items():
            headers[key] = value
        # And now overwrite any headers that have been passed into the call:
        headers.update(incoming_headers)
        url = self['host'] + uri
        response, data = self.reqmgr.request(url, data, headers, verb=verb,
                                             ckey=ckey, cert=cert, capath=capath, decode=decoder)
        return data, response.status, response.reason, response.fromcache

    def getKeyCert(self):
        """
        Get the user credentials if they exist, otherwise throw an exception.
        """
        key, cert = getKeyCertFromEnv()
        return key, cert

    def getCAPath(self):
        """
        _getCAPath_
        Return the path of the CA certificates. The check is loose in the pycurl_manager:
        is capath == None then the server identity is not verified. To enable this check
        you need to set either the X509_CERT_DIR variable or the cacert key of the request.
        """
        capath = getCAPathFromEnv()
        return capath

def getKeyCertFromEnv():
    """
    gets key and certificate from environment variables
    If no env variable is set return None, None for key, cert tuple
    """
    envPairs = [('X509_HOST_KEY', 'X509_HOST_CERT'),  # First preference to HOST Certificate,
                ('X509_USER_PROXY', 'X509_USER_PROXY'),  # Second preference to User Proxy, very common
                ('X509_USER_KEY', 'X509_USER_CERT')]  # Third preference to User Cert/Proxy combinition

    for keyEnv, certEnv in envPairs:
        key = os.environ.get(keyEnv)
        cert = os.environ.get(certEnv)
        if key and cert and os.path.exists(key) and os.path.exists(cert):
            # if it is found in env return key, cert
            return key, cert

    # TODO: only in linux, unix case, add other os case
    # look for proxy at default location /tmp/x509up_u$uid
    key = cert = '/tmp/x509up_u' + str(os.getuid())
    if os.path.exists(key):
        return key, cert

    if (os.environ.get('HOME') and
        os.path.exists(os.environ['HOME'] + '/.globus/usercert.pem')  and
        os.path.exists(os.environ['HOME'] + '/.globus/userkey.pem')):

        key = os.environ['HOME'] + '/.globus/userkey.pem'
        cert = os.environ['HOME'] + '/.globus/usercert.pem'
        return key, cert
    if (os.path.exists('/etc/grid-security/hostcert.pem') and
             os.path.exists('/etc/grid-security/hostkey.pem')):
        return '/etc/grid-security/hostkey.pem', '/etc/grid-security/hostcert.pem'
    else:
        # couldn't find the key, cert files
        return None, None


def getCAPathFromEnv():
    """
    Return the path of the CA certificates. The check is loose in the pycurl_manager:
    is capath == None then the server identity is not verified. To enable this check
    you need to set either the X509_CERT_DIR variable or the cacert key of the request.
    """
    capath = os.environ.get("X509_CERT_DIR")
    return capath
