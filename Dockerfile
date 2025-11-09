# Use a slim, official Python image to keep the container size small
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install the Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project folder to the container's working directory
COPY . .

# Set the port that the application will listen on
ENV PORT 8080

# This is the command that starts your application when the container runs
# It uses Gunicorn to run your Flask application.
# `main:app` assumes your Flask app instance is named `app` and is in `main.py`.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]