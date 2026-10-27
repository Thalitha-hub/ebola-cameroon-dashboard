import json
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Project folder and outbreak data files
BASE_DIR = Path(__file__).resolve().parent

COUNTS_FILE = BASE_DIR / "counts.tsv"
CASES_FILE = BASE_DIR / "cases.tsv"
SOURCES_FILE = BASE_DIR / "sources.tsv"

@st.cache_data
def load_tsv(file_path):
    return pd.read_csv(file_path, sep="\t", comment="#", dtype=str)

# Load files only when they exist
counts_df = load_tsv(COUNTS_FILE) if COUNTS_FILE.exists() else pd.DataFrame()
cases_df = load_tsv(CASES_FILE) if CASES_FILE.exists() else pd.DataFrame()
sources_df = load_tsv(SOURCES_FILE) if SOURCES_FILE.exists() else pd.DataFrame()

BASE = Path(__file__).parent
st.set_page_config(page_title="Ebola Monitoring Cameroon Focus", layout="wide")
st.title("Ebola Monitoring  Cameroon Focus")
st.caption("Source-data review dashboard | DRC surveillance observations and Cameroon geography are kept separate.")

data_path = BASE / "drc_sitrep_counts_reviewed.csv"
geo_path = BASE / "cameroon_health_districts.geojson"
qa_path = BASE / "data_quality_report.json"
readiness_path = BASE / "cameroon_district_readiness.csv"

df = pd.read_csv(data_path)
with open(qa_path, encoding="utf-8") as f:
    qa = json.load(f)




# International outbreak surveillance
st.header("International Outbreak Surveillance")

if not counts_df.empty:
    st.caption(
        "Reported figures outside the DRC, as recorded in the source exports. "
        "Blank values mean not reported, not zero."
    )

    # Convert numeric columns while preserving missing values
    numeric_columns = [
        "confirmed", "probable", "deaths", "imported",
        "imported_from_drc", "linked", "under_investigation"
    ]

    for column in numeric_columns:
        if column in counts_df.columns:
            counts_df[column] = pd.to_numeric(
                counts_df[column], errors="coerce"
            )

    countries = sorted(counts_df["country"].dropna().unique().tolist())
    selected_country = st.selectbox(
        "Select a country", ["All countries"] + countries
    )

    view = counts_df.copy()
    if selected_country != "All countries":
        view = view[view["country"] == selected_country]

    view["as_of"] = pd.to_datetime(view["as_of"], errors="coerce")
    view = view.sort_values("as_of")

    # Display the latest reported row per country
    latest = (
        view.dropna(subset=["as_of"])
        .sort_values("as_of")
        .groupby("country", as_index=False)
        .tail(1)
    )

    st.subheader("Latest available reports")
    st.dataframe(latest, use_container_width=True, hide_index=True)

    if selected_country != "All countries":
        st.subheader(f"Reported confirmed cases — {selected_country}")
        trend = view.dropna(subset=["as_of", "confirmed"])
        if not trend.empty:
            st.line_chart(
                trend.set_index("as_of")["confirmed"]
            )
        else:
            st.info("No confirmed-case values are available for this selection.")

    st.subheader("Source notes")
    if "source_id" in view.columns and "source_id" in sources_df.columns:
        source_view = view.merge(
            sources_df[["source_id", "publisher", "title", "url"]],
            on="source_id",
            how="left"
        )
        st.dataframe(
            source_view[[
                c for c in [
                    "country", "as_of", "confirmed", "probable",
                    "deaths", "source_id", "publisher", "title", "url"
                ] if c in source_view.columns
            ]],
            use_container_width=True,
            hide_index=True
        )
else:
    st.warning(
        "The counts.tsv file was not found or contains no data. "
        "Check that it is in the same folder as app.py."
    )




st.warning("This is not a validated forecast and does not estimate Ebola risk or cases in Cameroon. DRC observations must not be interpreted as Cameroon cases.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DRC source rows", f"{qa['source_rows']:,}")
c2.metric("Situation-report files", qa["distinct_sitrep_sources"])
c3.metric("Aggregate rows", qa["aggregate_rows"])
c4.metric("Cameroon district features", qa["geojson_district_features"])

st.subheader("1. Inspect DRC situation-report data")
report_list = sorted(df["sitrep_source"].dropna().unique().tolist())
chosen_report = st.selectbox("Situation report", report_list, index=len(report_list)-1)
report_df = df[df["sitrep_source"] == chosen_report].copy()
count_type = st.selectbox("Count type", ["All", "Nouveaux", "Cumules"])
if count_type != "All":
    report_df = report_df[report_df["count_type"] == count_type]
row_type = st.radio("Rows to display", ["All rows", "Location-level only", "Aggregate only"], horizontal=True)
if row_type == "Location-level only":
    report_df = report_df[~report_df["is_aggregate"].astype(bool)]
elif row_type == "Aggregate only":
    report_df = report_df[report_df["is_aggregate"].astype(bool)]

st.caption("Do not add aggregate rows to location-level rows. 'Cumules' means cumulative; 'Nouveaux' means new. Blank values are not zero.")
cols = ["count_start_date_iso", "count_end_date_iso", "count_type", "province", "zone",
        "cases_suspect", "cases_probable", "cases_confirmed", "deaths_suspected",
        "deaths_probable", "deaths_confirmed", "contacts", "is_aggregate", "quality_flags"]
available = [c for c in cols if c in report_df.columns]
st.dataframe(report_df[available], use_container_width=True, hide_index=True)
st.download_button("Download filtered rows as CSV", report_df.to_csv(index=False).encode("utf-8"),
                   file_name="filtered_drc_sitrep_rows.csv", mime="text/csv")

st.subheader("2. Data-quality checks")
quality = pd.DataFrame({
    "Check": ["Missing start date", "Missing confirmed-case value", "Missing zone", "Missing province", "Missing contacts"],
    "Rows": [qa["start_date_missing_rows"], qa["confirmed_case_missing_rows"], qa["zone_missing_rows"],
             qa["province_missing_rows"], qa["contacts_missing_rows"]]
})
fig = px.bar(quality, x="Check", y="Rows", title="Missing values in source file")
st.plotly_chart(fig, use_container_width=True)
st.json(qa["critical_caveats"])


st.subheader("3. Cameroon health-district geography")

with open(geo_path, encoding="utf-8") as f:
    gj = json.load(f)

districts = pd.DataFrame([
    feat["properties"]
    for feat in gj["features"]
])

# Keep only actual health-district features
districts = districts.dropna(subset=["area_id", "area_name"])
districts = districts.drop_duplicates(subset=["area_id"])

st.write(
    f"Loaded {len(districts)} health-district records "
    "from the supplied GeoJSON."
)

st.info(
    "Geography only: this map does not display confirmed cases, "
    "outbreak probabilities, or district risk scores."
)

# Draw district boundaries using the GeoJSON feature IDs
fig = go.Figure(
    go.Choropleth(
        geojson=gj,
        locations=districts["area_id"],
        z=[1] * len(districts),
        featureidkey="properties.area_id",
        colorscale=[
            [0, "#e5edf5"],
            [1, "#e5edf5"]
        ],
        showscale=False,
        marker_line_color="#526779",
        marker_line_width=0.6,
        customdata=districts[
            ["area_name", "parent_area_id"]
        ].fillna("").values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Parent area: %{customdata[1]}<br>"
            "<extra></extra>"
        )
    )
)

fig.update_geos(
    fitbounds="locations",
    visible=False,
    projection_type="mercator"
)

fig.update_layout(
    height=650,
    margin=dict(l=0, r=0, t=10, b=0),
    paper_bgcolor="white"
)

st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Select or hover over a district to inspect its name. "
    "Boundaries must be verified against current official "
    "health-administration data before operational use."
)

st.subheader("District reference table")

table_cols = [
    "area_id", "area_name", "parent_area_id",
    "center_x", "center_y"
]
available_cols = [
    col for col in table_cols if col in districts.columns
]

st.dataframe(
    districts[available_cols],
    use_container_width=True,
    hide_index=True
)





st.subheader("4. District geography quality checks")

total_districts = len(districts)

duplicate_ids = int(
    districts["area_id"].duplicated().sum()
)

missing_names = int(
    districts["area_name"].isna().sum()
)

if "center_x" in districts.columns:
    missing_longitudes = int(
        districts["center_x"].isna().sum()
    )
else:
    missing_longitudes = total_districts

if "center_y" in districts.columns:
    missing_latitudes = int(
        districts["center_y"].isna().sum()
    )
else:
    missing_latitudes = total_districts

col1, col2, col3, col4 = st.columns(4)

col1.metric("District records", total_districts)
col2.metric("Duplicate IDs", duplicate_ids)
col3.metric("Missing names", missing_names)
col4.metric(
    "Missing coordinates",
    missing_longitudes + missing_latitudes
)

if duplicate_ids == 0 and missing_names == 0:
    st.success(
        "No duplicate district IDs or missing district names "
        "were detected in the displayed reference table."
    )
else:
    st.warning(
        "Please review the district reference table for "
        "duplicate IDs or missing names."
    )

if missing_longitudes or missing_latitudes:
    st.warning(
        "Some district coordinates are missing or their "
        "coordinate columns are unavailable. Check the source data."
    )

st.caption(
    "These checks assess basic data completeness only. "
    "They do not establish that the district boundaries or "
    "coordinates are geographically correct."
)




st.subheader("5. Cameroon preparedness data readiness")

st.write(
    "Use the 197-district reference table as our temporary working geography. "
    "Upload a CSV containing verified district-level information when available."
)

readiness = districts[
    ["area_id", "area_name", "parent_area_id"]
].copy()

required_fields = {
    "cameroon_case_surveillance": "Cameroon case surveillance",
    "population": "District population",
    "travel_connectivity": "Travel and cross-border connectivity",
    "health_service_capacity": "Health-service capacity",
    "environmental_data": "Environmental data",
}

# Create an empty template with one row per district.
for field in required_fields:
    readiness[field] = pd.NA


# Load previously saved data when the app starts.
if readiness_path.exists():
    try:
        saved = pd.read_csv(
            readiness_path,
            dtype={"area_id": str},
        )

        current_ids = readiness["area_id"].astype(str)
        saved["area_id"] = saved["area_id"].astype(str)

        if (
            "area_id" in saved.columns
            and not saved["area_id"].duplicated().any()
        ):
            saved_fields = [
                field for field in required_fields
                if field in saved.columns
            ]

            if saved_fields:
                saved = saved[
                    ["area_id"] + saved_fields
                ]

                readiness["area_id"] = current_ids

                readiness = readiness.drop(
                    columns=saved_fields,
                    errors="ignore",
                ).merge(
                    saved,
                    on="area_id",
                    how="left",
                    validate="one_to_one",
                )

    except (OSError, ValueError, pd.errors.ParserError) as exc:
        st.warning(
            f"Saved district data could not be loaded: {exc}"
        )

st.download_button(
    "Download blank district data template",
    readiness.to_csv(index=False).encode("utf-8"),
    file_name="cameroon_district_data_template.csv",
    mime="text/csv",
)

st.markdown("**Upload verified district data**")
st.caption(
    "Your CSV must contain an area_id column matching the IDs in the "
    "district reference table. You can include any of the indicator "
    "columns in the template. Leave unknown values blank."
)

uploaded_data = st.file_uploader(
    "Choose a district data CSV",
    type=["csv"],
    key="district_readiness_upload",
)

if uploaded_data is not None:
    try:
        uploaded_df = pd.read_csv(uploaded_data)

        if "area_id" not in uploaded_df.columns:
            st.error(
                "The CSV must contain an area_id column. "
                "Download the template above and use its district IDs."
            )
        elif uploaded_df["area_id"].isna().any():
            st.error(
                "Some rows have a blank area_id. Please correct the CSV."
            )
        elif uploaded_df["area_id"].duplicated().any():
            st.error(
                "The CSV contains duplicate area_id values. "
                "Please keep one row per district."
            )
        else:
            uploaded_df["area_id"] = uploaded_df["area_id"].astype(str)
            readiness["area_id"] = readiness["area_id"].astype(str)

            unknown_ids = uploaded_df[
                ~uploaded_df["area_id"].isin(readiness["area_id"])
            ]
            matched = uploaded_df[
                uploaded_df["area_id"].isin(readiness["area_id"])
            ]

            usable_fields = [
                field for field in required_fields
                if field in uploaded_df.columns
            ]

            if not usable_fields:
                st.warning(
                    "The file contains district IDs but none of the "
                    "expected indicator columns. Use the template "
                    "column names to link indicator data."
                )
            else:
                matched_data = matched[
                    ["area_id"] + usable_fields
                ].copy()

                readiness = readiness.drop(
                    columns=usable_fields
                ).merge(
                    matched_data,
                    on="area_id",
                    how="left",
                    validate="one_to_one",
                )

                st.success(
                    f"Matched {len(matched)} uploaded district rows "
                    f"to the reference geography."
                )

                if not unknown_ids.empty:
                    st.warning(
                        f"{len(unknown_ids)} uploaded rows have IDs "
                        "that do not match the current 197-district "
                        "reference table."
                    )
                    st.dataframe(
                        unknown_ids,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.caption(
                    "Coverage measures non-missing entries only. "
                    "It does not measure data accuracy or Ebola risk."
                )

    except Exception as exc:
        st.error(
            f"Could not read this CSV: {exc}. "
            "Please check that it is a valid CSV file."
        )




st.markdown("**District readiness table — editable**")

edited_readiness = st.data_editor(
    readiness,
    disabled=["area_id", "area_name", "parent_area_id"],
    num_rows="fixed",
    hide_index=True,
    use_container_width=True,
    height=400,
    key="district_readiness_editor",
    column_config={
        "population": st.column_config.NumberColumn(
            "District population",
            min_value=0,
            step=1,
            format="%d",
        ),
    },
)


# Calculate coverage AFTER the editable table exists.
coverage_rows = []

for field, label in required_fields.items():
    available_count = (
        int(edited_readiness[field].notna().sum())
        if field in edited_readiness.columns
        else 0
    )

    total = len(edited_readiness)

    coverage_rows.append({
        "Indicator": label,
        "Districts with data": available_count,
        "Districts missing data": total - available_count,
        "Coverage (%)": round(
            100 * available_count / total, 1
        ) if total else 0,
    })

coverage = pd.DataFrame(coverage_rows)

st.markdown("**Data coverage**")
st.dataframe(
    coverage,
    use_container_width=True,
    hide_index=True,
)

st.download_button(
    "Export edited district table",
    edited_readiness.to_csv(index=False).encode("utf-8"),
    file_name="cameroon_district_readiness_edited.csv",
    mime="text/csv",
    key="export_edited_readiness",
)

if st.button("Save district data on this computer"):
    try:
        edited_readiness.to_csv(
            readiness_path,
            index=False,
        )
        st.success(
            "District data saved to cameroon_district_readiness.csv."
        )
    except OSError as exc:
        st.error(f"Could not save district data: {exc}")

st.caption(
    "Saving writes to the application's local folder. "
    "Keep exported backups of important data. Missing values do not "
    "mean zero population, absent health services, or zero Ebola cases."
)


# ---------------------------------------------------------------------
# 6. Cameroon risk scenario explorer (NOT a validated forecast)
# ---------------------------------------------------------------------
st.subheader("6. Cameroon Ebola risk scenario explorer")
st.warning(
    "Prototype only: this tool does not calculate a validated current risk for Cameroon. "
    "The scenario probability below is driven by assumptions entered by the user, not by "
    "a trained model or verified Cameroon case data. Do not use it for public-health decisions."
)

st.markdown(
    "Use this section to demonstrate how an introduction scenario and district exposure "
    "could affect a hypothetical 14-day risk estimate. Replace the assumptions with "
    "official, dated evidence before interpreting the result."
)

with st.expander("Set scenario assumptions", expanded=True):
    baseline_pct = st.slider(
        "Assumed probability of Ebola being introduced into Cameroon over the next 14 days (%)",
        min_value=0.0,
        max_value=100.0,
        value=1.0,
        step=0.5,
        help="Illustrative assumption only. This is NOT an observed or model-estimated Cameroon probability."
    )
    st.caption(
        "The default of 1% is only a demonstration value, not an estimate of Cameroon's actual risk. "
        "Change it only when you have a documented basis for the scenario."
    )
    exposure_multiplier = st.slider(
        "Illustrative district exposure multiplier",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.1,
        help="Scenario multiplier for connectivity/exposure; not calculated from verified district data."
    )
    transmission_multiplier = st.slider(
        "Illustrative local-transmission multiplier",
        min_value=0.5,
        max_value=3.0,
        value=1.0,
        step=0.1,
        help="Scenario multiplier for the possibility of onward transmission; not a validated parameter."
    )

# Convert a baseline probability to an equivalent hazard, scale it by scenario
# multipliers, then convert it back to a probability. This is only a transparent
# mathematical scenario, not an epidemiologically fitted model.
baseline_probability = baseline_pct / 100.0
if baseline_probability >= 1.0:
    scenario_probability = 1.0
elif baseline_probability <= 0.0:
    scenario_probability = 0.0
else:
    hazard = -__import__("math").log(1.0 - baseline_probability)
    scenario_probability = 1.0 - __import__("math").exp(
        -hazard * exposure_multiplier * transmission_multiplier
    )

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("Assumed 14-day introduction probability", f"{baseline_pct:.1f}%")
metric_col2.metric("Combined scenario multiplier", f"{exposure_multiplier * transmission_multiplier:.2f}×")
metric_col3.metric("Illustrative district scenario probability", f"{scenario_probability * 100:.2f}%")

st.caption(
    "Interpretation: the final figure is a what-if calculation derived from the assumptions above. "
    "It is not the probability that Ebola will occur in any named Cameroon district."
)

scenario_df = pd.DataFrame({
    "Scenario": ["Assumed introduction probability", "Illustrative district scenario"],
    "Probability (%)": [baseline_pct, scenario_probability * 100.0],
})
scenario_fig = px.bar(
    scenario_df,
    x="Scenario",
    y="Probability (%)",
    range_y=[0, 100],
    title="Illustrative scenario comparison (assumptions, not forecast)",
    text_auto=".2f",
)
st.plotly_chart(scenario_fig, use_container_width=True)

st.markdown("**What is needed for a genuine transfer-learning forecast?**")
st.write(
    "A harmonized historical dataset with dates, outbreak locations, case counts, virus species, "
    "and suitable predictors; a documented mapping between source locations and Cameroon districts; "
    "and temporal or outbreak-level validation. The model should then estimate the chance of at least "
    "one confirmed case in the next 14 days and expected cases over the next 7 days. Until those steps "
    "are completed, this dashboard should report scenario outputs or relative indicators—not a "
    "validated Cameroon outbreak probability."
)



# ============================================================
# CAMEROON DISTRICT PREPAREDNESS PRIORITIZATION
# This is NOT a validated Ebola outbreak probability.
# ============================================================
st.header("Cameroon District Preparedness Prioritization")

st.info(
    "This section supports preparedness planning. Scores are indicators "
    "for prioritization only, not probabilities of an Ebola outbreak."
)

from pathlib import Path

readiness_file = Path(__file__).resolve().parent / "cameroon_district_readiness.csv"

if readiness_file.exists():
    readiness = pd.read_csv(readiness_file)
elif "edited_readiness" in globals() and isinstance(edited_readiness, pd.DataFrame):
    readiness = edited_readiness.copy()
elif "readiness_df" in globals() and isinstance(readiness_df, pd.DataFrame):
    readiness = readiness_df.copy()
else:
    readiness = pd.DataFrame()

if not readiness.empty:
    st.caption("Review the available district information and update it using verified local data.")

    edited_priority = st.data_editor(
        readiness,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        key="cameroon_priority_editor"
    )

    st.download_button(
        "Download updated Cameroon readiness data",
        data=edited_priority.to_csv(index=False).encode("utf-8"),
        file_name="cameroon_district_readiness_updated.csv",
        mime="text/csv"
    )

    st.subheader("Data completeness")
    completeness = (
        edited_priority.notna().mean().mul(100).round(1)
        .rename("Completeness (%)")
        .to_frame()
    )
    st.dataframe(completeness, use_container_width=True)

else:
    st.warning(
        "The Cameroon readiness CSV was not found. Place "
        "'cameroon_district_readiness.csv' beside app.py, or connect "
        "the readiness table already used in your app."
    )