# Possible outage data: investigation

Public API/frontend investigation snapshot: 2026-10-17. The contract below is now implemented locally; the captured examples remain a point-in-time source record.

## Verified contract

- `todayPossible` / `tomorrowPossible` are optional parallel arrays for the corresponding day's `Date` and `Status`, not probabilities or an alternative queue.
- Each populated array contains 24 integer hour codes: `0` = no interval, `1` = both half hours, `2` = first half, `3` = second half.
- The frontend accepts an absent field or `[]` as no additional intervals. A present `null`, malformed array, boolean or unknown code is not a valid zero array. Code `9` is treated as emergency data by the site's day-plan logic.
- For planning, the website takes the union of planned and possible half hours, merges adjacent intervals and counts overlaps once. Numeric `max` is wrong: planned `2` plus possible `3` must become `1`.
- A valid planned array and correct day date/status are still required. A possible array alone does not prove a missing/invalid main schedule is complete.
- Possible intervals are conditional, not measured outages or guaranteed disconnections.

Sources: [methodology](https://alerts.energy/methodology), the public [schedule helper](https://alerts.energy/chunk-TQSVM2VN.js) (`De`, `pe`, `au`, `oe`). Helper SHA-256 at inspection: `703d9098e57e4bf640aecd03c0a12067151df6a09a9d0eff506fd40325ae6243`. Hashed frontend filenames can change.

## Live evidence

All 27 root territories returned successfully. Six had nonzero Possible arrays, covering 96 queue/day records: Zakarpattia, Mykolaiv, Poltava, Kharkiv, Cherkasy and Chernivtsi. Counts and schedules are a point-in-time observation, not a coverage guarantee.

| Region, queue, source date | Current integration (planned only) | Website planning union |
|---|---|---|
| Zakarpattia, 1.1, 2026-10-17 | No outages | 10:00–12:00; 18:00–20:00 |
| Mykolaiv, 1.1, 2026-10-17 | 10:30–12:30 | 10:00–13:00 |
| Kharkiv, 1.1, 2026-10-17 | No outages | 07:00–10:30; 17:30–21:00 |
| Cherkasy / UZ, 1.1, 2026-10-18 | No outages | 14:00–17:00; 20:00–22:00 |

Public responses: `/api/v1/source-registry/areas/{area}/shutdowns` on `https://alerts.energy`, with area slugs `zakarpatska-oblast`, `mikolayivska-oblast`, `kharkivska-oblast`, `cherkaska-oblast`.

## Implementation and compatibility

The previous implementation validated and consumed only the main arrays. Its outputs are recorded in the table above. `schedule.py` now validates both arrays and normalizes their half-hour union for every platform, using the existing regional poller.

- Existing entity/device identities and raw source `hours` are preserved. `possible_hours`, `planned_periods`, `possible_periods` and `outage_type` are additive. Existing `periods`, forecast calculations, calendar events and binary on/off now use the planning union; both READMEs explicitly document that behavior change.
- Types are `planned`, `possible`, `mixed`, `none`; planned coverage takes precedence on overlaps. Schedule text, calendar descriptions/titles and the notification blueprint explicitly label conditional data. The binary sensor is called Outage in schedule and exposes `planned_now`/`possible_now`.
- Events compare both normalized source arrays, even if their union is unchanged. `classification_changed` then explains a type revision without false added/removed hours. Restore accepts legacy planned-only list snapshots and new planned/possible snapshots; setup/reload remains quiet.
- No missing, malformed, stale or emergency day is treated as zero outages. Main-array NoShutdowns consistency is retained, with Possible participating independently as in the source planner.

Regression cases cover all 16 code pairs, absent/empty/null/malformed Possible, emergency codes, NoShutdowns consistency, overlaps, recorded regional examples across all platforms, possible-only DST, mixed midnight intervals, unknown horizon, classification-only notifications and restore/reload. Source fixtures are in `tests/fixtures/possible_outages.json`; network access is not required for tests.
