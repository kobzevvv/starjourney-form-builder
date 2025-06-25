import logging
from flask import jsonify, Request
from urllib.parse import parse_qs, urlparse
import json
import re
from settings import PROCESS_SUBMISSION_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("process_submission")

# --- Flask-приложение (оставлено для примера, не используется в Cloud Functions) ---
# from flask import Flask, request, redirect
# app = Flask(__name__)
# @app.route("/process_submission", methods=["GET"])
# def process_submission_flask():
#     ...

# --- Cloud Function ---
def validate_must_haves(must_haves_text, form_data):
    """
    Валидирует must-have параметры на основе ответов из формы.
    Возвращает True если все требования выполнены, False иначе.
    Особое правило: если есть вопрос budget_accept, именно его ответ считается must-have по бюджету.
    """
    logger.info(f"Валидация must-haves: {must_haves_text}")
    
    # Парсим must-haves из текста
    must_have_list = [line.strip('-•: .').strip() for line in must_haves_text.split('\n') if line.strip()]
    
    # Проверяем каждый must-have параметр
    for requirement in must_have_list:
        if not requirement:
            continue
        # Особая обработка для бюджета
        if 'бюджет' in requirement.lower() or 'budget' in requirement.lower():
            # Проверяем только ответ на budget_accept
            answer = form_data.get('budget_accept')
            if answer is None:
                logger.warning("Нет ответа на вопрос budget_accept (подтверждение бюджета)")
                return False
            if answer.lower() in ['yes', 'да', 'true', '1']:
                logger.info(f"✓ Требование по бюджету подтверждено (budget_accept: {answer})")
                continue
            else:
                logger.warning(f"✗ Требование по бюджету НЕ выполнено (budget_accept: {answer})")
                return False
        # Обычная проверка для остальных must-have
        found_match = False
        for field_ref, answer in form_data.items():
            if 'musthave' in field_ref.lower() and requirement.lower() in field_ref.lower():
                if answer.lower() in ['yes', 'да', 'true', '1']:
                    found_match = True
                    logger.info(f"✓ Требование '{requirement}' выполнено")
                    break
                else:
                    logger.warning(f"✗ Требование '{requirement}' НЕ выполнено (ответ: {answer})")
                    return False
        if not found_match and not ('бюджет' in requirement.lower() or 'budget' in requirement.lower()):
            logger.warning(f"⚠ Требование '{requirement}' не найдено в ответах формы")
    return True

def extract_form_data(url_params):
    """
    Извлекает данные формы из URL параметров Typeform.
    """
    form_data = {}
    
    # Typeform передает данные в формате field:ref=value
    for key, value in url_params.items():
        if ':' in key:
            field_type, field_ref = key.split(':', 1)
            form_data[field_ref] = value[0] if isinstance(value, list) else value
        else:
            form_data[key] = value[0] if isinstance(value, list) else value
    
    return form_data

def process_submission(request: Request):
    """
    Обрабатывает данные из формы Typeform и выполняет финальную валидацию.
    """
    logger.info("Получен запрос на обработку данных формы")
    
    try:
        # Получаем параметры из URL
        args = request.args
        
        # Проверяем обязательные параметры
        if 'pass' not in args:
            return jsonify({"error": "Отсутствует параметр pass"}), 400
        
        pass_status = args.get('pass')
        
        if pass_status != 'true':
            logger.info("Кандидат не прошел предварительную проверку")
            return jsonify({
                "status": "rejected",
                "message": "Кандидат не соответствует требованиям"
            }), 200
        
        # Извлекаем данные формы
        form_data = extract_form_data(args)
        logger.info(f"Данные формы: {form_data}")
        
        # Получаем must-haves
        must_haves = args.get('must_haves', '')
        if not must_haves:
            logger.warning("Отсутствуют must-have параметры")
            return jsonify({"error": "Отсутствуют must-have параметры"}), 400
        
        # Выполняем финальную валидацию
        is_valid = validate_must_haves(must_haves, form_data)
        
        if is_valid:
            logger.info("Кандидат прошел финальную валидацию")
            # Здесь можно добавить логику для сохранения данных в БД
            # или отправки уведомлений
            
            # Редирект на финальную ссылку
            success_url = args.get('success_url')
            # Извлекаем реальные значения полей из параметров field:ref
            actual_email = args.get('field:email', form_data.get('email', ''))
            actual_phone = args.get('field:phone', form_data.get('phone', ''))
            actual_name = args.get('field:name', form_data.get('name', ''))
            
            return jsonify({
                "status": "success",
                "message": "Кандидат успешно прошел все проверки",
                "redirect_url": success_url,
                "candidate_data": {
                    "email": actual_email,
                    "phone": actual_phone,
                    "name": actual_name,
                    "must_haves": must_haves
                }
            }), 200
        else:
            logger.info("Кандидат не прошел финальную валидацию")
            # Редирект на ссылку неудачи
            fail_url = args.get('fail_url')
            return jsonify({
                "status": "rejected",
                "message": "Кандидат не прошел финальную валидацию must-have параметров",
                "redirect_url": fail_url
            }), 200
            
    except Exception as e:
        logger.error(f"Ошибка обработки данных: {e}")
        return jsonify({"error": str(e)}), 500

#@app.route("/")
#def index():
#    return "OK" 