# v2.4.5: configurable polling / налаштування інтервалу опитування

Release date: 2026-10-17. / Дата релізу: 2026-10-17.

## Українською

- Додано параметр інтервалу опитування API: від 1 до 1440 цілих хвилин, типово 15, як у v2.4.4.
- Зміна інтервалу діє одразу без перезапуску HA чи перезавантаження сутностей.
- Записи однієї області використовують один спільний запит із найкоротшим інтервалом серед записів з увімкненим опитуванням. Області мають незалежні інтервали; записи з вимкненим опитуванням не пришвидшують запити.
- Півгодинні переходи графіка, прогнозні сенсори й автоматизації за часом відключень працюють незалежно від частоти запитів API.

Після встановлення v2.4.5 через HACS перезапустіть Home Assistant. Відкрийте **Налаштування → Пристрої та служби → Alerts Energy Outages → Налаштувати** для потрібного запису й задайте інтервал у хвилинах. Існуючі записи без параметра зберігають інтервал 15 хвилин; сутності, пристрої та їхні ідентифікатори збережені. Підтримка HA 2024.6+ залишається.

## English

- Add an API polling interval option from 1 to 1440 whole minutes, defaulting to 15 as in v2.4.4.
- Apply interval changes immediately, without restarting HA or reloading entities.
- Entries in the same region share one request using the shortest interval among polling-enabled entries. Regions retain independent intervals; entries with polling disabled do not shorten them.
- Half-hour schedule transitions, forecasts and outage timestamp automations remain independent of the API polling interval.

Restart Home Assistant after installing v2.4.5 through HACS. Open **Settings → Devices & services → Alerts Energy Outages → Configure** for the relevant entry and set the interval in minutes. Existing entries without this option retain 15-minute polling; entities, devices and their identities are preserved. HA 2024.6+ remains supported.

## Validation / Перевірки

- 147 local tests passed on each HA baseline: HA 2024.6/Python 3.12 and HA 2026.10/Python 3.14.
- Local Ruff, formatting, mypy, metadata/translations validation and official hassfest passed.
- Runtime coverage includes options validation/persistence, live shorter/longer intervals, shared polling, disabled polling, regional isolation, unload/reload cleanup, clock transitions and an actual HA timestamp automation.
- Release gates: GitHub CI/HACS/hassfest on the exact PR/main/tag and archive verification before publication.
