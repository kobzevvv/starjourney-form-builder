"""
Главная точка входа: объединяет все части json и отправляет форму в Typeform API.
"""

from flask import Request, jsonify
from gpt_json import generate_jobdesc_questions_json
from must_haves_json import generate_musthaves_questions_json
from constants_json import get_constants_fields_and_thankyou
from sheets_utils import read_row, write_questions_to_sheet, write_form_link_to_sheet
from settings import REDIRECT_URL, OPENAI_API_KEY, TYPEFORM_API_KEY
import requests
import logging
import re

logger = logging.getLogger("main_gcf")

# TODO: интеграция с Google Sheets для получения job_description, must_haves, budget
# TODO: интеграция с OpenAI API (OPENAI_API_KEY)
# TODO: интеграция с Typeform API (TYPEFORM_API_KEY)

def extract_budget(must_haves):
    for line in must_haves.split('\n'):
        if 'бюджет' in line.lower() or 'budget' in line.lower() or 'salary' in line.lower():
            match = re.search(r'(\d+[\.,]?\d*)', line)
            if match:
                return float(match.group(1).replace(',', '.'))
    return None

def extract_questions_text(jobdesc_fields, musthave_fields, constants_fields):
    """
    Извлекает все вопросы из полей формы и объединяет их в одну строку.
    """
    all_fields = jobdesc_fields + musthave_fields + constants_fields
    questions = []
    
    for i, field in enumerate(all_fields, 1):
        title = field.get('title', '')
        field_type = field.get('type', '')
        
        # Добавляем номер вопроса и заголовок
        question_text = f"{i}. {title}"
        
        # Если есть варианты ответов, добавляем их
        if field_type == 'multiple_choice' and 'properties' in field and 'choices' in field['properties']:
            choices = field['properties']['choices']
            choice_labels = [choice.get('label', '') for choice in choices]
            if choice_labels:
                question_text += f" ({', '.join(choice_labels)})"
        
        questions.append(question_text)
    
    return '\n'.join(questions)

def build_typeform_json(jobdesc_fields, musthave_fields, constants_fields, thankyou_screens, logic):
    """
    Собирает финальный JSON для Typeform из всех частей.
    """
    fields = jobdesc_fields + musthave_fields + constants_fields
    typeform_json = {
        "title": "Автоматическая форма найма",
        "type": "quiz",
        "workspace": {
            "href": "https://api.typeform.com/workspaces/LGttCw"
        },
        "theme": {
            "href": "https://api.typeform.com/themes/qHWOQ7"
        },
        "fields": fields,
        "logic": logic,
        "thankyou_screens": thankyou_screens,
        "settings": {
            "language": "en",
            "progress_bar": "proportion",
            "meta": {
                "allow_indexing": False
            },
            "hide_navigation": True,
            "is_public": True,
            "is_trial": False,
            "show_progress_bar": True,
            "show_typeform_branding": False,
            "are_uploads_public": False,
            "show_time_to_complete": True,
            "show_number_of_submissions": False,
            "show_cookie_consent": False,
            "show_question_number": True,
            "show_key_hint_on_choices": False,
            "autosave_progress": True,
            "free_form_navigation": True,
            "use_lead_qualification": False,
            "pro_subdomain_enabled": False,
            "auto_translate": True,
            "partial_responses_to_all_integrations": True
        }
    }
    return typeform_json

def send_to_typeform(typeform_json, typeform_api_key):
    url = "https://api.typeform.com/forms"
    headers = {
        "Authorization": f"Bearer {typeform_api_key}",
        "Content-Type": "application/json"
    }
    response = requests.post(url, headers=headers, json=typeform_json)
    if not response.ok:
        logger.error(f"Ошибка Typeform API: {response.status_code} {response.text}")
        response.raise_for_status()
    data = response.json()
    logger.info(f"Форма успешно создана: {data.get('id')}")
    return data.get("_links", {}).get("display")

def create_typeform(request: Request):
    try:
        args = request.args
        row_id = args.get("row_id")
        if not row_id:
            return jsonify({"error": "row_id обязателен"}), 400
        job_description, must_haves = read_row(row_id)
        must_haves_list = [line.strip('-•: .').strip() for line in must_haves.split('\n') if line.strip()]
        budget = extract_budget(must_haves)
        with open("prompt.md", encoding="utf-8") as f:
            prompt = f.read()
        jobdesc_fields = generate_jobdesc_questions_json(job_description, prompt, OPENAI_API_KEY, must_haves)
        musthave_fields, logic = generate_musthaves_questions_json(must_haves_list, job_description, budget)
        constants_fields, thankyou_screens = get_constants_fields_and_thankyou(REDIRECT_URL, job_description, must_haves)
        typeform_json = build_typeform_json(jobdesc_fields, musthave_fields, constants_fields, thankyou_screens, logic)
        
        # Отправляем форму в Typeform
        form_url = send_to_typeform(typeform_json, TYPEFORM_API_KEY)
        
        # Извлекаем вопросы из формы
        questions_text = extract_questions_text(jobdesc_fields, musthave_fields, constants_fields)
        
        # Записываем вопросы в ячейку G{row_id}
        write_questions_to_sheet(row_id, questions_text)
        logger.info(f"Вопросы записаны в ячейку G{row_id}")
        
        # Записываем ссылку на форму в ячейку H{row_id}
        write_form_link_to_sheet(row_id, form_url)
        logger.info(f"Ссылка на форму записана в ячейку H{row_id}")
        
        return jsonify({
            "ok": True, 
            "form_url": form_url,
            "questions_written_to": f"G{row_id}",
            "form_link_written_to": f"H{row_id}"
        })
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return jsonify({"error": str(e)}), 500 