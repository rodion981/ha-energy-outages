# v2.6.0-alpha.1: Authenticated API / Авторизований API

Release date / Дата релізу: 2026-10-30. **Alpha / Альфа.**

## Українською

Перша тестова версія для нового API [Alerts Energy](https://alerts.energy/). Безкоштовний доступ для відкритої інтеграції надає команда Alerts Energy; особистий обліковий запис, підписка чи ключ не потрібні.

- Спільний ключ проєкту й один випадковий UUIDv4 установки для всіх областей, черг і кроків налаштування. UUID зберігається між перезапусками; ключ та UUID не включаються до diagnostics або атрибутів сутностей.
- Нові поля API `snake_case` перетворюються на існуючий внутрішній формат. Старі відповіді також підтримуються; ідентифікатори пристроїв, сутностей і публічні атрибути збережені.
- Мінімум 15 хв між запитами графіків області, включно з вибором черги, ручними оновленнями, reload і перезапуском. Старі інтервали 1–14 хв підвищуються до 15; більші зберігаються.
- `Retry-After` і поступове збільшення пауз після збоїв. Вимкнений polling не запускає автоматичних повторів.
- Відповідь і терміни наступних запитів зберігаються у сховищі HA. За наявності попередньої відповіді можливий запуск із кешем при збої API. Дати й статуси графіків перевіряються, час отримання не підміняється часом запуску.
- Посилання на джерело даних у виборі області та переналаштуванні, актуальні README українською й англійською.

У HACS відкрийте меню інтеграції, виберіть повторне завантаження та покажіть попередні версії, потім виберіть `v2.6.0-alpha.1`. Після встановлення перезапустіть Home Assistant. Це попередній реліз; стабільний `v2.5.1` не замінюється в GitHub Latest. Старий клієнт без авторизації може не працювати з новим API, тому повернення старої версії не гарантує відновлення доступу.

## English

First alpha for the new [Alerts Energy](https://alerts.energy/) API. The Alerts Energy team provides free access for this open integration; no personal account, subscription or API key is required.

- Shared project authorization and one persistent random installation UUIDv4 across regions, queues and setup flows. Neither the key nor UUID is exported in diagnostics or entity attributes.
- Normalize new snake_case responses while retaining legacy response support, device/entity identities and public entity attributes.
- Enforce at least 15 minutes between regional schedule requests across queue discovery, polling, manual refresh, reload and restart. Raise saved 1–14 minute intervals to 15; preserve longer intervals.
- Honor Retry-After and progressive error backoff. Disabled polling suppresses automatic retries.
- Persist responses and request deadlines. Previously saved responses allow cached startup during an API failure, with truthful update health and receipt times; expired, invalid or emergency schedules are not revived.
- Link the data source in region selection/reconfiguration and update both READMEs.

Select this prerelease through the repository's HACS redownload/version selector, then restart Home Assistant. GitHub Latest remains v2.5.1. Rolling back to the unauthenticated client may not restore access after the upstream API transition.

## Validation / Перевірки

- 290 tests on HA 2026.10 / Python 3.14, 99% coverage; Ruff, formatting, mypy and metadata validation passed before release preparation.
- Authenticated check, territory directory, Kyiv suppliers and schedules returned HTTP 200; all 72 received Kyiv schedule rows passed the integration's date-based schedule validation.
- Production installation and frontend acceptance are verified separately after publication; failure/cancellation/backoff cases are tested in isolation.
