# Paster

`Paster` is a local WhatsApp-to-report helper for your connections workflow.

It is built for the pattern in your screenshots:

- morning or assignment posts with account, client name, phone, route, and location
- completion posts with `GPON INSTALL`, account, signals, cable lengths, ATB, patch cord, and field remarks

The app does four practical things:

1. Parses pasted or exported WhatsApp text into structured ticket data.
2. Watches one WhatsApp group through WhatsApp Web automation and stores messages locally.
3. Fills a connections workbook using your `sample.xlsx` layout.
4. Updates the daily summary workbook using your `Mon,,Wed,Friday Reports.xlsx` layout.

Image OCR is optional. The code includes a hook for `pytesseract`. The project now supports an unofficial WhatsApp Web watcher for a single group. This is practical, but it is not the official Meta API path, so expect occasional breakage if WhatsApp changes the web app.

The workflow is:

1. Start the WhatsApp watcher and scan the QR code.
2. Let it monitor one group and save messages plus media locally.
3. Open the Streamlit app and load the scraped capture or paste text manually.
4. Optionally OCR saved screenshots if Tesseract is installed.
5. Generate Excel output and, if needed later, sync to Google Sheets.

## Run

From `C:\Users\USER\OneDrive\Desktop\Mr\Schooll\paster`:

```powershell
streamlit run src/paster/app.py
```

The app opens in your browser, usually at `http://localhost:8501`.

## WhatsApp Watcher

Install Node dependencies once:

```powershell
npm install
```

Start the watcher for one group:

```powershell
npm run watch -- --group "COMCRAFT-SAVANNA CONNECTIONS & SUPPORT"
```

What happens:

- a Chromium session opens through WhatsApp Web
- a QR code appears in the terminal on first login
- the watcher stores chat messages in `data/messages.jsonl`
- downloaded images are stored in `data/media`
- watcher status is written to `data/status.json`

Useful endpoints while it runs:

- `http://localhost:3001/status`
- `http://localhost:3001/messages`

## Templates

The UI starts with these defaults:

- `C:\Users\USER\Downloads\sample.xlsx`
- `C:\Users\USER\Downloads\Mon,,Wed,Friday Reports.xlsx`

The generated files are written to:

- `C:\Users\USER\OneDrive\Desktop\Mr\Schooll\paster\outputs`

## Google Sheets

Google Sheets writing is optional.

To use it later:

1. Create a Google service account.
2. Share the target sheet with that service account email.
3. Download the credentials JSON.
4. Enter the credentials path and spreadsheet ID in the app.

For live tracking, the app syncs to dated tabs:

- `Connections YYYY-MM-DD`
- `Summary YYYY-MM-DD`

You can also run the realtime sync worker:

```powershell
python -m paster.realtime_sync --credentials "C:\path\service-account.json" --spreadsheet-id "your-sheet-id" --capture "C:\Users\USER\OneDrive\Desktop\Mr\Schooll\paster\data\messages.jsonl" --interval-seconds 60 --status-file "C:\Users\USER\OneDrive\Desktop\Mr\Schooll\paster\data\google-sync-status.json"
```

## Notes

- The parser is heuristic, because WhatsApp posts are not perfectly uniform.
- Formula columns in the Excel template are preserved by copying the previous row's formulas into new rows.
- Summary categories are driven by keyword matching and can be tuned easily in the parser if your team uses slightly different wording.
- WhatsApp group scraping in this project is based on WhatsApp Web automation, not an official normal-group ingestion API.
