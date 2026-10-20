# EufyMake Activity Lab

A developer-focused Home Assistant recorder for investigating EufyMake E1 cloud messages. It has its own domain, cloud connection and data folder, so EufyMake E1 Monitor updates do not replace it.

Preview 0.2.0. Automated tests pass; installation and independent cloud connectivity still need validation on real Home Assistant hardware. This is an unofficial community tool.

Local unreleased interpretation changes are described in [TELEMETRY_IMPLEMENTATION.md](TELEMETRY_IMPLEMENTATION.md). They are on an authorized review branch, not merged, released or deployed; HACS continues to install the published version.

## Installation through HACS

Requires Home Assistant Core 2026.10.0 or later and a public GitHub code repository. HACS does not support private GitHub repositories. Your data is not published with the code.

1. In HACS, open Custom repositories.
2. Add `https://github.com/deadmeat75/eufymake-activity-lab` with category Integration.
3. Download EufyMake Activity Lab. Enable beta versions if selecting a pre-release.
4. Restart Home Assistant.
5. Settings -> Devices & services -> Add integration -> EufyMake Activity Lab.
6. Choose **Use an existing EufyMake monitor** and select your printer. Credentials are reused locally; no file copying or code edits are needed.
7. Open **E1 Lab** in the sidebar as a Home Assistant administrator.

If no existing monitor is installed, choose Import Studio files. Import your `device_list.json`, `login_info.json` and matching broker CA certificate through Home Assistant's file selectors. Do not upload them to GitHub.

## What it records

- Every delivered raw state/step transition, including brief changes.
- Changed ink levels, expiration countdowns, waste capacity, print progress, remaining time and elapsed time from known commands 1000, 1001, 1068 and 1100.
- Numeric/boolean observations and structure from unfamiliar single-frame JSON commands on the subscribed topics. String values and recognizable sensitive field names are omitted.
- Connection, recording and session events, plus timestamped observation markers.
- Transport diagnostics: failed checksums, fragmented frames, malformed JSON, oversized frames and oversized batches.

Changed telemetry and unfamiliar commands are sampled no more than once per command every five seconds, except hardware identity changes from 1118/1153, which are retained immediately. State/step transitions are recorded immediately. Identical repeated messages are counted rather than repeatedly added to the timeline. This is an observation tool, not a complete packet capture.

## Interface

The sidebar shows current state/step, connection status, latest-message time and live telemetry cards. Ink percentages are also displayed as estimated mL for the six 100 mL cartridges; waste remains a percentage.

**Mark observation now** saves what you are seeing without waiting for a transition. Each timeline entry has a Details / note button. State/step entries also have a Label button that prefills the pair; mark labels suspected or confirmed based on your observations.

Filter by state/step, command number, label or note. The latest 300 entries are displayed; exports include all retained records. Dates use America/Los_Angeles on screen, including DST, and UTC in exports. CSV includes decoded fields as JSON in a column; JSON includes history, settings and labels. There is no export-import restore UI in this version.

Capture controls independently enable telemetry and unfamiliar-command recording. Pause/resume affects automatic records; you can still add manual markers. The history limit can be changed from 1,000 to 50,000 entries (default 10,000). Oldest entries are deleted when the limit is reached or reduced. Export periodically to retain them externally.

Durations describe state residence, not continuous cleaning time (especially for post-maintenance states 13/0 and 13/1). They measure the interval until the next recorded status, connection change or pause. They are not printer-reported timings. Telemetry messages and annotations do not end a status duration. A completed duration may include a missed transition if the cloud did not deliver it.

## Long-term storage

Data is stored separately in `/config/eufymake_activity_lab/<entry_id>.sqlite3`, using incremental transactions rather than rewriting the entire timeline. Files survive integration updates and Home Assistant restarts. Changes are normally saved within about two seconds, and pending records are flushed during a graceful shutdown. Abrupt power loss can lose the latest unsaved records.

Do not copy a live SQLite file alone as a backup: its WAL may contain recent transactions. Use the JSON export or stop Home Assistant before copying the database files. Home Assistant backups should include the data directory.

Removing the integration deletes its database; export first. Updating the integration does not remove data. Disabling it stops its independent cloud connection.

## Privacy and limitations

Config-entry credentials are stored by Home Assistant. Data files and exports do not intentionally include credentials or complete wire payloads. Text values and recognizable sensitive fields are omitted before recording. Unknown numeric fields may still contain identifying information: review unfamiliar-command exports before sharing. Do not put credentials in your notes or labels. Protect Home Assistant backups.

The tool uses verified TLS and a randomized MQTT client identity. It subscribes to the known broker topics and sends a telemetry query every 30 seconds. It does not start, cancel or otherwise control printing. Parallel connections with the normal monitor are not yet verified on hardware; disable Activity Lab if coexistence causes connection problems.

Only complete single frames are decoded. Fragmented frames are counted in diagnostics, not reassembled: their ordering semantics have not been established. Payloads over 1 MiB and batches over 256 entries are bounded. Diagnostic fields are bounded in depth, number of fields and list length. Supported region mappings are US, CA, MX, EU, GB, DE and FR.

A clean checksum is not a signature. The existing protocol uses AES-CBC and a checksum, protected in transit by verified broker TLS. No TLS or checksum validation is disabled.

## Development

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
npm --prefix tests ci
npm --prefix tests test
```

Python tests cover capture, redaction, known and unfamiliar commands, checksum/fragment diagnostics, deduplication, durations, annotations, bounded history, SQLite updates/deletions, restart behavior, admin-only actions, setup reuse and shutdown. Interface tests exercise real button clicks and form submissions in a DOM implementation. Home Assistant API doubles do not replace installation testing.

## Credits

Transport and credential parsing derive from the EufyMake E1 integration. Wire protocol derives from masto/eufy-ink (Unlicense); original credits and licenses are retained. New code is MIT licensed. Not affiliated with EufyMake or Home Assistant.
