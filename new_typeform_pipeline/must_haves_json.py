# must_haves_json.py
"""
Генерация второй части json (вопросы по must haves, логика для зарплаты) вручную.
"""

import re
import openai
from settings import OPENAI_API_KEY

def detect_language(job_description):
    """
    Определяет язык job description с помощью OpenAI.
    Возвращает код языка: 'en', 'ru', 'es', 'it', и т.д.
    """
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": "Determine the language of the given text. Respond with only the language code (en, ru, es, it, de, fr, etc.)"
                },
                {
                    "role": "user", 
                    "content": job_description[:500]  # Берем первые 500 символов для анализа
                }
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip().lower()
    except Exception:
        return "en"  # Fallback to English

def translate_text(text, target_language):
    """
    Переводит текст на целевой язык с помощью OpenAI.
    """
    if target_language == "ru":
        return text  # Already in Russian
    
    language_names = {
        "en": "English",
        "es": "Spanish", 
        "it": "Italian",
        "de": "German",
        "fr": "French"
    }
    
    target_lang_name = language_names.get(target_language, "English")
    
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system", 
                    "content": f"Translate the following text to {target_lang_name}. Return only the translation, nothing else."
                },
                {
                    "role": "user", 
                    "content": text
                }
            ],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return text  # Fallback to original text

def generate_musthaves_questions_json(must_haves, job_description, budget=None):
    """
    Генерирует список вопросов по must haves (fields) и jumps/logic для зарплаты.
    Возвращает tuple: (fields, logic)
    """
    fields = []
    logic = []
    salary_field_ref = None
    salary_question_idx = None
    flex_choice_id = None
    
    # Определяем язык job description
    target_language = detect_language(job_description)
    
    # Переводим стандартные фразы
    yes_label = translate_text("Да", target_language)
    no_label = translate_text("Нет", target_language)
    experience_template = translate_text("У вас есть опыт: {must}?", target_language)
    salary_question = translate_text("Каковы ваши ожидания по зарплате?", target_language)
    budget_question_template = translate_text("Наш бюджет {budget}. Вы готовы к нему?", target_language)
    
    no_choice_refs = []  # Собираем все ref'ы ответов "Нет"
    
    # Генерируем вопросы по must haves
    for idx, must in enumerate(must_haves):
        # Пример шаблона: "У вас есть опыт: {must}?"
        ref = f"musthave_{idx+1}"
        if re.search(r'зарплат|salary|budget', must, re.IGNORECASE):
            # Вопрос про зарплату
            salary_field_ref = ref
            salary_question_idx = len(fields)  # Используем текущую длину списка
            field = {
                "title": salary_question,
                "ref": ref,
                "type": "number",
                "validations": {"required": True}
            }
        else:
            # Генерируем уникальные choice IDs для вопросов да/нет
            no_choice_id = f"no_choice_{idx+1}"
            no_choice_refs.append(no_choice_id)
            field = {
                "title": experience_template.format(must=must),
                "ref": ref,
                "type": "multiple_choice",
                "properties": {
                    "choices": [
                        {"label": yes_label, "ref": f"yes_choice_{idx+1}"},
                        {"label": no_label, "ref": no_choice_id}
                    ]
                },
                "validations": {"required": True}
            }
        fields.append(field)
    
    # Добавляем вопрос про бюджет, если есть зарплатный вопрос и задан бюджет
    if salary_field_ref and budget:
        flex_ref = "salary_flexibility"
        flex_choice_no_id = "flex_no_choice"
        flex_field = {
            "title": budget_question_template.format(budget=budget),
            "ref": flex_ref,
            "type": "multiple_choice",
            "properties": {
                "choices": [
                    {"label": yes_label, "ref": "flex_yes_choice"},
                    {"label": no_label, "ref": flex_choice_no_id}
                ]
            },
            "validations": {"required": True}
        }
        fields.insert(salary_question_idx+1, flex_field)
        
        # Преобразуем budget в число
        try:
            budget_value = int(float(str(budget).replace(',', '.'))) #odd activity
        except (ValueError, TypeError):
            budget_value = 0
        
        # Логика: если зарплата выше бюджета — jump на вопрос про гибкость
        logic.append({
            "type": "field",
            "ref": salary_field_ref,
            "actions": [
                {
                    "action": "jump",
                    "details": {
                        "to": {
                            "type": "field",
                            "value": flex_ref
                        }
                    },
                    "condition": {
                        "op": "greater_than",
                        "vars": [
                            {"type": "field", "value": salary_field_ref},
                            {"type": "constant", "value": budget_value}
                        ]
                    }
                }
            ]
        })
        
        # Логика: если ответ "Нет" на гибкость — просто продолжаем к следующим вопросам
        # Решение принимается во второй Cloud Function
        # Не добавляем logic для отказа по гибкости зарплаты
    
    # Логика обработки must-have ответов перенесена в process_submission функцию
    # В Typeform оставляем только логику для зарплаты (если есть)
    
    return fields, logic

# TODO: реализовать генерацию must have вопросов и логику для зарплаты 