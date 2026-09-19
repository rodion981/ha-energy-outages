# ⚡ Alerts Energy Outages for Home Assistant

[![release](https://img.shields.io/github/v/release/rodion981/ha-energy-outages?display_name=tag&sort=semver)](https://github.com/rodion981/ha-energy-outages/releases)
![hacs](https://img.shields.io/badge/HACS-Custom-orange)
[![patreon](https://img.shields.io/badge/support-patreon-ff424d)](https://www.patreon.com/c/Rodion_Kurylenko)

[**English**](./README.md) | [Українською](./README.uk.md)

A custom Home Assistant integration that retrieves power outage schedules from [alerts.energy/kyiv](https://alerts.energy/kyiv) for DTEK Kyiv Electric Networks outage groups.

## Features

- outage group configuration through the Home Assistant UI;
- schedules for today and tomorrow;
- all outage periods with 30-minute precision;
- an “Outage now” binary sensor;
- raw hourly codes and calculated outage periods in entity attributes;
- automatic data updates every 60 seconds.

The integration domain is `alerts_energy_outages`.

## Installation via HACS

1. Open **HACS → Integrations**.
2. Open the menu in the top-right corner and select **Custom repositories**.
3. Add the repository:

   ```text
   https://github.com/rodion981/ha-energy-outages
   ```

   Type: **Integration**.

4. Find and install **Alerts Energy Outages**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services → Add integration**.
7. Find **Alerts Energy Outages**, enter a name, and select your outage group.

## Created entities

For each configured outage group, the integration creates three entities:

| Entity | Purpose |
|---|---|
| Today schedule | All outage periods for the current day |
| Tomorrow schedule | All published outage periods for the next day |
| Outage now | Turns on when the current time falls within an outage period |

Home Assistant generates entity IDs from the config entry name and entity name. You can see the current IDs under **Settings → Devices & services → Alerts Energy Outages → Entities**.

### Schedule sensor attributes

| Attribute | Description |
|---|---|
| `queue` | Selected outage group, for example `2.2` |
| `operator` | Operator identifier used by Alerts Energy |
| `updated` | Time of the latest schedule change, if provided by the API |
| `hours` | Array containing 24 hourly codes |
| `periods` | Calculated periods with `start` and `end` fields |

Code values:

- `0` — power is available;
- `1` — no power for the entire hour;
- `2` — no power for the first 30 minutes;
- `3` — no power for the second 30 minutes.

## Migrating from v2.0.x

Versions `v2.0.1–v2.0.2` incorrectly used the legacy domain `yasno_outages`. Because of this, Home Assistant could mix config entries and show a migration error.

To migrate to `v2.1.0` or newer:

1. In **Settings → Devices & services**, remove the **Alerts Energy** config entry.
2. Remove the old **Alerts Energy Outages** version from HACS.
3. Restart Home Assistant.
4. Install the current version of **Alerts Energy Outages**.
5. Restart Home Assistant again and add the integration from scratch.

Starting with `v2.1.0`, the integration uses the dedicated `custom_components/alerts_energy_outages` directory.

## How it works

The integration polls the public Alerts Energy JSON endpoint:

```text
https://alerts.energy/api/v1/source-registry/areas/kyiv/shutdowns
```

For the selected outage group, it uses the `kyiv_oblenergo` operator entry. Hourly codes are converted into 30-minute boundaries, and adjacent segments are merged into continuous outage periods.

If the API is temporarily unavailable or returns an invalid structure, the coordinator marks the update as failed and Home Assistant keeps the most recently retrieved successful data.

## Legacy YAML package

The repository still includes the older YAML-based version:

```text
includes/packages/energyua_22.yaml
```

It is only needed for manual setup without the custom integration. For new installations, the HACS integration is recommended. Do not configure the same outage group through both HACS and the legacy YAML package at the same time, because this will create duplicate entities.

## Requirements

- Home Assistant 2024.6 or newer;
- Home Assistant must be able to access `https://alerts.energy`;
- HACS is only required for automatic installation and updates.

## Known limitations

- currently supports Kyiv and the DTEK Kyiv Electric Networks operator;
- an empty API array may mean either that there are no outages or that the schedule has not been published yet;
- the data source is a third-party service and its API format may change.

## Support

Report bugs and suggestions through [GitHub Issues](https://github.com/rodion981/ha-energy-outages/issues).

Made with ❤️ in Ukraine.
