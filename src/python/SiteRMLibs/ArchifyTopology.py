#!/usr/bin/env python3
"""
Build Archify architecture diagrams from SiteFE topology.json and render them with the Archify CLI.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/10/30
"""

import hashlib
import json
import math
import os
import subprocess
import tempfile
import threading
import unicodedata
from collections import OrderedDict

ARCHIFY_CLI = os.environ.get("SITERM_ARCHIFY_CLI", "/opt/archify/archify/bin/archify.mjs")
NODE_BIN = os.environ.get("SITERM_NODE_BIN", "node")
RENDER_TIMEOUT = 120
CACHE_SIZE = 16
MAX_CARD_ITEMS = 200

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
ORIGIN = (60, 100)
NODE_H = 60
MIN_NODE_W = 140
GAP_X = 60
ROW_GAP = 100
TIER_GAP = 150
MAX_PER_ROW = 8
# Parallel routes in one row gap / column gap get their own track so they do not draw on top of each other.
CHANNEL_TRACKS = (0, -8, 8, -16, 16, -24, 24)
LANE_TRACKS = (0, -8, 8, -16, 16)

_CACHE = OrderedDict()
_CACHE_LOCK = threading.Lock()


class ArchifyUnavailable(Exception):
    """Archify CLI or Node.js runtime is not installed."""


class ArchifyRenderError(Exception):
    """Archify rejected the diagram or failed to render it."""


def _textUnits(text):
    """Approximate Archify text units: wide (CJK) characters count twice."""
    return sum(2 if unicodedata.east_asian_width(char) in ("W", "F") else 1 for char in str(text))


def _nodeWidth(labels, sublabels):
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
    """Return entry[key] if it is a dict, else an empty dict (topology.json is untrusted)."""
    value = entry.get(key)
    return value if isinstance(value, dict) else {}


def _remoteAlias(entry):
    """Return the isAlias URN of a cloud (WAN peer) entry."""
    return str(_field(entry, "DeviceInfo").get("name", ""))


def _selectDevices(topology, switches, servers):
    """Return {name: devtype} for devices that pass the switch/server filters; WAN peers follow their switch."""
    selected = {}
    for name, entry in topology.items():
        if not isinstance(entry, dict):
            continue
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
        selected[str(name)] = devtype
    return selected


def _linkText(name, localPort, peer, remotePort):
    """Describe one physical link; both LLDP directions produce the same text."""
    if isinstance(remotePort, dict):
        return f"{peer} <-> {name} ({remotePort.get('isAlias', localPort)})"
    left, right = sorted([(name, str(localPort)), (peer, str(remotePort))])
    return f"{left[0]}:{left[1]} <-> {right[0]}:{right[1]}"


def _collectLinks(topology, devices):
    """Return {(upper, lower): set(link texts)} for links whose both ends are selected devices."""
    links = {}
    for name in devices:
        for localPort, remote in _field(topology[name], "topo").items():
            if not isinstance(remote, dict):
                continue
            peer = remote.get("device")
            if not isinstance(peer, str) or peer == name or peer not in devices:
                continue
            pair = tuple(sorted((name, peer), key=lambda dev: (TIERS.index(devices[dev]), dev)))
            links.setdefault(pair, set()).add(_linkText(name, localPort, peer, remote.get("port")))
    return links


def _orderTiers(devices, links):
    """Order switches by name, then WAN peers and servers by the mean position of their switches to limit crossings."""
    tiers = {tier: sorted(name for name, devtype in devices.items() if devtype == tier) for tier in TIERS}
    switchIndex = {name: idx for idx, name in enumerate(tiers["switch"])}
    neighbours = {}
    for left, right in links:
        neighbours.setdefault(left, []).append(right)
        neighbours.setdefault(right, []).append(left)

    def rank(name):
        positions = [switchIndex[peer] for peer in neighbours.get(name, []) if peer in switchIndex]
        return (sum(positions) / len(positions) if positions else len(switchIndex), name)

    tiers["cloud"].sort(key=rank)
    tiers["server"].sort(key=rank)
    return tiers


def _sublabels(topology, devices, links):
    """Return {name: sublabel}: remote switch:port for WAN peers, otherwise the number of drawn links."""
    linkCount = {}
    for (left, right), texts in links.items():
        linkCount[left] = linkCount.get(left, 0) + len(texts)
        linkCount[right] = linkCount.get(right, 0) + len(texts)
    out = {}
    for name, devtype in devices.items():
        alias = _remoteAlias(topology[name]) if devtype == "cloud" else ""
        count = linkCount.get(name, 0)
        if alias:
            out[name] = ":".join(alias.split(":")[-2:])
        else:
            out[name] = f"{count} link{'' if count == 1 else 's'}" if count else "no links"
    return out


def _placeComponents(tiers, sublabels):
    """Place tiers top to bottom on one shared column grid (uniform width, rows wrapped at MAX_PER_ROW and centred by whole columns).

    Returns ({name: id}, components, layout); layout holds the grid so routes can use the empty row and column gaps.
    """
    width = _nodeWidth(list(sublabels), list(sublabels.values()))
    cols = min(max(len(tierNames) for tierNames in tiers.values()), MAX_PER_ROW)
    layout = {"width": width, "pitch": width + GAP_X, "cols": cols, "rows": [], "cells": {}}
    ids = {}
    components = []
    for tier in TIERS:
        tierNames = tiers[tier]
        ids.update({name: f"{tier}{idx}" for idx, name in enumerate(tierNames)})
        for start in range(0, len(tierNames), MAX_PER_ROW):
            row = tierNames[start : start + MAX_PER_ROW]
            rows = layout["rows"]
            rows.append(rows[-1] + NODE_H + (ROW_GAP if start else TIER_GAP) if rows else ORIGIN[1])
            firstCol = (cols - len(row)) // 2
            for idx, name in enumerate(row):
                layout["cells"][name] = (len(rows) - 1, firstCol + idx)
                components.append(
                    {
                        "id": ids[name],
                        "type": COMPONENT_TYPES[tier],
                        "label": name,
                        "sublabel": sublabels[name],
                        "pos": [ORIGIN[0] + (firstCol + idx) * layout["pitch"], rows[-1]],
                        "size": [width, NODE_H],
                    }
                )
    return ids, components, layout


def _track(tracks, key, offsets):
    """Return the next track offset for a shared row or column gap."""
    count = tracks.get(key, 0)
    tracks[key] = count + 1
    return offsets[count % len(offsets)]


def _channelY(layout, row):
    """Return the centre y of the empty gap below row (row -1 is the margin above the first row)."""
    rows = layout["rows"]
    top = rows[row] + NODE_H if row >= 0 else 0
    bottom = rows[row + 1] if row + 1 < len(rows) else top + ROW_GAP
    return (top + bottom) / 2


def _route(layout, upper, lower, tracks):
    """Return route fields for an orthogonal path that only runs through empty row gaps and column gaps.

    Archify anchors authored routes at side centres, so via points can start and end on the node centre lines.
    """
    (upRow, upCol), (lowRow, lowCol) = layout["cells"][upper], layout["cells"][lower]
    upX = ORIGIN[0] + upCol * layout["pitch"] + layout["width"] / 2
    lowX = ORIGIN[0] + lowCol * layout["pitch"] + layout["width"] / 2
    if upRow == lowRow:
        chanY = _channelY(layout, upRow - 1) + _track(tracks, ("row", upRow - 1), CHANNEL_TRACKS)
        return {"fromSide": "top", "toSide": "top", "via": [[upX, chanY], [lowX, chanY]]}
    if lowRow == upRow + 1 and upX == lowX:
        return {"fromSide": "bottom", "toSide": "top", "route": "straight"}
    firstY = _channelY(layout, upRow) + _track(tracks, ("row", upRow), CHANNEL_TRACKS)
    if lowRow == upRow + 1:
        return {"fromSide": "bottom", "toSide": "top", "via": [[upX, firstY], [lowX, firstY]]}
    # Drop through the column gap beside the lower node, on the side facing the upper node; never use an outer edge.
    laneCol = lowCol + 1 if upX > lowX or (upX == lowX and lowCol == 0) else lowCol
    laneX = ORIGIN[0] + laneCol * layout["pitch"] - GAP_X / 2
    if 0 < laneCol < layout["cols"]:
        laneX += _track(tracks, ("col", laneCol), LANE_TRACKS)
    lastY = _channelY(layout, lowRow - 1) + _track(tracks, ("row", lowRow - 1), CHANNEL_TRACKS)
    return {"fromSide": "bottom", "toSide": "top", "via": [[upX, firstY], [laneX, firstY], [laneX, lastY], [lowX, lastY]]}


def _connections(ids, devices, links, layout):
    """Return one Archify connection per linked device pair, upper row to lower; WAN links are emphasised."""
    connections = []
    tracks = {}
    for left, right in sorted(links, key=lambda pair: (layout["cells"][pair[0]], layout["cells"][pair[1]])):
        upper, lower = sorted((left, right), key=lambda name: layout["cells"][name])
        conn = {"from": ids[upper], "to": ids[lower]}
        if "cloud" in (devices[upper], devices[lower]):
            conn["variant"] = "emphasis"
        conn.update(_route(layout, upper, lower, tracks))
        connections.append(conn)
    return connections


def _cards(topology, tiers, links):
    """Return Archify cards listing every physical link and WAN peer alias."""
    cards = []
    linkItems = sorted(text for texts in links.values() for text in texts)
    if linkItems:
        cards.append({"dot": "slate", "title": "Links", "items": _capItems(linkItems)})
    wanItems = [f"{name}: {_remoteAlias(topology[name])}" for name in tiers["cloud"]]
    if wanItems:
        cards.append({"dot": "amber", "title": "WAN peers", "items": _capItems(wanItems)})
    return cards


def buildArchifyIR(topology, sitename, switches=None, servers=None):
    """Build an Archify architecture IR from topology.json content, optionally filtered by switch/server names."""
    topology = topology if isinstance(topology, dict) else {}
    devices = _selectDevices(topology, set(switches or []), set(servers or []))
    links = _collectLinks(topology, devices)
    tiers = _orderTiers(devices, links)
    ids, components, layout = _placeComponents(tiers, _sublabels(topology, devices, links))
    archIR = {
        "schema_version": 1,
        "diagram_type": "architecture",
        "meta": {
            "title": f"{sitename} topology",
            "subtitle": f"{len(tiers['switch'])} switches, {len(tiers['server'])} servers, {len(tiers['cloud'])} WAN peers",
            "output": "topology.html",
            "legend": LEGEND,
        },
        "components": components,
    }
    connections = _connections(ids, devices, links, layout)
    if connections:
        archIR["connections"] = connections
    cards = _cards(topology, tiers, links)
    if cards:
        archIR["cards"] = cards
    return archIR


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


def renderArchifyHTML(ir, timeout=RENDER_TIMEOUT):
    """Return Archify HTML for the IR, reusing a small in-process cache keyed by the IR content."""
    key = hashlib.sha256(json.dumps(ir, sort_keys=True).encode("utf-8")).hexdigest()
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    html = _renderUncached(ir, timeout)
    with _CACHE_LOCK:
        _CACHE[key] = html
        _CACHE.move_to_end(key)
        while len(_CACHE) > CACHE_SIZE:
            _CACHE.popitem(last=False)
    return html
