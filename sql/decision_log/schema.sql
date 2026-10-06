CREATE TABLE schema_meta (
    version INTEGER PRIMARY KEY CHECK (version = 1)
);

INSERT INTO schema_meta (version) VALUES (1);

CREATE TABLE decisions (
    id UUID PRIMARY KEY,
    supersedes UUID,
    market VARCHAR NOT NULL,
    thesis VARCHAR NOT NULL,
    invalidation VARCHAR NOT NULL,
    market_snapshot VARCHAR NOT NULL,
    observed_at TIMESTAMP NOT NULL,
    verdict VARCHAR NOT NULL,
    playbook_path VARCHAR NOT NULL,
    playbook_sha256 VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    outcome VARCHAR,
    resolved_at TIMESTAMP,
    outcome_notes VARCHAR,
    CHECK (length(trim(market)) > 0),
    CHECK (length(trim(thesis)) > 0),
    CHECK (length(trim(invalidation)) > 0),
    CHECK (length(trim(market_snapshot)) > 0),
    CHECK (verdict IN ('ready', 'not ready', 'hard-blocked')),
    CHECK (length(playbook_sha256) = 64),
    CHECK (outcome IS NULL OR outcome IN ('right', 'wrong', 'inconclusive')),
    CHECK (supersedes IS NULL OR supersedes <> id),
    FOREIGN KEY (supersedes) REFERENCES decisions (id)
);

CREATE TABLE evidence (
    id UUID PRIMARY KEY,
    decision_id UUID NOT NULL,
    position INTEGER NOT NULL,
    claim VARCHAR NOT NULL,
    evidence_class VARCHAR NOT NULL,
    core BOOLEAN NOT NULL,
    basis_ref VARCHAR,
    UNIQUE (decision_id, position),
    CHECK (length(trim(claim)) > 0),
    CHECK (evidence_class IN ('data-backed', 'plausible but unverified', 'narrative-only')),
    CHECK (
        evidence_class <> 'data-backed'
        OR (basis_ref IS NOT NULL AND length(trim(basis_ref)) > 0)
    ),
    FOREIGN KEY (decision_id) REFERENCES decisions (id)
);
