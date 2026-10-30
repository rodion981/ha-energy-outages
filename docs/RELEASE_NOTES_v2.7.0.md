# v2.7.0: Emergency notices / Аварійні повідомлення

Release date / Дата релізу: 2026-10-30.

## Українською

- Додано сутність **«Аварійні повідомлення»**: чинні або можливі аварійні обмеження з `today_announcements`, їхній масштаб і терміни чинності. Вона може показувати попередження одночасно з опублікованим плановим графіком.
- Додано два діагностичні сенсори **«Перевірка джерелом: сьогодні»** та **«Перевірка джерелом: завтра»**. Час перевірки даних сервісом відокремлено від часу отримання відповіді в HA.
- Один локальний таймер області обробляє початок і завершення чинності повідомлень без додаткових запитів, навіть із вимкненим опитуванням. Кеш зберігає початкові часові мітки; відсутні, некоректні або застарілі дані не означають відсутність обмежень.
- Оновлено diagnostics, переклади й README українською та англійською. Кожна черга тепер має 13 сутностей; наявні ідентифікатори, планові прогнози, календар та ліміти опитування збережено.

Це попередження оператора, а не вимірювання наявності світла у вашому будинку. `expires_at` означає закінчення чинності повідомлення, а не прогноз повернення електрики. Стан `off` не підтверджує відновлення живлення. Для сповіщень створіть автоматизацію переходу «Аварійні повідомлення» з `off` у `on`; повторні повідомлення, поки стан уже `on`, окремо не запускають такий тригер. Особисті повідомлення автоматично не вмикаються.

Оновіть через HACS і перезапустіть Home Assistant. Додаткове налаштування інтеграції або ключа не потрібне. Джерело даних: [Alerts Energy](https://alerts.energy/).

## English

- Add **Emergency notices** for active or possible emergency restrictions from `today_announcements`, with scope and validity metadata. An advisory can coexist with a published planned schedule.
- Add diagnostic **Source checked today** and **Source checked tomorrow** timestamps, distinct from the time HA received an API response.
- Share one local advisory timer per region for effective/expiry transitions without extra requests, including disabled polling. Cached responses retain original timestamps; missing, malformed or stale data does not mean an all-clear.
- Update diagnostics, translations and both READMEs. Each queue now has 13 entities; existing identities, scheduled forecasts, calendar and polling limits remain intact.

These are operator advisories, not measured power at your address. `expires_at` is a notice validity deadline, not a restoration estimate; `off` does not confirm electricity has returned. To notify, create an automation for Emergency notices changing from `off` to `on`. Further notices while already `on` do not trigger that automation again. Personal notifications are not enabled automatically.

Update through HACS and restart Home Assistant. No integration reconfiguration or personal API key is required. Data provided by [Alerts Energy](https://alerts.energy/).

## Validation / Перевірки

Local validation uses HA 2026.10/Python 3.14: 330 tests, including real HA entity setup, reload/unload, shared timers, disabled polling, notice expiry, persisted offline cache and a notification automation without recovery/reload repeats. Ruff, formatting, mypy and metadata checks are run separately. Hosted CI validates the final commit/tag, including hassfest and HACS. Local tests and hosted CI do not establish installation on an existing user's HA instance.
