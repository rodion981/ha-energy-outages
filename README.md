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
- An **Outage now** binary sensor for the current scheduled outage.
- **Next outage**, **Expected restoration** and **Outage duration** for dashboards and automations.
- **Data status** and **Last successful API update**, visible during source failures.
- Configurable polling interval, defaulting to 15 minutes, with one shared API request per active region.
- English and Ukrainian entity names and status labels.

> [!NOTE]
> This integration shows **planned schedules**, not measured grid power. Selecting a settlement does not discover your queue from an address: check the exact operator and queue on your electricity operator's official website.

## In Home Assistant

<img src="https://raw.githubusercontent.com/rodion981/ha-energy-outages/main/docs/images/integration-entities.png" alt="Alerts Energy Outages sensors and diagnostics in the Ukrainian Home Assistant interface" width="400">

Example from a working installation with the Ukrainian interface. Entity names follow Home Assistant's language; schedules and relative times in the screenshot are an example.

## Requirements

- Home Assistant **2024.6 or newer**.
- Internet access from Home Assistant to `https://alerts.energy`.
- HACS for installation and updates. No Alerts Energy account or API key is required.

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

Each configured queue creates **eight entities**:

| Entity | Purpose |
|---|---|
| Today schedule | All published outage periods for today |
| Tomorrow schedule | All published outage periods for tomorrow |
| Outage now | On while the current time is inside a scheduled outage |
| Next outage | Date and time of the next future outage start; excludes an ongoing outage |
| Expected restoration | Published end of the current outage, or the nearest upcoming one when none is ongoing |
| Outage duration | Full planned duration of that current/upcoming outage in minutes, when both boundaries are known |
| Data status | Today's publication, validity and source availability; attributes also describe tomorrow |
| Last successful API update | Time of the last successful response, retained during failures |

Find the actual entity IDs under **Settings → Devices & services → Alerts Energy Outages → Entities**. The last two entities are in the device's **Diagnostics** section.

Add the entities to an **Entities** card. For notifications, use **Next outage** in an automation time trigger, or the on/off transitions of **Outage now**. Duration is a full period, not a countdown.

## Reading the data

- **`unavailable`:** the relevant schedule is missing, invalid, undated, stale or unpublished, or its API update failed. Today and tomorrow are checked independently.
- **`unknown`:** a forecast entity has no matching event in published coverage, or its required boundary is unknown. This does not mean a zero-minute outage.
- **Midnight:** an outage ending at `24:00` in today's display may continue tomorrow. Restoration and full duration stay unknown until published coverage confirms an end. Continuous outages merge across midnight when both days are published.
- **Unknown start:** an outage already ongoing at the beginning of today's coverage may have started yesterday. Its full duration is unknown, but a published restoration remains available.
- **No scheduled outages:** a valid, dated schedule with 24 zero codes means no planned outages for that day. Emergency and unknown source statuses are not interpreted as power being available.

Calculations use **Europe/Kyiv**, including daylight saving transitions. Timestamp entities are displayed in Home Assistant's timezone. **Next outage** can describe a later period while restoration and duration describe the ongoing one.

Data status has stable machine values: `published`, `unpublished`, `stale`, `invalid`, `not_found`, `connection_error` and `emergency`. Frontend labels are translated. API response time is separate from the source's schedule publication time.

### Attributes for automations

Schedule sensors expose `area`, `operator`, `queue`, `date`, `updated`, `hours`, `periods`, `source_status` and `schedule_status`. Each period has `start` and `end`; long text states may be shortened, but all periods remain in attributes.

Forecast sensors expose `outage_context` (`current`, `next`, `none`), `outage_start`, `outage_end`, `coverage_end` and `forecast_status`. Data status attributes include `today_schedule_status` and `tomorrow_schedule_status`.

For automations, use typed timestamps, the binary sensor and machine attributes instead of matching translated schedule text.

For tomorrow's schedule notifications, select your **Tomorrow schedule** entity and watch its state and attribute changes. Send only while it is available and `schedule_status` is `published`; build the message from `date` and all `periods`. An empty `periods` list on a published schedule means no planned outages. To notify about corrections too, compare `date` and `periods` with the last sent schedule. Persist that record in a Home Assistant helper to prevent duplicates after reconnects or restarts; changes to `updated` alone should not resend a notification. Create the automation and select your notification service in Home Assistant.

## Source and updates

The integration reads the public Alerts Energy endpoint:

```text
https://alerts.energy/api/v1/source-registry/areas/{area}/shutdowns
```

It selects the exact operator/queue record and interprets each hourly code as two half-hour slots: `0` = no planned outage, `1` = outage for the whole hour, `2` = first half, `3` = second half. Adjacent slots form continuous periods.

Entries in the same region share one poller and clock listener. Removing one entry keeps the others working; removing the last releases the region's resources. Source coverage and publication depend on Alerts Energy, and its API may change.

Set the interval under **Settings → Devices & services → Alerts Energy Outages → Configure** for the relevant entry: **1–1440 whole minutes**, default **15**. It applies without restarting HA or reloading entities. The shared regional poller uses the shortest interval among entries with polling enabled; entries with polling disabled do not shorten it. Half-hour schedule transitions continue to update independently of API polling.

Update through HACS and restart Home Assistant. Configured entries and their entity identities are retained.

## Support and development

Report bugs and suggestions through [GitHub Issues](https://github.com/rodion981/ha-energy-outages/issues). Include your integration/HA versions, the region/operator/queue and diagnostics; never include passwords or tokens.

[Development and checks](./CONTRIBUTING.md) · [Changelog](./CHANGELOG.md) · [Releases](https://github.com/rodion981/ha-energy-outages/releases)

Support development through [monobank](https://send.monobank.ua/jar/9jqG7oXrZG) or [Patreon](https://www.patreon.com/c/Rodion_Kurylenko).

Made with ❤️ in Ukraine. Licensed under [MIT](./LICENSE).
