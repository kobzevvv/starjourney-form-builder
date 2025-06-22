import os
import re
from flask import Flask, request, jsonify, redirect
from generate_typeform import generate_and_create_typeform, generate_questions_via_gpt, generate_typeform_json_via_gpt, write_to_sheets, add_hidden_fields_to_json, create_typeform, fix_typeform_json, get_field_id_by_title, read_prompt_from_sheet
from google.oauth2 import service_account
from googleapiclient.discovery import build
import requests
import smtplib
from email.mime.text import MIMEText
import traceback
import json


# --- Глобальные переменные окружения (API-ключи и настройки) ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
TYPEFORM_API_KEY = os.environ.get("TYPEFORM_API_KEY")
GEN_PROMPT = os.environ.get("GEN_PROMPT")
EXAMPLE_JSON_PATH = os.environ.get("EXAMPLE_JSON_PATH", "typeform.json")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID", "19tfgKaNIcDD3zPUHaUoLExEgWipanUEgS_Sk0n-C9xc")
GOOGLE_CREDS_PATH = os.environ.get("GOOGLE_CREDS_PATH", "creds.json")
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "journeysс")  # Название листа в таблице
WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL") # Базовый URL для вебхуков (напр., от ngrok)

SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM")

# --- Функция для получения промпта (строка или путь к файлу) ---
def get_prompt():
    if GEN_PROMPT and os.path.isfile(GEN_PROMPT):
        with open(GEN_PROMPT, "r") as f:
            return f.read()
    return GEN_PROMPT

app = Flask(__name__)

# URL для редиректа, если зарплата больше 5500
BUDGET_EXPLANATION_URL = os.environ.get("BUDGET_EXPLANATION_URL", "https://example.com/budget-explanation")
# URL для следующего шага (quiz/self-info form), если зарплата в бюджете
NEXT_STEP_URL = os.environ.get("NEXT_STEP_URL", "https://hiretechfast.typeform.com/to/NEW_FORM_ID")

# --- Функции для работы с Google Sheets ---
def get_range_from_cell(cell):
    match = re.match(r"([A-Z]+)(\d+)", cell.upper())
    if not match:
        return None
    col, row = match.groups()
    next_col_char = chr(ord(col[-1]) + 1)
    next_col = col[:-1] + next_col_char
    return f"{GOOGLE_SHEET_NAME}!{col}{row}:{next_col}{row}"

def read_from_sheets(sheet_id, range_):
    try:
        creds = service_account.Credentials.from_service_account_file(
            GOOGLE_CREDS_PATH,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=sheet_id,
            range=range_
        ).execute()
        values = result.get('values', [[]])
        if values and len(values[0]) >= 2:
            job_desc = values[0][0]
            must_haves = values[0][1]
            return job_desc, must_haves
        return None, None
    except Exception as e:
        print(f"Error reading from Google Sheets: {e}")
        return None, None

# --- Новый endpoint для запуска из ячейки Google Sheets ---
@app.route("/run-for-cell", methods=["POST"])
def run_for_cell():
    cell = request.args.get("cell")
    prompt_questions_cell = request.args.get("prompt_questions_cell", "B7")
    prompt_typeform_cell = request.args.get("prompt_typeform_cell", "B6")
    prompt_sheet = request.args.get("prompt_sheet", "gpt instruction")
    if not cell:
        return jsonify({"error": "Не указана ячейка"}), 400
    range_ = get_range_from_cell(cell)
    if not range_:
        return jsonify({"error": "Некорректный формат ячейки"}), 400
    job_description, must_haves = read_from_sheets(GOOGLE_SHEET_ID, range_)
    if not job_description or not must_haves:
        return jsonify({"error": "Не удалось прочитать данные из таблицы"}), 400
    # Читаем промпты из Google Sheets
    prompt_questions = read_prompt_from_sheet(GOOGLE_SHEET_ID, prompt_sheet, prompt_questions_cell, GOOGLE_CREDS_PATH)
    prompt_typeform = read_prompt_from_sheet(GOOGLE_SHEET_ID, prompt_sheet, prompt_typeform_cell, GOOGLE_CREDS_PATH)
    # Генерируем вопросы по кастомному промпту
    questions_text = generate_questions_via_gpt(job_description, must_haves, prompt_questions, OPENAI_API_KEY)
    # Парсим вопросы и добавляем обязательные, если их нет
    def ensure_required_questions(questions_text):
        lines = [l for l in questions_text.split('\n') if l.strip()]
        has_salary = any('salary' in l.lower() or 'зарплат' in l.lower() for l in lines)
        has_email = any('email' in l.lower() or 'почт' in l.lower() for l in lines)
        has_name = any('name' in l.lower() or 'имя' in l.lower() for l in lines)
        # Только email и имя добавляем программно, зарплату — только через промпт
        if not has_email:
            lines.append('Email\n• field_type: email\n• required: yes')
        if not has_name:
            lines.append('Full Name\n• field_type: short_text\n• required: yes')
        return '\n'.join(lines)
    questions_text = ensure_required_questions(questions_text)
    # Сохраняем вопросы в G-колонку
    match = re.match(r"([A-Z]+)(\d+)", cell.upper())
    if match:
        row = match.groups()[1]
        questions_cell = f"G{row}"
        write_to_sheets(GOOGLE_SHEET_ID, questions_cell, questions_text, GOOGLE_CREDS_PATH)
    # Генерируем JSON для Typeform
    post_submit_url = None
    if WEBHOOK_BASE_URL:
        post_submit_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/post-submit?salary={{hidden:salary}}&must_haves={{hidden:must_haves}}"
    if not post_submit_url:
        post_submit_url = "https://example.com"
    prompt_typeform = escape_curly_braces_except_vars(prompt_typeform)
    typeform_json_str = generate_typeform_json_via_gpt(questions_text, post_submit_url, prompt_typeform, OPENAI_API_KEY)
    # Парсим JSON и создаём форму
    try:
        form_json = json.loads(typeform_json_str)
    except Exception as e:
        print(f"Ошибка парсинга JSON от OpenAI: {e}")
        return jsonify({"error": "Не удалось распарсить JSON формы"}), 500
    form_json = add_hidden_fields_to_json(form_json, ["salary", "must_haves"])
    form_json = fix_typeform_json(form_json)
    typeform_json_str_to_send = json.dumps(form_json)
    typeform_response = create_typeform(typeform_json_str_to_send, TYPEFORM_API_KEY)
    salary_field_id = get_field_id_by_title(typeform_response, "salary")
    must_haves_field_id = get_field_id_by_title(typeform_response, "must have")
    return jsonify({
        'form_id': typeform_response.get('id'),
        'form_url': typeform_response.get('_links', {}).get('display'),
        'salary_field_id': salary_field_id,
        'must_haves_field_id': must_haves_field_id,
        'questions_cell': questions_cell
    })

# --- Новый endpoint: генерация формы ---
@app.route("/generate-form", methods=["POST"])
def generate_form():
    data = request.get_json(force=True)
    job_description = data.get("job_description")
    must_haves = data.get("must_haves")
    prompt = data.get("prompt") or get_prompt()  # Готовый промпт (строка или из файла)
    example_json_path = data.get("example_json_path") or EXAMPLE_JSON_PATH
    with open(example_json_path, "r") as f:
        example_json = f.read()
    if not all([job_description, must_haves, prompt, example_json, OPENAI_API_KEY, TYPEFORM_API_KEY]):
        return jsonify({"error": "Не хватает обязательных данных или ключей"}), 400
    try:
        result = generate_and_create_typeform(job_description, must_haves, prompt, example_json, OPENAI_API_KEY, TYPEFORM_API_KEY)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Endpoint для проверки must have (зарплата и др.) ---
def extract_salary_limit(must_haves_text):
    match = re.search(r'(\d{3,6})\s*(eur|euro|€|евро)', must_haves_text.lower())
    if match:
        return int(match.group(1))
    return None

def extract_must_haves(must_haves_text):
    """Извлекает структурированные данные из текста 'must_haves'."""
    salary_limit = extract_salary_limit(must_haves_text)
    # В будущем здесь можно будет добавить извлечение других параметров
    return {
        "salary_limit": salary_limit
    }

@app.route("/salary-check", methods=["POST"])
def salary_check():
    data = request.get_json(force=True)
    print("DEBUG: Получен запрос:", data)
    answers = data.get("form_response", {}).get("answers", [])
    salary_field_id = data.get("salary_field_id")
    must_haves_field_id = data.get("must_haves_field_id")
    # Если не переданы явно — пробуем взять из hidden
    if not salary_field_id or not must_haves_field_id:
        hidden = data.get("form_response", {}).get("hidden", {})
        salary_field_id = salary_field_id or hidden.get("salary_field_id")
        must_haves_field_id = must_haves_field_id or hidden.get("must_haves_field_id")
    if not salary_field_id or not must_haves_field_id:
        return jsonify({"error": "Не переданы salary_field_id или must_haves_field_id (ни в теле, ни в hidden)"}), 400
    salary = None
    must_haves = None
    email = None
    for answer in answers:
        field_id = answer.get("field", {}).get("id")
        if field_id == salary_field_id and answer.get("type") == "number":
            salary = answer.get("number")
        elif field_id == must_haves_field_id and answer.get("type") == "text":
            must_haves = answer.get("text")
        elif answer.get("type") == "email":
            email = answer.get("email")
    # --- Сохраняем все must have параметры и их значения ---
    user_must_haves = {}
    if must_haves:
        # Разбиваем must_haves на строки/параметры
        for param in must_haves.split('\n'):
            param = param.strip('-•: .').strip()
            if not param:
                continue
            # Ищем значение в ответах пользователя
            for answer in answers:
                # Сравниваем по тексту вопроса (title)
                field_title = answer.get('field', {}).get('title', '').lower()
                if param.lower() in field_title:
                    user_must_haves[param] = answer.get(answer.get('type'))
    # Извлечение всех must_have (пока только salary_limit)
    must_have_vars = extract_must_haves(must_haves) if must_haves else {}
    salary_limit = must_have_vars.get("salary_limit")
    if salary is None:
        return jsonify({"error": "Зарплата не найдена в ответе"}), 400
    if salary_limit is None:
        return jsonify({"error": "Не удалось определить лимит зарплаты из must_haves"}), 400
    print("DEBUG: salary =", salary, "salary_limit =", salary_limit)
    try:
        salary = float(salary)
    except (TypeError, ValueError):
        return jsonify({"error": "Некорректное значение зарплаты"}), 400
    # --- Проверка must have ---
    if not email:
        return jsonify({"error": "Email не найден в ответе"}), 400
    # Формируем ссылку
    if salary > salary_limit:
        link = BUDGET_EXPLANATION_URL
        msg_text = f"К сожалению, ваши зарплатные ожидания выше бюджета. Подробнее: {link}"
    else:
        link = NEXT_STEP_URL
        msg_text = f"Поздравляем! Вы прошли на следующий этап. Перейдите по ссылке: {link}"
    # Отправляем email
    try:
        msg = MIMEText(msg_text)
        msg["Subject"] = "Результат проверки анкеты"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, [email], msg.as_string())
        print(f"DEBUG: Email отправлен на {email}")
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        return jsonify({"error": f"Ошибка отправки email: {e}"}), 500
    return jsonify({
        "ok": True,
        "email": email,
        "link": link,
        "user_must_haves": user_must_haves
    })

@app.route("/first-form-webhook", methods=["POST"])
def first_form_webhook():
    data = request.get_json(force=True)
    answers = data.get("form_response", {}).get("answers", [])
    job_description = None
    must_haves = None
    for answer in answers:
        field = answer.get("field", {})
        if field.get("ref") == "job_description" and answer.get("type") == "text":
            job_description = answer.get("text")
        if field.get("ref") == "must_haves" and answer.get("type") == "text":
            must_haves = answer.get("text")
    if not job_description or not must_haves:
        return jsonify({"error": "job_description или must_haves не найдены в первой форме"}), 400
    prompt = get_prompt()
    example_json_path = EXAMPLE_JSON_PATH
    with open(example_json_path, "r") as f:
        example_json = f.read()
    if not all([prompt, OPENAI_API_KEY, TYPEFORM_API_KEY]):
        return jsonify({"error": "Не хватает промпта или ключей"}), 400
    result = generate_and_create_typeform(job_description, must_haves, prompt, example_json, OPENAI_API_KEY, TYPEFORM_API_KEY)
    return jsonify(result)

@app.route("/post-submit", methods=["GET"])
def post_submit():
    try:
        salary = float(request.args.get("salary", "0"))
        must_haves = request.args.get("must_haves", "")
        # Извлекаем лимит зарплаты из must_haves
        salary_limit = None
        import re
        match = re.search(r'(\d{3,6})\s*(eur|euro|€|евро)', must_haves.lower())
        if match:
            salary_limit = int(match.group(1))
        if salary_limit is None:
            return "Не удалось определить лимит зарплаты", 400
        if salary > salary_limit:
            return redirect(BUDGET_EXPLANATION_URL, code=302)
        else:
            return redirect(NEXT_STEP_URL, code=302)
    except Exception as e:
        return f"Ошибка: {e}", 400

def escape_curly_braces_except_vars(text, allowed_vars=None):
    if allowed_vars is None:
        allowed_vars = ["questions", "post_submit_url"]
    # Экранируем все одинарные { и }, кроме разрешённых переменных
    # 1. Экранируем все {{ и }} чтобы не задвоить
    text = text.replace("{{", "<DBL_L>").replace("}}", "<DBL_R>")
    # 2. Экранируем все {var} из allowed_vars временно
    for var in allowed_vars:
        text = re.sub(rf"\{{{var}\}}", f"<VAR_{var.upper()}>", text)
    # 3. Все оставшиеся { и } заменяем на двойные
    text = text.replace("{", "{{").replace("}", "}}")
    # 4. Возвращаем разрешённые переменные
    for var in allowed_vars:
        text = text.replace(f"<VAR_{var.upper()}>", f"{{{var}}}")
    # 5. Возвращаем двойные скобки
    text = text.replace("<DBL_L>", "{{").replace("<DBL_R>", "}}")
    return text

@app.route("/")
def index():
    return "OK"

def entrypoint(request):
    with app.request_context(request.environ):
        return app.full_dispatch_request()