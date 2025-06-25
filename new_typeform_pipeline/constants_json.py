# constants_json.py
"""
Генерация третьей части json: константные поля формы (name, email, phone, thankyou screen).
"""

from must_haves_json import detect_language, translate_text

def get_constants_fields_and_thankyou(redirect_url: str, job_description: str = "", must_haves: str = ""):
    """
    Возвращает список dict (fields) для name, email, phone и thankyou screens с нужными аттрибутами и редиректами.
    job_description используется для определения языка и перевода вопросов.
    must_haves передается в redirect_url для обработки в process_submission.
    """
    # Определяем язык job description
    target_language = detect_language(job_description)

    # Переводим стандартные поля
    name_title = translate_text("Ваше имя", target_language)
    email_title = translate_text("Email", target_language)
    phone_title = translate_text("Телефон", target_language)
    success_message = translate_text("Спасибо за заполнение формы!", target_language)
    fail_message = translate_text("Спасибо за интерес, но к сожалению, вы не подходите по требованиям.", target_language)

    fields = [
        {
            "title": name_title,
            "ref": "name",
            "type": "short_text",
            "validations": {"required": True}
        },
        {
            "title": email_title,
            "ref": "email",
            "type": "email",
            "validations": {"required": True}
        },
        {
            "title": phone_title,
            "ref": "phone",
            "type": "phone_number",
            "validations": {"required": True}
        }
    ]
    
    # Строим полный redirect URL с необходимыми параметрами
    import urllib.parse
    
    # Базовые параметры для process_submission
    # Поскольку Typeform не поддерживает переменные в logic, используем статический pass=true
    # и проверяем ответы на must-have вопросы в process_submission функции
    params = {
        "pass": "true",  # Всегда true, логика проверки в process_submission
        "must_haves": must_haves,
        "email": "{{field:email}}",
        "phone": "{{field:phone}}", 
        "name": "{{field:name}}"
    }
    
    # Добавляем все ответы на must-have вопросы в URL для проверки в GCF
    must_haves_list = [line.strip('-•: .').strip() for line in must_haves.split('\n') if line.strip()]
    for idx, must in enumerate(must_haves_list, 1):
        field_key = f"musthave_{idx}"
        params[field_key] = "{{field:" + field_key + "}}}"
    
    # Добавляем параметры к базовому URL
    base_url = redirect_url.split('?')[0]
    query_string = urllib.parse.urlencode(params)
    full_redirect_url = f"{base_url}?{query_string}"
    
    # Создаем один thankyou screen с обязательным редиректом к GCF
    thankyou_screens = [
        {
            "ref": "redirect_to_gcf",
            "title": "redirect to processing",
            "type": "url_redirect",
            "properties": {
                "redirect_url": full_redirect_url
            }
        }
    ]
    
    return fields, thankyou_screens

# TODO: реализовать генерацию константных полей 