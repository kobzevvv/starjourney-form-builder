# Промпт для генерации вопросов по job description (Typeform)

Сгенерируй 3-6 вопросов для формы Typeform только на основе следующего job description. Не используй must have требования — не формулируй вопросы по must have, только по содержанию job description. Язык вопросов должен совпадать с языком job description.

**ВЕРНИ ТОЛЬКО ВАЛИДНЫЙ JSON-массив объектов, без пояснений, без форматирования, без нумерации, без текста до или после массива.**

Каждый вопрос — объект с полями:
- title (строка, текст вопроса)
- ref (уникальный читаемый идентификатор, латиницей, например: experience, stack, motivation и т.д.)
- type (multiple_choice, short_text, long_text, number и т.д. — только допустимые типы Typeform)
- properties (если применимо: choices для multiple_choice, description и т.д.)
- validations (required: true/false)

**Запрещено использовать type "yes_no"! Для всех бинарных (да/нет) вопросов используй type "multiple_choice" с полем properties.choices = [ {"label": "Yes"}, {"label": "No"} ]. ЗАПРЕЩЕНО ИСПОЛЬЗОВАТЬ long_text/short_text тип вопросов - только multiple_choice с указанием**

**Не формулируй вопросы по must have требованиям! Только по job description!**

Пример:
```json
[
  {
    "title": "What is your main programming language?",
    "ref": "main_language",
    "type": "multiple_choice",
    "properties": {
      "choices": [
        {"label": "Python"},
        {"label": "JavaScript"},
        {"label": "Java"},
        {"label": "Other"}
      ]
    },
    "validations": {"required": true}
  },
  {
    "title": "Do you have experience in eCommerce performance marketing?",
    "ref": "ecommerce_experience",
    "type": "multiple_choice",
    "properties": {
      "choices": [
        {"label": "Yes"},
        {"label": "No"}
      ]
    },
    "validations": {"required": true}
  }
]
```

**Не добавляй никаких пояснений, форматируй только как JSON-массив!** 