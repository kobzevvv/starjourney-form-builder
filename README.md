# HR Auto Form Pipeline

## Описание

Этот проект реализует полный автоматизированный пайплайн для генерации и обработки форм найма с помощью Google Cloud Functions, Typeform, OpenAI (ChatGPT) и Google Sheets.

- **generate_form/** — генерация вопросов, логики и финального JSON формы на основе промптов из Google Sheets, отправка формы в Typeform.
- **process_submission/** — обработка результатов заполнения формы, финальная валидация и редиректы.

---

## Архитектура

1. **Google Sheets** — источник промптов (B6 — финальная форма, B7 — вопросы, B8 — логика).
2. **generate_form**
    - Получает описание вакансии и must-have из таблицы.
    - Генерирует вопросы (OpenAI, промпт из B7).
    - Генерирует jumps/логику (OpenAI, промпт из B8).
    - Генерирует финальный JSON формы (OpenAI, промпт из B6).
    - Отправляет форму в Typeform, записывает ссылку в таблицу.
3. **Пользователь** — заполняет форму Typeform.
4. **Thankyou screen** — редиректит на process_submission с параметрами.
5. **process_submission** — финальная обработка, валидация, редиректы.

---

## Структура репозитория

```
HR_auto/
  generate_form/
    main.py              # Точка входа Cloud Function
    question_builder.py  # Генерация вопросов через OpenAI
    logic_generator.py   # Генерация логики (jumps) через OpenAI
    json_builder.py      # Сборка финального JSON, отправка в Typeform
    settings.py          # Все переменные и настройки
    requirements.txt     # Зависимости
  process_submission/
    main.py              # Обработка результатов формы
    settings.py          # Переменные окружения
    requirements.txt     # Зависимости
  .gitignore             # creds.json и чувствительные файлы не попадают в git
```

---

## Быстрый старт

### 1. Переменные окружения

- Все ключи (OpenAI, Typeform, Google API) задаются через переменные окружения или файл creds.json (НЕ коммитить!).
- Пример переменных:
  - `OPENAI_API_KEY`
  - `TYPEFORM_API_KEY`
  - `GOOGLE_SHEET_ID`
  - `GOOGLE_CREDS_PATH`
  - `FAIL_URL`

### 2. Установка зависимостей

```bash
cd generate_form
pip install -r requirements.txt
cd ../process_submission
pip install -r requirements.txt
```

### 3. Деплой в Google Cloud Functions

- Для каждой части (generate_form, process_submission) деплойте как отдельную функцию.
- Точка входа: `main.generate_form` и `main.process_submission` соответственно.

---

## Основные сценарии

1. **Генерация формы**
    - Вызов Cloud Function с row_id.
    - Вопросы, логика и финальный JSON генерируются через OpenAI по промптам из Google Sheets.
    - Ссылка на форму записывается обратно в таблицу.
2. **Заполнение формы**
    - Пользователь проходит Typeform, на thankyou screen происходит редирект с параметрами.
3. **Обработка результатов**
    - Все параметры попадают в process_submission, где происходит финальная валидация и редирект на success/fail.

---

## Безопасность
- Все ключи и creds.json должны быть в .gitignore и не попадать в репозиторий.
- Не храните чувствительные данные в коде или открытых файлах.

---

## Контакты

Вопросы по проекту — к @sobolev или через issues в репозитории. 