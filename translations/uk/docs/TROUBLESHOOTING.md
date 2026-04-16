<!-- i18n-source: docs/TROUBLESHOOTING.md -->
<!-- i18n-source-sha: HEAD -->
<!-- i18n-date: 2026-04-10 -->

# Усунення неполадок

## Типові проблеми

### Навичка не завантажується

**Симптом:** Команда `/seo` не розпізнається

**Рішення:**

1. Перевірте встановлення:
```bash
ls ~/.claude/skills/seo/SKILL.md
```

2. Перевірте frontmatter у SKILL.md:
```bash
head -5 ~/.claude/skills/seo/SKILL.md
```
Має починатися з `---` та YAML.

3. Перезапустіть Claude Code:
```bash
claude
```

4. Перезапустіть інсталятор:
```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/install.sh | bash
```

---

### Помилки залежностей Python

**Симптом:** `ModuleNotFoundError: No module named 'requests'`

**Рішення:**

Починаючи з v1.2.0, залежності встановлюються у venv. Спробуйте:

```bash
# Use the venv pip
~/.claude/skills/seo/.venv/bin/pip install -r ~/.claude/skills/seo/requirements.txt
```

Якщо venv не існує, встановіть з `--user`:
```bash
pip install --user -r ~/.claude/skills/seo/requirements.txt
```

Або встановіть окремо:
```bash
pip install --user beautifulsoup4 requests lxml playwright Pillow urllib3 validators
```

### requirements.txt не знайдено

**Симптом:** `No such file: requirements.txt` після встановлення

**Рішення:** Починаючи з v1.2.0, requirements.txt копіюється в каталог навички:

```bash
ls ~/.claude/skills/seo/requirements.txt
```

Якщо відсутній, завантажте напряму:
```bash
curl -fsSL https://raw.githubusercontent.com/AgriciDaniel/claude-seo/main/requirements.txt \
  -o ~/.claude/skills/seo/requirements.txt
```

### Проблеми з виявленням Python на Windows

**Симптом:** `python is not recognized` або `pip points to wrong Python`

**Рішення (v1.2.0+):** Інсталятор Windows тепер пробує і `python`, і `py -3`. Якщо обидва не працюють:

1. Встановіть Python з [python.org](https://python.org) та позначте "Add to PATH"
2. Або використовуйте лаунчер Windows: `py -3 -m pip install -r requirements.txt`
3. Використовуйте `python -m pip` замість `pip`

---

### Помилки скріншотів Playwright

**Симптом:** `playwright._impl._errors.Error: Executable doesn't exist`

**Рішення:**
```bash
playwright install chromium
```

Якщо не працює:
```bash
pip install playwright
python -m playwright install chromium
```

---

### Помилки відмови в доступі

**Симптом:** `Permission denied` при запуску скриптів

**Рішення:**
```bash
chmod +x ~/.claude/skills/seo/scripts/*.py
```

---

### Субагент не знайдено

**Симптом:** `Agent 'seo-technical' not found`

**Рішення:**

1. Перевірте наявність файлів агентів:
```bash
ls ~/.claude/agents/seo-*.md
```

2. Перевірте frontmatter агента:
```bash
head -5 ~/.claude/agents/seo-technical.md
```

3. Перевстановіть агентів:
```bash
cp /path/to/claude-seo/agents/*.md ~/.claude/agents/
```

---

### Помилки тайм-ауту

**Симптом:** `Request timed out after 30 seconds`

**Рішення:**

1. Цільовий сайт може бути повільним — спробуйте знову
2. Збільшіть тайм-аут у викликах скриптів
3. Перевірте мережеве з'єднання
4. Деякі сайти блокують автоматичні запити

---

### Хибні спрацьовування валідації Schema

**Симптом:** Хук блокує валідну розмітку Schema

**Перевірка:**

1. Переконайтеся, що плейсхолдери замінені
2. Перевірте, що @context — `https://schema.org`
3. Перевірте наявність застарілих типів (HowTo, SpecialAnnouncement)
4. Валідуйте на [Google Rich Results Test](https://search.google.com/test/rich-results)

---

### Повільна продуктивність аудиту

**Симптом:** Повний аудит займає занадто багато часу

**Рішення:**

1. Аудит сканує до 500 сторінок — великі сайти потребують часу
2. Субагенти працюють паралельно для прискорення аналізу
3. Для швидших перевірок використовуйте `/seo page` для конкретних URL
4. Перевірте, чи сайт має повільний час відповіді

---

## Отримання допомоги

1. **Перевірте документацію:** Перегляньте [COMMANDS.md](../../docs/COMMANDS.md) та [ARCHITECTURE.md](../../docs/ARCHITECTURE.md)

2. **GitHub Issues:** Повідомляйте про помилки в репозиторії

3. **Логи:** Перевірте вивід Claude Code для деталей помилок

## Режим налагодження

Для детального виводу перевірте внутрішні логи Claude Code або запустіть скрипти напряму:

```bash
# Test fetch
python3 ~/.claude/skills/seo/scripts/fetch_page.py https://example.com

# Test parse
python3 ~/.claude/skills/seo/scripts/parse_html.py page.html --json

# Test screenshot
python3 ~/.claude/skills/seo/scripts/capture_screenshot.py https://example.com
```
