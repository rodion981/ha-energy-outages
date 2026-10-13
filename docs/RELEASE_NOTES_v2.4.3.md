# v2.4.3: repository cleanup / прибирання репозиторію

Release date: 2026-10-13. / Дата релізу: 2026-10-13.

## Українською

- Прибрано застарілий окремий YAML-пакет, його автоматизацію сповіщень, приклад підключення та окремі тести/залежності.
- Видалено застарілі посилання й інструкції; валідація та CI перевіряють актуальну custom integration.
- У README додано пояснення сповіщень про графік на завтра через сенсор інтеграції, `date`, `periods` і `schedule_status`, із захистом від повторів.

Логіка графіків, іконка, налаштування, сутності, пристрої та сумісність з HA 2024.6+ збережені. Автоматизацію сповіщень і сервіс доставки користувач налаштовує в Home Assistant. Після оновлення через HACS перезапустіть Home Assistant.

## English

- Remove the obsolete standalone YAML package, its notification automation, configuration include example and dedicated tests/dependencies.
- Remove outdated references and instructions; validation and CI cover the current custom integration.
- Explain tomorrow-schedule notifications using the integration sensor, `date`, `periods` and `schedule_status`, including duplicate prevention.

Schedule behavior, icon, configuration, entity/device identities and HA 2024.6+ compatibility are preserved. Users configure their notification automation and delivery service in Home Assistant. Restart Home Assistant after updating through HACS.

## Validation / Перевірки

- 132 regression tests passed on each local HA baseline (2024.6/Python 3.12 and 2026.10/Python 3.14). Nine removed tests belonged exclusively to the retired package; integration coverage is unchanged at 97.64%.
- Local Ruff, formatting, mypy and Python/JSON/YAML/translations/metadata validation passed.
- Release gates: GitHub CI, HACS and hassfest for the exact PR/main/tag, plus archive verification before publication.
