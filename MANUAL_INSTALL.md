# Monitor 1.2.0 / Activity Lab 0.4.0: installation and verification

Use the numbered GitHub releases through HACS. HACS can take time to refresh its repository data after publication. Do not remove and re-add your integrations. This task does not install anything in Home Assistant or restart it.

## When you choose to install

1. Make a Home Assistant backup and download an Activity Lab JSON backup. Save copies of the existing component folders.
2. Use HACS to update each existing integration separately. For a manual preview, extract its complete package and copy the entire matching `custom_components` folder over the existing folder:
   - Monitor: `custom_components/eufymake_e1` → `/config/custom_components/eufymake_e1`
   - Lab: `custom_components/eufymake_activity_lab` → `/config/custom_components/eufymake_activity_lab`
   Include new `insights.py` in both components, and `notifications.py` in Monitor. Copy all translations/frontend files too; do not upload just one edited file.
3. Preserve `/config/.storage` and `/config/eufymake_activity_lab`. These contain existing entries, credentials, saved dates and the Lab SQLite journal. There is no new dashboard YAML to paste, credential import to repeat, or MQTT configuration to change.
4. Restart Home Assistant yourself when ready to load the new files. Fully refresh the browser afterward. Expected versions: Monitor 1.2.0 and Lab 0.4.0. If rolling back manually, restore the saved component folders; do not delete data stores.

## Monitor checks

- Open your existing dashboard in both layouts. Confirm Ink Supply, remembered percent/mL preference, six live cartridge levels, printer dates and existing automation/entity references.
- Waste is tank **filled**, with a growing bar: green below 60%, yellow at 60–<80%, red at ≥80%. The native `waste_tank_remaining` sensor still means remaining capacity.
- Confirm bed/accessory codes and known dimensions in mm/inches. If no bed is detected, check physical installation and the closed latch. No separately measured latch position is claimed. Do not move accessories while the printer is operating.
- Read named missing readings and data age. Missing inactive-job metrics are expected. A stale/disconnected warning must not imply zero ink or an empty waste tank.
- On the next ordinary print, compare progress and timing with Studio. Estimated finish is hidden when paused or stale. Reaching 100% does not mark completion until Idle. Last completed print should preserve the last elapsed time after current elapsed resets.
- Expand print/maintenance/connection history and ink history. New Monitor history starts after installation; Activity Lab can backfill its retained records. Sampled charts and boundary usage are estimates, not exact accounting.
- Configure optional notifications and thresholds under **Settings → Devices & services → EufyMake E1 Monitor → Configure** (or the integration entry’s options control). All alerts default off. They create local HA persistent notifications, not mobile push messages. Connection loss must last two minutes; waste alerts rearm after remaining capacity rises above 25%. Completion requires fresh evidence.
- Choose per-color low-ink thresholds and percent/mL units. Numeric thresholds are equivalent for 100 mL cartridges. The default 10 is provisional; a native Eufy threshold has not been verified.
- Cartridge changes appear only if the printer supplies usable identity data. Do not replace ink or run cleaning just to test this update. Current levels/expiration still follow the printer when swapping back to an old cartridge.

## Activity Lab checks

- Confirm existing event IDs, notes, labels, capture settings, retention and raw fields remain. Backfilled summaries do not rewrite events. API actions stay administrator-only.
- Bookmark a retained event, reload, and enable **Only bookmarks**. Bookmarks can still be removed by normal retention.
- Select **Compare** on two records. Check changed numeric fields, missing/added fields, and array positions. Comparison operates on captured redacted fields, not full wire payloads.
- Open **Named recording sessions and bookmarks**, choose **Start named session**, enter a name/observation, add ordinary observation markers, then end it with a final observation. Download that session’s JSON; only retained session events and session metadata should be included. A named session can span a Home Assistant restart, but active job/cleaning contexts do not span connection gaps.
- **Load all retained records** fetches older events on demand. Navigate 300-row pages or filter them. Normal five-second refreshes fetch only the latest records.
- Download a full JSON backup and CSV. The existing CSV column layout is preserved; full JSON additionally carries bookmark/session metadata. Times display in America/Los_Angeles with DST; exported event timestamps remain UTC.

## Limits

The physical/app start distinction and job-quantity units are not verified. Source command 1140 remains experimental. No new printing, cleaning, bed movement, camera access or automatic machine actions are included. Physical HA/printer/iPad verification remains for installation; standalone tests do not prove deployment.
