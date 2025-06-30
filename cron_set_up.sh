# Calculate time 20 minutes from now
CURRENT_TIME=$(date -u +"%H:%M")
CURRENT_HOUR=$(date -u +"%H" | sed 's/^0//')
CURRENT_MINUTE=$(date -u +"%M" | sed 's/^0//')

# Add 20 minutes
TOTAL_MINUTES=$((CURRENT_MINUTE + 20))
if [ $TOTAL_MINUTES -ge 60 ]; then
    SCHEDULE_HOUR=$(((CURRENT_HOUR + 1) % 24))
    SCHEDULE_MINUTE=$((TOTAL_MINUTES - 60))
else
    SCHEDULE_HOUR=$CURRENT_HOUR
    SCHEDULE_MINUTE=$TOTAL_MINUTES
fi

CRON_SCHEDULE="$SCHEDULE_MINUTE $SCHEDULE_HOUR * * *"
RUN_TIME=$(printf "%02d:%02d UTC" $SCHEDULE_HOUR $SCHEDULE_MINUTE)

echo "⏰ Current time: $CURRENT_TIME UTC"
echo "🎯 Scheduling to run at: $RUN_TIME (in ~20 minutes)"#!/bin/bash
set -e

# Simple Cloud Scheduler setup for SHFE Scraper
# Prompts for start date and schedules to run in 20 minutes

# Get project ID from argument or gcloud config
if [ -z "$1" ]; then
    PROJECT_ID=$(gcloud config get-value project)
    if [ -z "$PROJECT_ID" ]; then
        echo "Error: No project ID specified and no default project configured."
        echo "Usage: ./setup_simple_cron.sh <your-gcp-project-id>"
        exit 1
    fi
else
    PROJECT_ID=$1
fi

# Prompt for start date
echo "📅 Enter the start date for data collection:"
read -p "Start date (YYYY-MM-DD): " START_DATE

# Validate date format
if ! date -d "$START_DATE" >/dev/null 2>&1; then
    echo "❌ Invalid date format. Please use YYYY-MM-DD (example: 2025-04-01)"
    exit 1
fi

echo "✅ Using start date: $START_DATE"
echo ""

# Prompt for schedule choice
echo "🕒 Choose when to run the scraper:"
echo "1. In 20 minutes, then daily at that time"
echo "2. Custom daily time (HH:MM in UTC)"
echo ""
read -p "Enter your choice (1 or 2): " TIME_CHOICE

case $TIME_CHOICE in
    1)
        # Calculate time 20 minutes from now
        CURRENT_TIME=$(date -u +"%H:%M")
        CURRENT_HOUR=$(date -u +"%H" | sed 's/^0//')
        CURRENT_MINUTE=$(date -u +"%M" | sed 's/^0//')

        # Add 20 minutes
        TOTAL_MINUTES=$((CURRENT_MINUTE + 20))
        if [ $TOTAL_MINUTES -ge 60 ]; then
            SCHEDULE_HOUR=$(((CURRENT_HOUR + 1) % 24))
            SCHEDULE_MINUTE=$((TOTAL_MINUTES - 60))
        else
            SCHEDULE_HOUR=$CURRENT_HOUR
            SCHEDULE_MINUTE=$TOTAL_MINUTES
        fi

        RUN_TIME=$(printf "%02d:%02d UTC" $SCHEDULE_HOUR $SCHEDULE_MINUTE)
        echo "⏰ Current time: $CURRENT_TIME UTC"
        echo "🎯 Will run in ~20 minutes at: $RUN_TIME"
        ;;
    2)
        echo "Enter the daily run time in UTC (24-hour format):"
        read -p "Time (HH:MM): " CUSTOM_TIME
        
        # Validate time format
        if [[ ! $CUSTOM_TIME =~ ^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$ ]]; then
            echo "❌ Invalid time format. Please use HH:MM (example: 09:30)"
            exit 1
        fi
        
        SCHEDULE_HOUR=$(echo $CUSTOM_TIME | cut -d':' -f1 | sed 's/^0//')
        SCHEDULE_MINUTE=$(echo $CUSTOM_TIME | cut -d':' -f2 | sed 's/^0//')
        RUN_TIME=$(printf "%02d:%02d UTC" $SCHEDULE_HOUR $SCHEDULE_MINUTE)
        echo "✅ Will run daily at: $RUN_TIME"
        ;;
    *)
        echo "❌ Invalid choice. Please run the script again and choose 1 or 2."
        exit 1
        ;;
esac

CRON_SCHEDULE="$SCHEDULE_MINUTE $SCHEDULE_HOUR * * *"
echo ""

SERVICE_NAME="shfe-scraper-anthropic"
REGION="us-central1"

# Auto-detect the service URL
echo "🔍 Detecting Cloud Run service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform=managed --region=$REGION --format='value(status.url)' --project=$PROJECT_ID 2>/dev/null)

if [ -z "$SERVICE_URL" ]; then
    echo "❌ Could not find Cloud Run service '$SERVICE_NAME' in region '$REGION'"
    echo "Make sure your service is deployed first using deploy_shfe.sh"
    exit 1
fi

echo "✅ Found service URL: $SERVICE_URL"

echo ""
echo "================================================="
echo "🕒 Setting up SHFE Scraper"
echo "================================================="
echo "Project ID: $PROJECT_ID"
echo "Service URL: $SERVICE_URL"
echo "Start Date: $START_DATE"
echo "Schedule: Daily at $RUN_TIME"
echo ""

# Enable Cloud Scheduler API
echo "🔑 Enabling Cloud Scheduler API..."
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT_ID

# Create service account for scheduler
SA_NAME="shfe-scheduler"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "👤 Setting up service account..."
if gcloud iam service-accounts describe $SA_EMAIL --project=$PROJECT_ID &>/dev/null; then
    echo "Service account already exists."
else
    gcloud iam service-accounts create $SA_NAME \
        --display-name="SHFE Daily Scheduler" \
        --project=$PROJECT_ID
fi

# Grant permissions
echo "🔐 Granting permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/run.invoker"

# Delete existing job if it exists
echo "🧹 Cleaning up any existing job..."
gcloud scheduler jobs delete shfe-daily-auto --location=$REGION --project=$PROJECT_ID --quiet 2>/dev/null || echo "No existing job to delete"

# Create the scheduled job
echo "📅 Creating scheduled job..."
gcloud scheduler jobs create http shfe-daily-auto \
    --location=$REGION \
    --schedule="$CRON_SCHEDULE" \
    --time-zone="UTC" \
    --uri="${SERVICE_URL}/shfe/run" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"start_date": "'$START_DATE'"}' \
    --oidc-service-account-email=$SA_EMAIL \
    --oidc-token-audience="${SERVICE_URL}" \
    --max-retry-attempts=3 \
    --max-retry-duration=1800s \
    --project=$PROJECT_ID

echo ""
echo "✅ Setup Complete!"
echo "================================================="
echo "🎉 Your SHFE scraper is now scheduled!"
echo ""
echo "📋 Job Details:"
echo "   Name: shfe-daily-auto"
echo "   Start Date: $START_DATE"
echo "   Schedule: Daily at $RUN_TIME"
echo "   Output: Automatically saved to your GCS bucket"
echo ""
echo "🔍 Management Commands:"
echo "   View jobs: gcloud scheduler jobs list --location=$REGION"
echo "   Test now:  gcloud scheduler jobs run shfe-daily-auto --location=$REGION"
echo "   Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION"
echo ""
echo "🛑 To STOP the cron job:"
echo "   gcloud scheduler jobs delete shfe-daily-auto --location=$REGION --quiet"
echo ""
echo "▶️ To START it again:"
echo "   ./setup_simple_cron.sh"
echo ""
echo "🎯 Your scraper will run automatically every day at $RUN_TIME!"
echo "   Data will be saved to: gs://$(echo $PROJECT_ID | tr '[:upper:]' '[:lower:]')-shfe-data-bucket/SHFE/"
echo "================================================="