### Elsevier Scopus Fetcher

Fetch article metadata for journals (by ISSN) from the Elsevier Scopus API and optionally fetch basic author details (incl. h-index).

### Purpose
- main.py: Fetches articles from Scopus for journals in `journals.json`, writing per-journal CSVs and a combined `articles/all_articles.csv`. Run this first, as `authors.py` depends on its output.
- authors.py: Reads `articles/all_articles.csv` produced by `main.py`, extracts unique author IDs, fetches author profiles, and writes them to `articles/authors.csv`.

### Prerequisites
- Python 3.8+
- Elsevier API key (required)
- Optional institutional token

### Install
```bash
python3 -m pip install -r requirements.txt
```
(Optional virtual env)
```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Credentials
Ensure `credentials.json` exists in the project root with keys (you already have this file):
```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "inst_token": "YOUR_INSTITUTION_TOKEN_HERE",
  "test_mode": false
}
```

### Journals list
Add required journals to `journals.json` ensuring that the ISSN matches the required journal:
```json
{
  "journals": [
        {
            "name": "Marketing Science",
            "issn": "0732-2399"
        }  
    ]
}
```

### Run
```bash
python3 main.py      # fetch articles -> articles/*.csv and articles/all_articles.csv
python3 authors.py   # fetch author details -> articles/authors.csv
```

### Notes
- API keys are required. On 401/Unauthorized, the scripts will print/log the error and exit.
- Logs are written to `article_fetch.log`