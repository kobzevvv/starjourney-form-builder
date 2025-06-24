"""
Модуль logic_generator: генерация логики для формы Typeform.
"""

import logging
import re
from settings import DEFAULT_LOGIC_PROMPT


def extract_budget(must_haves):
    """
    Извлекает бюджет из текста must_haves (например, 'max budget is 2000 EUR').
    """
    match = re.search(r'(\d{3,6})\s*(eur|euro|€|евро)', must_haves.lower())
    if match:
        return int(match.group(1))
    return None


def find_salary_field(fields):
    """
    Находит индекс и ref поля зарплаты (salary) в списке вопросов.
    """
    for idx, f in enumerate(fields):
        if 'salary' in f.get('title', '').lower() or 'зарплат' in f.get('title', '').lower():
            return idx, f
    return None, None


def extract_must_haves(must_haves):
    # Пример: разбить по строкам, убрать пустые, убрать "зарплата" и т.д.
    return [line.strip('-•: .').strip() for line in must_haves.split('\n') if line.strip()]


def generate_logic_gpt(questions, must_haves, prompt, openai_api_key, budget=None, fail_url=None, quiz_url=None):
    """
    Генерирует JSON-логику для Typeform через OpenAI, используя вопросы, must-haves и промпт из B8.
    Добавляет технические требования по jump по зарплате и переходам на thankyou screen с нужными URL.
    Возвращает dict (logic).
    """
    logger = logging.getLogger("logic_generator")
    if not questions or not must_haves or not prompt:
        logger.error("Отсутствуют обязательные входные данные для генерации логики.")
        raise ValueError("Необходимо указать вопросы, must-haves и промпт.")
    must_have_list = [line.strip('-•: .').strip() for line in must_haves.split('\n') if line.strip()]
    tech_details = f"""
    Технические требования:
    - Если зарплата кандидата выше бюджета ({budget}), сделай jump на вопрос 'Наш бюджет {budget}, вы готовы на эти условия?' (multiple_choice: Да/Нет).
    - Если ответ на этот вопрос 'Нет' — делай jump на thankyou screen с redirect_url: {fail_url}.
    - Если ответ 'Да' — пользователь доходит до основного thankyou screen с redirect_url: {quiz_url}.
    - Остальную логику не добавляй. Используй только jumps внутри Typeform.
    """
    prompt_full = (
        prompt + "\n" + tech_details +
        f"Вопросы: {questions}\nMust haves: {', '.join(must_have_list)}"
    )
    try:
        import openai
        client = openai.OpenAI(api_key=openai_api_key)
        messages = [
            {"role": "system", "content": "Ты — генератор логики для Typeform API."},
            {"role": "user", "content": prompt_full}
        ]
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0
        )
        import json
        logic = json.loads(response.choices[0].message.content)
        logger.info(f"Сгенерирована логика: {logic}")
        return logic
    except Exception as e:
        logger.error(f"Ошибка генерации логики через OpenAI: {e}")
        raise 