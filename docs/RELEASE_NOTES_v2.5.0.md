# v2.5.0: outage calendar and schedule changes / календар і зміни графіка

Release date: 2026-10-17. / Дата релізу: 2026-10-17.

## Українською

- Новий календар відключень: опубліковані інтервали сьогодні й завтра, переходи через північ і коректний часовий пояс. Календар доступний лише для читання, без додаткових запитів API.
- Нова сутність події зміни графіка: публікація, додані та скасовані інтервали, зміна класифікації. Запуск, перезапуск, відновлення зв'язку та зміна лише часу відповіді API не створюють повторних сповіщень.
- [Blueprint сповіщень](https://github.com/rodion981/ha-energy-outages/blob/main/blueprints/automation/schedule_changes.yaml): виберіть сутність події й дію сповіщення. Типово створюється сповіщення у Home Assistant; інші канали налаштовуються користувачем.
- Можливі відключення з `todayPossible` / `tomorrowPossible` враховуються в графіках, прогнозах, binary sensor, календарі та подіях. Атрибути окремо показують планові/можливі інтервали й тип `planned`, `possible`, `mixed` або `none`.
- Важлива зміна для автоматизацій: `periods` тепер містить об'єднання планових і можливих інтервалів. Для лише планових використовуйте `planned_periods`, для можливих `possible_periods`. Сирий масив `hours` збережено; додано `possible_hours`.
- Прибрано тести старої HA 2024.6; поточна перевірена версія HA 2026.10/Python 3.14. Заявлений мінімум HACS 2024.6 незмінний, але більше не тестується.

Оновіть через HACS та перезапустіть Home Assistant. Кожен запис інтеграції отримує календар і сутність події автоматично; існуючі пристрої, сутності та їхні ідентифікатори збережено. Для сповіщень імпортуйте blueprint окремо й створіть автоматизацію. Для критичних сповіщень за точним часом використовуйте timestamp-сенсори: календарні тригери мають власний цикл оновлення Home Assistant.

## English

- Add a read-only calendar for published today/tomorrow outages, including midnight merging, timezone/DST handling and explicit unknown boundaries. Reuse existing polling without additional API requests.
- Add a schedule-change event for publication, added/cancelled periods and classification changes. Suppress startup/restart, unchanged recovery and response-timestamp-only notifications; restore bounded comparison snapshots.
- Add a [notification blueprint](https://github.com/rodion981/ha-energy-outages/blob/main/blueprints/automation/schedule_changes.yaml) with selectable event entity and notification action. The default creates a Home Assistant persistent notification; users configure other channels.
- Include optional `todayPossible` / `tomorrowPossible` intervals consistently across schedules, forecasts, binary sensor, calendar and events. Expose separate planned/possible intervals and `planned`, `possible`, `mixed` or `none` classifications.
- Automation behavior change: `periods` now contains the union of planned and possible intervals. Use `planned_periods` for planned-only and `possible_periods` for possible intervals. Preserve raw `hours` and add `possible_hours`.
- Retire HA 2024.6 tests. Current automated validation uses HA 2026.10/Python 3.14; the HACS 2024.6 minimum remains declared but is no longer tested.

Update through HACS and restart Home Assistant. Each integration entry automatically receives a calendar and event entity; existing entity/device identities are preserved. Import the blueprint separately and create an automation to enable notifications. For critical exact-time notifications use timestamp sensors: Home Assistant calendar triggers have their own refresh cycle.

## Validation / Перевірки

- 236 local tests passed on HA 2026.10/Python 3.14; Ruff, formatting, mypy, metadata/translations validation and official hassfest passed.
- Runtime coverage includes actual HA notification automations, restore/reload, classification-only changes, calendar HTTP/service calls and triggers, midnight/DST and recorded source examples.
- Hosted CI/HACS/hassfest and the tagged release archive are verified during publication. Installation and verification on an existing Home Assistant instance are separate deployment checks.
