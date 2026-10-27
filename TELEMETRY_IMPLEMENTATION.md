# Current preparation

See [NEXT_RELEASE.md](NEXT_RELEASE.md) for Monitor 1.2.0 / Activity Lab 0.4.0 behavior, evidence, limits and validation. The following sections document the previously published baseline; current waste colors, latch wording, optional notifications and history features supersede their older descriptions.

# Activity Lab 0.3.0 telemetry enhancement

Prepared for the authorized Activity Lab 0.3.0 release. No Home Assistant installation or restart is performed by publication. The existing integration, MQTT credentials/topics/query, SQLite journal, admin websocket actions, capture settings, retention, labels, notes, raw details, CSV/JSON exports and panel are retained.

New telemetry.py and interpretation.py add observed bed/accessory meanings, operation-specific maintenance progress and event-time interpretation. Bed codes 0/1/2/3 mean not detected/Standard/Mini/Rotary; accessory codes 0/1/2/4 mean not detected/Mini/Standard/Rotary. Zero detection does not establish physical absence. The mappings are deliberately independent. Unknown codes remain Unknown (code), with no guessed bed-present state. Reply belongs to command 1118 only; raw values and their times are preserved.

Important hardware changes bypass five-second sampling. Paired 1118/1153 reports do not produce duplicate detection descriptions. Baselines survive restart/reconnect without claiming a fresh installation. Redacted raw fields, original IDs, notes and revisions remain; old records are not rewritten. Timed duplicate packets are bounded-deduplicated; historical packets are ordered by their UTC observation time and cannot revert current values. MQTT callbacks capture receipt times before event-loop handoff; no job timestamp is mistaken for device event time.

Current progress uses command 1001, validated progress /100, remaining seconds and elapsed totalTime. Idle, reconnects and stale data do not revive old progress. New decoded maintenance progress uses 1148 for 5/7; 1155 for 5/9 and 5/10; 1136 for 5/3; snapshot uses 1105 for 8/0. It cannot replace print progress. 13/0 and 13/1 are post-maintenance states and their residence is not active cleaning time. Transitions describe a maintenance end without claiming success if its outcome is unknown.

Human displays use America/Los_Angeles with DST; JSON stays UTC. Existing user labels override built-in meanings. Version/model/serial metadata stays private in runtime memory; exported text remains omitted and numeric serial-number keys are now redacted. Tokens and identifiers are not logged. Complete wire payloads/fragment reassembly remain unavailable under the existing privacy/transport limits.

Validation: 35 Python tests and both jsdom suites pass. The identical available October 20 exports contain 5,501 retained events. Read-only replay of 5,373 field records identifies one Standard Flatbed detection change; later rotary observations are small synthetic fixtures copied from the user's exact physical tests. No real HA/MQTT, camera, physical iPad, deployment, HACS validator or restart test was run.

Dependencies, authentication and connection configuration are unchanged. The manifest, version constant and frontend cache URL identify version 0.3.0. Update the existing Activity Lab entry through HACS, or use the complete component ZIP from the v0.3.0 release. Export JSON and back up Home Assistant first; keep the database directory and configuration entry. The complete Lab component is in this project's custom_components/eufymake_activity_lab folder and in the versioned GitHub release ZIP. Persistent databases remain outside that folder and must not be overwritten.

New reports deliberately use detected/no-longer-detected wording: a zero code may mean a physical absence or an unlocked latch. The fresh no-detection warning describes both possibilities without inventing a latch sensor. A red waste-fullness display is derived from remaining capacity; raw fields remain unchanged. Configured history retention is respected during startup so a larger saved history is not truncated to the constructor's default. No database migration or deletion occurs.
