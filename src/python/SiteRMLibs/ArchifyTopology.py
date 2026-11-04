#!/usr/bin/env python3
"""
Build Archify architecture diagrams from SiteFE topology.json and render them with the Archify CLI.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/10/30
"""

import hashlib
import html
import json
import math
import os
import re
import subprocess
import tempfile
import threading
import unicodedata
from collections import Counter, OrderedDict

from SiteRMLibs.ArchifyLayout import NODE_H, layoutDiagram, offsetPolyline, svgPath
from SiteRMLibs.DefaultParams import SERVICE_DEAD_TIMEOUT

ARCHIFY_CLI = os.environ.get("SITERM_ARCHIFY_CLI", "/opt/archify/archify/bin/archify.mjs")
NODE_BIN = os.environ.get("SITERM_NODE_BIN", "node")
RENDER_TIMEOUT = 120
CACHE_SIZE = 16
MAX_CARD_ITEMS = 200
MIN_NODE_W = 140

# Tier order is top to bottom on the canvas; each SiteRM device type maps to an Archify component type.
TIERS = ("cloud", "switch", "server")
COMPONENT_TYPES = {"cloud": "cloud", "switch": "messagebus", "server": "backend"}
LEGEND = {
    "mode": "auto",
    "entries": {
        "cloud": {"label": "WAN peer"},
        "messagebus": {"label": "Switch"},
        "backend": {"label": "Server"},
    },
}

# Members of one port-channel sit MEMBER_GAP apart; separate links of one device pair LINK_GAP apart.
MEMBER_GAP = 4
LINK_GAP = 9
RING_DIST = 8
# Speed classes, slowest first: (css class, upper bound in Mb/s, legend label, stroke width). Width grows with speed so colour is never the only cue.
SPEED_CLASSES = (
    ("s10g", 10000, "<=10G", 1.3),
    ("s25g", 25000, "25G", 1.6),
    ("s50g", 50000, "40-50G", 1.9),
    ("s100g", 100000, "100G", 2.2),
    ("s200g", 200000, "200G", 2.5),
    ("s400g", 400000, "400G", 2.8),
    ("s800g", None, "800G+", 3.2),
)
UNKNOWN_SPEED = ("sunknown", "unknown", 1.3)
# Overrides the speed class: some vendors keep reporting the configured speed on a down port. Drawn dotted so colour is not the only cue.
DOWN_LINK = ("sdown", "down", 1.8)
# Categorical slots 1-7 in fixed order (light, dark); validated for CVD separation on Archify's light and dark canvases.
SPEED_COLOURS = {
    "s10g": ("#2a78d6", "#3987e5"),
    "s25g": ("#eb6834", "#d95926"),
    "s50g": ("#1baf7a", "#199e70"),
    "s100g": ("#eda100", "#c98500"),
    "s200g": ("#e87ba4", "#d55181"),
    "s400g": ("#008300", "#008300"),
    "s800g": ("#6250d6", "#9085e9"),
}
# Service states by severity; anything else a service reports counts as UNKNOWN. FE services report as host "default".
STATES = ("OK", "UNKNOWN", "WARNING", "FAILED")
STATE_ALIASES = {"KEYBOARDINTERRUPT": "FAILED"}
STATE_COLOURS = {"OK": "#0ca30c", "UNKNOWN": "#898781", "WARNING": "#fab219", "FAILED": "#d03b3b"}
STATE_DOTS = {"OK": "emerald", "UNKNOWN": "slate", "WARNING": "amber", "FAILED": "rose"}
STATE_LEGEND = {"OK": "OK", "UNKNOWN": "UNKNOWN (no recent report)", "WARNING": "WARNING", "FAILED": "FAILED"}
FRONTEND_HOST = "default"
NO_EXCEPTION = "No Exception provided by service"
SPEED_CARD = "Link speed"
HEALTH_CARD = "Node health"

_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()


class ArchifyUnavailable(Exception):
    """Archify CLI or Node.js runtime is not installed."""


class ArchifyRenderError(Exception):
    """Archify rejected the diagram or failed to render it."""


def _textUnits(text):
    """Approximate Archify text units: wide (CJK) characters count twice."""
    return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in str(text))


def _labelWidth(labels, sublabels):
    """Return a component width that fits every label at 11px and every sublabel at 6px (Archify validator limits)."""
    width = MIN_NODE_W
    for label in labels:
        width = max(width, math.ceil(_textUnits(label) * 6.6) + 40)
    for sublabel in sublabels:
        width = max(width, math.ceil(_textUnits(sublabel) * 3.6) + 24)
    return width


def _capItems(items):
    """Limit card items so very large sites do not produce unbounded pages."""
    if len(items) <= MAX_CARD_ITEMS:
        return items
    return items[:MAX_CARD_ITEMS] + [f"... and {len(items) - MAX_CARD_ITEMS} more"]


def _field(entry, key):
    """Return entry[key] if it is a dict, else an empty dict (topology.json and DB content are untrusted)."""
    value = entry.get(key) if isinstance(entry, dict) else None
    return value if isinstance(value, dict) else {}


def _int(value):
    """Return a non-negative int from untrusted data (0 when missing or malformed)."""
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return 0


def _plural(count, noun):
    """Return "1 link", "2 links", "2 switches"."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}{'es' if noun.endswith('h') else 's'}"


def _natural(text):
    """Sort key that orders Ethernet2 before Ethernet10."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(text))]


def _portKey(port):
    """Canonical port name: Ethernet 1/1/13, ethernet1/1/13 and the model's Ethernet_1-1-13 all match.

    Model names (replaceSpecialSymbols) turn " " into "_" and ":" into "__"; spaces are dropped, other separators kept.
    """
    name = str(port).lower().replace("__", ":")
    return re.sub(r"[^a-z0-9]+", "_", re.sub(r"[\s_]+", "", name)).strip("_")


def _remoteAlias(entry):
    """Return the isAlias URN of a cloud (WAN peer) entry."""
    return str(_field(entry, "DeviceInfo").get("name", ""))


def speedClass(speed):
    """Return (css class, legend label, stroke width) for a link speed in Mb/s."""
    if speed <= 0:
        return UNKNOWN_SPEED
    for cls, bound, label, width in SPEED_CLASSES:
        if bound is None or speed <= bound:
            return cls, label, width
    return UNKNOWN_SPEED


def _speedText(speed):
    """Human readable speed for a value in Mb/s."""
    if speed <= 0:
        return "unknown speed"
    if speed >= 1000000:
        return f"{speed / 1000000:g}T"
    return f"{speed / 1000:g}G" if speed >= 1000 else f"{speed}M"


def _linkState(link):
    """Return "down" or the speed text of one physical link."""
    return DOWN_LINK[1] if link["down"] else _speedText(link["speed"])


def _state(value):
    """Normalise a reported service state to one of STATES."""
    state = str(value).upper()
    state = STATE_ALIASES.get(state, state)
    return state if state in STATES else "UNKNOWN"


def _worst(states):
    """Return the most severe state (UNKNOWN when there are none)."""
    return max(states, key=STATES.index, default="UNKNOWN")


def summarizeServiceStates(rows, now):
    """Return {"hosts": {hostname: [entry]}, "frontend": [entry]} from servicestates rows; rows older than SERVICE_DEAD_TIMEOUT count as UNKNOWN."""
    out = {"hosts": {}, "frontend": []}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        age = now - _int(row.get("updatedate"))
        state = _state(row.get("servicestate")) if age < SERVICE_DEAD_TIMEOUT else "UNKNOWN"
        detail = ""
        if age >= SERVICE_DEAD_TIMEOUT:
            detail = f"no report for {age // 60} min"
        elif state != "OK" and str(row.get("exc", "")) not in ("", NO_EXCEPTION):
            detail = str(row.get("exc")).splitlines()[0][:120]
        entry = {"service": str(row.get("servicename", "")), "state": state, "detail": detail}
        host = str(row.get("hostname", ""))
        (out["frontend"] if host == FRONTEND_HOST else out["hosts"].setdefault(host, [])).append(entry)
    for entries in [out["frontend"], *out["hosts"].values()]:
        entries.sort(key=lambda entry: entry["service"])
    return out


def _vsw(active):
    """Return the L2 connections (vsw) of activeDeltas output."""
    vsw = _field(active, "vsw")
    return {str(key): val for key, val in vsw.items() if isinstance(val, dict)}


def _aliases(value):
    """Return isAlias values as a list of strings."""
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value] if isinstance(value, list) else []


def activePath(active, connid):
    """Return {"id", "state", "hops": {device: {portKey: hop}}, "aliases"} for one active L2 connection, or None if it is not active."""
    entry = _vsw(active).get(connid)
    if entry is None:
        return None
    hops = {}
    aliases = set(_aliases(entry.get("isAlias")))
    for device, ports in entry.items():
        if str(device).startswith("_") or not isinstance(ports, dict):
            continue
        for port, vals in ports.items():
            if str(port).startswith("_") or not isinstance(vals, dict):
                continue
            vlan = _field(vals, "hasLabel").get("value")
            hops.setdefault(str(device), {})[_portKey(port)] = {
                "port": str(port),
                "vlan": vlan if isinstance(vlan, int) else None,
                "state": str(_field(vals, "_params").get("networkstatus", "")),
            }
            aliases.update(_aliases(vals.get("isAlias")))
    return {"id": connid, "state": str(_field(entry, "_params").get("networkstatus", "")), "hops": hops, "aliases": sorted(aliases)}


def _pathVlans(path):
    """Return the sorted VLANs used along a path."""
    return sorted({hop["vlan"] for ports in path["hops"].values() for hop in ports.values() if hop["vlan"] is not None})


def activePaths(active):
    """Return [{"id", "state", "vlans", "devices"}] for every active L2 connection, ordered by VLAN."""
    out = []
    for connid in _vsw(active):
        path = activePath(active, connid)
        out.append({"id": path["id"], "state": path["state"], "vlans": _pathVlans(path), "devices": sorted(path["hops"])})
    return sorted(out, key=lambda item: (item["vlans"], item["id"]))


def _cloudOnPath(entry, path):
    """Return True if a path uses a WAN peer: its alias is on the path, or the path uses the switch port (or a member) facing it."""
    if _remoteAlias(entry) in path["aliases"]:
        return True
    for link in _field(entry, "topo").values():
        device = link.get("device") if isinstance(link, dict) else None
        if not isinstance(device, str) or device not in path["hops"]:
            continue
        members = link.get("members") if isinstance(link.get("members"), dict) else {}
        if any(_portKey(port) in path["hops"][device] for port in [link.get("localport") or "", *members] if port):
            return True
    return False


def _selectDevices(topology, switches, servers, path):
    """Return {name: devtype} for devices that pass the filters; WAN peers follow their switch, a path keeps only its devices."""
    selected = {}
    for name, entry in topology.items():
        devtype = _field(entry, "DeviceInfo").get("type")
        if devtype not in TIERS:
            continue
        if devtype == "switch" and switches and name not in switches:
            continue
        if devtype == "server" and servers and name not in servers:
            continue
        if devtype == "cloud" and switches:
            peers = [val.get("device") for val in _field(entry, "topo").values() if isinstance(val, dict)]
            if not any(isinstance(peer, str) and peer in switches for peer in peers):
                continue
        if path is not None and name not in path["hops"] and not (devtype == "cloud" and _cloudOnPath(entry, path)):
            continue
        selected[str(name)] = devtype
    return selected


def _end(port, lag="", local=False):
    """One end of a physical link; local means the port name comes from the device itself (preferred for display)."""
    return {"port": str(port), "lag": str(lag or ""), "local": local}


def _physicalLinks(name, localPort, peer, remote):
    """Return [(ends, speed, alias, down)] for one topology entry; WAN port-channels expand into their member links."""
    port = remote.get("port")
    down = remote.get("down") is True
    if not isinstance(port, dict):
        ends = {name: _end(localPort, remote.get("portchannel"), True), peer: _end(port, remote.get("remoteportchannel"))}
        return [(ends, _int(remote.get("bandwidth")), "", down)]
    # WAN peer entry: name is the cloud device, localPort the remote port, remote["localport"] the switch port.
    alias = str(port.get("isAlias", ""))
    switchPort = str(remote.get("localport") or "")
    members = remote.get("members") if isinstance(remote.get("members"), dict) else {}
    if members:
        membersDown = remote.get("membersdown") if isinstance(remote.get("membersdown"), list) else []
        return [({name: _end(localPort, localPort), peer: _end(member, switchPort, True)}, _int(speed), alias, member in membersDown) for member, speed in members.items()]
    return [({name: _end(localPort), peer: _end(switchPort, local=True)}, _int(remote.get("bandwidth")), alias, down)]


def _mergeLink(merged, ends, speed, alias, down):
    """Record one reported physical link, keeping the device's own port names, the highest speed and any down report."""
    link = merged.setdefault(frozenset((dev, _portKey(end["port"])) for dev, end in ends.items()), {"ends": ends, "speed": 0, "wan": alias, "down": False})
    for dev, end in ends.items():
        known = link["ends"][dev]
        if end["local"] and not known["local"]:
            known.update(port=end["port"], local=True)
        known["lag"] = known["lag"] or end["lag"]
    link["speed"] = max(link["speed"], speed)
    link["down"] = link["down"] or down


def _collectLinks(topology, devices):
    """Return {(devA, devB): [link]} for physical links whose both ends are selected.

    A link reported by both devices is merged even when they spell the ports differently (LLDP local vs remote names).
    """
    merged = {}
    for name in devices:
        for localPort, remote in _field(topology[name], "topo").items():
            if not isinstance(remote, dict):
                continue
            peer = remote.get("device")
            if not isinstance(peer, str) or peer == name or peer not in devices:
                continue
            for physical in _physicalLinks(name, str(localPort), peer, remote):
                _mergeLink(merged, *physical)
    pairs = {}
    for link in merged.values():
        pairs.setdefault(tuple(sorted(link["ends"])), []).append(link)
    return pairs


def _onPath(link, path):
    """Return True if the path uses this link: a port (or its port-channel) at either end is a hop, or it is the path's WAN link."""
    for dev, end in link["ends"].items():
        ports = path["hops"].get(dev, {})
        if _portKey(end["port"]) in ports or (end["lag"] and _portKey(end["lag"]) in ports):
            return True
    return bool(link["wan"]) and link["wan"] in path["aliases"]


def _linkText(link):
    """Describe one physical link: ends, speed (or down) and port-channels."""
    ends = [f"{dev}:{end['port']}" if end["port"] else dev for dev, end in sorted(link["ends"].items())]
    extras = [_linkState(link)] + sorted({end["lag"] for end in link["ends"].values() if end["lag"]})
    return f"{ends[0]} <-> {ends[1]} ({', '.join(extras)})"


def _bundleText(bundle):
    """Summarize port-channel members with down members last, e.g. "3 x 100G, 1 x down"."""
    counts = Counter(_linkState(link) for link in bundle)
    return ", ".join(f"{counts[state]} x {state}" for state in sorted(counts, key=lambda state: state == DOWN_LINK[1]))


def _orderTiers(devices, pairs):
    """Order switches by name, then WAN peers and servers by the mean position of their switches to limit crossings."""
    tiers = {tier: sorted(name for name, devtype in devices.items() if devtype == tier) for tier in TIERS}
    switchIndex = {name: idx for idx, name in enumerate(tiers["switch"])}
    neighbours = {}
    for left, right in pairs:
        neighbours.setdefault(left, []).append(right)
        neighbours.setdefault(right, []).append(left)

    def rank(name):
        positions = [switchIndex[peer] for peer in neighbours.get(name, []) if peer in switchIndex]
        return (sum(positions) / len(positions) if positions else len(switchIndex), name)

    tiers["cloud"].sort(key=rank)
    tiers["server"].sort(key=rank)
    return tiers


def _bundles(links):
    """Split one device pair's links into port-channel bundles and single links, in drawing order."""
    groups = {}
    for link in links:
        ends = sorted(link["ends"].items())
        lags = tuple(end["lag"] for _, end in ends)
        groups.setdefault(("lag", lags) if any(lags) else ("link", tuple(end["port"] for _, end in ends)), []).append(link)
    order = sorted(groups, key=lambda key: (key[0], [_natural(name) for name in key[1]]))
    return [sorted(groups[key], key=lambda link: [_natural(end["port"]) for _, end in sorted(link["ends"].items())]) for key in order]


def _memberOffsets(bundles):
    """Return (offset of every member line from the bundle centre, total bundle width)."""
    positions = []
    cursor = 0
    for bundle in bundles:
        for idx in range(len(bundle)):
            if positions:
                cursor += MEMBER_GAP if idx else LINK_GAP
            positions.append(cursor)
    return [pos - cursor / 2 for pos in positions], cursor


def _deviceStates(topology, devices, health):
    """Return {name: (state, issues)}: servers from their agent service states, switches from the last switch fetch."""
    out = {}
    for name, devtype in devices.items():
        if devtype == "server":
            entries = health["hosts"].get(name, [])
            issues = [f"{name}: {entry['service']} {entry['state']}" + (f" - {entry['detail']}" if entry["detail"] else "") for entry in entries if entry["state"] != "OK"]
            out[name] = (_worst(entry["state"] for entry in entries), issues or ([] if entries else [f"{name}: no agent service reports"]))
        elif devtype == "switch" and "errors" in _field(topology[name], "DeviceInfo"):
            errors = _int(_field(topology[name], "DeviceInfo").get("errors"))
            out[name] = ("FAILED", [f"{name}: last switch fetch failed ({errors} error{'' if errors == 1 else 's'})"]) if errors else ("OK", [])
    return out


def _sublabels(topology, devices, pairs, states):
    """Return {name: sublabel}: remote switch:port for WAN peers, otherwise link count and health."""
    linkCount = {}
    for (left, right), links in pairs.items():
        linkCount[left] = linkCount.get(left, 0) + len(links)
        linkCount[right] = linkCount.get(right, 0) + len(links)
    out = {}
    for name, devtype in devices.items():
        alias = _remoteAlias(topology[name]) if devtype == "cloud" else ""
        if alias:
            out[name] = ":".join(alias.split(":")[-2:])
            continue
        count = linkCount.get(name, 0)
        out[name] = _plural(count, "link") if count else "no links"
        if name in states:
            state = states[name][0]
            out[name] += f", agent {state}" if devtype == "server" else (", fetch error" if state == "FAILED" else ", OK")
    return out


def _rings(members, lags, bundle):
    """Return port-channel rings drawn across the member lines just outside both end nodes."""
    rings = []
    for tip, nxt, lag in ((0, 1, lags[0] or lags[1]), (-1, -2, lags[1] or lags[0])):
        tips = [points[tip] for points in members]
        dirX = (members[0][nxt][0] > tips[0][0]) - (members[0][nxt][0] < tips[0][0])
        dirY = (members[0][nxt][1] > tips[0][1]) - (members[0][nxt][1] < tips[0][1])
        spanX = max(point[0] for point in tips) - min(point[0] for point in tips)
        spanY = max(point[1] for point in tips) - min(point[1] for point in tips)
        rings.append(
            {
                "cx": sum(point[0] for point in tips) / len(tips) + dirX * RING_DIST,
                "cy": sum(point[1] for point in tips) / len(tips) + dirY * RING_DIST,
                "rx": spanX / 2 + 4 if dirX == 0 else 3.5,
                "ry": spanY / 2 + 4 if dirY == 0 else 3.5,
                "title": f"{lag}: {_bundleText(bundle)}",
            }
        )
    return rings


def _edgeDrawing(route, bundles, offsets, path):
    """Return the SiteRM drawing of one device pair: a line per physical link along the route, plus port-channel rings."""
    lines = []
    rings = []
    members = iter(offsets)
    for bundle in bundles:
        points = []
        for link in bundle:
            points.append(offsetPolyline(route["centreline"], next(members)))
            cls, _, width = DOWN_LINK if link["down"] else speedClass(link["speed"])
            lines.append({"d": svgPath(points[-1]), "cls": cls, "width": width, "title": _linkText(link), "off": path is not None and not _onPath(link, path)})
        lags = [bundle[0]["ends"][dev]["lag"] for dev in (route["upper"], route["lower"])]
        if any(lags):
            rings.extend(_rings(points, lags, bundle))
    return {"lines": lines, "rings": rings}


def _components(tiers, layout, sublabels):
    """Return ({name: id}, Archify components) placed by the layout."""
    ids = {}
    components = []
    for tier in TIERS:
        for idx, name in enumerate(tiers[tier]):
            ids[name] = f"{tier}{idx}"
            comp = {"id": ids[name], "type": COMPONENT_TYPES[tier], "label": name, "sublabel": sublabels[name], "pos": layout["nodes"][name], "size": [layout["width"], NODE_H]}
            components.append(comp)
    return ids, components


def _healthMarks(ids, layout, states):
    """Return status marks for the node overlay: component id, state, box and tooltip."""
    marks = []
    for name, (state, issues) in sorted(states.items()):
        posX, posY = layout["nodes"][name]
        title = "; ".join(issues) if issues else f"{name}: {state}"
        marks.append({"id": ids[name], "state": state, "x": posX + layout["width"] - 10, "y": posY + 10, "title": title})
    return marks


def _healthCards(states, health):
    """Return the frontend services and device issues cards."""
    frontend = health["frontend"]
    items = [f"{entry['service']}: {entry['state']}" + (f" - {entry['detail']}" if entry["detail"] else "") for entry in frontend]
    cards = [{"dot": STATE_DOTS[_worst(entry["state"] for entry in frontend)], "title": "Frontend services", "items": items or ["no frontend service reports"]}]
    issues = sorted(issue for _, deviceIssues in states.values() for issue in deviceIssues)
    if issues:
        worst = _worst(state for state, deviceIssues in states.values() if deviceIssues)
        cards.append({"dot": STATE_DOTS[worst], "title": "Device issues", "items": _capItems(issues)})
    return cards


def _pathCard(path):
    """Return the card describing the selected path and its hops."""
    items = [f"Connection: {path['id']}", f"State: {path['state'] or 'unknown'}", f"VLANs: {', '.join(str(vlan) for vlan in _pathVlans(path)) or 'none'}"]
    for device, ports in sorted(path["hops"].items()):
        for hop in sorted(ports.values(), key=lambda hop: _natural(hop["port"])):
            items.append(f"{device}:{hop['port']} vlan {hop['vlan'] if hop['vlan'] is not None else '-'} {hop['state']}".rstrip())
    return {"dot": "cyan", "title": "Path", "items": _capItems(items)}


def _cards(topology, tiers, pairs, extras):
    """Return legend cards, the extra (health, path) cards, then every physical link and WAN peer alias."""
    speedItems = [label for _, _, label, _ in SPEED_CLASSES] + [UNKNOWN_SPEED[1], DOWN_LINK[1], "port-channel (ring)"]
    cards = [{"dot": "slate", "title": SPEED_CARD, "items": speedItems}]
    if extras["health"]:
        cards.append({"dot": "slate", "title": HEALTH_CARD, "items": [STATE_LEGEND[state] for state in STATES]})
    if extras["path"] is not None:
        cards.append(_pathCard(extras["path"]))
    cards.extend(extras["health"])
    linkItems = sorted((_linkText(link) for links in pairs.values() for link in links), key=_natural)
    if linkItems:
        cards.append({"dot": "slate", "title": "Links", "items": _capItems(linkItems)})
    wanItems = [f"{name}: {_remoteAlias(topology[name])}" for name in tiers["cloud"]]
    if wanItems:
        cards.append({"dot": "amber", "title": "WAN peers", "items": _capItems(wanItems)})
    return cards


def _subtitle(tiers, health, path):
    """Return the diagram subtitle: device counts, frontend health and the selected path."""
    parts = [", ".join(_plural(len(tiers[tier]), noun) for tier, noun in (("switch", "switch"), ("server", "server"), ("cloud", "WAN peer")))]
    if health is not None:
        parts.append(f"frontend {_worst(entry['state'] for entry in health['frontend'])}")
    if path is not None:
        parts.append(f"path VLAN {', '.join(str(vlan) for vlan in _pathVlans(path)) or '-'} ({path['state'] or 'unknown'})")
    return "; ".join(parts)


def _layoutPairs(tiers, pairs, sublabels):
    """Bundle each device pair's links and lay out the diagram; returns {"layout", "bundles", "offsets"} with bundles in route order."""
    pairKeys = sorted(pairs)
    bundles = [_bundles(pairs[key]) for key in pairKeys]
    offsets = [_memberOffsets(groups) for groups in bundles]
    routed = [{"a": key[0], "b": key[1], "width": width} for key, (_, width) in zip(pairKeys, offsets)]
    layout = layoutDiagram([(tier, tiers[tier]) for tier in TIERS], routed, _labelWidth(list(sublabels), list(sublabels.values())))
    return {"layout": layout, "bundles": bundles, "offsets": [memberOffsets for memberOffsets, _ in offsets]}


def _connections(ids, drawing, path):
    """Return (logical Archify connections, {connection id: SiteRM drawing}) for every routed device pair."""
    connections = []
    edges = {}
    for idx, route in enumerate(drawing["layout"]["routes"]):
        connections.append({"id": f"e{idx}", "from": ids[route["upper"]], "to": ids[route["lower"]], **route["logical"]})
        edges[f"e{idx}"] = _edgeDrawing(route, drawing["bundles"][idx], drawing["offsets"][idx], path)
    return connections, edges


def _siteModel(topology, filters, health):
    """Select devices and links, order the tiers and derive device health and sublabels."""
    devices = _selectDevices(topology, set(filters.get("switch") or []), set(filters.get("server") or []), filters.get("path"))
    pairs = _collectLinks(topology, devices)
    states = _deviceStates(topology, devices, health) if health is not None else {}
    return {"pairs": pairs, "tiers": _orderTiers(devices, pairs), "states": states, "sublabels": _sublabels(topology, devices, pairs, states)}


def buildDiagram(topology, sitename, filters=None, health=None, cards=True):
    """Build {"ir": Archify IR, "edges": SiteRM link drawings, "marks": health marks} from topology.json content.

    filters may hold "switch"/"server" name lists and a "path" from activePath; health comes from summarizeServiceStates.
    cards=False leaves out the legend, health, path and link cards (graph only, for embedding).
    """
    topology = topology if isinstance(topology, dict) else {}
    filters = filters or {}
    model = _siteModel(topology, filters, health)
    drawing = _layoutPairs(model["tiers"], model["pairs"], model["sublabels"])
    ids, components = _components(model["tiers"], drawing["layout"], model["sublabels"])
    connections, edges = _connections(ids, drawing, filters.get("path"))
    archIR = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {"title": f"{sitename} topology", "subtitle": _subtitle(model["tiers"], health, filters.get("path")), "output": "topology.html", "legend": LEGEND},
        "components": components,
    }
    if connections:
        archIR["connections"] = connections
    if cards:
        extras = {"health": _healthCards(model["states"], health) if health is not None else [], "path": filters.get("path")}
        archIR["cards"] = _cards(topology, model["tiers"], model["pairs"], extras)
    return {"ir": archIR, "edges": edges, "marks": _healthMarks(ids, drawing["layout"], model["states"])}


def _styles(diagram):
    """Return the CSS for link speeds, port-channel rings, off-path links, health marks and legend swatches."""
    dark = " ".join(f"--st-{cls}: {colours[1]};" for cls, colours in SPEED_COLOURS.items())
    light = " ".join(f"--st-{cls}: {colours[0]};" for cls, colours in SPEED_COLOURS.items())
    rules = [
        f":root, html[data-theme='dark'] {{ {dark} }}",
        f"html[data-theme='light'] {{ {light} }}",
        "svg .st-link { fill: none; stroke-linecap: round; stroke-linejoin: round; }",
        "svg .st-sunknown { stroke: var(--text-dim); stroke-dasharray: 4 3; }",
        f"svg .st-{DOWN_LINK[0]} {{ stroke: {STATE_COLOURS['FAILED']}; stroke-dasharray: 1 5; }}",
        "svg .st-off { opacity: 0.22; }",
        "svg .st-lag { fill: var(--mask); stroke: var(--text-muted); stroke-width: 1; }",
        "svg .st-dot { stroke: var(--mask); stroke-width: 1.5; pointer-events: none; }",
        ".card li.st-legend { display: flex; align-items: center; gap: 0.5rem; padding-left: 0; }",
        ".card li.st-legend::before { display: none; }",
        ".st-swatch { flex: none; width: 24px; height: 0; border-top-style: solid; }",
        ".st-swatch.st-sunknown { border-top-style: dashed; border-color: var(--text-dim); }",
        f".st-swatch.st-{DOWN_LINK[0]} {{ border-top-style: dotted; border-color: {STATE_COLOURS['FAILED']}; border-top-width: {DOWN_LINK[2]}px; }}",
        ".st-ring { flex: none; width: 14px; height: 7px; border: 1px solid var(--text-muted); border-radius: 50%; }",
        ".st-state { flex: none; width: 9px; height: 9px; border-radius: 50%; }",
    ]
    for cls, _, _, width in SPEED_CLASSES:
        rules.append(f"svg .st-{cls} {{ stroke: var(--st-{cls}); }} .st-swatch.st-{cls} {{ border-color: var(--st-{cls}); border-top-width: {width}px; }}")
    rules.append(f".st-swatch.st-sunknown {{ border-top-width: {UNKNOWN_SPEED[2]}px; }}")
    for state, colour in STATE_COLOURS.items():
        nodes = sorted({mark["id"] for mark in diagram["marks"] if mark["state"] == state})
        rules.append(f".st-state-{state}, svg .st-dot-{state} {{ background: {colour}; fill: {colour}; }}")
        if nodes:
            rules.append(", ".join(f"#node-{node} > rect:not(.c-mask)" for node in nodes) + f" {{ stroke: {colour}; stroke-width: 2.5px; }}")
    return '<style id="siterm-archify">\n' + "\n".join(rules) + "\n</style>\n"


def _edgeMarkup(match, edges):
    """Replace one Archify edge with the SiteRM drawing for that device pair, keeping the attributes the viewer uses for focus."""
    attrs = " ".join(f'{key}="{val}"' for key, val in re.findall(r'(data-edge-(?:from|to|key|id))="([^"]*)"', match.group(0)))
    edge = edges[match.group(1)]
    parts = [f'<g data-siterm-link="{match.group(1)}">']
    for line in edge["lines"]:
        cls = f"st-link st-{line['cls']}" + (" st-off" if line["off"] else "")
        parts.append(f'<path {attrs} d="{line["d"]}" class="{cls}" stroke-width="{line["width"]}"><title>{html.escape(line["title"])}</title></path>')
    for ring in edge["rings"]:
        geometry = " ".join(f'{key}="{round(ring[key], 1):g}"' for key in ("cx", "cy", "rx", "ry"))
        parts.append(f'<ellipse {attrs} class="st-lag" {geometry}><title>{html.escape(ring["title"])}</title></ellipse>')
    parts.append("</g>")
    return "".join(parts)


def _legendList(title):
    """Return the swatch list that replaces the plain items of a legend card."""
    if title == SPEED_CARD:
        rows = [(f'<span class="st-swatch st-{cls}"></span>', label) for cls, _, label, _ in SPEED_CLASSES]
        rows += [(f'<span class="st-swatch st-{style[0]}"></span>', style[1]) for style in (UNKNOWN_SPEED, DOWN_LINK)]
        rows.append(('<span class="st-ring"></span>', "port-channel members"))
    else:
        rows = [(f'<span class="st-state st-state-{state}"></span>', STATE_LEGEND[state]) for state in STATES]
    return "<ul>" + "".join(f'<li class="st-legend">{swatch}{html.escape(label)}</li>' for swatch, label in rows) + "</ul>"


def _decorate(page, diagram):
    """Draw SiteRM links over Archify's logical edges and add styles, health marks and legend swatches.

    Archify validates and lays out one logical edge per device pair; anything not found in its output keeps Archify's own drawing.
    """
    edges = diagram["edges"]
    page = re.sub(
        r'<path data-edge-from="[^"]*" data-edge-to="[^"]*"[^>]*?\sdata-edge-id="(e\d+)"[^>]*/>', lambda match: _edgeMarkup(match, edges) if match.group(1) in edges else match.group(0), page
    )
    for title in (SPEED_CARD, HEALTH_CARD):
        page = re.sub(rf"(<h3>{re.escape(title)}</h3>\s*</div>\s*)<ul>.*?</ul>", lambda match, title=title: match.group(1) + _legendList(title), page, count=1, flags=re.DOTALL)
    marks = "".join(f'<circle class="st-dot st-dot-{mark["state"]}" cx="{mark["x"]:g}" cy="{mark["y"]:g}" r="4"><title>{html.escape(mark["title"])}</title></circle>' for mark in diagram["marks"])
    svgStart = page.find("<svg viewBox")
    svgEnd = page.find("</svg>", svgStart) if svgStart >= 0 else -1
    if marks and svgEnd >= 0:
        page = f'{page[:svgEnd]}<g data-siterm-health="">{marks}</g>{page[svgEnd:]}'
    return page.replace("</head>", _styles(diagram) + "</head>", 1)


def _renderUncached(ir, timeout):
    """Run the Archify CLI on the IR in a private temp dir and return the generated HTML."""
    if not os.path.isfile(ARCHIFY_CLI):
        raise ArchifyUnavailable(f"Archify CLI not found at {ARCHIFY_CLI}")
    with tempfile.TemporaryDirectory(prefix="siterm-archify-") as workdir:
        inPath = os.path.join(workdir, "topology.architecture.json")
        outPath = os.path.join(workdir, "topology.html")
        with open(inPath, "w", encoding="utf-8") as fd:
            json.dump(ir, fd)
        # Clean env: Archify reads ARCHIFY_* variables (quality profile, repo root) that must not leak in from the service.
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": workdir, "NO_COLOR": "1"}
        try:
            proc = subprocess.run(
                [NODE_BIN, ARCHIFY_CLI, "render", "architecture", inPath, outPath],
                cwd=workdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError as ex:
            raise ArchifyUnavailable(f"Node.js runtime '{NODE_BIN}' not found") from ex
        except subprocess.TimeoutExpired as ex:
            raise ArchifyRenderError(f"Archify render timed out after {timeout}s") from ex
        if proc.returncode != 0 or not os.path.isfile(outPath):
            output = (proc.stderr or proc.stdout or "").strip().replace(workdir, ".")
            raise ArchifyRenderError(output[-2000:] or f"Archify exited with code {proc.returncode}")
        with open(outPath, "r", encoding="utf-8") as fd:
            return fd.read()


def renderDiagramHTML(diagram, timeout=RENDER_TIMEOUT):
    """Return the Archify HTML for a buildDiagram result, reusing a small in-process cache keyed by the diagram content."""
    key = hashlib.sha256(json.dumps(diagram, sort_keys=True).encode("utf-8")).hexdigest()
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    page = _decorate(_renderUncached(diagram["ir"], timeout), diagram)
    with _CACHE_LOCK:
        _CACHE[key] = page
        _CACHE.move_to_end(key)
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
    return page
