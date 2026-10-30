# v2.7.1: Midnight rollover / Перехід доби

Release date / Дата релізу: 2026-10-31.

## Українською

- Виправлено втрату доступності графіка після півночі за Києвом: вже опубліковане «завтра» з відповідною датою використовується як «сьогодні» без очікування нового запиту API. Це працює для сенсорів, прогнозів, календаря та часу перевірки джерелом, також під час збою API або запуску зі збереженим кешем.
- Планові й можливі інтервали залишаються прив'язаними до початкової дати. Час останнього успішного отримання, ліміти запитів та ідентифікатори сутностей не змінюються. Учорашні аварійні повідомлення не переносяться; відсутній, некоректний або аварійний новий графік не підміняється старим планом.
- Додано [YAML-приклад мобільної картки](https://github.com/rodion981/ha-energy-outages/blob/v2.7.1/examples/outage-card.yaml) зі шкалами планових/можливих інтервалів, прогнозом наступної події, попередженнями й часом отримання/перевірки даних. Потрібен `custom:button-card` і підстановка власних entity IDs; картка не додається на дашборд автоматично. Вимірювання фактичного живлення є окремою необов'язковою сутністю.
- Оновлено обидва README, додано чітке зображення прикладу та регресійні тести переходу доби, кешу, перезапуску й літнього часу.

Оновіть інтеграцію через HACS і перезапустіть Home Assistant. Переналаштування наявних записів не потрібне. Джерело даних: [Alerts Energy](https://alerts.energy/).

## English

- Fix schedule availability after Kyiv midnight: an already published tomorrow schedule with the matching date becomes today's schedule without waiting for another API request. Sensors, forecasts, calendar and source-check timestamps use this view, including API failures and persisted-cache startup.
- Keep planned and possible intervals tied to their original date. Preserve the last successful receipt, request limits and entity identities. Do not carry yesterday's emergency notices forward or replace a new missing, invalid or emergency schedule with an old plan.
- Add a [mobile dashboard YAML example](https://github.com/rodion981/ha-energy-outages/blob/v2.7.1/examples/outage-card.yaml) with planned/possible bars, the next event, warnings and separate API/source timestamps. It requires `custom:button-card` and your entity IDs; no dashboard card is installed automatically. Measured power is an optional, separate entity.
- Update both READMEs with a high-resolution example and add midnight, cached recovery, restart and DST regression coverage.

Update through HACS and restart Home Assistant. Existing entries need no reconfiguration. Data provided by [Alerts Energy](https://alerts.energy/).

## Validation / Перевірки

Local HA 2026.10/Python 3.14 validation: 346 tests, 99% integration coverage, metadata, Ruff, formatting and mypy. Tests exercise real HA entities with controlled API responses, including setup/reload/unload, disabled polling, cached failures and date expiry. Hosted CI checks the release commit/tag, including hassfest and HACS.

The card's YAML/JavaScript and its mobile layout were checked with synthetic data in a separate preview. This is not a screenshot or acceptance test of the card in a running Home Assistant frontend. Publication does not establish installation or live API acceptance on a user's HA instance.
