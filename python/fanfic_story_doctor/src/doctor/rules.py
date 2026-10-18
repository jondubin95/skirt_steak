"""MVP rules. Fact rules are tri-state. Layer B is separate."""

from __future__ import annotations

import hashlib
import json
import re

from doctor.resolve import UNRESOLVED, is_enforceable, resolve
from doctor.timeline import UNKNOWN, compare, reading_before, scene_of

MVP_RULES = [
    "CANON.DIVERGENCE",
    "CONT.DEAD_REAPPEARS",
    "CONT.PAYOFF_BEFORE_SETUP",
    "CONT.TIMELINE_ORDER",
    "LEDGER.COVERAGE",
    "LEDGER.CONFLICT",
    "CANON.NAME_SPELLING",
    "AO3.SCHEMA",
    "AO3.TAG_FORMAT",
    "OOC.VOICE",
    "CANON.RAILS",
]


def depends_hash(fact_ids: list[str], extra: str = "") -> str:
    payload = json.dumps({"facts": sorted(fact_ids), "extra": extra}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _direction(fact: dict) -> tuple[str, str] | None:
    obj = fact.get("object") or {}
    relation = obj.get("relation")
    subject = fact.get("subject")
    target = obj.get("target")
    if not subject or not target or relation not in {"before", "after", "same"}:
        return None
    if relation == "before":
        return (subject, target)
    if relation == "after":
        return (target, subject)
    return (subject, target)


def _blocked(fact: dict) -> bool:
    return (
        fact.get("status") in {"confirmed", "disputed"}
        and fact.get("assertion", "state") == "state"
        and not fact.get("superseded_by")
        and (fact.get("status") == "disputed" or fact.get("citation_state") == "stale")
    )


def _question(kind: str, field: str, text: str, fact_ids: list[str]) -> dict:
    return {
        "rule_id": "CANON.DIVERGENCE",
        "item_state": "question",
        "tier": "A1",
        "severity": "info",
        "kind": kind,
        "symptom": text,
        "evidence": [{"kind": "file", "path": "intake.yaml", "field": field}],
        "fact_ids": fact_ids,
        "depends_on_hash": depends_hash(fact_ids, kind),
    }


def canon_divergence(
    facts: list[dict], graph, intake: dict, primary: str
) -> list[dict]:
    """event_order ledger vs primary canon, classified by the divergence event.

    Canon edges are not part of the work's timeline graph for pairs the ledger
    orders itself, so a deliberate branch is classified here and never shows up
    as a CONT.TIMELINE_ORDER cycle.
    """
    items: list[dict] = []
    asked: set[str] = set()
    au = (intake or {}).get("au") or {}
    is_au = bool(au.get("is_au"))
    divergence = au.get("divergence_event")
    canon_layer = f"canon:{primary}"
    order = [fact for fact in facts if fact.get("predicate") == "event_order"]
    ledger = [
        fact for fact in order if fact.get("layer") == "ledger" and is_enforceable(fact)
    ]
    canon = [
        fact
        for fact in order
        if fact.get("layer") == canon_layer and is_enforceable(fact)
    ]
    canon_blocked = [
        fact for fact in order if fact.get("layer") == canon_layer and _blocked(fact)
    ]
    au_rows = [
        fact for fact in order if fact.get("layer") == "au" and is_enforceable(fact)
    ]
    for left in ledger:
        pair = _direction(left)
        if pair is None:
            continue
        same_pair = [
            fact
            for fact in canon
            if _direction(fact) and set(_direction(fact)) == set(pair)
        ]
        blocked = [
            fact
            for fact in canon_blocked
            if _direction(fact) and set(_direction(fact)) == set(pair)
        ]
        disagree = [fact for fact in same_pair if _direction(fact) != pair]
        citation = (left.get("citation") or {}).get("at")
        paragraph = citation or _first_paragraph(graph, left.get("subject"))
        if blocked and not same_pair:
            ids = [left["id"], blocked[0]["id"]]
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "unverifiable",
                    "info",
                    "unverifiable",
                    "Canon order for this pair is stale or disputed. No lower canon source is used.",
                )
            )
            continue
        if not disagree:
            continue
        ids = [left["id"], disagree[0]["id"]]
        if any(_direction(fact) == pair for fact in au_rows):
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "coverage",
                    "info",
                    "coverage",
                    "Declared AU order covers this point.",
                )
            )
            continue
        if not is_au:
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "info",
                    "info",
                    "coverage",
                    "Draft event order differs from canon. The work is not declared AU.",
                )
            )
            continue
        if not divergence:
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "info",
                    "info",
                    "coverage",
                    "Declared AU has no divergence event.",
                )
            )
            if "DIVERGENCE_EVENT" not in asked:
                asked.add("DIVERGENCE_EVENT")
                items.append(
                    _question(
                        "DIVERGENCE_EVENT",
                        "au.divergence_event",
                        "Which canon event is the branch point?",
                        ids,
                    )
                )
            continue
        if not paragraph:
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "unverifiable",
                    "info",
                    "unverifiable",
                    "Event order differs from canon, and the scene is not placed.",
                )
            )
            continue
        where = compare(graph, (scene_of(paragraph), None), (divergence, None))
        if where == UNKNOWN:
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "unverifiable",
                    "info",
                    "unverifiable",
                    "Event order differs from canon, and this scene is unordered against the branch point.",
                )
            )
            if "TIMELINE_ANCHOR" not in asked:
                asked.add("TIMELINE_ANCHOR")
                items.append(
                    _question(
                        "TIMELINE_ANCHOR",
                        "au.divergence_event",
                        "Is this scene before or after the branch point?",
                        ids,
                    )
                )
        elif where == "BEFORE":
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "finding",
                    "should",
                    "internal_inconsistency",
                    "Event order contradicts canon before the declared branch.",
                )
            )
        else:
            items.append(
                _divergence_item(
                    left,
                    paragraph,
                    ids,
                    "coverage",
                    "info",
                    "coverage",
                    "Event order leaves canon at or after the declared branch.",
                )
            )
    if is_au and not divergence and "DIVERGENCE_EVENT" not in asked:
        items.append(
            _question(
                "DIVERGENCE_EVENT",
                "au.divergence_event",
                "Which canon event is the branch point? If the work is a full alternate setting, set au.au_kind: alternate_setting.",
                [],
            )
        )
    return items


def _divergence_item(left, paragraph, ids, state, severity, kind, symptom) -> dict:
    return {
        "rule_id": "CANON.DIVERGENCE",
        "item_state": state,
        "tier": "A1",
        "severity": severity,
        "kind": kind,
        "symptom": symptom,
        "fact_ids": ids,
        "depends_on_hash": depends_hash(ids),
        "evidence": _prose(paragraph, left),
    }


def _first_paragraph(graph, scene_id: str | None) -> str | None:
    if not scene_id:
        return None
    for pid in graph.scene_paragraphs():
        if scene_of(pid) == scene_id:
            return pid
    return None


def _prose(paragraph: str | None, fact: dict) -> list[dict]:
    quote = (fact.get("citation") or {}).get("text")
    if paragraph and quote:
        return [{"kind": "prose", "paragraph_id": paragraph, "quote": quote}]
    return [
        {"kind": "file", "path": "intake.yaml", "field": fact.get("id", "event_order")}
    ]


def dead_reappears(
    mentions: list[dict], facts: list[dict], graph, primary: str | None
) -> list[dict]:
    items = []
    for mention in mentions:
        if mention.get("stale"):
            continue
        state, value, ids = resolve(
            facts, mention["entity"], "status", mention["paragraph"], graph, primary
        )
        if state == UNRESOLVED:
            items.append(
                _unknown(
                    "CONT.DEAD_REAPPEARS",
                    mention,
                    ids,
                    "Status at this paragraph is unresolved.",
                )
            )
            continue
        if value != "dead":
            continue
        if mention.get("mode_status") != "confirmed":
            items.append(
                _unknown(
                    "CONT.DEAD_REAPPEARS",
                    mention,
                    ids,
                    "Appearance mode is not confirmed.",
                )
            )
            continue
        if mention.get("mode") == "unclear":
            items.append(
                _unknown(
                    "CONT.DEAD_REAPPEARS", mention, ids, "Appearance mode is unclear."
                )
            )
            continue
        if mention.get("mode") == "present_action":
            items.append(
                {
                    "rule_id": "CONT.DEAD_REAPPEARS",
                    "item_state": "finding",
                    "tier": "A1",
                    "severity": "blocker",
                    "kind": "load_bearing_break",
                    "symptom": f"{mention['entity']} is dead here and confirmed present.",
                    "evidence": [
                        {
                            "kind": "prose",
                            "paragraph_id": mention["paragraph"],
                            "quote": mention.get("surface", ""),
                        }
                    ],
                    "fact_ids": ids,
                    "annotation_ids": [mention["id"]],
                    "depends_on_hash": depends_hash(ids, mention["id"]),
                }
            )
    return items


def _unknown(rule: str, mention: dict, ids: list[str], symptom: str) -> dict:
    return {
        "rule_id": rule,
        "item_state": "unverifiable",
        "tier": "A1",
        "severity": "info",
        "kind": "unverifiable",
        "symptom": symptom,
        "evidence": [
            {
                "kind": "prose",
                "paragraph_id": mention["paragraph"],
                "quote": mention.get("surface", ""),
            }
        ],
        "fact_ids": ids,
        "annotation_ids": [mention.get("id", "")],
        "depends_on_hash": depends_hash(ids, mention.get("id", "")),
    }


def payoff_before_setup(facts: list[dict]) -> list[dict]:
    items = []
    threads: dict[str, list[dict]] = {}
    for fact in facts:
        if fact.get("predicate") in {"setup_anchor", "payoff_anchor"}:
            threads.setdefault(fact["subject"], []).append(fact)
    for thread, rows in threads.items():
        payoffs = [
            fact
            for fact in rows
            if fact.get("predicate") == "payoff_anchor" and is_enforceable(fact)
        ]
        setups = [
            fact
            for fact in rows
            if fact.get("predicate") == "setup_anchor" and is_enforceable(fact)
        ]
        proposed = [
            fact
            for fact in rows
            if fact.get("predicate") == "setup_anchor"
            and fact.get("status") == "proposed"
        ]
        if not payoffs:
            continue
        payoff_at = _anchor_at(payoffs[0])
        setup_ats = [_anchor_at(fact) for fact in setups]
        if any(reading_before(setup, payoff_at) for setup in setup_ats):
            continue
        if setups and all(reading_before(payoff_at, setup) for setup in setup_ats):
            items.append(
                {
                    "rule_id": "CONT.PAYOFF_BEFORE_SETUP",
                    "item_state": "finding",
                    "tier": "A1",
                    "severity": "blocker",
                    "kind": "load_bearing_break",
                    "symptom": f"Payoff for {thread} is before every confirmed setup.",
                    "evidence": [
                        {
                            "kind": "prose",
                            "paragraph_id": payoff_at,
                            "quote": (payoffs[0].get("citation") or {}).get("text")
                            or "",
                        }
                    ],
                    "fact_ids": [fact["id"] for fact in payoffs + setups],
                    "depends_on_hash": depends_hash(
                        [fact["id"] for fact in payoffs + setups]
                    ),
                }
            )
        elif not setups:
            symptom = (
                "Setup is only proposed."
                if proposed
                else "No confirmed setup for this payoff."
            )
            items.append(
                {
                    "rule_id": "CONT.PAYOFF_BEFORE_SETUP",
                    "item_state": "unverifiable",
                    "tier": "A1",
                    "severity": "info",
                    "kind": "unverifiable",
                    "symptom": symptom,
                    "evidence": [
                        {
                            "kind": "prose",
                            "paragraph_id": payoff_at,
                            "quote": (payoffs[0].get("citation") or {}).get("text")
                            or "",
                        }
                    ],
                    "fact_ids": [payoffs[0]["id"]],
                    "depends_on_hash": depends_hash([payoffs[0]["id"]]),
                }
            )
        else:
            items.append(
                {
                    "rule_id": "CONT.PAYOFF_BEFORE_SETUP",
                    "item_state": "unverifiable",
                    "tier": "A1",
                    "severity": "info",
                    "kind": "unverifiable",
                    "symptom": "A setup and a payoff share a work position.",
                    "evidence": [
                        {"kind": "prose", "paragraph_id": payoff_at, "quote": ""}
                    ],
                    "fact_ids": [fact["id"] for fact in payoffs + setups],
                    "depends_on_hash": depends_hash(
                        [fact["id"] for fact in payoffs + setups]
                    ),
                }
            )
    return items


def _anchor_at(fact: dict) -> str:
    interval = fact.get("interval") or {}
    bound = interval.get("from") or {}
    return bound.get("work") or (fact.get("citation") or {}).get("at")


def timeline_order(graph) -> list[dict]:
    if not graph.contradicted:
        return []
    return [
        {
            "rule_id": "CONT.TIMELINE_ORDER",
            "item_state": "finding",
            "tier": "A1",
            "severity": "blocker",
            "kind": "load_bearing_break",
            "symptom": "Confirmed timeline edges contradict each other.",
            "evidence": [
                {"kind": "file", "path": "intake.yaml", "field": "canon_event_order"}
            ],
            "fact_ids": [],
            "depends_on_hash": depends_hash(sorted(graph.contradicted)),
        }
    ]


# Common English words that are often capitalized at a sentence start and sit
# within edit distance of short names. The document's own lowercase vocabulary
# is checked too, so this list only needs the usual suspects.
COMMON_WORDS = {
    "shame",
    "share",
    "shake",
    "shade",
    "shape",
    "shine",
    "shone",
    "shore",
    "harder",
    "hidden",
    "heard",
    "heart",
    "haven",
    "hated",
    "laden",
    "maybe",
    "marry",
    "mercy",
    "major",
    "manor",
    "dare",
    "dark",
    "dave",
    "davit",
    "carry",
    "carol",
    "eric",
    "even",
    "ever",
    "ella",
    "else",
    "into",
    "idea",
    "ideal",
    "just",
    "june",
    "jack",
    "mark",
    "will",
    "grace",
    "faith",
    "hope",
    "joy",
    "may",
    "art",
    "bill",
    "chase",
    "dawn",
    "gene",
    "glen",
    "mason",
    "pat",
    "ray",
    "rob",
    "sue",
    "tim",
    "wade",
    "frank",
    "earnest",
}

_WORD = re.compile(r"[A-Z][A-Za-z]*(?:['\u2019][A-Za-z]+)?['\u2019]?-*")
_DIALOGUE = re.compile(r"[\"\u201c]([^\"\u201c\u201d]*)[\"\u201d]")


def _candidate_spans(text: str) -> list[tuple[int, int]]:
    """Exact spans of 1-3 capitalized words joined by single spaces only.

    A run never crosses punctuation, so every candidate is a substring of the
    paragraph and quotes always validate.
    """
    words = [(m.start(), m.end()) for m in _WORD.finditer(text)]
    runs: list[list[tuple[int, int]]] = []
    for span in words:
        prev = runs[-1][-1] if runs else None
        joinable = (
            prev is not None
            and text[prev[1] : span[0]] == " "
            and not text[prev[0] : prev[1]].endswith(("-", "'", "\u2019"))
        )
        if joinable:
            runs[-1].append(span)
        else:
            runs.append([span])
    out = []
    for run in runs:
        for size in (3, 2, 1):
            for i in range(len(run) - size + 1):
                out.append((run[i][0], run[i + size - 1][1]))
    return out


def _candidates(text: str) -> list[str]:
    return [text[a:b] for a, b in _candidate_spans(text)]


def _core(token: str) -> str:
    core = token.rstrip("-")
    for suffix in ("'s", "\u2019s", "'", "\u2019"):
        if core.endswith(suffix):
            core = core[: -len(suffix)]
            break
    return core


def _vocabulary(paragraphs: list) -> set[str]:
    vocab: set[str] = set()
    for paragraph in paragraphs:
        for word in re.findall(r"\b[a-z][a-z']+\b", paragraph.text):
            vocab.add(word)
    return vocab


def surnames_of(aliases: list[str]) -> set[str]:
    return {alias.split()[-1] for alias in aliases if len(alias.split()) > 1}


def _unique_aliases(aliases: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = alias.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(alias)
    return unique


def _alias_limit(alias: str) -> int:
    return 1 if len(alias) <= 5 else 2


def _is_prefix(core: str, alias: str) -> bool:
    return (
        " " not in core
        and " " not in alias
        and len(core) >= 3
        and len(alias) > len(core)
        and alias.casefold().startswith(core.casefold())
    )


def _inside_dialogue(text: str, start: int, end: int) -> bool:
    return any(quote.start() < start and end < quote.end() for quote in _DIALOGUE.finditer(text))


def _owner_ids(alias: str, owners: dict[str, set[str]] | None) -> set[str]:
    if not owners:
        return {alias.casefold()}
    found = owners.get(alias)
    if found:
        return set(found)
    for surface, ids in owners.items():
        if surface.casefold() == alias.casefold():
            return set(ids)
    return {alias.casefold()}


def name_spelling(
    paragraphs: list,
    aliases: list[str],
    dismissed: list[str] | None = None,
    owners: dict[str, set[str]] | None = None,
) -> list[dict]:
    dismissed = {item.casefold() for item in (dismissed or [])}
    aliases = _unique_aliases([str(alias) for alias in aliases])
    alias_set = set(aliases)
    folded = {alias.casefold(): alias for alias in aliases}
    surnames = surnames_of(aliases)
    vocab = _vocabulary(paragraphs)
    occurrences: list[dict] = []
    for paragraph in paragraphs:
        taken: list[tuple[int, int]] = []
        for start, end in _candidate_spans(paragraph.text):
            if any(not (end <= a or start >= b) for a, b in taken):
                continue
            token = paragraph.text[start:end]
            core = _core(token)
            if not core or token.casefold() in dismissed or core.casefold() in dismissed:
                continue
            if core in alias_set or core.casefold() in folded:
                continue
            if core.endswith("s") and core[:-1] in surnames:
                continue  # plural surname: "the Venns"
            if _possessive_of_alias(token, core, alias_set, folded):
                continue
            words = core.split()
            if len(words) == 1 and (
                core.lower() in vocab or core.lower() in COMMON_WORDS
            ):
                continue
            if token.endswith("-"):
                continue  # interrupted name: "Ter-"
            matched = [
                alias
                for alias in aliases
                if len(alias.split()) == len(words)
                and (
                    _damerau(core, alias) <= _alias_limit(alias) or _is_prefix(core, alias)
                )
            ]
            characters = set().union(
                *(_owner_ids(alias, owners) for alias in matched)
            ) if matched else set()
            if len(characters) != 1:
                continue
            taken.append((start, end))
            occurrences.append(
                {
                    "paragraph_id": paragraph.id,
                    "paragraph_hash": paragraph.content_hash,
                    "token": token,
                    "core": core,
                    "aliases": matched,
                    "start": start,
                    "end": end,
                    "dialogue": _inside_dialogue(paragraph.text, start, end),
                }
            )
    counts: dict[str, int] = {}
    for row in occurrences:
        counts[row["core"].casefold()] = counts.get(row["core"].casefold(), 0) + 1
    items = []
    for row in occurrences:
        core = row["core"]
        questions = [
            alias
            for alias in row["aliases"]
            if _is_prefix(core, alias)
            and (
                row["dialogue"]
                or counts[core.casefold()] >= 2
                or len(alias) - len(core) >= 2
            )
        ]
        if questions:
            for alias in questions:
                items.append(
                    _spelling_item(
                        "question",
                        "intake_question",
                        f"Is {row['token']} a nickname for {alias}? Add it to names.",
                        row,
                        alias,
                    )
                )
            continue
        editable = [
            alias
            for alias in row["aliases"]
            if _damerau(core, alias) <= _alias_limit(alias)
        ] or list(row["aliases"])
        alias = min(editable, key=lambda item: (_damerau(core, item), -len(item), item.casefold()))
        items.append(
            _spelling_item(
                "finding",
                "internal_inconsistency",
                f"{row['token']} is near the alias {alias} and is not itself an alias.",
                row,
                alias,
            )
        )
    return _dedupe(items)


def _spelling_item(state: str, kind: str, symptom: str, row: dict, alias: str) -> dict:
    return {
        "rule_id": "CANON.NAME_SPELLING",
        "item_state": state,
        "tier": "A1",
        "severity": "info",
        "kind": kind,
        "symptom": symptom,
        "evidence": [
            {
                "kind": "prose",
                "paragraph_id": row["paragraph_id"],
                "quote": row["token"],
                "span": [row["start"], row["end"]],
                "paragraph_hash": row["paragraph_hash"],
            }
        ],
        "fact_ids": [],
        "depends_on_hash": depends_hash([alias, row["token"]], state),
    }


def _possessive_of_alias(token: str, core: str, alias_set: set, folded: dict) -> bool:
    """alias+s, alias+s', alias+'s (either apostrophe), or a possessive whose
    core plus s is an alias (Mara's when the alias is Maras)."""

    def known(name: str) -> bool:
        return bool(name) and (name in alias_set or name.casefold() in folded)

    bare = token.rstrip("-")
    for suffix in ("s'", "s\u2019", "s"):
        if bare.endswith(suffix) and known(bare[: -len(suffix)]):
            return True
    if bare != core and (known(core + "s") or (core.endswith("s") and known(core[:-1]))):
        return True
    return False


def _dedupe(items: list[dict]) -> list[dict]:
    """Identical findings (same symptom) collapse into one item with a count."""
    merged: dict[str, dict] = {}
    counts: dict[str, int] = {}
    for item in items:
        key = item["symptom"]
        if key not in merged:
            merged[key] = {**item, "evidence": list(item["evidence"])}
            counts[key] = 0
        elif len(merged[key]["evidence"]) < 5:
            merged[key]["evidence"].append(item["evidence"][0])
        counts[key] += 1
    out = []
    for key, item in merged.items():
        if counts[key] > 1:
            item["total"] = counts[key]
            item["symptom"] = f"{key} Seen {counts[key]} times."[:300]
        out.append(item)
    return out


def _damerau(a: str, b: str) -> int:
    if a == b:
        return 0
    la, lb = len(a), len(b)
    grid = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        grid[i][0] = i
    for j in range(lb + 1):
        grid[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            grid[i][j] = min(
                grid[i - 1][j] + 1, grid[i][j - 1] + 1, grid[i - 1][j - 1] + cost
            )
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                grid[i][j] = min(grid[i][j], grid[i - 2][j - 2] + 1)
    return grid[la][lb]


def ao3_schema(tags: dict | None) -> list[dict]:
    if not tags:
        return []
    missing = []
    for field in ("rating", "archive_warnings", "fandoms", "title", "language"):
        value = tags.get(field)
        if value is None or value == [] or value == "":
            missing.append(field)
    warnings = tags.get("archive_warnings") or []
    allowed = {
        "Graphic Depictions Of Violence",
        "Major Character Death",
        "Rape/Non-Con",
        "Underage",
        "Creator Chose Not To Use Archive Warnings",
        "No Archive Warnings Apply",
    }
    if any(item not in allowed for item in warnings):
        missing.append("archive_warnings")
    if not missing:
        return []
    return [
        {
            "rule_id": "AO3.SCHEMA",
            "item_state": "finding",
            "tier": "A1",
            "severity": "should",
            "kind": "tagging",
            "symptom": "Required AO3 field missing: "
            + ", ".join(sorted(set(missing)))
            + ".",
            "evidence": [
                {"kind": "file", "path": "tags.yaml", "field": min(set(missing))}
            ],
            "fact_ids": [],
            "depends_on_hash": depends_hash(missing),
        }
    ]


def ao3_tag_format(tags: dict | None) -> list[dict]:
    if not tags:
        return []
    bag = []
    for key in ("fandoms", "characters", "relationships", "additional_tags"):
        bag.extend(tags.get(key) or [])
    problems = []
    if any(len(tag) > 150 or "," in tag for tag in bag):
        problems.append("tag length or comma")
    if len(bag) > 75:
        problems.append("more than 75 tags")
    if not problems:
        return []
    return [
        {
            "rule_id": "AO3.TAG_FORMAT",
            "item_state": "finding",
            "tier": "A1",
            "severity": "should",
            "kind": "tagging",
            "symptom": "AO3 tag format: " + "; ".join(problems) + ".",
            "evidence": [
                {"kind": "file", "path": "tags.yaml", "field": "additional_tags"}
            ],
            "fact_ids": [],
            "depends_on_hash": depends_hash(problems),
        }
    ]


def status_coverage(facts: list[dict], main_cast: list[str], graph) -> dict:
    covered = 0
    for entity in main_cast:
        rows = [
            fact
            for fact in facts
            if fact.get("subject") == entity
            and fact.get("predicate") == "status"
            and is_enforceable(fact)
        ]
        if rows:
            covered += 1
    return {
        "rule_id": "LEDGER.COVERAGE",
        "item_state": "coverage",
        "tier": "A1",
        "severity": "info",
        "kind": "coverage",
        "symptom": f"status facts cover {covered} of {len(main_cast)} main-cast characters.",
        "evidence": [{"kind": "file", "path": "intake.yaml", "field": "main_cast"}],
        "fact_ids": [],
        "depends_on_hash": depends_hash(main_cast),
        "covered": covered,
        "total": len(main_cast),
    }
