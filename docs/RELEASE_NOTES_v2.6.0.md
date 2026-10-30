# v2.6.0: Authenticated API / Авторизований API

Release date / Дата релізу: 2026-10-30.

## Українською

Стабільна версія для нового авторизованого API [Alerts Energy](https://alerts.energy/). Команда Alerts Energy надає безкоштовний доступ для цієї відкритої інтеграції: особистий обліковий запис, підписка чи ключ не потрібні.

- Спільний ключ проєкту та один постійний випадковий UUIDv4 установки для всіх областей, черг і кроків налаштування. Ключ та UUID не включаються до diagnostics або атрибутів сутностей.
- Підтримка нових полів snake_case і попереднього формату відповідей без зміни ідентифікаторів пристроїв, сутностей та їхніх публічних атрибутів.
- Мінімум 15 хв між запитами графіків області, включно з вибором черги, ручним оновленням, reload і перезапуском. Раніше збережені інтервали 1–14 хв підвищуються до 15; більші зберігаються.
- Обробка Retry-After і поступове збільшення пауз після збоїв. Вимкнення polling вимикає автоматичні повтори.
- Постійний кеш відповідей і термінів наступних запитів. Якщо відповідь уже збережена, можливий запуск із кешем при тимчасово недоступному API. Дати та статуси графіків перевіряються; нова непридатна відповідь не підміняється старим планом.
- Клікабельне посилання на Alerts Energy у виборі області, переналаштуванні та налаштуваннях інтервалу опитування. Оновлені README українською й англійською.

Оновіть інтеграцію через HACS і перезапустіть Home Assistant. Існуючі записи й сутності зберігаються. Для відкритих до оновлення вкладок HA може знадобитися оновлення сторінки та повторне відкриття форми.

Інтеграція показує опубліковані планові та можливі інтервали, а не виміряну наявність світла. Локальні аварійні відключення можуть відбуватися поза графіком. Старий клієнт без авторизації може не працювати з новим API, тому повернення попередньої версії не гарантує відновлення доступу.

## English

Stable support for the new authenticated [Alerts Energy](https://alerts.energy/) API. The Alerts Energy team provides free access for this open integration; no personal account, subscription or API key is required.

- Shared project authorization and one persistent random installation UUIDv4 across regions, queues and setup flows. Neither the key nor UUID is exported in diagnostics or entity attributes.
- Normalize new snake_case and legacy responses while preserving device/entity identities and public entity attributes.
- Enforce at least 15 minutes between regional schedule requests across queue discovery, polling, manual refresh, reload and restart. Raise saved 1–14 minute intervals to 15; preserve longer intervals.
- Honor Retry-After and progressive error backoff. Disabled polling suppresses automatic retries.
- Persist responses and request deadlines. Previously saved responses allow cached startup during API failures, with truthful receipt times and per-day validity. Never revive an older published plan after a new unusable response.
- Link Alerts Energy in region selection, reconfiguration and polling options, and update both READMEs.

Update through HACS and restart Home Assistant. Existing entries and entities are retained. Refresh previously open HA tabs and reopen the form if its text has not updated.

The integration reports published planned/possible intervals, not measured grid power. Local emergency outages can occur outside the plan. Rolling back to the unauthenticated client may not restore access after the upstream API transition.

## Validation / Перевірки

- Local HA runtime tests, Ruff, formatting, mypy and metadata checks; exact final commit/tag CI, HACS and hassfest verified before publication.
- Authenticated API check, directories and Kyiv schedules were verified live. The alpha was loaded successfully on an existing HA installation with both configured entries and all 20 entities preserved; current schedules, calendars, options and the region-selection provider link were checked, with no integration errors in the filtered startup log.
- Backoff, cancellation, durable cache/identity and failure cases are verified in isolated tests, without forced production outages. The polling-options provider link is additionally covered by options-flow tests.
