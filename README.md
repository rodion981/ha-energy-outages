# Alerts Energy Outages

Ukrainian power outage schedules from [Alerts Energy](https://alerts.energy/) directly in Home Assistant. Select your region, settlement, operator and exact queue to see published schedules, the next outage and expected restoration.

[![GitHub Release](https://img.shields.io/github/v/release/rodion981/ha-energy-outages?display_name=tag&sort=semver)](https://github.com/rodion981/ha-energy-outages/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![License](https://img.shields.io/github/license/rodion981/ha-energy-outages)](https://github.com/rodion981/ha-energy-outages/blob/main/LICENSE)
[![Support via monobank](https://img.shields.io/badge/Support-monobank-black)](https://send.monobank.ua/jar/9jqG7oXrZG)

[**English**](./README.md) | [Українською](./README.uk.md)

## Features

- Region, city/village, operator and exact queue selection through the Home Assistant UI.
- Today and tomorrow schedules with every outage period at 30-minute precision.
- An **Outage in schedule** binary sensor for the current planned/possible interval, with its type exposed separately.
- **Next outage**, **Expected restoration** and **Outage duration** for dashboards and automations.
- **Data status** and **Last successful API update**, visible during source failures.
- Configurable polling interval, defaulting to 15 minutes, with one shared API request per active region.
- English and Ukrainian entity names and status labels.

> [!NOTE]
> This integration shows **planned and possible schedule intervals**, not measured grid power. Possible intervals are included for planning; their application is not guaranteed. Selecting a settlement does not discover your queue from an address: check the exact operator and queue on your electricity operator's official website.

## In Home Assistant

<img src="https://raw.githubusercontent.com/rodion981/ha-energy-outages/main/docs/images/integration-entities.png" alt="Alerts Energy Outages sensors and diagnostics in the Ukrainian Home Assistant interface" width="400">

Example from a working installation with the Ukrainian interface. Entity names follow Home Assistant's language; schedules and relative times in the screenshot are an example.

## Requirements

- Home Assistant **2024.6 or newer**.
- Internet access from Home Assistant to `https://alerts.energy`.
- HACS for installation and updates. No personal Alerts Energy account, subscription or API key is required: the integration uses the shared project key provided by Alerts Energy.

The integration includes its own icon for Home Assistant 2026.3 and newer. Earlier supported versions may show a generic integration icon.

## Installation

1. Open the repository in HACS using **Open in HACS**, then download **Alerts Energy Outages**.
2. Restart Home Assistant.
3. Use **Add Integration**, or open **Settings → Devices & services → Add integration** and search for **Alerts Energy Outages**.
4. Complete the region, settlement, operator and queue selection.

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rodion981&repository=ha-energy-outages&category=integration)
[![Add Integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=alerts_energy_outages)

The first button requires HACS. The second works after downloading the integration and restarting Home Assistant.

If the repository is not listed, add `https://github.com/rodion981/ha-energy-outages` under **HACS → Custom repositories**, with type **Integration**.

## Region and queue selection

1. **Region:** choose an oblast or a city with special status. Kyiv city and Kyiv oblast have separate schedules.
2. **Settlement:** for an oblast, navigate through district and community to your city or village. You can go back or skip settlement selection; Kyiv city does not need this step.
3. **Operator:** select the electricity network serving your address. A region may contain several operators.
4. **Queue:** select your exact queue, enter a display name and finish setup.

Schedules are regional by **region + operator + queue**. A settlement is saved for convenience and does not produce a separate city schedule. Add separate entries for different queues or operators; the same regional schedule cannot be added twice through different cities.

If operators or queues are missing, retry or return to the previous selection. A directory listing does not guarantee a published schedule, and the integration never substitutes another queue.

To change a selection, open **Settings → Devices & services → Alerts Energy Outages → Reconfigure**. Changes apply after the final step; cancellation leaves the current setup unchanged. Existing entity IDs and the device are preserved.

## Entities

Each configured queue creates **ten entities**:

| Entity | Purpose |
|---|---|
| Today schedule | All published outage periods for today |
| Tomorrow schedule | All published outage periods for tomorrow |
| Outage in schedule | On inside a planned or possible interval; `outage_type` distinguishes them |
| Next outage | Date and time of the next future outage start; excludes an ongoing outage |
| Expected restoration | Published end of the current outage, or the nearest upcoming one when none is ongoing |
| Outage duration | Full planning interval duration, including possible intervals, when both boundaries are known |
| Data status | Today's publication, validity and source availability; attributes also describe tomorrow |
| Last successful API update | Time of the last successful response, retained during failures |
| Schedule change | Event when today's or tomorrow's schedule is published or its outage periods change |
| Outage calendar | Read-only calendar of published outage periods today and tomorrow |

Find the actual entity IDs under **Settings → Devices & services → Alerts Energy Outages → Entities**. **Data status** and **Last successful API update** are in the device's **Diagnostics** section.

Add the entities to an **Entities** card. For notifications, use **Next outage** in an automation time trigger, or the on/off transitions of **Outage in schedule**. Duration is a full period, not a countdown. Check `outage_type` when your automation must distinguish planned from conditional intervals.

## Reading the data

- **`unavailable`:** the relevant schedule is missing, invalid, undated, stale or unpublished. Today and tomorrow are checked independently. A failed API refresh alone does not hide a previously received schedule that is still valid for its date.
- **`unknown`:** a forecast entity has no matching event in published coverage, or its required boundary is unknown. This does not mean a zero-minute outage.
- **Midnight:** an outage ending at `24:00` in today's display may continue tomorrow. Restoration and full duration stay unknown until published coverage confirms an end. Continuous outages merge across midnight when both days are published.
- **Unknown start:** an outage already ongoing at the beginning of today's coverage may have started yesterday. Its full duration is unknown, but a published restoration remains available.
- **No scheduled outages:** both the valid planned and possible arrays contain no intervals for that date. A zero planned array alone does not exclude possible outages. Emergency and unknown source statuses are not interpreted as power being available.

Calculations use **Europe/Kyiv**, including daylight saving transitions. Timestamp entities are displayed in Home Assistant's timezone. **Next outage** can describe a later period while restoration and duration describe the ongoing one.

Data status has stable machine values: `published`, `unpublished`, `stale`, `invalid`, `not_found`, `connection_error` and `emergency`. Frontend labels are translated. API response time is separate from the source's schedule publication time.

### Attributes for automations

Schedule sensors expose `area`, `operator`, `queue`, `date`, `updated`, `hours`, `periods`, `source_status` and `schedule_status`. Each period has `start` and `end`; long text states may be shortened, but all periods remain in attributes.

`hours` remains the raw planned source array; `possible_hours` is the raw optional Possible field. **`periods` now contains the union of planned and possible intervals**, matching the website's planning view. Use `planned_periods` or `possible_periods` for the separate source classifications. Overlaps count once in the union. Schedule text labels conditional data as **Possible** or **Planned and possible**.

`outage_type` is `planned`, `possible`, `mixed` or `none`: it describes the whole day for schedule sensors, the current half hour for the binary sensor, and the selected interval for forecasts/calendar. Planned intervals take precedence in overlaps; `mixed` means there are also possible-only half hours. The binary sensor additionally exposes `planned_now` and `possible_now`; missing classifications use null. Always check entity availability before acting on attributes. All entities retain their unique IDs. Forecast timestamps and durations include conditional intervals for planning, without guaranteeing actual power-off/restoration times.

Forecast sensors expose `outage_context` (`current`, `next`, `none`), `outage_start`, `outage_end`, `coverage_end` and `forecast_status`. Data status attributes include `today_schedule_status` and `tomorrow_schedule_status`.

For automations, use typed timestamps, the binary sensor and machine attributes instead of matching translated schedule text.

### Schedule change notifications

1. Import the [notification blueprint](https://github.com/rodion981/ha-energy-outages/blob/main/blueprints/automation/schedule_changes.yaml) through **Settings → Automations & scenes → Blueprints → Import blueprint**. HACS installs the integration; import the blueprint separately.
2. Create an automation from the blueprint and select your queue's **Schedule change** event entity.
3. Keep the default action for a notification inside Home Assistant. For a phone or another channel, select its notification action and put `{{ notification_message }}` in the message field; `{{ notification_title }}` is also available. The supplied message is Ukrainian.
4. Save and enable the automation. Disable equivalent older schedule-change automations if you do not want duplicate messages from separate automations.

The message includes the queue, date, added/cancelled intervals and the full new schedule. It covers both today and tomorrow, including a newly published schedule without outages. One observed update changing both days produces one notification. The integration itself does not select or contact a notification service.

The first successful snapshot after setup/reload is a quiet baseline. Identical schedules, changes to `updated` alone, clock transitions, midnight rollover and recovery with unchanged periods do not produce new events. Published snapshots are retained by date through temporary missing/invalid data and restored by Home Assistant; reconfiguring the queue establishes a new baseline. Missing, stale, invalid and emergency data are never presented as cancellations. The event retains its last value during source failures; use **Data status** for current source health. Before the first change its state is `unknown`.

Changes are detected at the configured polling interval, without extra API requests. This reports differences between observed published snapshots, not every intermediate edit or changes while HA was stopped. No startup catch-up notification is sent.

For custom automations, the event type is `schedule_changed`. Attributes are `area`, `operator`, `queue` and `changes`. Each change contains `date`, `change_type` (`published` or `changed`), `before` (null for first publication), `after`, `added` and `removed`. Period lists contain `start`/`end` in Europe/Kyiv, including `24:00`. The event state is the detection timestamp. The supplied blueprint filters restored states and handles attribute-only event changes on older HA releases.

Change periods use the planning union. `planned`, `possible`, `previous_planned` and `previous_possible` retain each classification. If the union stays the same but the source classifications change, `classification_changed` is true: one notification explains the updated type without claiming intervals were added or cancelled. The blueprint explicitly identifies possible outages as conditional.

### Outage calendar

Each queue automatically gets an **Outage calendar** entity on its existing device. After installing the integration and restarting HA, open **Calendar** in the sidebar and enable that calendar, or add a **Calendar** dashboard card and select the entity. No `.ics` import is required. The calendar supports viewing and `calendar.get_events`; events cannot be created or edited manually.

Published intervals for today and tomorrow refresh with the configured regional poller, without additional requests. Cancelled/replaced periods disappear on the next successful refresh. Events use Europe/Kyiv source dates and are displayed in Home Assistant's timezone; continuous intervals merge across midnight when both days are published. Daylight saving changes use actual UTC intervals.

The calendar contains the available published dates, not history or a long-term forecast. A missing, stale, invalid or emergency day contributes no confirmed events, while the other published day remains visible. Empty dates outside that coverage do not mean there will be no outages. A failed API refresh retains previously received events whose schedule dates are still valid; the calendar becomes unavailable when neither day is published. `today_schedule_status` and `tomorrow_schedule_status` explain partial coverage.

An event touching the edge of published coverage is displayed only up to that boundary, with an explanation in its description. `event_start_known` and `event_end_known` describe the current/next event's actual boundary knowledge. Calendar event end can mean the published graph ends, rather than power restoration. Use **Expected restoration** for restoration notifications and **Schedule change** for graph revisions. Calendar automation triggers follow Home Assistant's calendar refresh cycle and may retain a previously queued event until that cycle refreshes.

## Source and updates

The integration reads the authenticated Alerts Energy endpoint:

```text
https://alerts.energy/api/v1/source-registry/areas/{area}/shutdowns
```

It selects the exact operator/queue record and interprets each hourly code as two half-hour slots: `0` = no planned outage, `1` = outage for the whole hour, `2` = first half, `3` = second half. Adjacent slots form continuous periods.

The same codes apply to `today_possible`/`tomorrow_possible`. An absent field or `[]` adds no conditional intervals; a present null, malformed array or unknown code makes that day's data unusable. Code `9` in either array or `EmergencyShutdowns` on a current date is emergency data. The main array must still be complete and dated; Possible alone cannot complete a missing schedule. `NoShutdowns` requires a zero planned array; separately supplied possible intervals still participate in planning, as on the source website.

Entries in the same region share one poller and clock listener. Removing one entry keeps the others working; removing the last releases the region's resources. Source coverage and publication depend on Alerts Energy, and its API may change.

Set the interval under **Settings → Devices & services → Alerts Energy Outages → Configure** for the relevant entry: **15–1440 whole minutes**, default **15**. It applies without restarting HA or reloading entities. The shared regional poller uses the shortest interval among entries with polling enabled; entries with polling disabled do not shorten it. Half-hour schedule transitions continue to update independently of API polling.

Requests to an area's schedules are separated by at least 15 minutes, including setup, queue selection, manual updates, reloads and restarts. Previously saved intervals below 15 minutes are raised to 15; longer intervals are preserved. Concurrent callers share the same regional response. After failures, retries use increasing delays (15, 30, 60 minutes and so on, capped at 24 hours); a longer configured interval or server `Retry-After` takes precedence. Disabling polling also disables automatic retries.

The last received response and request deadlines are saved in Home Assistant storage. This permits startup with retained data if the API is temporarily unavailable, provided a response has previously been saved. The last successful update keeps its actual receipt time. The schedule is usable only while its day/date and publication status are valid; new missing, invalid or emergency data replace the older response and are never silently replaced with an old published plan.

Each Home Assistant installation generates one random UUIDv4, persists it locally and sends it in `X-HA-Instance-ID` alongside the project authorization key on API requests. It is shared across all regions and queues, including setup flows. No address, Home Assistant URL or HA authentication token is sent. The project key and installation UUID are excluded from integration diagnostics and entity attributes. Data and free access for this integration are provided by [Alerts Energy](https://alerts.energy/).

Schedule/forecast sensors, the binary sensor and calendar expose **`data_is_cached: true`** while using a retained response after a failed refresh. **Data status** continues to report the actual error (`connection_error` or `invalid`), exposes the same flag and keeps the per-day statuses; **Last successful API update** retains its previous timestamp. A cached schedule may miss subsequent source corrections. Dashboards can display it with an update warning instead of hiding it solely because Data status reports a request error. Cached clock transitions and calculations continue, but dates are never extended or silently moved to another day. Recovery with unchanged periods does not produce a schedule-change notification.

Update through HACS and restart Home Assistant. Configured entries and their entity identities are retained.

## Support and development

Report bugs and suggestions through [GitHub Issues](https://github.com/rodion981/ha-energy-outages/issues). Include your integration/HA versions, the region/operator/queue and diagnostics; never include passwords or tokens.

[Development and checks](./CONTRIBUTING.md) · [Changelog](./CHANGELOG.md) · [Releases](https://github.com/rodion981/ha-energy-outages/releases)

Support development through [monobank](https://send.monobank.ua/jar/9jqG7oXrZG) or [Patreon](https://www.patreon.com/c/Rodion_Kurylenko).

Made with ❤️ in Ukraine. Licensed under [MIT](./LICENSE).
