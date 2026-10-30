#!/usr/bin/env python3
"""
Orthogonal layout for Archify topology diagrams: node grid, spread link ports and non-overlapping channel and lane tracks.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/10/30
"""

import heapq

ORIGIN_X = 60
TOP_MARGIN = 100
NODE_H = 60
MAX_NODE_W = 360
MIN_GAP_X = 60
MIN_ROW_GAP = 100
MIN_TIER_GAP = 150
MAX_PER_ROW = 8
# Link ends keep this far from node corners; bundles on one node side keep SLOT_GAP between them.
PORT_GUTTER = 16
SIDE_GUTTER = 12
SLOT_GAP = 14
# Parallel tracks in a row channel or column lane keep TRACK_GAP between bundles and MARGIN from the nodes.
TRACK_GAP = 6
CHANNEL_MARGIN = 14
LANE_MARGIN = 12
CORNER_RADIUS = 6


def _grid(tierRows):
    """Assign (row, col) cells: tiers top to bottom, rows wrapped at MAX_PER_ROW and centred by whole columns."""
    cols = min(max((len(names) for _, names in tierRows), default=0), MAX_PER_ROW)
    cells = {}
    rowTiers = []
    for tier, names in tierRows:
        for start in range(0, len(names), MAX_PER_ROW):
            row = names[start : start + MAX_PER_ROW]
            rowTiers.append(tier)
            firstCol = (cols - len(row)) // 2
            for idx, name in enumerate(row):
                cells[name] = (len(rowTiers) - 1, firstCol + idx)
    return cols, cells, rowTiers


def _routeKind(cells, pair):
    """Classify one device pair: side (same-row neighbours), over (same row), down (next row) or lane (rows further apart)."""
    upper, lower = sorted((pair["a"], pair["b"]), key=lambda name: (cells[name], name))
    (upRow, upCol), (lowRow, lowCol) = cells[upper], cells[lower]
    route = {"upper": upper, "lower": lower, "width": pair["width"], "fromSide": "bottom", "toSide": "top"}
    if upRow == lowRow:
        sideFits = pair["width"] <= NODE_H - 2 * SIDE_GUTTER
        if lowCol == upCol + 1 and sideFits:
            route.update(kind="side", fromSide="right", toSide="left")
        else:
            route.update(kind="over", fromSide="top", toSide="top")
    elif lowRow == upRow + 1:
        route["kind"] = "down"
    else:
        # Drop through the column gap beside the lower node, on the side facing the upper node; never an outer edge.
        route.update(kind="lane", lane=lowCol + 1 if upCol > lowCol or (upCol == lowCol and lowCol == 0) else lowCol)
    return route


def _spread(count, widths, extent, gutter):
    """Return centre offsets (from the side start) for bundles of the given widths spread along one node side."""
    usable = extent - 2 * gutter
    gap = SLOT_GAP
    if count > 1:
        gap = min(SLOT_GAP, (usable - sum(widths)) / (count - 1))
    span = sum(widths) + gap * (count - 1)
    cursor = gutter + (usable - span) / 2
    out = []
    for width in widths:
        out.append(cursor + width / 2)
        cursor += width + gap
    return out


class _Layout:
    """Node positions, port slots and track assignment for one diagram."""

    def __init__(self, tierRows, pairs, labelWidth):
        _, self.cells, self.rowTiers = _grid(tierRows)
        self.routes = [_routeKind(self.cells, pair) for pair in pairs]
        self.slots = {}
        stacks = {}
        lanes = {}
        for idx, route in enumerate(self.routes):
            for end, name, side in (("upper", route["upper"], route["fromSide"]), ("lower", route["lower"], route["toSide"])):
                if side in ("left", "right"):
                    self.slots[(idx, end)] = NODE_H / 2
                    continue
                # A node's bottom side and the top side of the node below it face the same channel: spread their ends together.
                row, col = self.cells[name]
                stacks.setdefault((row if side == "bottom" else row - 1, col), {}).setdefault(idx, []).append(end)
            if route["kind"] == "lane":
                lanes.setdefault(route["lane"], []).append(idx)
        self.width = max(labelWidth, min(MAX_NODE_W, max((self._span(items) + 2 * PORT_GUTTER for items in stacks.values()), default=0)))
        need = max((sum(self.routes[idx]["width"] for idx in members) + TRACK_GAP * (len(members) - 1) for members in lanes.values()), default=0)
        self.gapX = max(MIN_GAP_X, need + 2 * LANE_MARGIN)
        self._placeSlots(stacks)
        self._placeLanes(lanes)
        self.rowTops = []
        self._placeRows()

    def _span(self, items):
        """Width needed to spread the given routes' bundles along one node side."""
        return sum(self.routes[idx]["width"] for idx in items) + SLOT_GAP * (len(items) - 1)

    def colX(self, col):
        """Left x of a grid column."""
        return ORIGIN_X + col * (self.width + self.gapX)

    def centreX(self, name):
        """Centre x of a node."""
        return self.colX(self.cells[name][1]) + self.width / 2

    def laneX(self, lane):
        """Centre x of the column gap left of a column."""
        return self.colX(lane) - self.gapX / 2

    def _heading(self, idx, ends):
        """Return the x a route heads to after leaving a node side (orders slots so neighbouring links do not cross)."""
        route = self.routes[idx]
        if len(ends) == 2:
            # Straight drop between stacked nodes: both ends share one slot.
            return (self.centreX(route["upper"]), self.cells[route["upper"]], route["upper"])
        other = route["lower"] if ends[0] == "upper" else route["upper"]
        if route["kind"] == "lane":
            return (self.laneX(route["lane"]), self.cells[other], other)
        return (self.centreX(other), self.cells[other], other)

    def _placeSlots(self, stacks):
        """Spread the bundles meeting each column of a row channel along the node width, ordered by where they head."""
        for (_, col), items in stacks.items():
            order = sorted(items, key=lambda idx, items=items: self._heading(idx, items[idx]))
            offsets = _spread(len(order), [self.routes[idx]["width"] for idx in order], self.width, PORT_GUTTER)
            for idx, offset in zip(order, offsets):
                for end in items[idx]:
                    self.slots[(idx, end)] = self.colX(col) + offset

    def _placeLanes(self, lanes):
        """Give every route through a column gap its own vertical track, centred in the gap."""
        for lane, members in lanes.items():
            members = sorted(members, key=lambda idx: (self.cells[self.routes[idx]["upper"]], self.slots[(idx, "upper")]))
            widths = [self.routes[idx]["width"] for idx in members]
            span = sum(widths) + TRACK_GAP * (len(members) - 1)
            cursor = self.laneX(lane) - span / 2
            for idx, width in zip(members, widths):
                self.routes[idx]["laneX"] = cursor + width / 2
                cursor += width + TRACK_GAP

    def _segments(self):
        """Return {channel row: [horizontal segment]}; channel r is the gap below row r (-1 is the top margin)."""
        channels = {}

        def add(channel, idx, field, start, end):
            width = self.routes[idx]["width"]
            # Rightward runs leaving further right go higher, leftward runs leaving further left go higher: no crossings at the source.
            key = (0, -start if end > start else start)
            channels.setdefault(channel, []).append({"route": idx, "field": field, "width": width, "key": key, "above": [(start, width)], "below": [(end, width)]})

        for idx, route in enumerate(self.routes):
            upRow, lowRow = self.cells[route["upper"]][0], self.cells[route["lower"]][0]
            start, end = self.slots[(idx, "upper")], self.slots[(idx, "lower")]
            if route["kind"] == "down" and start != end:
                add(upRow, idx, "y", start, end)
            elif route["kind"] == "lane":
                add(upRow, idx, "y", start, route["laneX"])
                add(lowRow - 1, idx, "y2", route["laneX"], end)
            elif route["kind"] == "over":
                # Both ends rise from the row below; wider spans go higher so nested spans do not cross them.
                seg = {"route": idx, "field": "y", "width": route["width"], "key": (1, -abs(end - start)), "above": [], "below": [(start, route["width"]), (end, route["width"])]}
                channels.setdefault(upRow - 1, []).append(seg)
        return channels

    def _placeRows(self):
        """Size each row channel for its tracks, then fix row tops and absolute track positions."""
        channels = self._segments()
        tracks = {channel: _assignTracks(segments) for channel, segments in channels.items()}
        for row, tier in enumerate(self.rowTiers):
            minGap = TOP_MARGIN if row == 0 else (MIN_ROW_GAP if tier == self.rowTiers[row - 1] else MIN_TIER_GAP)
            height = max(minGap, tracks.get(row - 1, ({}, 0))[1])
            self.rowTops.append(height if row == 0 else self.rowTops[-1] + NODE_H + height)
        for channel, segments in channels.items():
            offsets, need = tracks[channel]
            top = self.rowTops[channel] + NODE_H if channel >= 0 else 0
            base = top + (self.rowTops[channel + 1] - top - need) / 2
            for pos, seg in enumerate(segments):
                self.routes[seg["route"]][seg["field"]] = base + offsets[pos]

    def nodeBox(self, name):
        """Return (x, y) of a node's top-left corner."""
        row, col = self.cells[name]
        return self.colX(col), self.rowTops[row]

    def centreline(self, idx):
        """Return the centre polyline of a route from the upper node side to the lower node side."""
        route = self.routes[idx]
        (upX, upY), (lowX, lowY) = self.nodeBox(route["upper"]), self.nodeBox(route["lower"])
        start, end = self.slots[(idx, "upper")], self.slots[(idx, "lower")]
        if route["kind"] == "side":
            return [[upX + self.width, upY + start], [lowX, lowY + end]]
        if route["kind"] == "over":
            return [[start, upY], [start, route["y"]], [end, route["y"]], [end, lowY]]
        if route["kind"] == "lane":
            laneX = route["laneX"]
            return [[start, upY + NODE_H], [start, route["y"]], [laneX, route["y"]], [laneX, route["y2"]], [end, route["y2"]], [end, lowY]]
        if start == end:
            return [[start, upY + NODE_H], [end, lowY]]
        return [[start, upY + NODE_H], [start, route["y"]], [end, route["y"]], [end, lowY]]

    def logical(self, idx):
        """Return Archify connection route fields: the same channels, anchored at side centres as Archify draws authored routes."""
        route = self.routes[idx]
        out = {"fromSide": route["fromSide"], "toSide": route["toSide"]}
        upX, lowX = self.centreX(route["upper"]), self.centreX(route["lower"])
        if route["kind"] == "side" or (route["kind"] == "down" and upX == lowX):
            out["route"] = "straight"
        elif route["kind"] == "lane":
            out["via"] = [[upX, route["y"]], [route["laneX"], route["y"]], [route["laneX"], route["y2"]], [lowX, route["y2"]]]
        else:
            out["via"] = [[upX, route["y"]], [lowX, route["y"]]]
        return out


def _overlaps(left, right):
    """Return True if two vertical runs given as (x, bundle width) lists share any x, allowing for TRACK_GAP."""
    for leftX, leftW in left:
        for rightX, rightW in right:
            if abs(leftX - rightX) < (leftW + rightW + TRACK_GAP) / 2:
                return True
    return False


def _assignTracks(segments):
    """Order one channel's horizontal segments top to bottom and return (offset per segment, channel height needed).

    A segment whose vertical run comes from above must sit above any segment whose run goes below at the same x,
    otherwise the two runs would draw on top of each other; ties follow each segment's key to limit crossings.
    """
    after = [[j for j, lower in enumerate(segments) if i != j and _overlaps(upper["above"], lower["below"])] for i, upper in enumerate(segments)]
    indegree = [0] * len(segments)
    for successors in after:
        for j in successors:
            indegree[j] += 1
    heap = [(seg["key"], i) for i, seg in enumerate(segments) if not indegree[i]]
    heapq.heapify(heap)
    order = []
    placed = set()
    while len(order) < len(segments):
        if heap:
            _, idx = heapq.heappop(heap)
            if idx in placed:
                continue
        else:
            # Conflicting constraints (a cycle): release the best remaining segment.
            idx = min((seg["key"], i) for i, seg in enumerate(segments) if i not in placed)[1]
        placed.add(idx)
        order.append(idx)
        for j in after[idx]:
            indegree[j] -= 1
            if indegree[j] == 0 and j not in placed:
                heapq.heappush(heap, (segments[j]["key"], j))
    offsets = {}
    cursor = CHANNEL_MARGIN
    for idx in order:
        offsets[idx] = cursor + segments[idx]["width"] / 2
        cursor += segments[idx]["width"] + TRACK_GAP
    return offsets, cursor - TRACK_GAP + CHANNEL_MARGIN


def layoutDiagram(tierRows, pairs, labelWidth):
    """Place nodes on a shared column grid and route every device pair through empty row channels and column lanes.

    Returns {"width", "height", "nodes": {name: [x, y]}, "routes": [{"upper", "lower", "centreline", "logical"}]} with routes in pair order.
    """
    layout = _Layout(tierRows, pairs, labelWidth)
    routes = []
    for idx, route in enumerate(layout.routes):
        routes.append({"upper": route["upper"], "lower": route["lower"], "centreline": layout.centreline(idx), "logical": layout.logical(idx)})
    return {"width": layout.width, "height": NODE_H, "nodes": {name: list(layout.nodeBox(name)) for name in layout.cells}, "routes": routes}


def _simplify(points):
    """Drop repeated and collinear points from an orthogonal polyline."""
    out = []
    for point in points:
        if out and out[-1] == point:
            continue
        if len(out) >= 2 and (out[-2][0] == out[-1][0] == point[0] or out[-2][1] == out[-1][1] == point[1]):
            out[-1] = point
            continue
        out.append(point)
    return out


def _sign(value):
    """Return -1, 0 or 1."""
    return (value > 0) - (value < 0)


def offsetPolyline(points, offset):
    """Shift an orthogonal polyline sideways by offset along each segment's right-hand normal, keeping corners square."""
    points = _simplify(points)
    normals = []
    for start, end in zip(points, points[1:]):
        dirX, dirY = _sign(end[0] - start[0]), _sign(end[1] - start[1])
        normals.append((-dirY * offset, dirX * offset))
    out = [[points[0][0] + normals[0][0], points[0][1] + normals[0][1]]]
    for idx in range(1, len(points) - 1):
        before, after = normals[idx - 1], normals[idx]
        # One of the two segments is vertical (moves x) and the other horizontal (moves y): the corner takes both shifts.
        out.append([points[idx][0] + before[0] + after[0], points[idx][1] + before[1] + after[1]])
    out.append([points[-1][0] + normals[-1][0], points[-1][1] + normals[-1][1]])
    return out


def _num(value):
    """Format a coordinate compactly."""
    return f"{round(value, 1):g}"


def svgPath(points, radius=CORNER_RADIUS):
    """Return an SVG path with rounded corners for an orthogonal polyline."""
    points = _simplify(points)
    parts = [f"M {_num(points[0][0])} {_num(points[0][1])}"]
    for prev, corner, nxt in zip(points, points[1:], points[2:]):
        inLen = abs(corner[0] - prev[0]) + abs(corner[1] - prev[1])
        outLen = abs(nxt[0] - corner[0]) + abs(nxt[1] - corner[1])
        rad = min(radius, inLen / 2, outLen / 2)
        inDir = (_sign(corner[0] - prev[0]), _sign(corner[1] - prev[1]))
        outDir = (_sign(nxt[0] - corner[0]), _sign(nxt[1] - corner[1]))
        parts.append(f"L {_num(corner[0] - inDir[0] * rad)} {_num(corner[1] - inDir[1] * rad)}")
        parts.append(f"Q {_num(corner[0])} {_num(corner[1])} {_num(corner[0] + outDir[0] * rad)} {_num(corner[1] + outDir[1] * rad)}")
    parts.append(f"L {_num(points[-1][0])} {_num(points[-1][1])}")
    return " ".join(parts)
