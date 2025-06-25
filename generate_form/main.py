import logging
from flask import jsonify, Request
from googleapiclient.discovery import build
from google.oauth2 import service_account
from question_builder import generate_questions_gpt
from logic_generator import generate_logic_gpt
from json_builder import generate_form_json, send_to_typeform, sanitize_redirect_url, basic_manual_check
from settings import (
    SHEET_NAME, CONFIG_SHEET, COLUMN_JOB_DESC, COLUMN_MUST_HAVES, COLUMN_QUESTIONS, COLUMN_FORM_LINK,
    QUESTIONS_PROMPT_CELL, LOGIC_PROMPT_CELL, DEFAULT_QUESTIONS_PROMPT, DEFAULT_LOGIC_PROMPT,
    REGION, PROJECT, GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH, OPENAI_API_KEY, TYPEFORM_API_KEY, PROCESS_SUBMISSION_URL,
    FAIL_URL, FORM_PROMPT_CELL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# --- Cloud Function ---
def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDS_PATH,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

def read_row(row_id):
    sheet = get_sheets_service()
    ranges = [
        f"{SHEET_NAME}!{COLUMN_JOB_DESC}{row_id}:{COLUMN_MUST_HAVES}{row_id}",  # C и D
        f"{SHEET_NAME}!{COLUMN_FORM_LINK}{row_id}"  # H
    ]
    result = sheet.values().batchGet(spreadsheetId=GOOGLE_SHEET_ID, ranges=ranges).execute()
    values = result.get('valueRanges', [])
    job_desc = values[0]['values'][0][0] if len(values) > 0 and 'values' in values[0] else ''
    must_haves = values[0]['values'][0][1] if len(values) > 0 and 'values' in values[0] and len(values[0]['values'][0]) > 1 else ''
    form_link = values[1]['values'][0][0] if len(values) > 1 and 'values' in values[1] else ''
    return job_desc, must_haves, form_link

def write_to_sheet(cell, value):
    sheet = get_sheets_service()
    sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=cell,
        valueInputOption='RAW',
        body={'values': [[value]]}
    ).execute()

def read_config(cell):
    sheet = get_sheets_service()
    range_ = f"{CONFIG_SHEET}!{cell}"
    result = sheet.values().get(spreadsheetId=GOOGLE_SHEET_ID, range=range_).execute()
    values = result.get('values', [[]])
    return values[0][0] if values and values[0] else ''

# --- Основная функция Cloud Function ---
def generate_form(request: Request):
    args = request.args if request.method == 'GET' else request.form
    row_id = args.get("row_id")
    if not row_id:
        return jsonify({"error": "row_id обязателен"}), 400
    logger.info(f"Получен запрос: row_id={row_id}")
    try:
        job_desc, must_haves, form_link = read_row(row_id)
        prompt_questions = read_config(QUESTIONS_PROMPT_CELL) or DEFAULT_QUESTIONS_PROMPT
        prompt_logic = read_config(LOGIC_PROMPT_CELL) or ""
        prompt_form = read_config(FORM_PROMPT_CELL) or DEFAULT_QUESTIONS_PROMPT
        # 1. Генерируем вопросы через OpenAI
        questions = generate_questions_gpt(job_desc, must_haves, prompt_questions, OPENAI_API_KEY)
        # Получаем значения для логики
        budget = None
        for line in must_haves.split('\n'):
            if 'budget' in line.lower() or 'бюджет' in line.lower():
                import re
                match = re.search(r'(\d+[\.,]?\d*)', line)
                if match:
                    budget = match.group(1)
        fail_url = FAIL_URL
        quiz_url = PROCESS_SUBMISSION_URL
        # 2. Генерируем логику через OpenAI
        logic = generate_logic_gpt(questions, must_haves, prompt_logic, OPENAI_API_KEY, budget, fail_url, quiz_url)
        # 3. Генерируем финальный JSON формы через OpenAI
        form_json = generate_form_json(questions, logic, prompt_form, OPENAI_API_KEY)
        # 4. Минимальная ручная проверка и замена плейсхолдеров
        form_json = sanitize_redirect_url(form_json)
        basic_manual_check(form_json)
        # 5. Отправляем в Typeform
        logger.info(f"Form JSON before sending to Typeform: {form_json}")
        response = send_to_typeform(form_json, TYPEFORM_API_KEY)
        form_url = response.get('form_url')
        form_link_cell = f"{COLUMN_FORM_LINK}{row_id}"
        write_to_sheet(form_link_cell, form_url)
        logger.info(f"Ссылка на форму записана в {form_link_cell}")
        return jsonify({"ok": True, "form_url": form_url})
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({"error": str(e)}), 500