#!/bin/bash
set -e

# Check for required tools
if ! command -v gcloud &> /dev/null
then
    echo "gcloud command not found. Please install the Google Cloud SDK."
    exit 1
fi

# Get project ID from argument or gcloud config
if [ -z "$1" ]; then
    PROJECT_ID=$(gcloud config get-value project)
    if [ -z "$PROJECT_ID" ]; then
        echo "Error: No project ID specified and no default project configured."
        echo "Usage: ./deploy_shfe.sh <your-gcp-project-id>"
        exit 1
    fi
else
    PROJECT_ID=$1
fi

SERVICE_NAME="shfe-scraper"
REGION="us-central1" # Or your preferred region
BUCKET_NAME="${PROJECT_ID}-shfe-data-bucket" # Define a bucket name

echo "================================================="
echo "🚀 Deploying SHFE Scraper to GCP Project: $PROJECT_ID"
echo "================================================="
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"
echo "Storage Bucket: $BUCKET_NAME"
echo ""

# Enable necessary APIs
echo "🔑 Enabling required Google Cloud APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  storage-component.googleapis.com \
  aiplatform.googleapis.com \
  --project=$PROJECT_ID

# Create GCS Bucket if it doesn't exist
echo "☁️  Checking for GCS Bucket: $BUCKET_NAME"
if gsutil ls -b gs://$BUCKET_NAME &> /dev/null; then
    echo "Bucket $BUCKET_NAME already exists."
else
    echo "Creating GCS Bucket: $BUCKET_NAME"
    gsutil mb -p $PROJECT_ID -l $REGION gs://$BUCKET_NAME
fi
echo ""

# Securely get the Gemini API key
read -sp "🔑 Please enter your Gemini API Key: " GEMINI_API_KEY
echo ""
if [ -z "$GEMINI_API_KEY" ]; then
    echo "❌ API Key cannot be empty. Aborting."
    exit 1
fi
echo ""

# Build the Docker image using Google Cloud Build
echo "🏗️  Building Docker image..."
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$SERVICE_NAME" --project=$PROJECT_ID

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image="gcr.io/$PROJECT_ID/$SERVICE_NAME" \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --project=$PROJECT_ID \
  --set-env-vars="STORAGE_BUCKET=$BUCKET_NAME" \
  --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY" \
  --cpu=2 \
  --memory=2Gi \
  --timeout=900 # 15 minutes, as scraping can be long

SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform=managed --region=$REGION --format='value(status.url)' --project=$PROJECT_ID)

echo ""
echo "✅ Deployment Successful!"
echo "================================================="
echo "Service URL: $SERVICE_URL"
echo "To run the pipeline, send a POST request:"
echo "curl -X POST -H \"Content-Type: application/json\" -d '{\"start_date\": \"YYYY-MM-DD\"}' $SERVICE_URL/shfe/run"
echo ""
echo "Example:"
echo "curl -X POST -H \"Content-Type: application/json\" -d '{\"start_date\": \"2025-01-10\"}' $SERVICE_URL/shfe/run"
echo "================================================="