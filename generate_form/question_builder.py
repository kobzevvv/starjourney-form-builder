"""
Модуль question_builder: генерация вопросов для формы через OpenAI.
"""

import logging
import openai
from settings import DEFAULT_QUESTIONS_PROMPT, OPENAI_API_KEY
import re


def ensure_must_have_questions(questions_list, must_haves):
    """
    Для каждого must-have, по которому нет вопроса, добавляет multiple_choice вопрос с Yes/No.
    Убирает company name из вопросов.
    """
    # Удаляем вопросы, которые совпадают с названием компании или формы
    filtered_questions = [q for q in questions_list if not re.search(r'company|название компании|head of|e-commerce', q, re.IGNORECASE)]
    # Добавляем must-have вопросы, если их нет
    for must in must_haves:
        found = any(must.lower() in q.lower() for q in filtered_questions)
        if not found:
            filtered_questions.append(f"Do you have: {must}? (Yes/No)")
    return filtered_questions 

def generate_questions_gpt(job_description, must_haves, prompt, openai_api_key):
    """
    Генерирует список вопросов для Typeform через OpenAI, используя промпт из B7.
    Возвращает текст (или список строк) с вопросами и характеристиками, без требований к формату.
    """
    logger = logging.getLogger("question_builder")
    if not job_description or not must_haves or not prompt:
        logger.error("Отсутствуют обязательные входные данные для генерации вопросов.")
        raise ValueError("Необходимо указать описание вакансии, must-haves и промпт.")
    # must_haves всегда список строк с реальными значениями
    if isinstance(must_haves, str):
        must_have_list = [line.strip('-•: .').strip() for line in must_haves.split('\n') if line.strip()]
    else:
        must_have_list = [str(m).strip() for m in must_haves if str(m).strip()]
    prompt_full = (
        prompt + "\n"
        "Для каждого вопроса укажи ref — уникальный читаемый идентификатор (например, email, phone, musthave_english и т.д.). "
        "Не используй плейсхолдеры или переменные, только реальные значения must have. "
        f"Описание: {job_description}\nMust haves: {', '.join(must_have_list)}"
    )
    try:
        client = openai.OpenAI(api_key=openai_api_key)
        messages = [
            {"role": "system", "content": "Ты — генератор вопросов для Typeform API."},
            {"role": "user", "content": prompt_full}
        ]
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0
        )
        content = response.choices[0].message.content
        logger.error(f"Ответ OpenAI (questions): {content}")
        return content
    except Exception as e:
        logger.error(f"Ошибка генерации вопросов через OpenAI: {e}")
        raise 