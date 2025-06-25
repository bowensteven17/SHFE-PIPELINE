# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED True
ENV APP_HOME /app
WORKDIR $APP_HOME

# Install system dependencies for Selenium and Chrome
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Add Google Chrome's official GPG key
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    # Add the Chrome repository
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    # Install Chrome
    && apt-get update && apt-get install -y \
    google-chrome-stable \
    # Clean up
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements_shfe.txt .
RUN pip install --no-cache-dir -r requirements_shfe.txt

# Copy the application code into the container
COPY shfe_scraper.py .
COPY app_shfe.py .

# Expose the port the app runs on
EXPOSE 8080

# Define the command to run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "900", "app_shfe:app"]