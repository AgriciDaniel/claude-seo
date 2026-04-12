<!-- i18n-source: README.md -->
<!-- i18n-source-sha: HEAD -->
<!-- i18n-date: 2026-04-10 -->

![Claude SEO](../../screenshots/cover-image.jpeg)

# Claude SEO — навичка SEO-аудиту для Claude Code

🌐 **Language / Мова:** [English](../../README.md) | [Українська](README.md)

Комплексна навичка SEO-аналізу для Claude Code. Охоплює технічне SEO, аналіз сторінок, якість контенту (E-E-A-T), розмітку Schema, оптимізацію зображень, архітектуру карти сайту, оптимізацію для AI-пошуку (GEO), локальне SEO, аналітику карт, Google SEO API (Search Console, PageSpeed, CrUX, GA4), генерацію PDF-звітів та стратегічне планування.

![SEO Command Demo](../../screenshots/seo-command-demo.gif)

[![CI](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml/badge.svg)](https://github.com/AgriciDaniel/claude-seo/actions/workflows/ci.yml)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/claude-code)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../LICENSE)
[![Version](https://img.shields.io/github/v/release/AgriciDaniel/claude-seo)](https://github.com/AgriciDaniel/claude-seo/releases)

> **Блог:** [Повний огляд SEO-стеку Claude Code](https://agricidaniel.com/blog/claude-code-seo-stack) | [Реліз v1.7.2: аналіз зворотних посилань Firecrawl](https://agricidaniel.com/blog/claude-seo-172-firecrawl-backlink-analysis)

## Зміст

- [Встановлення](#встановлення)
- [Швидкий старт](#швидкий-старт)
- [Команди](#команди)
- [Функції](#функції)
- [Архітектура](#архітектура)
- [Розширення](#розширення)
- [Екосистема](#екосистема)
- [Документація](#документація)
- [Вимоги](#вимоги)
- [Видалення](#видалення)
- [Внесок](#внесок)

## Встановлення

### Встановлення як плагін (Claude Code 1.0.33+)

```bash
# Add marketplace (one-time)
/plugin marketplace add AgriciDaniel/claude-seo

# Install plugin
/plugin install claude-seo@AgriciDaniel-claude-seo
```

### Ручне встановлення (Unix/macOS/Linux)

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/install.sh
```

<details>
<summary>Однорядкове встановлення (curl)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

Або через [install.cat](https://install.cat):

```bash
curl -fsSL install.cat/AgriciDaniel/claude-seo | bash
```

Бажаєте переглянути скрипт перед запуском?

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh > install.sh
cat install.sh        # review
bash install.sh       # run when satisfied
rm install.sh
```

</details>

### Windows (PowerShell)

```powershell
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
powershell -ExecutionPolicy Bypass -File claude-seo\install.ps1
```

> **Чому git clone, а не `irm | iex`?** Власні захисні механізми Claude Code позначають `irm ... | iex` як ризик ланцюга постачання (завантаження та виконання віддаленого коду без перевірки). Підхід з git clone дозволяє переглянути скрипт `claude-seo\install.ps1` перед його запуском.

## Швидкий старт

```bash
# Start Claude Code
claude

# Run a full site audit
/seo audit https://example.com

# Analyze a single page
/seo page https://example.com/about

# Check schema markup
/seo schema https://example.com

# Generate a sitemap
/seo sitemap generate

# Optimize for AI search
/seo geo https://example.com
```

### Демо:
[Дивіться повне демо на YouTube](https://www.youtube.com/watch?v=COMnNlUakQk)

**`/seo audit`: повний аудит сайту з паралельними субагентами:**

![SEO Audit Demo](../../screenshots/seo-audit-demo.gif)

## Команди

| Команда | Опис |
|---------|------|
| `/seo audit <url>` | Повний аудит сайту з паралельним делегуванням субагентам |
| `/seo page <url>` | Глибокий аналіз окремої сторінки |
| `/seo sitemap <url>` | Аналіз існуючої XML-карти сайту |
| `/seo sitemap generate` | Генерація нової карти сайту з галузевими шаблонами |
| `/seo schema <url>` | Виявлення, валідація та генерація розмітки Schema.org |
| `/seo images <url>` | Аналіз оптимізації зображень |
| `/seo technical <url>` | Технічний SEO-аудит (9 категорій) |
| `/seo content <url>` | Аналіз якості контенту та E-E-A-T |
| `/seo geo <url>` | AI Overviews / оптимізація для генеративних систем |
| `/seo plan <type>` | Стратегічне SEO-планування (saas, local, ecommerce, publisher, agency) |
| `/seo programmatic <url>` | Аналіз та планування програматичного SEO |
| `/seo competitor-pages <url>` | Генерація порівняльних сторінок з конкурентами |
| `/seo local <url>` | Аналіз локального SEO (GBP, цитування, відгуки, блок карти) |
| `/seo maps [command]` | Аналітика карт (геосітка, аудит GBP, відгуки, конкуренти) |
| `/seo hreflang <url>` | Аудит та генерація hreflang/i18n |
| `/seo google [command] [url]` | Google SEO API (GSC, PageSpeed, CrUX, Indexing, GA4) |
| `/seo google report [type]` | Генерація PDF/HTML-звіту з графіками (cwv-audit, gsc-performance, full) |

### `/seo programmatic [url|plan]`
**Аналіз та планування програматичного SEO**

Створення SEO-сторінок у масштабі з джерел даних із контролем якості.

**Можливості:**
- Аналіз існуючих програматичних сторінок на тонкий контент та канібалізацію
- Планування URL-патернів та шаблонних структур для сторінок на основі даних
- Автоматизація внутрішніх посилань між згенерованими сторінками
- Канонічна стратегія та запобігання роздуванню індексу
- Контроль якості: ПОПЕРЕДЖЕННЯ при 100+ сторінок, СТОП при 500+ без аудиту

### `/seo competitor-pages [url|generate]`
**Генератор порівняльних сторінок з конкурентами**

Створення сторінок "X vs Y" та "альтернативи X" з високою конверсією.

**Можливості:**
- Структуровані таблиці порівняння з матрицями функцій
- Розмітка Product schema з AggregateRating
- Макети, оптимізовані для конверсії, з розміщенням CTA
- Таргетування ключових слів для порівняльних запитів
- Правила чесності для точного представлення конкурентів

### `/seo hreflang [url]`
**Аудит та генерація hreflang / i18n SEO**

Валідація та генерація hreflang-тегів для мультимовних сайтів.

**Можливості:**
- Генерація hreflang-тегів (HTML, HTTP-заголовки або XML-карта сайту)
- Валідація самопосилальних тегів, зворотних тегів, x-default
- Виявлення типових помилок (відсутні зворотні, невалідні коди, невідповідність HTTP/HTTPS)
- Підтримка крос-доменних hreflang
- Валідація кодів мов/регіонів (ISO 639-1 + ISO 3166-1)

## Функції

### Core Web Vitals (поточні метрики)
- **LCP** (Largest Contentful Paint): Ціль < 2.5с
- **INP** (Interaction to Next Paint): Ціль < 200мс
- **CLS** (Cumulative Layout Shift): Ціль < 0.1

> Примітка: INP замінив FID 12 березня 2024. FID було повністю видалено з усіх інструментів Chrome 9 вересня 2024.

### Аналіз E-E-A-T
Оновлено до Настанов оцінювачів якості від вересня 2025:
- **Experience (Досвід)**: Сигнали безпосереднього знання
- **Expertise (Експертність)**: Кваліфікація автора та глибина
- **Authoritativeness (Авторитетність)**: Визнання в галузі
- **Trustworthiness (Довіра)**: Контактна інформація, безпека, прозорість

### Розмітка Schema
- Виявлення: JSON-LD (пріоритет), Microdata, RDFa
- Валідація за підтримуваними типами Google
- Генерація за шаблонами
- Обізнаність щодо застарілих типів:
  - HowTo: Застарілий (вересень 2023)
  - FAQ: Обмежений для gov/health сайтів (серпень 2023)
  - SpecialAnnouncement: Застарілий (липень 2025)

### Оптимізація для AI-пошуку (GEO)
Нове у 2026 — оптимізація для:
- Google AI Overviews
- Веб-пошук ChatGPT
- Perplexity
- Інші AI-пошукові системи

### Google SEO API (нове у v1.7.0)
Пряма інтеграція з SEO-даними Google:
- **PageSpeed Insights + CrUX**: Лабораторні та польові дані Core Web Vitals
- **Search Console**: Топ-запити, інспекція URL, статус карти сайту
- **Indexing API**: Сповіщення Google про нові/оновлені/видалені URL
- **GA4**: Органічний трафік, топ посадкових сторінок, розбивка за пристроями/країнами
- **PDF-звіти**: Корпоративні A4-звіти з графіками через WeasyPrint + matplotlib

4-рівнева система облікових даних — отримайте цінність на кожному рівні:
| Рівень | Авторизація | API |
|--------|-------------|-----|
| 0 | API-ключ | PSI, CrUX, CrUX History |
| 1 | + OAuth/SA | + GSC, URL Inspection, Indexing |
| 2 | + конфіг GA4 | + органічний трафік GA4 |
| 3 | + токен Ads | + Keyword Planner |

### Локальне SEO та аналітика карт (нове у v1.6.0)
- Оптимізація Google Business Profile
- Аудит консистентності NAP
- Аналіз цитувань та відгуків
- Відстеження позицій по геосітці та картування радіусу конкурентів

### Контроль якості
- Попередження при 30+ сторінках локацій
- Стоп при 50+ сторінках локацій
- Виявлення тонкого контенту за типом сторінки
- Запобігання doorway-сторінкам

## Архітектура

```
~/.claude/skills/seo/         # Main orchestrator skill
~/.claude/skills/seo-*/       # Sub-skills (15 + 2 extensions)
~/.claude/agents/seo-*.md     # Subagents (10 + 2 extensions)
```

### Розмітка Video та Live Schema (нове)
Додаткові типи Schema для відеоконтенту, прямих трансляцій та ключових моментів:
- VideoObject: Розмітка відеосторінки з мініатюрами, тривалістю, датою завантаження
- BroadcastEvent: Підтримка значка LIVE для прямих трансляцій
- Clip: Ключові моменти / розділи у відео
- SeekToAction: Функція перемотки у відеорезультатах пошуку
- SoftwareSourceCode: Сторінки відкритого коду та репозиторіїв

Див. `schema/templates.json` для готових JSON-LD сніпетів.

### Нещодавно додано
- Навичка програматичного SEO (`/seo programmatic`)
- Навичка порівняльних сторінок з конкурентами (`/seo competitor-pages`)
- Мультимовна валідація hreflang (`/seo hreflang`)
- Типи Schema для Video та Live (VideoObject, BroadcastEvent, Clip, SeekToAction)
- Швидкий довідник Google SEO

## Вимоги

- Python 3.10+
- Claude Code CLI
- Опціонально: Playwright для скріншотів
- Опціонально: Облікові дані Google API для розширених даних (див. `/seo google setup`)

## Видалення

```bash
git clone --depth 1 https://github.com/AgriciDaniel/claude-seo.git
bash claude-seo/uninstall.sh
```

<details>
<summary>Однорядкове видалення (curl)</summary>

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.sh | bash
```

</details>

### Інтеграції MCP

Інтегрується з MCP-серверами для отримання SEO-даних у реальному часі, включаючи офіційні сервери від **Ahrefs** (`@ahrefs/mcp`) та **Semrush**, а також серверні рішення спільноти для Google Search Console, PageSpeed Insights та DataForSEO. Див. [Посібник з інтеграції MCP](../../docs/MCP-INTEGRATION.md) для налаштування.

## Розширення

Опціональні додатки для інтеграції зовнішніх джерел даних через MCP-сервери.

### DataForSEO

Дані SERP у реальному часі, дослідження ключових слів, зворотні посилання, аналіз на сторінці, аналіз контенту, бізнес-каталоги, перевірка AI-видимості та відстеження згадок LLM. 22 команди у 9 API-модулях.

```bash
# Install (requires DataForSEO account)
./extensions/dataforseo/install.sh
```

```bash
# Example commands
/seo dataforseo serp best coffee shops
/seo dataforseo keywords seo tools
/seo dataforseo backlinks example.com
/seo dataforseo ai-mentions your brand
/seo dataforseo ai-scrape your brand name
```

Див. [Розширення DataForSEO](../../extensions/dataforseo/README.md) для повної документації.

### Banana (генерація AI-зображень)

Генерація SEO-зображень (OG-прев'ю, герої блогів, фото продуктів, інфографіка) за допомогою пайплайну
[Claude Banana](https://github.com/AgriciDaniel/banana-claude) Creative Director.

```bash
# Install extension
./extensions/banana/install.sh
```

```bash
# Example commands
/seo image-gen og "Professional SaaS dashboard"
/seo image-gen hero "AI-powered content creation"
/seo image-gen batch "Product photography" 3
```

Див. [Розширення Banana](../../extensions/banana/README.md) для повної документації.
Вже використовуєте окремий Claude Banana? Розширення використовує вашу існуючу конфігурацію nanobanana-mcp.

## Екосистема

Claude SEO є частиною сімейства навичок Claude Code, що працюють разом:

| Навичка | Що робить | Як з'єднується |
|---------|-----------|----------------|
| [Claude SEO](https://github.com/AgriciDaniel/claude-seo) | SEO-аналіз, аудити, Schema, GEO | Ядро — аналізує сайти, генерує плани дій |
| [Claude Blog](https://github.com/AgriciDaniel/claude-blog) | Написання блогів, оптимізація, оцінювання | Компаньйон — створення контенту на основі SEO-знахідок |
| [Claude Banana](https://github.com/AgriciDaniel/banana-claude) | Генерація AI-зображень через Gemini | Спільний — генерація зображень для SEO та блогів |
| [AI Marketing Claude](https://github.com/zubair-trabzada/ai-marketing-claude) | Копірайтинг, email, соцмережі, реклама, воронки, CRO | Спільнота — маркетингові дії після SEO-аудиту |

**Приклад робочого процесу:**
1. `/seo audit https://example.com` — визначення прогалин контенту та технічних проблем
2. `/seo backlinks https://example.com` — аналіз профілю посилань та прогалин конкурентів
3. `/blog write "target keyword"` — створення SEO-оптимізованих блог-постів
4. `/seo image-gen hero "blog topic"` — генерація зображень-героїв (розширення banana)
5. `/seo geo https://example.com/blog/post` — оптимізація для AI-цитувань

## Документація

- [Посібник зі встановлення](../../docs/INSTALLATION.md)
- [Довідник команд](../../docs/COMMANDS.md)
- [Архітектура](../../docs/ARCHITECTURE.md)
- [Інтеграція MCP](../../docs/MCP-INTEGRATION.md)
- [Усунення неполадок](../../docs/TROUBLESHOOTING.md)

## Ліцензія

Ліцензія MIT — див. [LICENSE](../../LICENSE) для деталей.

## Внесок

Внески вітаються! Будь ласка, прочитайте [CONTRIBUTING.md](../../CONTRIBUTING.md) перед створенням PR.

---

Створено для Claude Code [@AgriciDaniel](https://github.com/AgriciDaniel)
