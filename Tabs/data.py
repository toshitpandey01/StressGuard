import streamlit as st

COLUMN_DESCRIPTIONS = {
    "Age": "Age of the person",
    "ScreenTimeHours": "Daily screen time in hours",
    "rr": "Respiration rate",
    "bt": "Body temperature",
    "lm": "Limb movement",
    "bo": "Blood oxygen",
    "rem": "REM sleep duration",
    "sh": "Sleep hours",
    "hr": "Heart rate",
    "sl": "Stress level",
}


def app(df):
    st.title("Data Info page")
    st.subheader("Dataset column meaning")

    col1, col2 = st.columns(2)
    items = list(COLUMN_DESCRIPTIONS.items())
    left_items = items[:5]
    right_items = items[5:]

    with col1:
        st.markdown("\n".join([f"- **{col}** — {desc}" for col, desc in left_items]))
    with col2:
        st.markdown("\n".join([f"- **{col}** — {desc}" for col, desc in right_items]))

    st.subheader("View Data")
    with st.expander("View full data"):
        st.dataframe(df, use_container_width=True)

    st.subheader("Columns Description")
    if st.checkbox("View Summary"):
        st.dataframe(df.describe().T, use_container_width=True)

    col_name, col_dtype, col_data = st.columns(3)
    with col_name:
        if st.checkbox("Column Names"):
            st.dataframe(df.columns.to_frame(name="Column Name"), use_container_width=True)
    with col_dtype:
        if st.checkbox("Columns data types"):
            dtypes = df.dtypes.astype(str).reset_index()
            dtypes.columns = ["Column", "Data Type"]
            st.dataframe(dtypes, use_container_width=True)
    with col_data:
        if st.checkbox("Column Data"):
            col = st.selectbox("Column Name", list(df.columns))
            st.dataframe(df[[col]], use_container_width=True)

    if st.checkbox("Show Missing Values"):
        missing = df.isna().sum().reset_index()
        missing.columns = ["Column", "Missing Values"]
        st.dataframe(missing, use_container_width=True)
