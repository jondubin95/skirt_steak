"""Independent expectations for DEAD_REAPPEARS. This file does not call resolve()."""

from doctor.rules import dead_reappears
from doctor.timeline import SceneNode, build_graph

FACT = {
    "id": "f-canon-001",
    "subject": "teodor",
    "predicate": "status",
    "object": "dead",
    "layer": "canon:books",
    "status": "confirmed",
    "assertion": "state",
    "citation_state": "ok",
    "interval": {"from": {"story": "ev-bridge"}},
}


def expect(au: str, window: str, flash: str, ordering: str, anchors: str, mode: str) -> str:
    """Return finding, unverifiable, or none. Encodes the spec, not resolve()."""
    if anchors == "cycle" or ordering == "disconnected" or flash == "pending" or window == "within":
        return "unverifiable"
    dead = flash != "offline" and window == "post" and au != "survival"
    if not dead:
        return "none"
    if mode == "proposed":
        return "unverifiable"
    if mode == "present":
        return "finding"
    return "none"


def _graph(au, window, flash, ordering, anchors):
    kind = "flashback" if flash == "offline" else None
    uncertain = flash == "pending"
    scene = SceneNode("ch01.s1", anchor_kind=kind, uncertain=uncertain)
    edges = []
    if anchors == "cycle":
        edges = [("ev-bridge", "ch01.s1"), ("ch01.s1", "ev-bridge")]
    elif ordering == "disconnected":
        edges = []
    elif flash == "offline":
        edges = [("ch01.s1", "ev-bridge")]
    elif window == "post":
        edges = [("ev-bridge", "ch01.s1")]
    elif window == "pre":
        edges = [("ch01.s1", "ev-start"), ("ev-start", "ev-bridge")]
    elif window == "within":
        edges = []
    same = [("ev-bridge", "ch01.s1")] if window == "within" and anchors != "cycle" and ordering != "disconnected" else []
    facts = [FACT]
    if au == "survival":
        facts.append({**FACT, "id": "au", "layer": "au", "object": "alive"})
    elif au == "death":
        facts.append({**FACT, "id": "au", "layer": "au", "object": "dead"})
    graph = build_graph([scene], ["ev-bridge", "ev-start"], edges, same_pairs=same, paragraph_ids=["ch01.s1.p1"])
    return graph, facts


def test_interaction_matrix_matches_independent_table():
    modes = {"present": ("confirmed", "present_action"), "mentioned": ("confirmed", "mentioned"), "proposed": ("proposed", "present_action")}
    mismatches = []
    for au in ("none", "survival", "death"):
        for window in ("pre", "within", "post"):
            for flash in ("none", "offline", "pending"):
                for ordering in ("connected", "disconnected"):
                    for anchors in ("ok", "cycle"):
                        for mode_name, (status, value) in modes.items():
                            graph, facts = _graph(au, window, flash, ordering, anchors)
                            got = dead_reappears(
                                [
                                    {
                                        "id": "m",
                                        "entity": "teodor",
                                        "paragraph": "ch01.s1.p1",
                                        "surface": "Teodor",
                                        "stale": False,
                                        "mode_status": status,
                                        "mode": value,
                                    }
                                ],
                                facts,
                                graph,
                                "books",
                            )
                            actual = got[0]["item_state"] if got else "none"
                            wanted = expect(au, window, flash, ordering, anchors, mode_name)
                            if actual != wanted:
                                mismatches.append((au, window, flash, ordering, anchors, mode_name, actual, wanted))
    assert mismatches == []
