# Journal Lookup & Compare Tool

This Streamlit app recreates the Excel workbook as an online journal search, comparison, and recommendation tool.

## Features

- Search journals by keyword, subject area, content tags, publisher, publishing model, and minimum Impact Factor
- Sort by Impact Factor, 5-year Impact Factor, H5-index, or journal name
- Compare up to five journals side by side
- Recommend journals from paper topics or keywords
- Download filtered search results as CSV
- Review or replace the source journal data

## Project structure

```text
journal_tool/
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── journals.csv
```

## Run locally

```bash
cd journal_tool
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Updating journal data

The app reads from `data/journals.csv`. To update the data, replace that file with a CSV containing these columns from the workbook:

- Journal
- IF (JCR year 2024)
- IF (5 yr)
- H5-index
- Publisher
- Publishing Model
- Subject Area (tags)
- Aims & Scope
- Content Tags

## Deployment options

Good first deployment targets:

- Streamlit Community Cloud
- Render
- Azure App Service
- Internal server/container

For a production internal tool, consider adding login, edit permissions, and a database such as PostgreSQL.
