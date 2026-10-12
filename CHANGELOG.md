# Changelog

## v2.4.0 (2026-10-12)

### English
- Add next outage, expected restoration and total outage duration with typed timestamps/minutes, explicit unknown horizons, midnight merging and DST-aware calculations.
- Add localized data status and last successful API response time, visible during failures.
- Share one poller/clock per area while preserving queue identities, disable-polling preferences and cleanup on concurrent setup, cancellation and final unload.

### Українською
- Наступне відключення, очікуване відновлення й повна тривалість: timestamp/хвилини, невідомий кінець горизонту, злиття через північ та врахування DST.
- Локалізований статус даних і останній успішний час відповіді API, доступні при збої.
- Один poller/clock на область зі збереженням черг, pref_disable_polling і cleanup при паралельному setup, скасуванні та останньому unload.

## v2.3.0 (2026-10-12)

### English
- Dynamic oblast/city directory, district/community/settlement navigation and exact operator/queue selection.
- Poll the chosen region; preserve historical Kyiv settings and all existing entity/device identities through migration and reconfiguration.
- Area-qualified duplicate protection; selecting another city does not duplicate the same regional schedule.
- Retry/back for missing source data, regional device links and allowlisted area diagnostics.
- Support dated, validated zero-outage NoShutdowns schedules used by additional operators.
- Extend regression coverage and document regional setup and downgrade limits.

### Українською
- Динамічний вибір області/міста, навігація район → громада → населений пункт, точні оператори та черги.
- Запити до обраної області; збереження київських налаштувань, entity/device identity під час міграції й переналаштування.
- Захист від дублювання за областю/оператором/чергою; інше місто не дублює той самий регіональний графік.
- Retry/back за відсутніх даних, посилання device на область, diagnostics без даних населеного пункту.
- Підтримка датованих NoShutdowns лише для валідного масиву з 24 нулів.
- Нові regression-тести, інструкція налаштування й обмеження повернення до старої версії.

## v2.2.0

### English
- Discover exact API queues and provide reconfiguration without changing existing entity/device identities.
- Keep missing queues registered and unavailable instead of silently mapping them or repeatedly failing setup.
- Validate each day independently, including integer codes, source date/status and Kyiv timezone.
- Update clock-dependent states at half-hour boundaries, preserve all periods in attributes and keep states within 255 characters.
- Correct outage binary sensor semantics and translate the no-outage label for English/Ukrainian.
- Add allowlisted diagnostics, runtime/regression tests, lint, formatting, type checks and HACS/hassfest CI.
- Migrate legacy YAML to modern templates with stable IDs, all outage periods and unavailable-data handling; correct the automation include example.
- Include local brand icons and repository metadata required by HACS validation.
- Retain HA 2024.6+ support using the compatible entity callback API.

Existing v2.1.x entries are preserved. If your queue disappears, explicitly select your verified current queue through Reconfigure. Text states can be shortened/localized; prefer `periods` and `schedule_status` in automations.

### Українською
- Точні черги з API та переналаштування зі збереженням entity/device identity.
- Відсутня черга залишається зареєстрованою й unavailable без автоматичної підміни.
- Незалежна валідація днів, цілочисельних кодів, дат/статусів джерела та київського часу.
- Оновлення на півгодинних межах, повні періоди в атрибутах і дотримання ліміту стану 255 символів.
- Коректна семантика binary sensor і український/англійський текст відсутності відключень.
- Diagnostics, runtime/regression-тести, lint, formatting, type checking та HACS/hassfest CI.
- Сучасний legacy YAML зі сталими IDs, усіма періодами та обробкою unavailable; виправлений приклад include автоматизацій.
- Локальна іконка й metadata репозиторію для успішної перевірки HACS.
- Збережена підтримка HA 2024.6+ завдяки сумісному callback API.

Існуючі entries v2.1.x зберігаються. Якщо черга зникла, оберіть перевірену поточну чергу через Reconfigure. Текстові стани можуть скорочуватися/локалізуватися; в автоматизаціях використовуйте `periods` і `schedule_status`.
