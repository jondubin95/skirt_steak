"""Event graph, compare, covers. Tier A1. Stdlib only."""

from __future__ import annotations

from dataclasses import dataclass, field

from doctor.ids import compare_ids, paragraph_index, scene_of

BEFORE = "BEFORE"
AFTER = "AFTER"
SAME = "SAME"
UNKNOWN = "UNKNOWN"
YES = "YES"
NO = "NO"

OFFLINE_KINDS = {"flashback", "flash_forward"}


@dataclass
class SceneNode:
    scene_id: str
    anchor_kind: str | None = None
    uncertain: bool = False

    @property
    def offline(self) -> bool:
        return self.anchor_kind in OFFLINE_KINDS

    @property
    def mainline(self) -> bool:
        return not self.offline and not self.uncertain


@dataclass
class Graph:
    scenes: list[SceneNode]
    events: list[str]
    confirmed_before: list[tuple[str, str]]
    same_pairs: list[tuple[str, str]]
    default_before: list[tuple[str, str]] = field(default_factory=list)
    dropped_defaults: list[tuple[str, str]] = field(default_factory=list)
    contradicted: set[str] = field(default_factory=set)
    uncertain_nodes: set[str] = field(default_factory=set)
    parent: dict[str, str] = field(default_factory=dict)
    adj: dict[str, set[str]] = field(default_factory=dict)

    def nodes(self) -> list[str]:
        return [scene.scene_id for scene in self.scenes] + list(self.events)

    def find(self, node: str) -> str:
        self.parent.setdefault(node, node)
        if self.parent[node] != node:
            self.parent[node] = self.find(self.parent[node])
        return self.parent[node]

    def scene_paragraphs(self) -> list[str]:
        return list(getattr(self, "paragraph_ids", []))


def _tarjan(nodes: list[str], adj: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    stack: list[str] = []
    onstack: set[str] = set()
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strong(node: str) -> None:
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        onstack.add(node)
        for nxt in adj.get(node, ()):
            if nxt not in indices:
                strong(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in onstack:
                low[node] = min(low[node], indices[nxt])
        if low[node] == indices[node]:
            comp: list[str] = []
            while True:
                top = stack.pop()
                onstack.discard(top)
                comp.append(top)
                if top == node:
                    break
            sccs.append(comp)

    for node in nodes:
        if node not in indices:
            strong(node)
    return sccs


def _reaches(adj: dict[str, set[str]], start: str, goal: str) -> bool:
    if start == goal:
        return False
    seen = {start}
    stack = [start]
    while stack:
        node = stack.pop()
        for nxt in adj.get(node, ()):
            if nxt == goal:
                return True
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def build_graph(
    scenes: list[SceneNode],
    events: list[str],
    confirmed_before: list[tuple[str, str]],
    same_pairs: list[tuple[str, str]] | None = None,
    paragraph_ids: list[str] | None = None,
    window_before: str | None = None,
) -> Graph:
    graph = Graph(
        scenes=list(scenes),
        events=list(events),
        confirmed_before=list(confirmed_before),
        same_pairs=list(same_pairs or []),
    )
    graph.paragraph_ids = list(paragraph_ids or [])  # type: ignore[attr-defined]
    extras = []
    for src, dst in list(graph.confirmed_before) + list(graph.same_pairs):
        extras.extend([src, dst])
    for node in graph.nodes() + extras:
        graph.find(node)
    for left, right in graph.same_pairs:
        graph.parent[graph.find(left)] = graph.find(right)
    classes = {graph.find(node) for node in graph.nodes()}
    classes.update(graph.find(node) for node in extras)
    adj: dict[str, set[str]] = {cls: set() for cls in classes}
    for src, dst in graph.confirmed_before:
        adj[graph.find(src)].add(graph.find(dst))
    sccs = _tarjan(list(classes), adj)
    contradicted: set[str] = set()
    for comp in sccs:
        if len(comp) > 1:
            contradicted.update(comp)
    for cls, nxts in adj.items():
        if cls in nxts:
            contradicted.add(cls)
    graph.contradicted = contradicted
    graph.uncertain_nodes = {
        scene.scene_id for scene in graph.scenes if scene.uncertain
    }
    graph.adj = adj

    mainline = [scene for scene in graph.scenes if scene.mainline]
    mainline.sort(key=lambda scene: scene.scene_id and _scene_sort(scene.scene_id))
    for scene in mainline[1:]:
        prev = _prev_mainline(mainline, scene)
        if prev is None:
            continue
        edge = (prev.scene_id, scene.scene_id)
        src, dst = graph.find(edge[0]), graph.find(edge[1])
        if src in contradicted or dst in contradicted:
            graph.dropped_defaults.append(edge)
            continue
        if src == dst or _reaches(graph.adj, dst, src):
            graph.dropped_defaults.append(edge)
            continue
        graph.adj[src].add(dst)
        graph.default_before.append(edge)
    # Pre-canon window only: when intake says the work is set before
    # `window_before`, a mainline scene that follows one already placed before
    # that event is also before it, unless a confirmed edge already puts the
    # scene after the event (E2, E7). Other events get no such inference.
    scoped = [window_before] if window_before and window_before in graph.events else []
    for event in scoped:
        ecls = graph.find(event)
        for scene in mainline:
            scls = graph.find(scene.scene_id)
            if (
                _reaches(graph.adj, scls, ecls)
                or _reaches(graph.adj, ecls, scls)
                or scls == ecls
            ):
                continue
            earlier = [
                item
                for item in mainline
                if _scene_sort(item.scene_id) < _scene_sort(scene.scene_id)
            ]
            if not any(
                _reaches(graph.adj, graph.find(item.scene_id), ecls) for item in earlier
            ):
                continue
            if _reaches(graph.adj, ecls, scls):
                graph.dropped_defaults.append((scene.scene_id, event))
                continue
            graph.adj[scls].add(ecls)
            graph.default_before.append((scene.scene_id, event))
    return graph


def _scene_sort(scene_id: str) -> tuple[int, int]:
    from doctor.ids import parse_scene_id

    return parse_scene_id(scene_id)


def _prev_mainline(mainline: list[SceneNode], scene: SceneNode) -> SceneNode | None:
    ordered = sorted(mainline, key=lambda item: _scene_sort(item.scene_id))
    previous = None
    for item in ordered:
        if item.scene_id == scene.scene_id:
            return previous
        previous = item
    return None


def _point(
    bound: dict | None, paragraph_id: str | None = None
) -> tuple[str, int | None]:
    if bound is None:
        raise ValueError("empty bound")
    if "story" in bound:
        return bound["story"], None
    if "work" in bound:
        return scene_of(bound["work"]), paragraph_index(bound["work"])
    raise ValueError("bound needs story or work")


def compare(graph: Graph, a: tuple[str, int | None], b: tuple[str, int | None]) -> str:
    a_node, a_index = a
    b_node, b_index = b
    if a_node in graph.uncertain_nodes or b_node in graph.uncertain_nodes:
        return UNKNOWN
    if (
        graph.find(a_node) in graph.contradicted
        or graph.find(b_node) in graph.contradicted
    ):
        return UNKNOWN
    if graph.find(a_node) == graph.find(b_node):
        if a_node == b_node and a_index is not None and b_index is not None:
            if a_index < b_index:
                return BEFORE
            if a_index > b_index:
                return AFTER
            return SAME
        return SAME
    src, dst = graph.find(a_node), graph.find(b_node)
    if _reaches(graph.adj, src, dst):
        return BEFORE
    if _reaches(graph.adj, dst, src):
        return AFTER
    return UNKNOWN


def covers(graph: Graph, fact: dict, paragraph_id: str) -> str:
    interval = fact.get("interval") or {}
    query = (scene_of(paragraph_id), paragraph_index(paragraph_id))
    if not interval.get("from"):
        c1 = BEFORE
    else:
        c1 = compare(graph, _point(interval["from"]), query)
    if not interval.get("to"):
        c2 = BEFORE
    else:
        c2 = compare(graph, query, _point(interval["to"]))
    if c1 == AFTER or c2 in {AFTER, SAME}:
        return NO
    would_yes = c1 in {BEFORE, SAME} and c2 == BEFORE
    if would_yes and _same_class_story_from(graph, interval.get("from"), query):
        return UNKNOWN
    if would_yes:
        return YES
    return UNKNOWN


def _same_class_story_from(
    graph: Graph, bound: dict | None, query: tuple[str, int | None]
) -> bool:
    """YES would rest only on a story-time bound contemporaneous with another node."""
    if not bound or "story" not in bound:
        return False
    origin = (bound["story"], None)
    if compare(graph, origin, query) != SAME:
        return False
    return origin[0] != query[0]


def overlap(graph: Graph, left: dict, right: dict) -> str:
    if not left.get("interval") and not right.get("interval"):
        return YES
    points = list(graph.scene_paragraphs())
    for fact in (left, right):
        interval = fact.get("interval") or {}
        for key in ("from", "to"):
            bound = interval.get(key)
            if bound and "work" in bound:
                points.append(bound["work"])
    if not points:
        return UNKNOWN
    saw_unknown = False
    for paragraph_id in points:
        ca = covers(graph, left, paragraph_id)
        cb = covers(graph, right, paragraph_id)
        if ca == YES and cb == YES:
            return YES
        if UNKNOWN in {ca, cb}:
            saw_unknown = True
    if saw_unknown:
        return UNKNOWN
    return NO


def reading_before(left_paragraph: str, right_paragraph: str) -> bool:
    return compare_ids(left_paragraph, right_paragraph) < 0
