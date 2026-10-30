# Changelog

## v2.6.0-alpha.1 (2026-10-30)

### English
- Support authenticated Alerts Energy API with the shared project key, one persistent installation UUID, and snake_case/legacy response normalization without entity identity changes.
- Enforce a shared 15-minute regional request minimum across setup, polling, manual refresh and restart; honor Retry-After and exponential error backoff. Persist response/deadlines for cache recovery without extending schedule dates.
- Raise saved intervals below 15 minutes, preserve longer intervals, and link Alerts Energy in region selection and reconfiguration.

### Українською
- Підтримка авторизованого API Alerts Energy: спільний ключ проєкту, постійний UUID установки, snake_case і старий формат без зміни ідентифікаторів сутностей.
- Спільний мінімум 15 хв між запитами області для налаштування, опитування, ручного оновлення й перезапуску; Retry-After та поступове збільшення пауз. Збереження відповіді й термінів запитів без подовження дат графіка.
- Підвищення збережених інтервалів нижче 15 хв, збереження більших і посилання на Alerts Energy у виборі області та переналаштуванні.

## v2.5.1 (2026-10-18)

### English
- Keep dated, published schedules, forecasts, binary state and calendar available during failed API refreshes, with an explicit `data_is_cached` flag and truthful error/last-success diagnostics. Never reuse an older schedule after a new missing, invalid or emergency response, or extend its dates.
- Retry failed regional requests once per minute, then restore the configured shared polling interval after recovery; preserve disabled polling and final-unload cleanup.

### Українською
- При збої оновлення API датовані опубліковані графіки, прогнози, binary sensor і календар залишаються доступними з явним `data_is_cached`; помилка й час останнього успішного отримання залишаються чесними. Старий графік не підміняє нову відсутню, некоректну чи аварійну відповідь, дати не подовжуються.
- Повторні спроби запитів області раз на хвилину до відновлення, після чого повертається налаштований спільний інтервал; вимкнення polling і cleanup останнього запису збережені.

## v2.5.0 (2026-10-17)

### English
- Include optional Possible intervals consistently in schedules, forecasts, binary sensor, calendar and change notifications; preserve raw source arrays and expose planned/possible classification. Validate malformed/emergency conditional data and restore both comparison arrays without replaying notifications.
- Retire the HA 2024.6/Python 3.12 CI job and its historical test dependencies; retain current HA 2026.10/Python 3.14 validation and the existing HACS minimum.
- Add a read-only outage calendar for published today/tomorrow periods, sharing polling and DST calculations with the existing entities; retain explicit coverage-boundary descriptions and independent day validity.
- Add a schedule-change event with per-date publication, added/cancelled intervals and full before/after periods, using the existing regional polling.
- Add a notification blueprint with a selectable action; suppress startup/recovery/timestamp-only repeats and retain bounded published snapshots through HA restore.

### Українською
- Можливі відключення узгоджено враховуються в графіках, прогнозах, binary sensor, календарі та сповіщеннях; сирі масиви збережені, тип інтервалу доступний окремо. Перевірка некоректних/аварійних умовних даних і відновлення обох масивів порівняння без повторних сповіщень.
- Прибрано CI-тести HA 2024.6/Python 3.12 та їхні історичні залежності; залишено HA 2026.10/Python 3.14, мінімум HACS незмінний.
- Календар опублікованих відключень сьогодні й завтра: спільне опитування та розрахунки DST, незалежна коректність днів і явні пояснення на межах відомого графіка.
- Подія зміни графіка з публікацією за датою, доданими/скасованими інтервалами й повними періодами до/після; використовується наявне опитування області.
- Шаблон сповіщень із вибором дії; захист від повторів при запуску, відновленні зв’язку та зміні лише часу оновлення, відновлення останніх опублікованих графіків засобами HA.

## v2.4.5 (2026-10-17)

### English
- Add an options flow for polling intervals of 1–1440 whole minutes, defaulting to 15; apply changes without restarting HA or reloading entities.
- Keep one regional poller using the shortest requested interval among polling-enabled entries, with independent half-hour clock updates.

### Українською
- Налаштування інтервалу опитування від 1 до 1440 цілих хвилин, типово 15; зміни діють без перезапуску HA чи перезавантаження сутностей.
- Один цикл області з найкоротшим інтервалом серед записів з увімкненим polling; незалежні оновлення на півгодинних межах.

## v2.4.3 (2026-10-13)

### English
- Remove the obsolete standalone YAML package, its notification example, configuration include example and dedicated tests/dependencies. Keep the custom integration and ConfigEntry migrations intact.
- Document tomorrow-schedule notifications using the integration's current entities and attributes; update repository validation and agent guidance.

### Українською
- Прибрано застарілий окремий YAML-пакет, його приклад сповіщень, приклад підключення та окремі тести/залежності. Custom integration та міграції ConfigEntry збережені.
- Описано сповіщення про графік на завтра через актуальні сутності й атрибути інтеграції; оновлено валідацію репозиторію та правила для агентів.

## v2.4.2 (2026-10-13)

### English
- Replace the integration icon with a refined lightning-and-clock mark in blue/yellow, supplied as transparent RGBA PNGs at 256 and 512 pixels.
- Outage logic, configuration, entity/device identities and supported HA versions are unchanged. The HACS catalog placeholder remains a separate HACS issue.

### Українською
- Нова іконка інтеграції: доопрацьована блискавка з годинником у синьо-жовтих кольорах, RGBA PNG 256 і 512 px з прозорими кутами.
- Логіка графіків, налаштування, ідентифікатори сутностей/пристроїв і підтримувані версії HA збережені. Заглушка в каталозі HACS залишається окремою проблемою HACS.

## v2.4.1 (2026-10-12)

### English
- Publish the current English/Ukrainian README and working-UI screenshot in a versioned release, so HACS can load them from the release tag.
- Remove historical migration/legacy sections from the README and document regional setup, all eight entities and unknown forecast boundaries.
- Use an absolute license badge link for HACS rendering. Runtime behavior, configuration and entity identities remain unchanged from v2.4.0.

### Українською
- Актуальні README українською й англійською та скріншот робочого інтерфейсу включені у версійний реліз, щоб HACS отримував їх із тегу.
- З README прибрано історичні міграції/legacy-розділи; описано регіональний вибір, вісім сутностей і невідомі межі прогнозу.
- Посилання бейджа ліцензії зроблено абсолютним для відображення в HACS. Поведінка інтеграції, налаштування та ідентифікатори сутностей ті самі, що у v2.4.0.

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
- Локальна іконка й metadata репозиторію для успішної перевірки HACS.
- Збережена підтримка HA 2024.6+ завдяки сумісному callback API.

Існуючі entries v2.1.x зберігаються. Якщо черга зникла, оберіть перевірену поточну чергу через Reconfigure. Текстові стани можуть скорочуватися/локалізуватися; в автоматизаціях використовуйте `periods` і `schedule_status`.
