# Changelog

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
