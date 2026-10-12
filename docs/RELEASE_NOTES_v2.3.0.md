# v2.3.0: regional selection / вибір місця

Regional schedule selection. / Вибір місця для регіональних графіків.

## Українською

- Додано область → район/громада → місто або село → оператор → точна черга. Довідники завантажуються з Alerts Energy; Київ і Київська область розділені.
- Населений пункт можна пропустити. За відсутніх даних є повторний запит і повернення до попереднього вибору.
- Старі київські записи оновлюються без видалення інтеграції. Переналаштування зберігає entity IDs, unique IDs сутностей і пристрій навіть при зміні області.
- Додано посилання пристрою на вибрану область і атрибут `area`. Diagnostics не експортує дані населеного пункту.
- Датований статус `NoShutdowns` з 24 нулями коректно відображається як графік без відключень.

Оновлення: після встановлення v2.3.0 перезапустіть Home Assistant. Існуючі записи залишаються київськими. Для іншого місця додайте новий запис або відкрийте **Settings → Devices & services → Alerts Energy Outages → Reconfigure**. Поточний запис змінюється тільки після завершення останнього кроку.

Графік визначається областю, оператором і чергою. Місто не визначає чергу за адресою; перевірте її у свого оператора. Однаковий регіональний графік не можна додати двічі через різні міста. Наявність області чи оператора в довіднику не гарантує опублікованих черг. Повернення до v2.2.x підходить лише для київських записів; інші області потребують v2.3.0+.

## English

- Add area → district/community → city or village → operator → exact queue selection using the live Alerts Energy directory. Kyiv city and Kyiv oblast remain distinct.
- Allow skipping a settlement, retrying unavailable source data and returning to the previous choice.
- Preserve historical Kyiv entries, entity IDs, entity unique IDs and devices when upgrading or reconfiguring across areas.
- Add regional device links and an `area` sensor attribute. Diagnostics excludes settlement details.
- Accept dated `NoShutdowns` schedules only with 24 validated zero codes.

Upgrade: restart Home Assistant after installing v2.3.0. Existing entries stay in Kyiv. Add another entry or use **Reconfigure** for a different location; changes apply only after the final step.

Schedules remain regional by area/operator/queue. A city does not discover an address's queue. Duplicate regional schedules across cities are prevented. Directory entries do not guarantee published queues. Downgrading to v2.2.x is only suitable for Kyiv entries; other areas require v2.3.0+.

## Validation / Перевірки

- HA 2024.6.0 / Python 3.12.14: 107 tests passed.
- HA 2026.10.0 / Python 3.14.2: 107 tests passed.
- Integration coverage: 98.55% (pytest rounds to 99%).
- Ruff, formatting, mypy, Python/JSON/YAML/translations/metadata validation passed on both environments.
- Tests cover full city navigation, skip/back/retry, multiple operators, cross-area identities, duplicates, atomic/cancelled reconfigure, migration/reload, unavailable data and prior time-boundary regressions.
- Read-only live API check on 2026-10-12: 27 top-level directory areas; Bucha city path verified; Kyiv city, Kyiv oblast, Dnipropetrovsk and Lviv region endpoints verified. Kyiv schedules were published; Dnipropetrovsk operators returned NoShutdowns; Lviv operators had no queues.
- Local official hassfest container: 1 integration, 0 invalid integrations.
- GitHub CI/HACS must pass for the exact PR, merged main and release tag before publication. Production HA and visual frontend installation were not exercised.
