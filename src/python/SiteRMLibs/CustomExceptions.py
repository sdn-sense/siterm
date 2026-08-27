#!/usr/bin/env python3
"""
Custom Exceptions for Sense Site FE.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""

from rdflib.plugins.parsers.notation3 import BadSyntax

# Named non-exception sentinel codes (-101 … -199). Import these constants
# rather than passing raw strings to addWarning()/exceptionCode(), so a typo
# fails an import instead of silently falling back to -100.
SNMP_TIMEOUT = "SNMP_TIMEOUT"
SNMP_UNKNOWN_OID = "SNMP_UNKNOWN_OID"
ANSIBLE_UNREACHABLE = "ANSIBLE_UNREACHABLE"
ANSIBLE_PLAYBOOK_FAILED = "ANSIBLE_PLAYBOOK_FAILED"
SERVICE_DEAD = "SERVICE_DEAD"
SERVICE_DOWN = "SERVICE_DOWN"
VALIDATOR_SWITCH_NO_ANSIBLE_OUTPUT = "VALIDATOR_SWITCH_NO_ANSIBLE_OUTPUT"
VALIDATOR_PORT_NO_ANSIBLE_OUTPUT = "VALIDATOR_PORT_NO_ANSIBLE_OUTPUT"
VALIDATOR_HOST_LLDP_MISMATCH = "VALIDATOR_HOST_LLDP_MISMATCH"
LIVENESS_READINESS_DISABLED = "LIVENESS_READINESS_DISABLED"
DELTA_STATE_TRANSITION_ERROR = "DELTA_STATE_TRANSITION_ERROR"
SWITCH_VLAN_RANGE_EXHAUSTED = "SWITCH_VLAN_RANGE_EXHAUSTED"
NODE_VLAN_RANGE_EXHAUSTED = "NODE_VLAN_RANGE_EXHAUSTED"
VLAN_MANUAL_CONFIG_MISMATCH = "VLAN_MANUAL_CONFIG_MISMATCH"
MODEL_UPDATE_LOOP_SUSPECTED = "MODEL_UPDATE_LOOP_SUSPECTED"
SWITCH_CHANNEL_MEMBER_DOWN = "SWITCH_CHANNEL_MEMBER_DOWN"
SWITCH_PORT_NOT_SWITCHPORT = "SWITCH_PORT_NOT_SWITCHPORT"
AGENT_HOST_PUBLISH_FAILED = "AGENT_HOST_PUBLISH_FAILED"


def exceptionCode(excName):
    """Return a stable, machine-readable error code for an exception class or
    a named non-exception sentinel string (e.g. 'SNMP_TIMEOUT').

    Codes are **permanent**: once assigned a number is never reused or changed.

    Exception-class codes  : -1   …  -99  (negative, grouped by domain)
    Non-exception sentinels: -101 … -199  (SNMP, Ansible, etc.)
    Unknown / fallback     : -100
    """
    # --- Exception-class codes (-1 … -99) ---
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
        HTTPServerNotReady: -34,
        HTTPException: -35,
        # Codes -36 … -99 reserved for future exception classes.
        # NOTE: WrongIPAddress and OverSubscribeException intentionally omitted
        # from the original map are assigned here.
        WrongIPAddress: -36,
        OverSubscribeException: -37,
        FailedGetDataFromFE: -38,
        SwitchException: -39,
        RequestWithoutCert: -40,
        IssuesWithAuth: -41,
        # policyService.getError() previously mapped BadSyntax (rdflib) to -6
        # locally; -6 is already PluginException here, so BadSyntax gets a new
        # slot rather than an ambiguous shared code.
        BadSyntax: -42,
    }

    # --- Named non-exception sentinel codes (-101 … -199) ---
    # These cover infrastructure events and free-text Warnings.addWarning()
    # categories that do not map to a Python exception.
    sentinelCodes = {
        SNMP_TIMEOUT: -101,
        SNMP_UNKNOWN_OID: -102,
        ANSIBLE_UNREACHABLE: -103,
        ANSIBLE_PLAYBOOK_FAILED: -104,
        SERVICE_DEAD: -105,
        SERVICE_DOWN: -106,
        VALIDATOR_SWITCH_NO_ANSIBLE_OUTPUT: -107,
        VALIDATOR_PORT_NO_ANSIBLE_OUTPUT: -108,
        VALIDATOR_HOST_LLDP_MISMATCH: -109,
        LIVENESS_READINESS_DISABLED: -110,
        DELTA_STATE_TRANSITION_ERROR: -111,
        SWITCH_VLAN_RANGE_EXHAUSTED: -112,
        NODE_VLAN_RANGE_EXHAUSTED: -113,
        VLAN_MANUAL_CONFIG_MISMATCH: -114,
        MODEL_UPDATE_LOOP_SUSPECTED: -115,
        SWITCH_CHANNEL_MEMBER_DOWN: -116,
        SWITCH_PORT_NOT_SWITCHPORT: -117,
        AGENT_HOST_PUBLISH_FAILED: -118,
    }

    if excName in exCodes:
        return exCodes[excName]
    if excName in sentinelCodes:
        return sentinelCodes[excName]
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


class HTTPServerNotReady(ExceptionTemplate):
    """HTTP Server Not Ready Error."""


class HTTPException(ExceptionTemplate):
    """HTTP Exception."""
