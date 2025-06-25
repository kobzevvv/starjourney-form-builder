from googleapiclient.discovery import build
from google.oauth2 import service_account
from settings import (
    SHEET_NAME, COLUMN_JOB_DESC, COLUMN_MUST_HAVES, COLUMN_QUESTIONS, COLUMN_FORM_LINK,
    GOOGLE_SHEET_ID, GOOGLE_CREDS_PATH
)

def get_sheets_service():
    creds = service_account.Credentials.from_service_account_file(
        GOOGLE_CREDS_PATH,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

def read_row(row_id):
    sheet = get_sheets_service()
    ranges = [
        f"{SHEET_NAME}!{COLUMN_JOB_DESC}{row_id}:{COLUMN_MUST_HAVES}{row_id}"
    ]
    result = sheet.values().batchGet(spreadsheetId=GOOGLE_SHEET_ID, ranges=ranges).execute()
    values = result.get('valueRanges', [])
    job_desc = values[0]['values'][0][0] if len(values) > 0 and 'values' in values[0] else ''
    must_haves = values[0]['values'][0][1] if len(values) > 0 and 'values' in values[0] and len(values[0]['values'][0]) > 1 else ''
    return job_desc, must_haves

def write_to_cell(cell_range, value):
    """
    Записывает значение в указанную ячейку Google Sheets.
    cell_range: строка вида "G2" или "H2"
    value: значение для записи
    """
    sheet = get_sheets_service()
    range_name = f"{SHEET_NAME}!{cell_range}"
    body = {
        'values': [[value]]
    }
    result = sheet.values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()
    return result

def write_questions_to_sheet(row_id, questions_text):
    """
    Записывает вопросы формы в ячейку G{row_id}.
    """
    cell_range = f"{COLUMN_QUESTIONS}{row_id}"
    return write_to_cell(cell_range, questions_text)

def write_form_link_to_sheet(row_id, form_url):
    """
    Записывает ссылку на форму в ячейку H{row_id}.
    """
    cell_range = f"{COLUMN_FORM_LINK}{row_id}"
    return write_to_cell(cell_range, form_url)
