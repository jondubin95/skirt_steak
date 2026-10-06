SELECT
    'count' AS section,
    v.verdict AS verdict,
    COALESCE(c.n, 0)::BIGINT AS n,
    CAST(NULL AS UUID) AS decision_id,
    CAST(NULL AS INTEGER) AS position,
    CAST(NULL AS VARCHAR) AS claim,
    CAST(NULL AS VARCHAR) AS outcome
FROM (VALUES ('ready'), ('not ready'), ('hard-blocked')) AS v(verdict)
LEFT JOIN (
    SELECT verdict, COUNT(*)::BIGINT AS n
    FROM decisions
    GROUP BY verdict
) AS c ON c.verdict = v.verdict
UNION ALL
SELECT
    'narrative-only' AS section,
    CAST(NULL AS VARCHAR) AS verdict,
    CAST(NULL AS BIGINT) AS n,
    e.decision_id,
    e.position,
    e.claim,
    CAST(NULL AS VARCHAR) AS outcome
FROM evidence AS e
WHERE e.evidence_class = 'narrative-only'
UNION ALL
SELECT
    'outcome' AS section,
    d.verdict,
    COUNT(*)::BIGINT AS n,
    CAST(NULL AS UUID) AS decision_id,
    CAST(NULL AS INTEGER) AS position,
    CAST(NULL AS VARCHAR) AS claim,
    d.outcome
FROM decisions AS d
WHERE d.outcome IS NOT NULL
GROUP BY d.verdict, d.outcome
