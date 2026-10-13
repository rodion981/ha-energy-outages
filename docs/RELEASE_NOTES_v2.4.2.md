# v2.4.2: refreshed integration icon / нова іконка інтеграції

Prepared for release; not published. / Підготовлено до релізу, не опубліковано.

## Українською

- Замінено іконку на доопрацьовану блискавку з годинником, що поєднує електрику та графік відключень.
- Спрощено кільце й потовщено стрілки для читабельності в малому розмірі. Пакет містить RGBA PNG 256×256 та 512×512 з прозорими кутами.
- Робочий код, графіки, налаштування й ідентифікатори сутностей/пристроїв залишаються такими, як у v2.4.1.

Після встановлення перезапустіть Home Assistant. Локальні іконки підтримуються з HA 2026.3; старі підтримувані версії можуть показувати стандартну іконку. Якщо браузер показує попередню іконку, оновіть сторінку без кешу.

Цей реліз не виправляє заглушку в каталозі HACS 2.0.5: це окрема проблема його інтерфейсу.

## English

- Replace the icon with a refined lightning-and-clock mark representing electricity and outage schedules.
- Simplify the ring and thicken the clock hands for small-size clarity. Ship transparent-corner RGBA PNGs at 256×256 and 512×512.
- Runtime code, schedules, configuration and entity/device identities are unchanged from v2.4.1.

Restart Home Assistant after installing. Local brand images require HA 2026.3+; earlier supported HA versions may show a generic icon. Refresh the browser without its cache if it still shows the previous image.

This release does not fix the HACS 2.0.5 catalog placeholder, which is a separate frontend issue.

## Validation / Перевірки

- PNG dimensions, RGBA format, transparency and exact correspondence with the approved design.
- Small-size previews at 32/48/64 px on light and dark backgrounds.
- Repository metadata, Ruff, formatting, mypy and regression tests on both HA baselines.
- Hosted HACS/hassfest and exact PR/main/tag checks required before publication.
