import os

import streamlit as st
from web_functions import predict

FEATURE_CONFIG = [
    ("Age", "Age", 1.0),
    ("ScreenTimeHours", "Screen Time Hours", 0.1),
    ("rr", "Respiration Rate", 0.1),
    ("bt", "Body Temperature (°F)", 0.1),
    ("lm", "Limb Movement", 0.1),
    ("bo", "Blood Oxygen (%)", 0.1),
    ("rem", "Rapid Eye Movement", 0.1),
    ("sh", "Sleep Hours", 0.1),
    ("hr", "Heart Rate", 0.1),
]


def _slider_value(df, column_name, label, step):
    min_value = float(df[column_name].min())
    max_value = float(df[column_name].max())
    default_value = float(df[column_name].median())

    if step == 1.0:
        return st.slider(label, int(min_value), int(max_value), int(round(default_value)))
    return st.slider(label, min_value, max_value, default_value, step=step)


def app(df, X, y):
    st.markdown(
        "<h1 style='text-decoration:underline;text-align:center;'>Prediction Page</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='font-size:22px;text-align:center;'>"
        "An <b style='color:green'>optimized Logistic Regression</b> model predicts your stress level "
        "using the actual columns from <code>Stress.csv</code>."
        "</p>",
        unsafe_allow_html=True,
    )

    with st.form("prediction_form"):
        user_inputs = []
        left_col, right_col = st.columns(2)

        for idx, (column_name, label, step) in enumerate(FEATURE_CONFIG):
            target_col = left_col if idx % 2 == 0 else right_col
            with target_col:
                user_inputs.append(_slider_value(df, column_name, label, step))

        submitted = st.form_submit_button("Predict")

    if submitted:
        prediction, metrics, probabilities = predict(X, y, user_inputs)
        pred_val = int(prediction[0])

        labels = {
            0: "Safe 😄",
            1: "Low Stress 🙂",
            2: "Medium Stress 😐",
            3: "High Stress 😞",
            4: "Very High Stress 😫",
        }
        imgs = {
            0: "./images/calm.png",
            1: "./images/low_stress.png",
            2: "./images/medium_stress.png",
            3: "./images/high_stress.png",
            4: "./images/very_high_stress.png",
        }
        alerts = {0: "success", 1: "success", 2: "warning", 3: "error", 4: "error"}

        col_result, col_img = st.columns([2, 3])
        with col_result:
            st.info("Stress level detected")
            st.write("Stress score =", pred_val)
            st.write("Selected model =", metrics.get("model_scope", "Global"))
            st.write("Age group =", metrics.get("age_group", "Unknown"))
            if metrics.get("cv_accuracy") is not None:
                st.write("Cross-validation accuracy =", f"{metrics['cv_accuracy']:.2%}")
            else:
                st.write("Cross-validation accuracy =", "Not available for this subset")
            st.write("Training accuracy =", f"{metrics['train_accuracy']:.2%}")

            desc = labels.get(pred_val, "Unknown")
            if alerts.get(pred_val) == "success":
                st.success(desc)
            elif alerts.get(pred_val) == "warning":
                st.warning(desc)
            else:
                st.error(desc)

            probability_map = {
                "Safe": float(probabilities[0]),
                "Low": float(probabilities[1]),
                "Medium": float(probabilities[2]),
                "High": float(probabilities[3]),
                "Very High": float(probabilities[4]),
            }
            st.subheader("Prediction confidence")
            st.bar_chart(probability_map)

        with col_img:
            img_p = imgs.get(pred_val, "./images/calm.png")
            if os.path.exists(img_p):
                st.image(img_p, use_container_width=True)
