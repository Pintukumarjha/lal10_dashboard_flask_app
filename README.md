<<<<<<< HEAD
# 📊 LAL10 Dashboard: Flask & BigQuery Application

This is a Flask-based web dashboard designed to track manufacturing and production statuses for the LAL10 project, retrieving aggregated data from Google BigQuery.


## 🔑 Setup and Secrets

This application requires specific files for credentials that must be available locally but **MUST NOT** be pushed to Git:

1.  **`service-account-key.json`**: Your Google Cloud service account key for BigQuery access.
2.  **`.env`**: Create this file in the root directory to store your Flask secret key.

**Contents of your `.env` file:**

```env
FLASK_SECRET_KEY='your_long_random_secret_key_here'
=======
# lal10_dashboard_flask_app
>>>>>>> be71e43081936c61c934a7104476c7bab9b84967
