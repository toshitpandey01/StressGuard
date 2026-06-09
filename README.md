<div align="center">

# StressGuard

### AI-Powered Mental Wellness Monitoring Platform

A comprehensive multi-role healthcare and wellness platform built with **Streamlit**, combining **stress prediction**, **patient-doctor collaboration**, **appointment management**, **support ticketing**, **analytics**, **PDF reporting**, and **role-based dashboards** for patients, doctors, and administrators.

</div>

---

## ✨ Overview

**StressGuard** is an end-to-end digital wellness and stress monitoring platform designed to assist individuals and healthcare professionals in assessing, tracking, and managing stress-related conditions through a unified interface.

The platform integrates machine learning-powered stress prediction with healthcare workflow management tools, enabling patients to monitor their wellness while allowing doctors and administrators to coordinate care efficiently.

StressGuard provides:

* AI-assisted stress level prediction
* Comprehensive patient management tools
* Doctor-patient communication channels
* Appointment scheduling and tracking
* Wellness checklists and progress monitoring
* Secure report generation and storage
* Administrative oversight and analytics
* Notification and update management
* Support ticket handling and issue resolution

Built on a modular architecture using **Streamlit**, **SQLite**, and **scikit-learn**, the platform is designed to be easy to deploy, maintain, and extend.

---

# 🧠 Core Features

## 1. Stress Prediction Engine

The platform includes a machine learning pipeline that evaluates stress levels using physiological and lifestyle indicators.

### Input Features

The model uses the following features from the dataset:

| Feature         | Description            |
| --------------- | ---------------------- |
| Age             | Patient age            |
| ScreenTimeHours | Daily screen exposure  |
| rr              | Respiratory rate       |
| bt              | Body temperature       |
| lm              | Lifestyle metric       |
| bo              | Blood oxygen indicator |
| rem             | REM sleep measurement  |
| sh              | Sleep hours            |
| hr              | Heart rate             |

### Target Variable

* `sl` → Stress Level

### Prediction Capabilities

* Real-time stress prediction
* Probability-based classification
* Prediction history tracking
* Historical trend analysis
* Individual patient monitoring

### Model Evaluation

The system includes:

* Accuracy reporting
* Precision and recall metrics
* F1-score analysis
* Confusion matrix visualization
* ROC curve analysis
* Precision-recall analysis
* Learning curve generation
* Class-wise performance reporting

---

## 2. Multi-Role Access Control

StressGuard supports three dedicated user roles.

### 👤 Patient

Patients access wellness monitoring tools and healthcare resources.

### 🩺 Doctor

Doctors manage patient care, communication, and clinical review workflows.

### 🔴 Admin

Administrators oversee platform operations, user management, analytics, and system-wide activities.

Role-based permissions ensure users only access features relevant to their responsibilities.

---

## 3. Authentication & Security

The platform includes a complete authentication workflow.

### Features

* User registration
* Secure login
* Session management
* Role-based authorization
* Password recovery support
* OTP verification workflows
* Account recovery mechanisms
* Google OAuth integration
* Protected dashboard routing

### Security Goals

* Controlled access to sensitive information
* Secure user authentication
* Role isolation
* Activity tracking and logging

---

## 4. Communication & Care Coordination

StressGuard facilitates collaboration between patients and healthcare providers.

### Messaging

* Real-time doctor-patient communication
* Conversation history management
* Secure message storage

### Notes Management

Patients can:

* Maintain personal wellness notes
* Track observations and symptoms

Doctors can:

* Create clinical notes
* Maintain private professional notes
* Monitor patient progress

### Updates & Notifications

The platform provides:

* Appointment updates
* System notifications
* Wellness reminders
* Administrative announcements

---

## 5. Wellness Tracking System

Patients can actively participate in their wellness journey through structured tracking tools.

### Checklist Management

* Daily wellness checklists
* Habit tracking
* Stress management tasks
* Progress monitoring

### Historical Tracking

* Stress prediction history
* Wellness trends
* Personal health records
* Performance analytics

---

## 6. Appointment Management System

StressGuard includes a complete appointment lifecycle management workflow.

### Patient Features

* Book appointments
* View upcoming appointments
* Reschedule requests
* Appointment history review

### Doctor Features

* Review appointment requests
* Accept appointments
* Reject appointments
* Propose rescheduling
* Manage schedules

### Admin Features

* Monitor all appointments
* Resolve scheduling conflicts
* Handle emergency reassignment
* Audit appointment activities

---

## 7. Ticketing & Support System

The integrated support module helps users report issues and request assistance.

### Features

* Ticket creation
* Status tracking
* Administrative review
* Issue resolution workflow
* Communication between users and administrators

---

## 8. PDF Reporting & Documentation

StressGuard provides automated report generation capabilities.

### Available Reports

* Stress assessment reports
* Patient wellness reports
* Appointment summaries
* Login activity reports
* Doctor reports
* Administrative exports
* User roster reports

### Export Formats

* PDF
* Printable summaries
* Downloadable records

---

# 👥 Role-Based Capabilities

## 👤 Patient Portal

Patients can:

* Run stress predictions
* View prediction history
* Analyze wellness trends
* Manage appointments
* Chat with assigned doctors
* Complete wellness checklists
* Access the wellness assistant
* Upload medical reports
* Review doctor feedback
* Manage personal notes
* Update profile information

---

## 🩺 Doctor Portal

Doctors can:

* View assigned patients
* Review stress predictions
* Monitor patient progress
* Manage appointments
* Communicate with patients
* Create doctor notes
* Maintain private notes
* Review uploaded reports
* Configure profile information
* Manage patient wellness tasks

---

## 🔴 Admin Portal

Administrators can:

* Add users
* Manage user accounts
* Assign doctors to patients
* Review platform analytics
* Monitor stress prediction activity
* Manage appointments
* Review support tickets
* Audit login logs
* Manage doctor portfolios
* Generate administrative reports

---

# 🏗️ Technology Stack

## Frontend

* Streamlit

## Backend

* SQLite (`users.db`)

## Machine Learning & Data Science

* pandas
* NumPy
* scikit-learn
* SciPy

## Visualization

* Matplotlib
* Seaborn

## Reporting

* ReportLab
* FPDF / fpdf2
* PyPDF2
* pdfplumber

## Authentication & Integrations

* requests
* google-auth
* google-auth-oauthlib

## Image Processing

* Pillow

---

# 🤖 Machine Learning Pipeline

The prediction workflow is implemented within `web_functions.py`.

### Pipeline Components

* `SimpleImputer(strategy="median")`
* `StandardScaler()`
* `LogisticRegression(max_iter=2500, solver="lbfgs", random_state=42)`

### Workflow

1. Dataset loading
2. Data preprocessing
3. Missing value handling
4. Feature scaling
5. Model training
6. Prediction generation
7. Performance evaluation
8. Visualization generation

---

# 📂 Project Structure

```text
StressGuard/
├── main.py
├── auth.py
├── database.py
├── utils.py
├── time_utils.py
├── landing.py
├── web_functions.py
├── patient_dashboard.py
├── doctor_dashboard.py
├── admin_dashboard.py
├── patient_appointments.py
├── doctor_appointments.py
├── admin_appointments.py
├── updates_center.py
├── report_generator.py
├── pdf_report.py
├── email_service.py
├── Stress.csv
├── users.db
├── requirements.txt
├── Tabs/
│   ├── __init__.py
│   ├── home.py
│   ├── data.py
│   ├── predict.py
│   ├── visualise.py
│   ├── support.py
│   ├── patient_dashboard.py
│   ├── doctor_dashboard.py
│   └── admin_dashboard.py
```

---

# 🚀 Installation

```bash
git clone <repository-url>
cd StressGuard
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the application:

```bash
streamlit run main.py
```

---

# 📊 Dataset

The application uses `Stress.csv` as the primary dataset for training and evaluating the stress prediction model.

The dataset contains physiological and behavioral indicators used to estimate stress levels and support wellness analysis.

---

# 🎯 Project Goals

* Improve accessibility to stress assessment tools
* Support proactive wellness monitoring
* Enhance doctor-patient collaboration
* Centralize healthcare workflow management
* Provide actionable insights through analytics
* Deliver an integrated digital wellness experience

---

# 📜 License

This project is intended for educational, research, and healthcare workflow demonstration purposes.

Please ensure compliance with applicable healthcare, privacy, and data protection regulations before deploying in production environments.
