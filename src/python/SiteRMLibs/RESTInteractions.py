#!/usr/bin/env python3
"""To be changed with HTTPLibrary...

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
import cgi
import urllib.request
import urllib.error
from SiteRMLibs.CustomExceptions import NotFoundError
from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.MainUtilities import evaldict


class getContent():
    """Get Content from url."""
    def __init__(self):
        # We would want to add later more things to init,
        # for example https and security details from config.
        self.initialized = True

    @staticmethod
    def get_method(url):
        """Only used inside the site for forwardning requests."""
        try:
            if not url.lower().startswith('http'):
                raise ValueError from None
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                thePage = response.read()
                return thePage
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                raise NotFoundError from ex
            raise BadRequestError from ex


def is_application_json(environ):
    """Check if environ has set content type to json."""
    content_type = environ.get('CONTENT_TYPE', 'application/json')
    return content_type.startswith('application/json')


def is_post_request(environ):
    """Check if environ has set it to POST method."""
    if environ['REQUEST_METHOD'].upper() != 'POST':
        return False
    content_type = environ.get('CONTENT_TYPE', 'application/x-www-form-urlencoded')
    return content_type.startswith('application/x-www-form-urlencoded') or \
           content_type.startswith('multipart/form-data')


def get_json_post_form(environ):
    """Get Json from Post form."""
    try:
        request_body_size = int(environ.get('CONTENT_LENGTH', 0))
    except ValueError:
        request_body_size = 0
    request_body = environ['wsgi.input'].read(request_body_size)
    try:
        params = evaldict(request_body)
    except:
        print('Reached except in data load')
        params = evaldict(request_body)
        if not isinstance(params, dict):
            params = evaldict(params)
    environ.setdefault('params', {})
    for key in list(params.keys()):
        environ['params'][key] = params[key]
    return environ['params']


def get_post_form(environ):
    """Get content submitted through POST method."""
    postEnv = environ.copy()
    postEnv['QUERY_STRING'] = ''
    inputP = environ['wsgi.input']
    post_form = environ.get('wsgi.post_form')
    if post_form is not None and post_form[0] is input:
        return post_form[2]
    fieldS = cgi.FieldStorage(fp=inputP,
                              environ=postEnv,
                              keep_blank_values=True)
    new_input = InputProcessed()
    post_form = (new_input, inputP, fieldS)
    environ['wsgi.post_form'] = post_form
    environ['wsgi.input'] = new_input
    return fieldS


class InputProcessed():
    """wsgi Input processing class."""
    @staticmethod
    def read(*args):
        """Process wsgi Input reads"""
        raise EOFError('The wsgi.input stream has already been consumed')
    readline = readlines = __iter__ = read
