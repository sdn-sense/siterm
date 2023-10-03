#!/usr/bin/env python3
"""
Custom Exceptions for Sense Site FE.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
def exceptionCode(excName):
    """Return Exception code.
    """
    exCodes = {IOError: -1, KeyError: -2, AttributeError: -3, IndentationError: -4,
               ValueError: -5, PluginException: -6, NameError: -7}
    if excName in exCodes:
        return exCodes[excName]
    return -100


class ExceptionTemplate(Exception):
    """Exception template."""
    def __call__(self, *args):
        return self.__class__(*(self.args + args))
    def __str__(self):
        return ': '.join(self.args)

class NotFoundError(ExceptionTemplate):
    """Not Found error."""


class ConfigException(ExceptionTemplate):
    """Config Exception."""


class WrongInputError(ExceptionTemplate):
    """Wrong Input Error."""


class FailedToParseError(ExceptionTemplate):
    """Failed to parse correct type."""


class BadRequestError(ExceptionTemplate):
    """Bad Request Error."""


class ValidityFailure(ExceptionTemplate):
    """Failed Validation of type."""


class NoOptionError(ExceptionTemplate):
    """No option available in configuration."""


class NoSectionError(ExceptionTemplate):
    """No section available in configuration."""


class WrongDeltaStatusTransition(ExceptionTemplate):
    """Delta is now allowed to be changed to that specific state."""


class DeltaNotFound(ExceptionTemplate):
    """Delta with this specific ID was not found in the system."""


class ModelNotFound(ExceptionTemplate):
    """Model with this specific ID was not found in the system."""


class HostNotFound(ExceptionTemplate):
    """Host wwas not found in the system."""


class ExceededCapacity(ExceptionTemplate):
    """Exceeded possible node capacity."""


class ExceededLinkCapacity(ExceptionTemplate):
    """Exceeded possible Link capacity."""


class ExceededSwitchCapacity(ExceptionTemplate):
    """Exceeded possible Link capacity."""


class DeltaKeyMissing(ExceptionTemplate):
    """Mandatory key is not present."""


class UnrecognizedDeltaOption(ExceptionTemplate):
    """Unrecognized Delta Options."""


class FailedInterfaceCommand(ExceptionTemplate):
    """Failed to execute Interface command."""


class FailedRoutingCommand(ExceptionTemplate):
    """Failed to execute Routing command."""


class TooManyArgumentalValues(ExceptionTemplate):
    """Too many argumental values."""


class NotSupportedArgument(ExceptionTemplate):
    """Argument value is not supported."""


class PluginException(ExceptionTemplate):
    """Plugin Exception."""


class OverlapException(ExceptionTemplate):
    """Overlap Exception."""


class WrongIPAddress(ExceptionTemplate):
    """Wrong IP Address Exception"""


class OverSubscribeException(ExceptionTemplate):
    """OverSubscribe Exception."""


class FailedGetDataFromFE(ExceptionTemplate):
    """Failed to Get Data from FE"""


class MethodNotSupported(ExceptionTemplate):
    """Method Not Supported"""


class NotAcceptedHeader(ExceptionTemplate):
    """Not Accepted Header"""


class ConflictEntries(ExceptionTemplate):
    """Conflict Entries"""


class SwitchException(ExceptionTemplate):
    """Switch communication exception"""


class HTTPResponses():
    """Frontend HTTP Responses."""
    def __init__(self):
        self.cacheHeaders = [('Cache-Control', 'no-cache, no-store, must-revalidate'),
                             ('Pragma', 'no-cache'), ('Expires', '0')]

    def _header_append(self, headers, head_append, nocache=True):
        outheaders = []
        if head_append:
            outheaders += head_append
        if nocache:
            outheaders = self.cacheHeaders
        if outheaders:
            for item in outheaders:
                headers.append((item[0], item[1]))
        return headers

    def ret_200(self, content_type, start_response, head_append):
        """200 OK."""
        status = '200 OK'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_201(self, content_type, start_response, head_append):
        """The request has been fulfilled, resulting in the creation of a new
        resource."""
        status = '201 Created'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_204(self, content_type, start_response, head_append):
        """The server successfully processed the request and is not returning
        any content."""
        status = '204 No Content'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_304(self, content_type, start_response, head_append):
        """Indicates that the resource has not been modified since the version
        specified by the request headers If-Modified-Since or If-None-Match.

        In such case, there is no need to retransmit the resource since
        the client still has a previously-downloaded copy.
        """
        status = '304 Not Modified'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_400(self, content_type, start_response, head_append):
        """400 Bad Request."""
        status = '400 Bad Request'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_401(self, content_type, start_response, head_append):
        """401 Unauthorized."""
        status = '401 Unauthorized'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_403(self, content_type, start_response, head_append):
        """403 Forbidden."""
        status = '403 Forbidden'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_404(self, content_type, start_response, head_append):
        """404 Not Found."""
        status = '404 Not Found'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_405(self, content_type, start_response, head_append):
        """405 Method Not Allowed."""
        status = '405 Method Not Allowed'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_406(self, content_type, start_response, head_append):
        """405 Not Acceptable."""
        status = '406 Not Acceptable'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_409(self, content_type, start_response, head_append):
        """409 Conflict."""
        status = '409 Conflict'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_500(self, content_type, start_response, head_append):
        """500 Internal Server Error."""
        status = '500 Internal Server Error'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_501(self, content_type, start_response, head_append):
        """501 Not Implemented."""
        status = '501 Not Implemented'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)

    def ret_503(self, content_type, start_response, head_append):
        """503 Service Unavailable."""
        status = '503 Service Unavailable'
        headers = [('Content-type', content_type)]
        headers = self._header_append(headers, head_append)
        start_response(status, headers)
