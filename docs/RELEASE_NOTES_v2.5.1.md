# v2.5.1: retain schedules during API failures / графіки під час збою API

Release date: 2026-10-18. / Дата релізу: 2026-10-18.

## Українською

Виправлено ситуацію, коли один невдалий запит робив сенсори недоступними до наступного налаштованого опитування, наприклад на 15 хвилин.

- Сенсори графіків і прогнозів, binary sensor та календар зберігають останній отриманий графік, поки його дата й статус публікації залишаються коректними. Півгодинні переходи та автоматизації за timestamp продовжують працювати.
- Атрибут `data_is_cached: true` явно позначає використання попередньої відповіді. «Статус даних» показує фактичну помилку, «Останнє успішне отримання» зберігає попередній час.
- Після невдалого запиту одна повторна спроба на область виконується раз на хвилину до успіху, після чого повертається налаштований інтервал. Вимкнений polling не запускає повторні запити; cleanup останнього запису збережений.
- Нова відповідь із відсутнім, некоректним чи аварійним графіком не підміняється старим опублікованим графіком. Дати кешу не подовжуються й не переносяться на інший день.
- Відновлення зв’язку без зміни графіка не створює повторних сповіщень. Ідентифікатори сутностей і пристроїв збережено.

Оновіть через HACS і перезапустіть Home Assistant. Налаштування змінювати не потрібно. Кеш зберігається в пам’яті: запуск після перезапуску HA все ще потребує успішної відповіді API. Кешований графік може не містити останніх виправлень джерела; дашборди можуть показувати його з попередженням через `data_is_cached`, не приховуючи лише через помилку у статусі даних.

## English

Fix a failed request making all schedule entities unavailable until the next configured poll, potentially for 15 minutes or longer.

- Retain schedule/forecast sensors, the binary sensor and calendar while the last received schedule still has a valid publication status and date. Clock transitions and timestamp automations continue to work.
- Expose `data_is_cached: true` when retaining a previous response. Data status still reports the actual request error and Last successful API update keeps its previous timestamp.
- Retry once per minute per active region until recovery, then restore the configured shared interval. Preserve disabled polling and final-entry cleanup.
- A new missing, invalid or emergency response replaces the previous response; it never resurrects an older published schedule. Cached dates are not extended or silently shifted.
- Unchanged recovery does not replay schedule-change notifications. Existing entity/device identities are retained.

Update through HACS and restart Home Assistant; no configuration changes are required. The cache is in memory, so setup after an HA restart still requires a successful API response. Cached schedules may miss subsequent source corrections. Dashboards can use `data_is_cached` to display an update warning while retaining valid schedules instead of hiding them solely because Data status reports a request error.

## Validation / Перевірки

- 250 local tests passed on HA 2026.10/Python 3.14, including an actual timestamp automation during API failure, cached clock/date boundaries, independent days, timed recovery, shared polling, options changes and unload cleanup.
- Ruff, formatting, mypy and Python/JSON/YAML/translations/metadata validation passed. Hosted CI/HACS/hassfest and the exact tagged archive are checked before release publication.
- Dashboard adaptation is separate from the HACS integration package; 40 isolated rendering scenarios passed for the prepared template.
