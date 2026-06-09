import warnings

import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st


PLOT_COLUMNS = ["Age", "ScreenTimeHours", "rr", "bt", "lm", "bo", "rem", "sh", "hr", "sl"]


def app(df, X, y):
    warnings.filterwarnings("ignore")
    st.title("Visualise the Stress Level")

    numeric_columns = [col for col in PLOT_COLUMNS if col in df.columns]
    plot_df = df[numeric_columns].copy()

    if st.checkbox("Show the correlation heatmap"):
        st.subheader("Correlation Heatmap")
        fig, ax = plt.subplots(figsize=(12, 7))
        sns.heatmap(plot_df.corr(), annot=True, fmt=".2f", cmap="coolwarm", ax=ax)
        st.pyplot(fig, clear_figure=True)

    if st.checkbox("Show Scatter Plot"):
        figure, axis = plt.subplots(2, 2, figsize=(15, 10))
        sns.scatterplot(ax=axis[0, 0], data=df, x="Age", y="ScreenTimeHours", hue="sl", palette="viridis", legend=False)
        axis[0, 0].set_title("Age vs Screen Time")

        sns.scatterplot(ax=axis[0, 1], data=df, x="rr", y="bt", hue="sl", palette="viridis", legend=False)
        axis[0, 1].set_title("Respiration vs Body Temperature")

        sns.scatterplot(ax=axis[1, 0], data=df, x="bo", y="hr", hue="sl", palette="viridis", legend=False)
        axis[1, 0].set_title("Blood O₂ vs Heart Rate")

        sns.scatterplot(ax=axis[1, 1], data=df, x="sh", y="rem", hue="sl", palette="viridis")
        axis[1, 1].set_title("Sleep Hours vs REM Sleep")

        figure.tight_layout()
        st.pyplot(figure, clear_figure=True)

    if st.checkbox("Display Boxplot"):
        fig, ax = plt.subplots(figsize=(15, 5))
        df[[col for col in ["Age", "ScreenTimeHours", "rr", "bt", "lm", "bo", "rem", "sh", "hr"] if col in df.columns]].boxplot(ax=ax)
        ax.set_title("Feature Distribution")
        ax.tick_params(axis="x", rotation=45)
        st.pyplot(fig, clear_figure=True)

    if st.checkbox("Show Sample Results"):
        fig, ax = plt.subplots(figsize=(8, 5))
        counts = df["sl"].value_counts().sort_index()
        labels = ["Safe", "Low", "Medium", "High", "Very High"]
        sns.barplot(x=labels[: len(counts)], y=counts.values, palette="pastel", ax=ax)
        ax.set_title("Stress Level Distribution")
        ax.set_xlabel("Stress Class")
        ax.set_ylabel("Count")
        for i, value in enumerate(counts.values):
            ax.text(i, value + max(counts.values) * 0.01, str(value), ha="center")
        st.pyplot(fig, clear_figure=True)
