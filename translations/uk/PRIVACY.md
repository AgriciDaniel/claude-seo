<!-- i18n-source: PRIVACY.md -->
<!-- i18n-source-sha: HEAD -->
<!-- i18n-date: 2026-04-10 -->

# Конфіденційність

## Обробка даних

Claude SEO — це навичка Claude Code, яка працює повністю на вашому локальному комп'ютері. Основна навичка не збирає, не передає та не зберігає жодних персональних даних.

## Що залишається локально

- Весь SEO-аналіз виконується у вашій сесії Claude Code
- Парсинг HTML, аналіз контенту та генерація звітів відбуваються локально
- Згенеровані звіти (PDF, HTML, Excel) зберігаються у вашій локальній файловій системі
- Жодної телеметрії, аналітики чи відстеження використання

## API розширень

Опціональні розширення здійснюють API-виклики до сторонніх сервісів, коли ви викликаєте їхні команди:

| Розширення | Сервіс | Передані дані | Політика конфіденційності |
|------------|--------|---------------|--------------------------|
| **DataForSEO** | api.dataforseo.com | URL та домени, які ви аналізуєте | [Конфіденційність DataForSEO](https://dataforseo.com/privacy-policy) |
| **Firecrawl** | api.firecrawl.dev | URL, які ви скануєте | [Конфіденційність Firecrawl](https://www.firecrawl.dev/privacy) |
| **Banana (Gemini)** | generativelanguage.googleapis.com | Промпти для генерації зображень | [Конфіденційність Google AI](https://ai.google.dev/terms) |

## Google SEO API

При налаштуванні з обліковими даними Google API ці скрипти передають дані до Google:

| Скрипт | Google API | Передані дані |
|--------|-----------|---------------|
| `pagespeed_check.py` | PageSpeed Insights | URL для аналізу |
| `gsc_query.py` | Search Console | Автентифікований запит для ваших підтверджених ресурсів |
| `gsc_inspect.py` | URL Inspection | URL для інспекції |
| `indexing_notify.py` | Indexing API | URL для подання на індексацію |
| `ga4_report.py` | Analytics Data | Автентифікований запит для ваших ресурсів GA4 |
| `crux_history.py` | CrUX History | URL або домен для запиту |

Використання Google API регулюється [Політикою конфіденційності Google](https://policies.google.com/privacy) та [Умовами використання Google API](https://developers.google.com/terms).

## Облікові дані

- API-ключі та токени OAuth зберігаються локально в `~/.config/claude-seo/` або змінних оточення
- Облікові дані ніколи не комітяться в репозиторій (заблоковано `.gitignore`)
- Токени OAuth використовують refresh-токени та ніколи не зберігають client secrets у файлах токенів
