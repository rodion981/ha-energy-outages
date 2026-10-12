# v2.4.1: current documentation in HACS / актуальна документація в HACS

## Українською

- Актуальні README українською й англійською та скріншот інтерфейсу тепер входять до релізного тегу. HACS читає документацію з вибраного релізу, тому оновлення лише `main` не змінювало README для v2.4.0.
- Описано вибір області/населеного пункту/оператора/черги, усі вісім сутностей, діагностику та поведінку `unknown/unavailable`. Старі міграції й огляди попередніх версій прибрані з README.
- Виправлено посилання бейджа ліцензії для HACS. Короткий опис GitHub також актуальний і охоплює регіони, прогноз та стан даних.

Це реліз документації. Код інтеграції, налаштування й ідентифікатори сутностей збережені; у пакеті змінено лише номер версії. Для отримання актуального опису в HACS використайте **Update information**. Після встановлення v2.4.1 перезапустіть HA, щоб він відобразив нову версію; повторне налаштування не потрібне.

Відсутня іконка в каталозі HACS є окремою проблемою HACS і цим релізом не виправляється. Локальна іконка Home Assistant залишається в пакеті.

## English

- Include the current English/Ukrainian README and working-UI screenshot in the release tag. HACS reads documentation from the selected release; updating only `main` did not replace v2.4.0's README.
- Describe region/settlement/operator/queue selection, all eight entities, diagnostics and unknown/unavailable behavior. Remove historical migrations and version-by-version sections from the README.
- Fix the license badge link for HACS. The GitHub repository description now covers regions, forecasts and source health.

Documentation release: runtime code, configuration and entity identities are unchanged; only the manifest version changes inside the integration package. Use **Update information** in HACS to refresh repository information. Restart HA after installing v2.4.1 to display the new version; no reconfiguration is needed.

The missing HACS catalog icon is a separate HACS issue and is not fixed by this release. The integration retains its local Home Assistant icon.

## Validation / Перевірки

- 141 regression tests on each supported HA baseline: HA 2024.6/Python 3.12 and HA 2026.10/Python 3.14.
- Ruff, formatting, mypy, repository metadata, HACS and hassfest checks.
- English/Ukrainian documentation, screenshot and tagged archive validation; runtime files identical to v2.4.0 except the manifest version.
- Exact PR/main/tag CI links are included with the GitHub release.
