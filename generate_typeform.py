import openai
import requests
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re

# Функция для генерации typeform JSON через ChatGPT

def generate_typeform_via_gpt(job_description, must_haves, prompt, post_submit_url, openai_api_key):
    client = openai.OpenAI(api_key=openai_api_key)
    messages = [
        {"role": "system", "content": "Ты помощник, который генерирует typeform JSON по шаблону."},
        {"role": "user", "content": prompt.format(job_description=job_description, must_haves=must_haves, post_submit_url=post_submit_url)}
    ]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2
    )
    return response.choices[0].message.content

# Функция для создания формы через Typeform API

def create_typeform(form_json, typeform_api_key):
    url = "https://api.typeform.com/forms"
    headers = {
        "Authorization": f"Bearer {typeform_api_key}",
        "Content-Type": "application/json"
    }
    print(f"DEBUG: Отправляем в Typeform JSON длиной: {len(form_json)}")
    print(f"DEBUG: Первые 500 символов JSON: {form_json[:500]}...")
    response = requests.post(url, headers=headers, data=form_json.encode('utf-8'))
    if not response.ok:
        print(f"DEBUG: Typeform API ошибка: {response.status_code}")
        print(f"DEBUG: Ответ Typeform: {response.text}")
    response.raise_for_status()
    return response.json()

def set_typeform_webhook(form_id, webhook_url, typeform_api_key):
    """Устанавливает webhook для указанной формы."""
    tag = "salary_check_webhook"  # Уникальный тег для нашего вебхука
    url = f"https://api.typeform.com/forms/{form_id}/webhooks/{tag}"
    headers = {
        "Authorization": f"Bearer {typeform_api_key}"
    }
    payload = {
        "url": webhook_url,
        "enabled": True
    }
    print(f"DEBUG: Устанавливаем Webhook для формы {form_id} на URL: {webhook_url}")
    response = requests.put(url, headers=headers, json=payload)
    if not response.ok:
        print(f"DEBUG: Ошибка установки Webhook: {response.status_code}")
        print(f"DEBUG: Ответ Typeform: {response.text}")
    response.raise_for_status()
    print("DEBUG: Webhook успешно установлен.")
    return response.json()

def get_field_id_by_title(form_json, title_substring):
    for field in form_json.get('fields', []):
        if title_substring.lower() in field.get('title', '').lower():
            return field.get('id')
    return None

def add_hidden_fields_to_json(form_json, hidden_fields):
    # Обеспечить, что hidden всегда есть
    if 'hidden' not in form_json or not isinstance(form_json['hidden'], list):
        form_json['hidden'] = []
    for field in hidden_fields:
        if field not in form_json['hidden']:
            form_json['hidden'].append(field)
    return form_json

def clean_typeform_json(form_json, post_submit_url=None):
    """Сортирует поля: основные вопросы — сначала, личные — в конце."""
    cleaned_json = {}
    cleaned_json['title'] = form_json.get('title', 'Job Application Form')
    fields = form_json.get('fields', [])

    personal_fields = []
    main_fields = []
    for f in fields:
        t = f.get('type')
        title = f.get('title', '').lower()
        if t == 'email' or 'email' in title or 'name' in title or 'phone' in title:
            personal_fields.append(f)
        else:
            main_fields.append(f)
    cleaned_json['fields'] = main_fields + personal_fields

    # Thank you screen с редиректом (оставим для совместимости, но не используем для email)
    if post_submit_url:
        cleaned_json['thankyou_screens'] = [
            {
                "ref": "redirect_thankyou",
                "title": "Спасибо за заполнение формы! Вы будете перенаправлены...",
                "type": "redirect",
                "properties": {
                    "redirect_url": post_submit_url
                }
            }
        ]
    else:
        cleaned_json['thankyou_screens'] = [
            {
                "ref": "default_thankyou_screen",
                "title": "Thank you for completing the form!",
                "properties": {
                    "show_button": False,
                    "share_icons": False
                }
            }
        ]
    return cleaned_json

def fix_typeform_json(form_json):
    # Исправляем поля: question -> title, choices -> properties, etc
    if isinstance(form_json, str):
        try:
            form_json = json.loads(form_json)
        except Exception:
            return form_json
    if 'fields' in form_json:
        for field in form_json['fields']:
            # question -> title
            if 'question' in field:
                field['title'] = field.pop('question')
            # choices -> properties.choices
            if 'choices' in field:
                field['properties'] = field.get('properties', {})
                field['properties']['choices'] = field.pop('choices')
            # если choices есть вне properties, переносим
            if 'properties' in field and 'choices' in field:
                field['properties']['choices'] = field.pop('choices')
            # если title отсутствует, но есть question
            if 'title' not in field and 'question' in field:
                field['title'] = field.pop('question')
            # если properties отсутствует, создаём
            if 'properties' not in field:
                field['properties'] = {}
            # --- Оставляем только допустимые свойства для number ---
            if field.get('type') == 'number':
                allowed = {'description'}
                field['properties'] = {k: v for k, v in field['properties'].items() if k in allowed}
            # убираем невалидные ключи
            for k in list(field.keys()):
                if k not in ['type', 'title', 'ref', 'properties', 'validations', 'id', 'attachment', 'description', 'allow_multiple_selections', 'allow_other_choice']:
                    del field[k]
    # Thank you screen
    if 'thankyou_screens' in form_json:
        for screen in form_json['thankyou_screens']:
            # Приводим к type thankyou_screen
            screen['type'] = 'thankyou_screen'
            if 'message' in screen:
                del screen['message']
            if 'button' in screen:
                del screen['button']
            # Добавляем title, если нет
            if 'title' not in screen:
                screen['title'] = 'Спасибо!'
            # show_button по умолчанию false
            if 'properties' not in screen:
                screen['properties'] = {}
            if 'show_button' not in screen['properties']:
                screen['properties']['show_button'] = False
            # redirect_url переносим в properties
            if 'redirect_url' in screen:
                screen['properties']['redirect_url'] = screen.pop('redirect_url')
            # убираем невалидные ключи
            for k in list(screen.keys()):
                if k not in ['type', 'ref', 'properties', 'title']:
                    del screen[k]
    return form_json

# Основная функция пайплайна

def generate_and_create_typeform(job_description, must_haves, prompt, example_json, openai_api_key, typeform_api_key, webhook_base_url=None):
    # 1. Готовим post_submit_url для prompt
    post_submit_url = None
    if webhook_base_url:
        post_submit_url = f"{webhook_base_url.rstrip('/')}/post-submit?salary={{hidden:salary}}&must_haves={{hidden:must_haves}}"
    # 2. Получаем JSON формы через ChatGPT
    typeform_json_str = generate_typeform_via_gpt(job_description, must_haves, prompt, post_submit_url, openai_api_key)
    print(f"OpenAI вернул: '{typeform_json_str}'")
    
    # 2. Парсим JSON
    try:
        form_json = json.loads(typeform_json_str)
        print("JSON от OpenAI успешно распарсен")
    except Exception as e:
        print(f"Ошибка парсинга JSON от OpenAI: {e}")
        print("Используем example_json как fallback")
        try:
            form_json = json.loads(example_json)
        except Exception as e2:
            print(f"Ошибка парсинга example_json: {e2}")
            return {"error": "Не удалось создать валидный JSON формы"}
    
    # 3. Очищаем JSON и добавляем hidden fields
    form_json = clean_typeform_json(form_json, post_submit_url=post_submit_url)
    form_json = add_hidden_fields_to_json(form_json, ["salary_field_id", "must_haves_field_id"])
    
    # 4. Отправляем форму в Typeform
    typeform_json_str_to_send = json.dumps(form_json)
    typeform_response = create_typeform(typeform_json_str_to_send, typeform_api_key)
    
    # 5. Устанавливаем Webhook, если передан URL
    if webhook_base_url:
        form_id = typeform_response.get('id')
        webhook_full_url = f"{webhook_base_url.rstrip('/')}/salary-check"
        set_typeform_webhook(form_id, webhook_full_url, typeform_api_key)
    else:
        print("DEBUG: WEBHOOK_BASE_URL не установлен, пропускаем настройку вебхука.")

    # 6. Ищем ID полей в ответе от Typeform
    salary_field_id = get_field_id_by_title(typeform_response, "salary")
    must_haves_field_id = get_field_id_by_title(typeform_response, "must have")
    
    # 7. Возвращаем результат
    return {
        'form_id': typeform_response.get('id'),
        'form_url': typeform_response.get('_links', {}).get('display'),
        'salary_field_id': salary_field_id,
        'must_haves_field_id': must_haves_field_id
    }

def generate_questions_via_gpt(job_description, must_haves, prompt, openai_api_key):
    client = openai.OpenAI(api_key=openai_api_key)
    messages = [
        {"role": "system", "content": "Ты помощник, который генерирует вопросы для анкеты."},
        {"role": "user", "content": prompt.format(job_description=job_description, must_haves=must_haves)}
    ]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2
    )
    return response.choices[0].message.content

def generate_typeform_json_via_gpt(questions, post_submit_url, prompt, openai_api_key):
    client = openai.OpenAI(api_key=openai_api_key)
    messages = [
        {"role": "system", "content": "Ты помощник, который генерирует typeform JSON по списку вопросов."},
        {"role": "user", "content": prompt.format(questions=questions, post_submit_url=post_submit_url)}
    ]
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0.2
    )
    return response.choices[0].message.content

# Функция для записи в Google Sheets

def write_to_sheets(sheet_id, cell, value, creds_path):
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    sheet.values().update(
        spreadsheetId=sheet_id,
        range=cell,
        valueInputOption='RAW',
        body={'values': [[value]]}
    ).execute()

def read_prompt_from_sheet(sheet_id, sheet_name, cell, creds_path):
    # Удаляем кавычки, если они есть
    sheet_name = sheet_name.strip("'\"")
    # Если есть пробелы или дефисы — добавляем кавычки
    if (" " in sheet_name or "-" in sheet_name):
        range_str = f"'{sheet_name}'!{cell}"
    else:
        range_str = f"{sheet_name}!{cell}"
    creds = service_account.Credentials.from_service_account_file(
        creds_path,
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=sheet_id,
        range=range_str
    ).execute()
    values = result.get('values', [[]])
    return values[0][0] if values and values[0] else None 