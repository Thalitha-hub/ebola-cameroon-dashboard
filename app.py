import json
from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

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