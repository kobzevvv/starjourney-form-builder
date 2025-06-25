"""
Модуль json_builder: сборка финального JSON для Typeform и отправка в API.
"""

import logging
import requests
from settings import REGION, PROJECT, PROCESS_SUBMISSION_URL, OPENAI_API_KEY
import openai
import re


def validate_with_gpt(form_json, OPENAI_API_KEY):
    """
    Проверяет и исправляет структуру формы через OpenAI (GPT), чтобы она соответствовала Typeform API.
    Возвращает исправленный JSON (dict).
    """
    prompt = (
        "Проверь, что этот JSON полностью соответствует формату Typeform API. "
        "Если есть ошибки — исправь их. Верни только валидный JSON без пояснений.\n"
        f"{form_json}"
    )
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    import json
    return json.loads(response.choices[0].message.content)


def basic_manual_check(form_json):
    """
    Минимальная ручная проверка структуры формы.
    """
    if not isinstance(form_json, dict):
        raise ValueError("JSON формы должен быть словарём.")
    if "fields" not in form_json or not isinstance(form_json["fields"], list):
        raise ValueError("В JSON формы должен быть список fields.")
    if "title" not in form_json or not isinstance(form_json["title"], str):
        raise ValueError("В JSON формы должен быть строковый title.")
    for i, field in enumerate(form_json["fields"]):
        if not isinstance(field, dict):
            raise ValueError(f"Field #{i+1} должен быть словарём.")
        if "type" not in field or "title" not in field:
            raise ValueError(f"Field #{i+1} должен содержать type и title.")


def sanitize_redirect_url(form_json):
    """
    Заменяет любые плейсхолдеры в redirect_url на реальный PROCESS_SUBMISSION_URL.
    """
    if "thankyou_screens" in form_json:
        for screen in form_json["thankyou_screens"]:
            if (
                "properties" in screen and
                "redirect_url" in screen["properties"] and
                isinstance(screen["properties"]["redirect_url"], str)
            ):
                url = screen["properties"]["redirect_url"]
                # Заменяем любые плейсхолдеры вида {post_submit_url}, {redirect_url}, {url}
                if re.search(r"\{.*url.*\}", url, re.IGNORECASE):
                    screen["properties"]["redirect_url"] = PROCESS_SUBMISSION_URL
    return form_json


def build_final_redirect_url(fields, contact_refs=("email", "phone")):
    """
    Формирует redirect_url для thankyou screen с подстановками по всем must-have ref и контактным ref.
    fields: список вопросов (dict), каждый с ref
    contact_refs: список ref для контактов
    """
    params = []
    for field in fields:
        ref = field.get("ref")
        if ref and (ref.startswith("musthave") or ref in contact_refs):
            params.append(f"{ref}={{field:{ref}}}")
    # Добавляем email и phone, если их нет среди musthave
    for ref in contact_refs:
        if not any(f"{ref}=" in p for p in params):
            params.append(f"{ref}={{field:{ref}}}")
    base = PROCESS_SUBMISSION_URL.split('?')[0]
    return base + '?' + '&'.join(params)


def generate_form_json(questions, logic, prompt, openai_api_key):
    """
    Генерирует финальный JSON формы Typeform через OpenAI, используя вопросы (fields), jumps/logic и промпт из B6.
    Возвращает dict.
    """
    logger = logging.getLogger("json_builder")
    if not questions or not prompt:
        logger.error("Отсутствуют обязательные входные данные для генерации формы.")
        raise ValueError("Необходимо указать вопросы и промпт.")
    prompt_full = (
        prompt + "\n"
        "Собери финальный JSON для Typeform. Используй вопросы (fields) из списка ниже и jumps/logic (если есть). "
        "Не добавляй свои вопросы, не меняй структуру fields, просто собери валидный JSON формы. "
        f"fields: {questions}\nlogic: {logic if logic else 'нет логики'}"
    )
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        messages = [
            {"role": "system", "content": "Ты — генератор валидных JSON для Typeform API."},
            {"role": "user", "content": prompt_full}
        ]
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0
        )
        import json
        form_json = json.loads(response.choices[0].message.content)
        logger.info(f"Сгенерирован финальный JSON формы: {form_json}")
        # Валидация и автокоррекция через GPT
        try:
            form_json = validate_with_gpt(form_json, openai_api_key)
        except Exception as e:
            logger.error(f"Ошибка автокоррекции финального JSON через GPT: {e}. Исходный JSON: {form_json}")
            raise
        # Формируем redirect_url с подстановками
        redirect_url = build_final_redirect_url(form_json["fields"])
        # ... используем redirect_url для thankyou screen ...
    return form_json
    except Exception as e:
        logger.error(f"Ошибка генерации финального JSON формы через OpenAI: {e}")
        raise


def send_to_typeform(typeform_json, typeform_api_key):
    """
    Отправляет JSON в Typeform API, возвращает ответ с ID и URL формы.
    """
    logger = logging.getLogger("json_builder")
    url = "https://api.typeform.com/forms"
    headers = {
        "Authorization": f"Bearer {typeform_api_key}",
        "Content-Type": "application/json"
    }
    try:
        logger.info("Отправка формы в Typeform API...")
        response = requests.post(url, headers=headers, json=typeform_json)
        if not response.ok:
            logger.error(f"Ошибка Typeform API: {response.status_code} {response.text}")
            response.raise_for_status()
        data = response.json()
        logger.info(f"Форма успешно создана: {data.get('id')}")
        return {
            "form_id": data.get("id"),
            "form_url": data.get("_links", {}).get("display")
        }
    except Exception as e:
        logger.error(f"Ошибка отправки в Typeform: {e}")
        raise 