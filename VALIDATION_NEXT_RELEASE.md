# Release 0.4.0: validation

- Python: 54 tests passed with the existing unittest framework and HA API doubles.
- UI: `npm --prefix tests test (three jsdom suites)` passed. New cases cover approved UI behavior, escaping, freshness and history. Lab additionally checks bookmark/session/compare actions, paged rendering and copied codes.
- All component Python files parse; JSON metadata/translations parse; frontend JavaScript syntax checks pass.
- Existing MQTT configuration/authentication and entity IDs are retained. No external Python runtime dependencies were added; Monitor enables the built-in HA persistent-notification component.
- Existing notes/labels/IDs are covered by compatibility tests. New history survives restart without restoring an active job. Journal tests cover incremental SQLite persistence and new bookmark/session actions.
- Read-only replay of the available 7,639-event October 27 export generated bounded history without changing its source. Second-export completion findings are user-reported and covered by synthetic cases, not locally replayed.
- Archive integrity, full component file membership and manifest/cache versions are checked during packaging. See the artifact directory’s SHA256SUMS for checksums.
- Live Home Assistant/printer/MQTT deployment, physical iPad behavior, hassfest/HACS validation, push notifications and camera access were not tested. Notifications implemented here are local persistent HA notifications, disabled by default.
- GitHub commit/tag/publication is authorized separately from the completed local preparation. Home Assistant installation and restart are not performed by publication.

See NEXT_RELEASE.md and MANUAL_INSTALL.md for scope, uncertainty and manual verification.
