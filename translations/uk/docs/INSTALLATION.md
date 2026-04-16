<!-- i18n-source: docs/INSTALLATION.md -->
<!-- i18n-source-sha: HEAD -->
<!-- i18n-date: 2026-04-10 -->

# Посібник зі встановлення

## Передумови

- **Python 3.10+** з pip
- **Git** для клонування репозиторію
- **Claude Code CLI** встановлений та налаштований

Опціонально:
- **Playwright** для можливості створення скріншотів

## Швидке встановлення

### Unix/macOS/Linux

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.ps1 | iex
```

## Ручне встановлення

1. **Клонуйте репозиторій**

```bash
git clone https://github.com/AgriciDaniel/claude-seo.git
cd claude-seo
```

2. **Запустіть інсталятор**

```bash
./install.sh
```

3. **Встановіть залежності Python** (якщо не встановлено автоматично)

Інсталятор створює venv у `~/.claude/skills/seo/.venv/`. Якщо це не вдалося, встановіть вручну:

```bash
# Option A: Use the venv
~/.claude/skills/seo/.venv/bin/pip install -r ~/.claude/skills/seo/requirements.txt

# Option B: User-level install
pip install --user -r ~/.claude/skills/seo/requirements.txt
```

4. **Встановіть браузери Playwright** (опціонально, для візуального аналізу)

```bash
pip install playwright
playwright install chromium
```

Playwright опціональний. Без нього візуальний аналіз використовує WebFetch як резервний варіант.

## Шляхи встановлення

Інсталятор копіює файли до:

| Компонент | Шлях |
|-----------|------|
| Основна навичка | `~/.claude/skills/seo/` |
| Піднавички | `~/.claude/skills/seo-*/` |
| Субагенти | `~/.claude/agents/seo-*.md` |

## Перевірка встановлення

1. Запустіть Claude Code:

```bash
claude
```

2. Перевірте, що навичка завантажена:

```
/seo
```

Ви повинні побачити довідкове повідомлення або запит на URL.

## Видалення

```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.sh | bash
```

Або вручну:

```bash
rm -rf ~/.claude/skills/seo
rm -rf ~/.claude/skills/seo-audit
rm -rf ~/.claude/skills/seo-competitor-pages
rm -rf ~/.claude/skills/seo-content
rm -rf ~/.claude/skills/seo-geo
rm -rf ~/.claude/skills/seo-hreflang
rm -rf ~/.claude/skills/seo-images
rm -rf ~/.claude/skills/seo-page
rm -rf ~/.claude/skills/seo-plan
rm -rf ~/.claude/skills/seo-programmatic
rm -rf ~/.claude/skills/seo-schema
rm -rf ~/.claude/skills/seo-sitemap
rm -rf ~/.claude/skills/seo-technical
rm -f ~/.claude/agents/seo-*.md
```

## Оновлення

Для оновлення до останньої версії:

```bash
# Uninstall current version
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/uninstall.sh | bash

# Install new version
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

## Усунення неполадок

### Помилка "Skill not found"

Переконайтеся, що навичка встановлена у правильному місці:

```bash
ls ~/.claude/skills/seo/SKILL.md
```

Якщо файл не існує, запустіть інсталятор повторно.

### Помилки залежностей Python

Встановіть залежності вручну:

```bash
pip install beautifulsoup4 requests lxml playwright Pillow urllib3 validators
```

### Помилки скріншотів Playwright

Встановіть браузер Chromium:

```bash
playwright install chromium
```

### Помилки дозволів на Unix

Переконайтеся, що скрипти мають права на виконання:

```bash
chmod +x ~/.claude/skills/seo/scripts/*.py
```
