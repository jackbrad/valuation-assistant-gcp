-- 06 — Feedback loop checks

-- 6.1 Review item status (derived, never stored)
CREATE OR REPLACE VIEW `${PROJECT}.val_ops.review_status` AS
SELECT r.review_id, r.route, r.requires_two_approvals, r.property_id, r.field, r.created_at,
  COUNTIF(d.decision = 'reject') AS rejects,
  COUNT(DISTINCT IF(d.decision = 'approve', d.reviewer_id, NULL)) AS approvals,
  CASE
    WHEN COUNTIF(d.decision = 'reject') > 0 THEN 'rejected'
    WHEN COUNT(DISTINCT IF(d.decision = 'approve', d.reviewer_id, NULL))
         >= IF(r.requires_two_approvals, 2, 1) THEN 'approved'
    ELSE 'open'
  END AS status
FROM `${PROJECT}.val_ops.review_items` r
LEFT JOIN `${PROJECT}.val_ops.review_decisions` d USING (review_id)
GROUP BY 1, 2, 3, 4, 5, 6;

-- 6.2 Assertion: must return ZERO rows.
-- Any applied correction without two distinct approvers who are not the flagger and have no stake.
SELECT c.correction_id
FROM `${PROJECT}.val_ops.corrections` c
LEFT JOIN `${PROJECT}.val_ops.review_decisions` d
  ON d.review_id = c.review_id AND d.decision = 'approve'
     AND d.reviewer_id != c.flagger_id AND NOT d.reviewer_has_stake
GROUP BY c.correction_id
HAVING COUNT(DISTINCT d.reviewer_id) < 2;

-- 6.3 Weekly random sample of confident, shown valuations → review queue
INSERT INTO `${PROJECT}.val_ops.review_items`
  (review_id, created_at, source, valuation_id, property_id, route, requires_two_approvals, summary)
SELECT GENERATE_UUID(), CURRENT_TIMESTAMP(), 'random_sample', valuation_id, property_id,
       'appraiser', FALSE, 'Random-sample QC of a valuation the gates passed'
FROM `${PROJECT}.val_core.valuations`
WHERE gate_result = 'shown' AND purpose != 'frozen_prelist'
  AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
ORDER BY RAND()
LIMIT ${RANDOM_SAMPLE_PER_WEEK};
