#!/usr/bin/env python3
"""
Custom Exceptions for Sense Site FE.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""


def exceptionCode(excName):
    """Return Exception code."""
    exCodes = {
        IOError: -1,
        KeyError: -2,
        AttributeError: -3,
        IndentationError: -4,
        ValueError: -5,
        PluginException: -6,
        NameError: -7,
        PluginFatalException: -8,
        OverlapException: -9,
        NotFoundError: -10,
        BackgroundException: -11,
        ServiceWarning: -12,
        ConfigException: -13,
        WrongInputError: -14,
        FailedToParseError: -15,
        BadRequestError: -16,
        ValidityFailure: -17,
        NoOptionError: -18,
        NoSectionError: -19,
        WrongDeltaStatusTransition: -20,
        DeltaNotFound: -21,
        ModelNotFound: -22,
        HostNotFound: -23,
        ExceededCapacity: -24,
        ExceededLinkCapacity: -25,
        ExceededSwitchCapacity: -26,
        DeltaKeyMissing: -27,
        UnrecognizedDeltaOption: -28,
        FailedInterfaceCommand: -29,
        FailedRoutingCommand: -30,
        TooManyArgumentalValues: -31,
        NotSupportedArgument: -32,
        ServiceNotReady: -33,
    }
    if excName in exCodes:
        return exCodes[excName]
    return -100


class ExceptionTemplate(Exception):
    """Exception template."""

    def __call__(self, *args):
        return self.__class__(*(self.args + args))

    def __str__(self):
        return ": ".join(self.args)


class NotFoundError(ExceptionTemplate):
    """Not Found error."""


class BackgroundException(ExceptionTemplate):
    """Background Exception."""


class ServiceWarning(ExceptionTemplate):
    """Service Warning - Not Fatal."""


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


class PluginFatalException(ExceptionTemplate):
    """Plugin Fatal Exception."""


class OverlapException(ExceptionTemplate):
    """Overlap Exception."""


class WrongIPAddress(ExceptionTemplate):
    """Wrong IP Address Exception"""


class OverSubscribeException(ExceptionTemplate):
    """OverSubscribe Exception."""


class FailedGetDataFromFE(ExceptionTemplate):
    """Failed to Get Data from FE"""


class SwitchException(ExceptionTemplate):
    """Switch communication exception"""


class RequestWithoutCert(ExceptionTemplate):
    """Request Without Certificate Error."""


class IssuesWithAuth(ExceptionTemplate):
    """IssuesWithAuth Error."""


class ServiceNotReady(ExceptionTemplate):
    """Service Not Ready Error."""
