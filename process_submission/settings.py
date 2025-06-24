# settings.py

import os

# Названия листов и столбцов
SHEET_NAME = "journeys"
CONFIG_SHEET = "gpt instruction"
COLUMN_JOB_DESC = "C"
COLUMN_MUST_HAVES = "D"
COLUMN_QUESTIONS = "G"
COLUMN_FORM_LINK = "H"  # Например, если ссылка справа от вопросов

# Фиксированные ячейки для промптов
QUESTIONS_PROMPT_CELL = "B6"
LOGIC_PROMPT_CELL = "B7"

# Дефолтные промпты (если не пришли из Google Sheets)
DEFAULT_QUESTIONS_PROMPT = (
    "Сгенерируй вопросы для собеседования по описанию и must have. "
    "Все вопросы про must have параметры должны быть в формате Да/нет, и в форме должен быть выбор да/нет."
)
DEFAULT_LOGIC_PROMPT = (
    "Построй логику формы: если на любой must have ответ 'Нет' — завершить форму с отказом."
)

# Переменные окружения
REGION = os.environ.get("REGION", "us-central1")
PROJECT = os.environ.get("PROJECT", "qalearn")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
GOOGLE_CREDS_PATH = os.environ.get("GOOGLE_CREDS_PATH", "creds.json")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TYPEFORM_API_KEY = os.environ.get("TYPEFORM_API_KEY")

# Настройки логирования
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Настройки валидации
REQUIRED_FIELDS = ["email", "phone"]
PROCESS_SUBMISSION_URL = "https://us-central1-qalearn.cloudfunctions.net/process_submission"
