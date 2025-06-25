import os
from dotenv import load_dotenv

load_dotenv()

# Google Sheets
SHEET_NAME = os.environ.get("SHEET_NAME", "journeys")
CONFIG_SHEET = os.environ.get("CONFIG_SHEET", "gpt instruction")
COLUMN_JOB_DESC = os.environ.get("COLUMN_JOB_DESC", "C")
COLUMN_MUST_HAVES = os.environ.get("COLUMN_MUST_HAVES", "D")
COLUMN_QUESTIONS = os.environ.get("COLUMN_QUESTIONS", "G")
COLUMN_FORM_LINK = os.environ.get("COLUMN_FORM_LINK", "H")
GOOGLE_SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
GOOGLE_CREDS_PATH = os.environ.get("GOOGLE_CREDS_PATH", "creds.json")

# OpenAI
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Typeform
TYPEFORM_API_KEY = os.environ.get("TYPEFORM_API_KEY")

# Redirects
REDIRECT_URL = os.environ.get("REDIRECT_URL", "https://your-gcf-url")

# Прочее
ROW_ID = os.environ.get("ROW_ID", "2") 