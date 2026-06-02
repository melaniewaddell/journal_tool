from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "journals.csv"
APP_TITLE = "Journal Lookup & Compare Tool"

COLUMN_ALIASES = {
    "Journal": "journal",
    "IF (JCR year 2024)": "impact_factor",
    "IF (5 yr)": "five_year_if",
    "H5-index": "h5_index",
    "Publisher": "publisher",
    "Publishing Model": "publishing_model",
    "Subject Area (tags)": "subject_tags",
    "Aims & Scope": "aims_scope",
    "Content Tags": "content_tags",
}
DISPLAY_COLUMNS = [
    "journal",
    "impact_factor",
    "five_year_if",
    "h5_index",
    "publisher",
    "publishing_model",
    "subject_tags",
    "content_tags",
]
DISPLAY_LABELS = {
    "journal": "Journal",
    "impact_factor": "Impact Factor",
    "five_year_if": "5-Year IF",
    "h5_index": "H5-index",
    "publisher": "Publisher",
    "publishing_model": "Publishing Model",
    "subject_tags": "Subject Area / Tags",
    "content_tags": "Content Tags",
    "aims_scope": "Aims & Scope",
}


def split_tags(value: object) -> list[str]:
    """Split comma/semicolon/pipe separated tags into normalized labels."""
    if pd.isna(value) or value is None:
        return []
    parts = re.split(r"[,;|]", str(value))
    return sorted({p.strip() for p in parts if p and p.strip()})


def normalize_text(value: object) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip().lower()


def contains_any(text: object, selected: Iterable[str]) -> bool:
    haystack = normalize_text(text)
    return any(normalize_text(term) in haystack for term in selected)


@st.cache_data(show_spinner=False)
def load_data(path: Path = DATA_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})

    # Drop fully empty rows and unnamed Excel export leftovers.
    df = df.dropna(how="all")
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]

    for col in ["impact_factor", "five_year_if", "h5_index"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["journal", "publisher", "publishing_model", "subject_tags", "content_tags", "aims_scope"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()

    df = df[df["journal"].astype(str).str.strip().ne("")].copy()
    df = df.sort_values("journal", kind="stable").reset_index(drop=True)
    return df


def metric_format(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    visible = df.rename(columns=DISPLAY_LABELS)
    fmt = {}
    for label in ["Impact Factor", "5-Year IF"]:
        if label in visible.columns:
            fmt[label] = "{:.1f}"
    if "H5-index" in visible.columns:
        fmt["H5-index"] = "{:.0f}"
    return visible.style.format(fmt, na_rep="")


def sidebar_filters(df: pd.DataFrame) -> dict[str, object]:
    st.sidebar.header("Filters")

    subject_options = sorted({tag for value in df["subject_tags"] for tag in split_tags(value)})
    content_options = sorted({tag for value in df["content_tags"] for tag in split_tags(value)})
    publisher_options = sorted([x for x in df["publisher"].dropna().unique() if str(x).strip()])
    model_options = sorted([x for x in df["publishing_model"].dropna().unique() if str(x).strip()])

    filters = {
        "query": st.sidebar.text_input("Search journal, publisher, tag, or scope"),
        "subjects": st.sidebar.multiselect("Subject Area", subject_options),
        "content_tags": st.sidebar.multiselect("Content Tags", content_options),
        "publishers": st.sidebar.multiselect("Publisher", publisher_options),
        "models": st.sidebar.multiselect("Publishing Model", model_options),
        "min_if": st.sidebar.number_input("Minimum Impact Factor", min_value=0.0, value=0.0, step=0.5),
        "sort_by": st.sidebar.selectbox(
            "Sort Results",
            ["Impact Factor", "5-Year IF", "H5-index", "Journal A-Z"],
            index=0,
        ),
    }
    return filters


def apply_filters(df: pd.DataFrame, filters: dict[str, object]) -> pd.DataFrame:
    result = df.copy()
    query = normalize_text(filters.get("query", ""))
    if query:
        search_cols = ["journal", "publisher", "publishing_model", "subject_tags", "content_tags", "aims_scope"]
        mask = result[search_cols].apply(lambda row: query in normalize_text(" ".join(row.astype(str))), axis=1)
        result = result[mask]

    if filters.get("subjects"):
        result = result[result["subject_tags"].apply(lambda x: contains_any(x, filters["subjects"]))]
    if filters.get("content_tags"):
        result = result[result["content_tags"].apply(lambda x: contains_any(x, filters["content_tags"]))]
    if filters.get("publishers"):
        result = result[result["publisher"].isin(filters["publishers"])]
    if filters.get("models"):
        result = result[result["publishing_model"].isin(filters["models"])]
    if filters.get("min_if", 0) > 0:
        result = result[result["impact_factor"].fillna(0) >= float(filters["min_if"])]

    sort_map = {
        "Impact Factor": ("impact_factor", False),
        "5-Year IF": ("five_year_if", False),
        "H5-index": ("h5_index", False),
        "Journal A-Z": ("journal", True),
    }
    sort_col, ascending = sort_map.get(str(filters.get("sort_by")), ("journal", True))
    return result.sort_values(sort_col, ascending=ascending, na_position="last", kind="stable")


def render_search(df: pd.DataFrame) -> None:
    st.subheader("Search Journals")
    filters = sidebar_filters(df)
    results = apply_filters(df, filters)

    col1, col2, col3 = st.columns(3)
    col1.metric("Matching journals", len(results))
    col2.metric("Median IF", f"{results['impact_factor'].median():.1f}" if len(results) else "—")
    col3.metric("Median H5", f"{results['h5_index'].median():.0f}" if len(results) else "—")

    st.dataframe(
        metric_format(results[DISPLAY_COLUMNS]),
        use_container_width=True,
        hide_index=True,
    )

    csv = results[DISPLAY_COLUMNS].rename(columns=DISPLAY_LABELS).to_csv(index=False).encode("utf-8")
    st.download_button("Download filtered results as CSV", csv, "journal_search_results.csv", "text/csv")

    with st.expander("View journal details"):
        selected = st.selectbox("Choose a journal", results["journal"].tolist() if len(results) else [])
        if selected:
            row = results.loc[results["journal"] == selected].iloc[0]
            st.markdown(f"### {row['journal']}")
            st.write(f"**Publisher:** {row['publisher'] or 'Not listed'}")
            st.write(f"**Publishing Model:** {row['publishing_model'] or 'Not listed'}")
            st.write(f"**Impact Factor:** {row['impact_factor'] if pd.notna(row['impact_factor']) else 'Not listed'}")
            st.write(f"**5-Year IF:** {row['five_year_if'] if pd.notna(row['five_year_if']) else 'Not listed'}")
            st.write(f"**H5-index:** {row['h5_index'] if pd.notna(row['h5_index']) else 'Not listed'}")
            st.write(f"**Subject Area / Tags:** {row['subject_tags'] or 'Not listed'}")
            st.write(f"**Content Tags:** {row['content_tags'] or 'Not listed'}")
            if row["aims_scope"]:
                st.write("**Aims & Scope / Link:**")
                st.write(row["aims_scope"])


def render_compare(df: pd.DataFrame) -> None:
    st.subheader("Compare Journals")
    selected = st.multiselect(
        "Choose up to 5 journals",
        df["journal"].tolist(),
        max_selections=5,
    )
    if not selected:
        st.info("Select journals above to compare their metrics side by side.")
        return

    compare = df[df["journal"].isin(selected)].copy()
    compare["journal"] = pd.Categorical(compare["journal"], categories=selected, ordered=True)
    compare = compare.sort_values("journal")

    metrics = [
        ("Impact Factor", "impact_factor"),
        ("5-Year IF", "five_year_if"),
        ("H5-index", "h5_index"),
        ("Publisher", "publisher"),
        ("Publishing Model", "publishing_model"),
        ("Subject Area / Tags", "subject_tags"),
        ("Content Tags", "content_tags"),
    ]
    table = {"Metric": [name for name, _ in metrics]}
    for _, row in compare.iterrows():
        table[str(row["journal"])] = [row[col] for _, col in metrics]
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    chart_cols = ["journal", "impact_factor", "five_year_if", "h5_index"]
    chart_data = compare[chart_cols].set_index("journal")
    st.bar_chart(chart_data)


def score_recommendations(df: pd.DataFrame, terms: list[str]) -> pd.DataFrame:
    scored = df.copy()
    if not terms:
        scored["match_score"] = 0
        return scored

    def score_row(row: pd.Series) -> int:
        searchable = " ".join(
            normalize_text(row.get(col, ""))
            for col in ["journal", "publisher", "subject_tags", "content_tags", "aims_scope"]
        )
        return sum(1 for term in terms if normalize_text(term) in searchable)

    scored["match_score"] = scored.apply(score_row, axis=1)
    return scored.sort_values(["match_score", "impact_factor"], ascending=[False, False], na_position="last")


def render_recommend(df: pd.DataFrame) -> None:
    st.subheader("Recommend Journals by Topic")
    raw_terms = st.text_area(
        "Enter paper topics, methods, keywords, or subject phrases",
        placeholder="Example: infectious disease, public health, emergency management",
        height=120,
    )
    min_score = st.slider("Minimum matching keyword count", 1, 5, 1)
    terms = [t.strip() for t in re.split(r"[,\n;]", raw_terms) if t.strip()]

    if not terms:
        st.info("Enter one or more terms to generate recommendations.")
        return

    recommendations = score_recommendations(df, terms)
    recommendations = recommendations[recommendations["match_score"] >= min_score]
    st.write(f"Showing {len(recommendations)} recommended journals.")
    columns = ["journal", "match_score", "impact_factor", "five_year_if", "h5_index", "publisher", "subject_tags", "content_tags"]
    labels = {**DISPLAY_LABELS, "match_score": "Match Score"}
    st.dataframe(recommendations[columns].rename(columns=labels), use_container_width=True, hide_index=True)


def render_admin(df: pd.DataFrame) -> None:
    st.subheader("Data Admin")
    st.write("Use this page to review the source data and replace it with an updated CSV export if needed.")
    st.caption(f"Current data file: {DATA_PATH}")
    st.dataframe(metric_format(df[DISPLAY_COLUMNS]), use_container_width=True, hide_index=True)

    uploaded = st.file_uploader("Upload replacement journals CSV", type=["csv"])
    if uploaded is not None:
        try:
            new_df = pd.read_csv(uploaded)
            st.success("CSV loaded successfully. Preview below. To make it permanent, replace data/journals.csv in the project folder.")
            st.dataframe(new_df.head(25), use_container_width=True)
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="📚", layout="wide")
    st.title(APP_TITLE)
    st.caption("Online version of the Excel journal lookup and comparison workbook.")

    df = load_data()
    tab_search, tab_compare, tab_recommend, tab_admin = st.tabs([
        "Search",
        "Compare",
        "Recommend",
        "Admin / Data",
    ])

    with tab_search:
        render_search(df)
    with tab_compare:
        render_compare(df)
    with tab_recommend:
        render_recommend(df)
    with tab_admin:
        render_admin(df)


if __name__ == "__main__":
    main()
