// ================================================================
// CYBER-PHYSICAL SECURITY | KNOWLEDGE GRAPH CYPHER QUERY LIBRARY
// ================================================================
// Neo4j property graph. Read-only queries; none changes graph data.
// Execute ONE query at a time in Neo4j Query (each ends in ;).
// Existing schema: User, Device, PhysicalEvent, CyberEvent, Location.
// Location display property is `location` (not `name`).
// Event timestamps are LOCAL DATETIME; normal_start/end are strings.
//
// Q1-Q11: exploration, correlation, contextual features and validation.
// Q12: KG-first symbolic-reasoning context export (separate from Q8).
//
// IMPORTANT: Q8 is a general scenario-evidence output. Q12 is the
// exact column layout expected by the KG-first Colab notebook.
// Q12 intentionally exports physical_event_id and cyber_event_id;
// scenario_id (S0001 etc.) is joined in Python using the mapping CSV.
// The query results are facts/context, NOT final rule-based risk.
// ================================================================

// ------------------------------------------------------------
// Q1. Basic one-hop traversal: User -> Device
// ------------------------------------------------------------
MATCH (u:User)-[:USES]->(d:Device)
RETURN
    u.user_id AS user_id,
    u.role AS role,
    u.department AS department,
    d.device_id AS device_id
ORDER BY u.user_id
LIMIT 20;

// ------------------------------------------------------------
// Q2. Physical-security context: User -> PhysicalEvent -> Location
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
RETURN
    u.user_id AS user_id,
    p.event_id AS physical_event_id,
    p.timestamp AS physical_timestamp,
    l.location AS location,
    l.location_type AS location_type,
    p.access_result AS access_result
ORDER BY p.event_id
LIMIT 20;

// ------------------------------------------------------------
// Q3. Cybersecurity context: User -> Device -> CyberEvent
// ------------------------------------------------------------
MATCH (u:User)-[:USES]->(d:Device)-[:GENERATED]->(c:CyberEvent)
RETURN
    u.user_id AS user_id,
    d.device_id AS device_id,
    c.event_id AS cyber_event_id,
    c.timestamp AS cyber_timestamp,
    c.severity AS cyber_severity,
    c.failed_logins AS failed_logins,
    c.files_accessed AS files_accessed,
    c.sensitive_files AS sensitive_files,
    c.usb_connected AS usb_connected
ORDER BY c.event_id
LIMIT 20;

// ------------------------------------------------------------
// Q4. Cross-domain scenario traversal
// PhysicalEvent -> CORRELATED_WITH -> CyberEvent, validated through
// the same user's assigned device.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
MATCH (u)-[:USES]->(d:Device)-[:GENERATED]->(c)
RETURN
    u.user_id AS user_id,
    d.device_id AS device_id,
    p.event_id AS physical_event_id,
    l.location AS location,
    c.event_id AS cyber_event_id
ORDER BY p.event_id
LIMIT 20;

// ------------------------------------------------------------
// Q5. Temporal context derivation
// after_hours is computed from the event time and user's working
// hours. time_gap_minutes is computed from event timestamps.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
WITH
    u, p, c,
    (
        time(p.timestamp) < time(u.normal_start)
        OR time(p.timestamp) > time(u.normal_end)
    ) AS after_hours,
    duration.inSeconds(p.timestamp, c.timestamp).seconds / 60.0 AS time_gap_minutes
RETURN
    u.user_id AS user_id,
    p.event_id AS physical_event_id,
    p.timestamp AS physical_timestamp,
    after_hours,
    c.event_id AS cyber_event_id,
    c.timestamp AS cyber_timestamp,
    round(time_gap_minutes, 2) AS time_gap_minutes
ORDER BY p.event_id
LIMIT 20;

// ------------------------------------------------------------
// Q6. Security-focused conjunctive query
// Retrieves scenarios combining after-hours activity at a
// restricted location with a Medium/High cyber event.
// This query retrieves suspicious context; it does NOT assign
// the final security risk.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
MATCH (u)-[:USES]->(d:Device)-[:GENERATED]->(c)
WITH
    u, p, l, c, d,
    (
        time(p.timestamp) < time(u.normal_start)
        OR time(p.timestamp) > time(u.normal_end)
    ) AS after_hours,
    duration.inSeconds(p.timestamp, c.timestamp).seconds / 60.0 AS time_gap_minutes
WHERE after_hours = true
  AND l.location_type = 'Restricted'
  AND c.severity IN ['Medium', 'High']
RETURN
    u.user_id AS user_id,
    d.device_id AS device_id,
    p.event_id AS physical_event_id,
    p.timestamp AS physical_timestamp,
    l.location AS location,
    l.location_type AS location_type,
    p.access_result AS access_result,
    after_hours,
    c.event_id AS cyber_event_id,
    c.timestamp AS cyber_timestamp,
    c.severity AS cyber_severity,
    c.failed_logins AS failed_logins,
    c.files_accessed AS files_accessed,
    c.sensitive_files AS sensitive_files,
    c.usb_connected AS usb_connected,
    round(time_gap_minutes, 2) AS time_gap_minutes
ORDER BY time_gap_minutes;

// ------------------------------------------------------------
// Q7. Representative scenario finder
// Use the returned IDs for both the graph screenshot and table
// screenshot so that the figures remain consistent.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
MATCH (u)-[:USES]->(d:Device)-[:GENERATED]->(c)
WHERE
    (
        time(p.timestamp) < time(u.normal_start)
        OR time(p.timestamp) > time(u.normal_end)
    )
    AND l.location_type = 'Restricted'
    AND c.severity IN ['Medium', 'High']
RETURN
    u.user_id AS user_id,
    d.device_id AS device_id,
    p.event_id AS physical_event_id,
    l.location AS location,
    c.event_id AS cyber_event_id,
    c.severity AS cyber_severity
ORDER BY p.event_id
LIMIT 1;

// ------------------------------------------------------------
// Q8. Final reasoning-integration extraction query
// This is the proposed KG -> symbolic reasoning interface.
// It returns one structured row per correlated scenario.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
MATCH (u)-[:USES]->(d:Device)-[:GENERATED]->(c)
WITH
    u, p, l, c, d,
    (
        time(p.timestamp) < time(u.normal_start)
        OR time(p.timestamp) > time(u.normal_end)
    ) AS after_hours,
    duration.inSeconds(p.timestamp, c.timestamp).seconds / 60.0 AS time_gap_minutes
RETURN
    u.user_id AS user_id,
    u.role AS role,
    u.department AS department,
    d.device_id AS device_id,
    p.event_id AS physical_event_id,
    p.timestamp AS physical_timestamp,
    l.location AS location,
    l.location_type AS location_type,
    p.access_result AS access_result,
    after_hours,
    c.event_id AS cyber_event_id,
    c.timestamp AS cyber_timestamp,
    c.severity AS cyber_severity,
    c.failed_logins AS failed_logins,
    c.files_accessed AS files_accessed,
    c.sensitive_files AS sensitive_files,
    c.usb_connected AS usb_connected,
    round(time_gap_minutes, 2) AS time_gap_minutes
ORDER BY p.event_id;

// ------------------------------------------------------------
// Q9. KG structural and integrity validation
// Expected results:
// User=50, Device=50, PhysicalEvent=800, CyberEvent=800,
// Location=9; USES=50; PERFORMED/AT/GENERATED/CORRELATED_WITH=800;
// orphan checks=0; min/max correlations per PhysicalEvent=1.
// ------------------------------------------------------------
CALL () {
    MATCH (u:User)
    RETURN 1 AS order, 'User nodes' AS validation_check, count(u) AS result
    UNION ALL
    MATCH (d:Device)
    RETURN 2 AS order, 'Device nodes' AS validation_check, count(d) AS result
    UNION ALL
    MATCH (p:PhysicalEvent)
    RETURN 3 AS order, 'PhysicalEvent nodes' AS validation_check, count(p) AS result
    UNION ALL
    MATCH (c:CyberEvent)
    RETURN 4 AS order, 'CyberEvent nodes' AS validation_check, count(c) AS result
    UNION ALL
    MATCH (l:Location)
    RETURN 5 AS order, 'Location nodes' AS validation_check, count(l) AS result
    UNION ALL
    MATCH (:User)-[r:USES]->(:Device)
    RETURN 6 AS order, 'USES relationships' AS validation_check, count(r) AS result
    UNION ALL
    MATCH (:User)-[r:PERFORMED]->(:PhysicalEvent)
    RETURN 7 AS order, 'PERFORMED relationships' AS validation_check, count(r) AS result
    UNION ALL
    MATCH (:PhysicalEvent)-[r:AT]->(:Location)
    RETURN 8 AS order, 'AT relationships' AS validation_check, count(r) AS result
    UNION ALL
    MATCH (:Device)-[r:GENERATED]->(:CyberEvent)
    RETURN 9 AS order, 'GENERATED relationships' AS validation_check, count(r) AS result
    UNION ALL
    MATCH (:PhysicalEvent)-[r:CORRELATED_WITH]->(:CyberEvent)
    RETURN 10 AS order, 'CORRELATED_WITH relationships' AS validation_check, count(r) AS result
    UNION ALL
    OPTIONAL MATCH (p:PhysicalEvent)
    WHERE NOT EXISTS { MATCH (:User)-[:PERFORMED]->(p) }
    RETURN 11 AS order, 'PhysicalEvents without User' AS validation_check, count(p) AS result
    UNION ALL
    OPTIONAL MATCH (p:PhysicalEvent)
    WHERE NOT EXISTS { MATCH (p)-[:AT]->(:Location) }
    RETURN 12 AS order, 'PhysicalEvents without Location' AS validation_check, count(p) AS result
    UNION ALL
    OPTIONAL MATCH (c:CyberEvent)
    WHERE NOT EXISTS { MATCH (:Device)-[:GENERATED]->(c) }
    RETURN 13 AS order, 'CyberEvents without Device' AS validation_check, count(c) AS result
    UNION ALL
    MATCH (p:PhysicalEvent)
    OPTIONAL MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
    WITH p, count(c) AS correlation_count
    WITH min(correlation_count) AS min_count
    RETURN 14 AS order, 'Minimum correlations per PhysicalEvent' AS validation_check, min_count AS result
    UNION ALL
    MATCH (p:PhysicalEvent)
    OPTIONAL MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
    WITH p, count(c) AS correlation_count
    WITH max(correlation_count) AS max_count
    RETURN 15 AS order, 'Maximum correlations per PhysicalEvent' AS validation_check, max_count AS result
}
RETURN validation_check, result
ORDER BY order;

// ------------------------------------------------------------
// Q10. After-hours validation
// Validated project result: FALSE=548, TRUE=252.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)
WITH
    (
        time(p.timestamp) < time(u.normal_start)
        OR time(p.timestamp) > time(u.normal_end)
    ) AS after_hours
RETURN after_hours, count(*) AS number_of_events
ORDER BY after_hours;

// ------------------------------------------------------------
// Q11. Temporal-gap validation against CORRELATED_WITH property
// The calculated timestamp gap should match the stored validation
// property (maximum difference approximately zero).
// ------------------------------------------------------------
MATCH (p:PhysicalEvent)-[r:CORRELATED_WITH]->(c:CyberEvent)
WITH
    r,
    duration.inSeconds(p.timestamp, c.timestamp).seconds / 60.0 AS calculated_gap
RETURN
    count(*) AS scenarios,
    round(min(calculated_gap), 2) AS minimum_gap,
    round(avg(calculated_gap), 2) AS average_gap,
    round(max(calculated_gap), 2) AS maximum_gap,
    round(max(abs(calculated_gap - r.time_gap_minutes)), 6) AS maximum_difference_from_stored;


// ------------------------------------------------------------
// Q12. KG-FIRST REASONING EXPORT (kg_scenario_context.csv)
// ------------------------------------------------------------
// Use this query to feed Member 4's R1-R11 Python rule engine.
// 1. Run this query alone in Neo4j Query.
// 2. Switch to Table view; export the entire result as CSV.
// 3. Name the file kg_scenario_context.csv.
// 4. Join by physical_event_id + cyber_event_id to scenario_id_mapping.csv
//    in the notebook; do NOT invent scenario_id from Neo4j row order.
// Expected: 800 rows for the currently validated project graph.
// Temporal-proximity rule threshold (0-10 min) is applied in Python,
// not in this query; time_gap_minutes remains a measured value.
// ------------------------------------------------------------
MATCH (u:User)-[:PERFORMED]->(p:PhysicalEvent)-[:AT]->(l:Location)
MATCH (p)-[:CORRELATED_WITH]->(c:CyberEvent)
MATCH (u)-[:USES]->(d:Device)-[:GENERATED]->(c)
RETURN
  p.event_id AS physical_event_id,
  c.event_id AS cyber_event_id,
  u.user_id AS user_id,
  d.device_id AS device_id,
  p.timestamp AS physical_timestamp,
  c.timestamp AS cyber_timestamp,
  l.location AS location,
  l.location_type AS location_type,
  p.access_result AS access_result,
  (time(p.timestamp) < time(u.normal_start) OR time(p.timestamp) > time(u.normal_end)) AS after_hours,
  c.severity AS cyber_severity,
  c.failed_logins AS failed_logins,
  c.files_accessed AS files_accessed,
  c.sensitive_files AS sensitive_files,
  c.usb_connected AS usb_connected,
  round(duration.inSeconds(p.timestamp,c.timestamp).seconds / 60.0, 4) AS time_gap_minutes
ORDER BY p.event_id;
