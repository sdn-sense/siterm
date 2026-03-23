#!/usr/bin/env python3
# pylint: disable=C0301
"""
DSCP Component for Ruler on the host

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2025/12/22
Host DSCP at Layer 2:
This configuration below uses Linux tc (traffic control) with u32 classifiers and pedit actions to rewrite the DSCP field for all traffic on vlan.1409.
Three classes are enforced:

    GuaranteedCapped → DSCP 46 (0x2E, encoded as 0xB8 in IPv4 TOS)
    SoftCapped → DSCP 18 (0x12, encoded as 0x48 in IPv4 TOS)
    BestEffort → DSCP 0

Because IPv4 and IPv6 store DSCP in different spots, each class has two filters: one for IPv4 and one for IPv6.

GuaranteedCapped: (DSCP 46)
tc filter add dev vlan.1409 parent 1: protocol ipv6 prio 11 u32 match u32 0 0 action pedit munge offset 0 u8 set 0x6b action pedit munge offset 1 u8 set 0x80 action ok
tc filter add dev vlan.1409 parent 1: protocol ip prio 1 u32 match u32 0 0 action pedit munge ip tos set 0xb8 action ok
SoftCapped: (DSCP 18)
tc filter add dev vlan.1409 parent 1: protocol ip prio 2 u32 match u32 0 0 action pedit munge ip tos set 0x48 action ok
tc filter add dev vlan.1409 parent 1: protocol ipv6 prio 12 u32 match u32 0 0 action pedit munge offset 0 u8 set 0x64 action pedit munge offset 1 u8 set 0x80 action ok
BestEffort: (DSCP 0)
tc filter add dev vlan.1409 parent 1: protocol ip prio 3 u32 match u32 0 0 action pedit munge ip tos set 0x00 action ok
tc filter add dev vlan.1409 parent 1: protocol ipv6 prio 13 u32 match u32 0 0 action pedit munge offset 0 u8 set 0x60 action pedit munge offset 1 u8 set 0x00 action ok

L3 needs to happen at the IP level and this is only done if host has ip6tables installed:
Create:
ip6tables -t mangle -A OUTPUT -d 2605:9a00:10:2010::/64 -m comment --comment "SENSE_GuaranteedCapped_DSCP46_UUID" -j DSCP --set-dscp 46
Delete:
ip6tables -t mangle -D OUTPUT -d 2605:9a00:10:2010::/64 -m comment --comment "SENSE_GuaranteedCapped_DSCP46_UUID" -j DSCP --set-dscp 46
"""

import shutil

from SiteRMLibs.MainUtilities import execute, externalCommand

COMPONENT = "DSCP"

# SENSE service class → DSCP parameters
# ipv6_b0/b1: bytes 0 and 1 of the IPv6 header when TC = DSCP<<2
#   byte0 = 0x60 | (TC >> 4)   (version=6 in upper nibble)
#   byte1 = (TC & 0x0f) << 4   (lower nibble of TC, upper nibble of Flow Label)
_DSCP_CLASSES = {
    "guaranteedCapped": {"dscp": 46, "ipv4_tos": 0xB8, "ipv6_b0": 0x6B, "ipv6_b1": 0x80, "ipv4_prio": 1, "ipv6_prio": 11},
    "softCapped":       {"dscp": 18, "ipv4_tos": 0x48, "ipv6_b0": 0x64, "ipv6_b1": 0x80, "ipv4_prio": 2, "ipv6_prio": 12},
    "bestEffort":       {"dscp":  0, "ipv4_tos": 0x00, "ipv6_b0": 0x60, "ipv6_b1": 0x00, "ipv4_prio": 3, "ipv6_prio": 13},
}


class DSCP:
    """DSCP marking component: L2 via tc pedit on VLAN interfaces, L3 via ip6tables."""

    # pylint: disable=E1101,R0903
    def __init__(self):
        self._ip6tables_avail = bool(shutil.which("ip6tables"))

    # ── active-delta helpers ───────────────────────────────────────────────────

    def _get_active_l2_dscp(self, activeDeltas):
        """Return {dev: entry} for every vlan interface with a DSCP service class."""
        result = {}
        for actkey in ["vsw", "kube"]:
            for uuid, vals in activeDeltas.get("output", {}).get(actkey, {}).items():
                if not isinstance(vals, dict) or self.hostname not in vals:
                    continue
                if not self._started(vals):
                    continue
                for _port, vals1 in vals[self.hostname].items():
                    vlan_id = vals1.get("hasLabel", {}).get("value", "")
                    svc_type = vals1.get("hasService", {}).get("type", "")
                    if not vlan_id or svc_type not in _DSCP_CLASSES:
                        continue
                    dev = f"vlan.{vlan_id}"
                    result[dev] = {"vlan": vlan_id, "svc_type": svc_type, "uuid": uuid}
        return result

    def _get_active_l3_dscp(self, activeDeltas):
        """Return list of {dst_ipv6, svc_type, uuid} for RST entries with a DSCP class."""
        result = []
        for uuid, vals in activeDeltas.get("output", {}).get("rst", {}).items():
            for _, ipDict in vals.items():
                for iptype, routes in ipDict.items():
                    if iptype != "ipv6" or "hasService" not in routes:
                        continue
                    svc_type = routes["hasService"].get("type", "")
                    if svc_type not in _DSCP_CLASSES:
                        continue
                    for _, routeInfo in routes.get("hasRoute", {}).items():
                        dst = routeInfo.get("routeTo", {}).get("ipv6-prefix-list", {}).get("value", "")
                        if not dst:
                            continue
                        src = routeInfo.get("routeFrom", {}).get("ipv6-prefix-list", {}).get("value", "")
                        if src:
                            ipVal, _ = self.findOverlaps(src, "ipv6")
                            if not ipVal:
                                self.logger.debug("DSCP L3: skipping %s - routeFrom %s not present on this host", dst, src)
                                continue
                        result.append({"dst_ipv6": dst, "svc_type": svc_type, "uuid": uuid})
        return result

    # ── L2: tc qdisc / filter helpers ─────────────────────────────────────────

    def _has_root_prio(self, dev):
        """Return True if dev already has a root prio qdisc."""
        out, _ = externalCommand(f"tc qdisc show dev {dev}")
        return "qdisc prio" in out and "root" in out

    def _ensure_prio_qdisc(self, dev):
        """Add root handle 1: prio qdisc on dev if not already present."""
        if not self._has_root_prio(dev):
            execute(f"tc qdisc add dev {dev} root handle 1: prio", self.logger, raiseError=False)

    def _clear_dscp_filters(self, dev):
        """Delete all protocol ip/ipv6 tc filters from dev parent 1:."""
        execute(f"tc filter del dev {dev} parent 1: protocol ip", self.logger, raiseError=False)
        execute(f"tc filter del dev {dev} parent 1: protocol ipv6", self.logger, raiseError=False)

    def _apply_l2_dscp(self, dev, svc_type):
        """Install u32 + pedit DSCP rewrite filters on dev for svc_type."""
        cls = _DSCP_CLASSES[svc_type]
        # IPv4: overwrite TOS byte
        execute(
            f"tc filter add dev {dev} parent 1: protocol ip prio {cls['ipv4_prio']} "
            f"u32 match u32 0 0 "
            f"action pedit munge ip tos set {hex(cls['ipv4_tos'])} action ok",
            self.logger,
            raiseError=False,
        )
        # IPv6: overwrite Traffic Class across bytes 0-1 of the IPv6 header
        execute(
            f"tc filter add dev {dev} parent 1: protocol ipv6 prio {cls['ipv6_prio']} "
            f"u32 match u32 0 0 "
            f"action pedit munge offset 0 u8 set {hex(cls['ipv6_b0'])} "
            f"action pedit munge offset 1 u8 set {hex(cls['ipv6_b1'])} action ok",
            self.logger,
            raiseError=False,
        )

    def _remove_prio_qdisc(self, dev):
        """Remove root prio qdisc (and all attached filters) from dev."""
        execute(f"tc qdisc del dev {dev} root", self.logger, raiseError=False)

    # ── L3: ip6tables helpers ──────────────────────────────────────────────────

    @staticmethod
    def _ip6t_comment(svc_type, uuid):
        """Build the ip6tables comment used to identify SENSE DSCP rules."""
        dscp = _DSCP_CLASSES[svc_type]["dscp"]
        return f"SENSE_{svc_type}_DSCP{dscp}_{uuid}"

    def _ip6t_exists(self, dst_ipv6, svc_type, uuid):
        """Return True if the ip6tables OUTPUT rule already exists."""
        comment = self._ip6t_comment(svc_type, uuid)
        dscp = _DSCP_CLASSES[svc_type]["dscp"]
        proc = externalCommand(
            f'ip6tables -t mangle -C OUTPUT -d {dst_ipv6} -m comment --comment "{comment}" -j DSCP --set-dscp {dscp}',
            communicate=False,
        )
        proc.communicate()
        return proc.returncode == 0

    def _add_l3_dscp(self, dst_ipv6, svc_type, uuid):
        """Add ip6tables OUTPUT DSCP rule for dst_ipv6 (idempotent)."""
        if self._ip6t_exists(dst_ipv6, svc_type, uuid):
            return
        comment = self._ip6t_comment(svc_type, uuid)
        dscp = _DSCP_CLASSES[svc_type]["dscp"]
        execute(
            f'ip6tables -t mangle -A OUTPUT -d {dst_ipv6} -m comment --comment "{comment}" -j DSCP --set-dscp {dscp}',
            self.logger,
            raiseError=False,
        )

    def _del_l3_dscp(self, dst_ipv6, svc_type, uuid):
        """Delete ip6tables OUTPUT DSCP rule for dst_ipv6."""
        comment = self._ip6t_comment(svc_type, uuid)
        dscp = _DSCP_CLASSES[svc_type]["dscp"]
        execute(
            f'ip6tables -t mangle -D OUTPUT -d {dst_ipv6} -m comment --comment "{comment}" -j DSCP --set-dscp {dscp}',
            self.logger,
            raiseError=False,
        )

    # ── main convergence ───────────────────────────────────────────────────────

    def startdscp(self):
        """Converge DSCP rules: apply desired state from activeFromFE, remove stale rules."""
        # L2 ──────────────────────────────────────────────────────────────────
        desired_l2 = self._get_active_l2_dscp(self.activeFromFE)
        previous_l2 = self._get_active_l2_dscp(self.activeDeltas)

        for dev in previous_l2:
            if dev not in desired_l2:
                self.logger.info("DSCP: removing L2 rules from %s", dev)
                self._remove_prio_qdisc(dev)

        for dev, entry in desired_l2.items():
            self.logger.info("DSCP: applying L2 %s on %s", entry["svc_type"], dev)
            self._ensure_prio_qdisc(dev)
            self._clear_dscp_filters(dev)
            self._apply_l2_dscp(dev, entry["svc_type"])

        # L3 ──────────────────────────────────────────────────────────────────
        if not self._ip6tables_avail:
            self.logger.info("DSCP: ip6tables not found, skipping L3 rules")
            return

        desired_l3 = self._get_active_l3_dscp(self.activeFromFE)
        previous_l3 = self._get_active_l3_dscp(self.activeDeltas)

        desired_keys = {(e["dst_ipv6"], e["svc_type"], e["uuid"]) for e in desired_l3}
        for entry in previous_l3:
            if (entry["dst_ipv6"], entry["svc_type"], entry["uuid"]) not in desired_keys:
                self.logger.info("DSCP: removing L3 rule for %s", entry["dst_ipv6"])
                self._del_l3_dscp(entry["dst_ipv6"], entry["svc_type"], entry["uuid"])

        for entry in desired_l3:
            self.logger.info("DSCP: applying L3 %s for %s", entry["svc_type"], entry["dst_ipv6"])
            self._add_l3_dscp(entry["dst_ipv6"], entry["svc_type"], entry["uuid"])
