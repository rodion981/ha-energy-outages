# v2.4.0: forecasts and data health / прогноз і стан даних

Five additional entities and shared regional polling. / П’ять додаткових сутностей і спільне опитування області.

## Українською

- Додано п’ять сутностей: наступне відключення, очікуване відновлення, тривалість у хвилинах, статус даних та останнє успішне отримання API.
- Наступне відключення означає майбутній початок. Відновлення й тривалість стосуються поточного відключення або найближчого майбутнього, якщо зараз відключення немає.
- Обчислення враховують півгодинні межі, Europe/Kyiv, DST і безперервні періоди через північ. Якщо повний початок або кінець виходить за опублікований графік, відповідні значення залишаються `unknown`. Опублікований час відновлення доступний навіть за невідомої повної тривалості.
- Статус даних пояснює відсутній, застарілий, неопублікований або некоректний графік, помилку API чи аварійні відключення. Інформаційні сутності залишаються видимими при збої; останній успішний час не стирається.
- Кілька черг або операторів однієї області використовують один запит кожні 60 секунд і спільний часовий обробник. Видалення одного запису не зупиняє решту; останній запис звільняє ресурси.

Оновлення: встановіть версію та перезапустіть Home Assistant. Існуючі три сутності, пристрій, налаштування та ідентифікатори зберігаються; загалом буде вісім сутностей на запис. Знайдіть нові в **Settings → Devices & services → Alerts Energy Outages → Entities** і додайте до картки Entities. Час наступного відключення можна вибрати в часовому тригері автоматизації. Нові сутності створює custom integration; legacy YAML-пакет залишається окремим варіантом.

Це плановий графік, а не вимірювання фактичного живлення. Час успішного отримання API відрізняється від часу публікації графіка. Тривалість не є зворотним відліком і не записує статистику як вимірювання. Пошук черги за адресою не додавався. ConfigEntry schema не змінена; повернення до v2.3.0 підтримує регіональні налаштування, але прибирає нові можливості.

## English

- Add next outage, expected restoration, outage duration in minutes, data status and last successful API update entities.
- Next outage is strictly a future start; restoration/duration describe the current outage, or the nearest upcoming one when no outage is ongoing.
- Respect half-hour boundaries, Europe/Kyiv, DST and continuous outages across midnight. Unknown boundaries outside published coverage produce `unknown` values. A published restoration remains available when the full duration is unknown.
- Keep source health and the last successful response visible through failures; distinguish missing, stale, unpublished, invalid, emergency and connection-error states.
- Share one 60-second request and clock listener per area across operators/queues. Unloading one entry preserves other entries; final unload releases the source.

Upgrade: restart HA after installing. Existing entities, devices and configuration identity are preserved; each entry now has eight entities. Find the additions in the integration's Entities list, add them to an Entities card, or select the next outage timestamp in an automation time trigger. The legacy YAML package is unchanged.

These are planned schedules, not measured grid power. API response time is distinct from schedule publication. Duration is not a countdown and has no measurement statistics state class. No address lookup is included. ConfigEntry schema is unchanged; v2.3.0 can read regional configuration but does not offer the new entities.

## Validation / Перевірки

- HA 2024.6.0 / Python 3.12.14: 141 tests passed.
- HA 2026.10.0 / Python 3.14.2: 141 tests passed.
- Integration coverage: 97.64% (635 statements, 15 uncovered); forecast helper coverage: 100%.
- Ruff, formatting, mypy and Python/JSON/YAML/translations/metadata validation passed on both environments.
- Runtime tests cover typed entities, an actual HA timestamp automation, failure/recovery, unknown horizons, midnight/DST boundaries, concurrent area setup, cancellation, polling preferences and unloading shared sources.
- Local official hassfest: 1 integration, 0 invalid integrations.
- New v2.4 frontend/HACS installation has not been exercised on a production HA instance. Hosted tests, HACS and hassfest are checked for the exact PR, merged main and release tag before publication.

CI results and the downloadable integration archive are available with the GitHub release.
