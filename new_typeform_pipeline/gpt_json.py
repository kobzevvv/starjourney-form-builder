"""
Генерация первой части json (вопросы по job description) через chatGPT и промпт из файла.
"""

import openai
import logging
import re

logger = logging.getLogger("gpt_json")

def fallback_questions_to_json(text):
    questions = []
    for line in text.split('\n'):
        line = line.strip()
        if not line or not re.match(r'\d+\.', line):
            continue
        q_text = re.sub(r'^\d+\.\s*', '', line)
        questions.append({
            "title": q_text,
            "ref": re.sub(r'\W+', '_', q_text.lower())[:30],
            "type": "short_text",
            "validations": {"required": True}
        })
    return questions

def generate_jobdesc_questions_json(job_description: str, prompt: str, openai_api_key: str, must_haves: str):
    """
    Генерирует список вопросов по job description через chatGPT и промпт из файла.
    Возвращает список dict (fields) для Typeform.
    """
    prompt_full = f"{prompt}\n\nJob description:\n{job_description}\n\nMust have requirements (for context, do not generate questions about them!):\n{must_haves}"
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
        import json
        content = response.choices[0].message.content
        logger.error(f"Ответ OpenAI (jobdesc questions): {content}")
        # Извлекаем только JSON-блок
        match = re.search(r'(\[.*\]|\{[\s\S]*\})', content, re.DOTALL)
        if not match:
            logger.error(f"Не удалось найти JSON-блок в ответе OpenAI (jobdesc questions)! Ответ: {content}")
            # fallback: парсим вопросы из текста
            return fallback_questions_to_json(content)
        json_str = match.group(0)
        try:
            fields = json.loads(json_str)
        except Exception as e:
            logger.error(f"Ошибка парсинга JSON из ответа OpenAI (jobdesc questions): {e}. JSON: {json_str}")
            raise ValueError(f"Ошибка парсинга JSON из ответа OpenAI (jobdesc questions): {e}")
        logger.info(f"Сгенерированы вопросы по job description: {fields}")
        return fields
    except Exception as e:
        logger.error(f"Ошибка генерации вопросов по job description через OpenAI: {e}")
        raise

# TODO: реализовать генерацию первой части json 