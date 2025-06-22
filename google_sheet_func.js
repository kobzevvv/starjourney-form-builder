function runHRPipelineUniversal() {
    var ui = SpreadsheetApp.getUi();
    var response = ui.prompt(
      'Введите параметры через запятую:',
      'job_cell, prompt_questions_cell, prompt_typeform_cell, output_cell\nПример: C4,B7,B6,H4',
      ui.ButtonSet.OK_CANCEL
    );
    if (response.getSelectedButton() != ui.Button.OK) {
      ui.alert('Отмена.');
      return;
    }
    var parts = response.getResponseText().split(',');
    if (parts.length < 4) {
      ui.alert('Ошибка: нужно 4 параметра!');
      return;
    }
    var jobCell = parts[0].trim();
    var promptQuestionsCell = parts[1].trim();
    var promptTypeformCell = parts[2].trim();
    var outputCell = parts[3].trim();
    var promptSheet = 'gpt instruction'; // теперь всегда по умолчанию

    // Подставьте свой URL ниже!
    var url = "https://REGION-PROJECT.cloudfunctions.net/hr_auto_entrypoint/run-for-cell"
      + "?cell=" + jobCell
      + "&prompt_questions_cell=" + promptQuestionsCell
      + "&prompt_typeform_cell=" + promptTypeformCell
      + "&prompt_sheet=" + encodeURIComponent(promptSheet);

    var options = {
      "method": "post",
      "muteHttpExceptions": true
    };
    try {
      var response = UrlFetchApp.fetch(url, options);
      var json = JSON.parse(response.getContentText());
      var formUrl = json.form_url;
      if (!formUrl) {
        ui.alert('Ошибка: ссылка на форму не получена!\n' + response.getContentText());
        return;
      }
      var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      sheet.getRange(outputCell).setValue(formUrl);
      ui.alert('Ссылка успешно вставлена в ' + outputCell + ':\n' + formUrl);
    } catch (e) {
      ui.alert('Ошибка при выполнении запроса:\n' + e);
    }
  }