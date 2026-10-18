"""Hand-written expectations for CONT.DEAD_REAPPEARS.

Every row below was written from the spec, one scenario at a time, before the
rule was run against it. There is no expect() function that mirrors the rule's
branches: each expected value is a literal. Do not regenerate this table from
output. If a row fails, decide from the spec whether the row or the code is wrong.

Scenario: one scene ch01.s1, a canon status fact for teodor from ev-bridge on,
optionally an AU status override, and one mention of teodor in ch01.s1.p1.
"""

import pytest

from doctor.rules import dead_reappears
from doctor.timeline import SceneNode, build_graph

MODES = {
    "present": ("confirmed", "present_action"),
    "mentioned": ("confirmed", "mentioned"),
    "proposed": ("proposed", "present_action"),
    "remembered": ("confirmed", "remembered"),
    "quoted": ("confirmed", "quoted_or_recorded"),
    "dream": ("confirmed", "dream_or_vision"),
}

# (canon status, au override, placement, mode) -> expected item_state or "none"
# placement:
#   post         scene confirmed after ev-bridge
#   pre          scene before ev-start, which is before ev-bridge
#   flashback    scene is a flashback placed before ev-bridge
#   pending      scene has an unconfirmed temporal marker
#   disconnected no edge between scene and ev-bridge
#   cycle        confirmed edges put the scene both before and after ev-bridge
#   within       scene is contemporaneous with ev-bridge (SAME class)
ROWS = [
    # Dead from the bridge, scene after it: only a confirmed present appearance is a break.
    ("dead", None, "post", "present", "finding"),
    ("dead", None, "post", "mentioned", "none"),
    ("dead", None, "post", "proposed", "unverifiable"),
    ("dead", None, "post", "remembered", "none"),
    ("dead", None, "post", "quoted", "none"),
    ("dead", None, "post", "dream", "none"),
    # Scene before the death: alive by default, nothing to say.
    ("dead", None, "pre", "present", "none"),
    ("dead", None, "pre", "mentioned", "none"),
    ("dead", None, "flashback", "present", "none"),
    # Placement unknown: never an all-clear, never a finding.
    ("dead", None, "pending", "present", "unverifiable"),
    ("dead", None, "pending", "mentioned", "unverifiable"),
    ("dead", None, "disconnected", "present", "unverifiable"),
    ("dead", None, "cycle", "present", "unverifiable"),
    ("dead", None, "within", "present", "unverifiable"),
    ("dead", None, "within", "mentioned", "unverifiable"),
    # AU survival overrides canon death after the branch.
    ("dead", "alive", "post", "present", "none"),
    ("dead", "alive", "post", "proposed", "none"),
    ("dead", "alive", "disconnected", "present", "unverifiable"),
    # AU agrees with canon death: still a break.
    ("dead", "dead", "post", "present", "finding"),
    ("dead", "dead", "pre", "present", "none"),
    # Other statuses are never a dead-reappears break.
    ("alive", None, "post", "present", "none"),
    ("alive", None, "post", "proposed", "none"),
    ("alive", None, "pre", "present", "none"),
    ("unspecified", None, "post", "present", "none"),
    ("unspecified", None, "post", "proposed", "none"),
    # A value outside the closed set (e.g. hand-edited facts.json) is not death.
    ("captured", None, "post", "present", "none"),
    ("missing", None, "post", "present", "none"),
    # Canon alive, AU kills him after the branch: the AU death is enforced.
    ("alive", "dead", "post", "present", "finding"),
    ("alive", "dead", "post", "mentioned", "none"),
]


def _fact(fid: str, layer: str, value: str) -> dict:
    return {
        "id": fid,
        "subject": "teodor",
        "predicate": "status",
        "object": value,
        "layer": layer,
        "status": "confirmed",
        "assertion": "state",
        "citation_state": "ok",
        "interval": {"from": {"story": "ev-bridge"}},
    }


def _graph(placement: str):
    kind = "flashback" if placement == "flashback" else None
    scene = SceneNode("ch01.s1", anchor_kind=kind, uncertain=placement == "pending")
    edges = {
        "post": [("ev-bridge", "ch01.s1")],
        "pending": [("ev-bridge", "ch01.s1")],
        "pre": [("ch01.s1", "ev-start"), ("ev-start", "ev-bridge")],
        "flashback": [("ch01.s1", "ev-bridge")],
        "disconnected": [],
        "cycle": [("ev-bridge", "ch01.s1"), ("ch01.s1", "ev-bridge")],
        "within": [],
    }[placement]
    same = [("ev-bridge", "ch01.s1")] if placement == "within" else []
    return build_graph(
        [scene],
        ["ev-bridge", "ev-start"],
        edges,
        same_pairs=same,
        paragraph_ids=["ch01.s1.p1"],
    )


@pytest.mark.parametrize("canon, au, placement, mode, wanted", ROWS)
def test_dead_reappears_table(canon, au, placement, mode, wanted):
    facts = [_fact("f-canon", "canon:books", canon)]
    if au:
        facts.append(_fact("f-au", "au", au))
    status, value = MODES[mode]
    mention = {
        "id": "m",
        "entity": "teodor",
        "paragraph": "ch01.s1.p1",
        "surface": "Teodor",
        "stale": False,
        "mode_status": status,
        "mode": value,
    }
    got = dead_reappears([mention], facts, _graph(placement), "books")
    actual = got[0]["item_state"] if got else "none"
    assert actual == wanted
    if wanted == "finding":
        assert got[0]["severity"] == "blocker"
        assert got[0]["depends_on_hash"]
