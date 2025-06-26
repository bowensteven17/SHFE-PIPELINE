#!/usr/bin/env python3
"""
Flask Web Service for the SHFE Data Pipeline
Orchestrates the scraping process and handles cloud storage integration.
"""

import os
import json
import tempfile
import logging
from datetime import datetime, date, timedelta 
from flask import Flask, jsonify, request
from google.cloud import storage

# Import the refactored scraper
from shfe_scraper import LLMEnhancedSHFEScraper #

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
PORT = int(os.environ.get('PORT', 8080))
PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT')
BUCKET_NAME = os.environ.get('STORAGE_BUCKET')
GOOGLE_GEMINI_API_KEY = os.environ.get('GOOGLE_GEMINI_API_KEY') # Updated to use GOOGLE_GEMINI_API_KEY

if not BUCKET_NAME:
    raise ValueError("STORAGE_BUCKET environment variable is not set.")
if not GOOGLE_GEMINI_API_KEY:
    logger.warning("GOOGLE_GEMINI_API_KEY environment variable is not set. Gemini parsing will be disabled.")


def upload_to_gcs(local_file_path: str, bucket_name: str) -> str:
    """Uploads a file to the GCS bucket."""
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        # Define the destination blob name
        destination_blob_name = f"SHFE/{os.path.basename(local_file_path)}"
        
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        
        gcs_url = f"gs://{bucket_name}/{destination_blob_name}"
        logger.info(f"Successfully uploaded {local_file_path} to {gcs_url}")
        return gcs_url
    except Exception as e:
        logger.error(f"Failed to upload {local_file_path} to GCS: {e}")
        raise

@app.route('/')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'SHFE Data Pipeline',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/shfe/run', methods=['POST'])
def run_shfe_pipeline():
    """
    Triggers the SHFE scraping and processing pipeline.
    Accepts a JSON body with a 'start_date' (e.g., {"start_date": "2025-01-10"}).
    """
    try:
        data = request.get_json() or {}
        start_date = data.get('start_date', (date.today() - timedelta(days=30)).strftime('%Y-%m-%d'))
        
        logger.info(f"Starting SHFE pipeline with start_date={start_date}")
        
        # Use a temporary directory for all outputs
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory: {temp_dir}")
            
            # Initialize and run the scraper with the Gemini API Key
            scraper = LLMEnhancedSHFEScraper(
                start_date=start_date,
                gemini_api_key=GOOGLE_GEMINI_API_KEY, # Updated to use the new variable
                output_dir=temp_dir
            )
            
            # The run_scraper method now returns the path to the final ZIP file
            zip_file_path = scraper.run_scraper() #
            
            if zip_file_path and os.path.exists(zip_file_path):
                # Upload the final ZIP to GCS
                gcs_url = upload_to_gcs(zip_file_path, BUCKET_NAME)
                
                return jsonify({
                    'success': True,
                    'message': 'SHFE scraping and export completed successfully.',
                    'start_date': start_date,
                    'output_file': gcs_url,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Scraper ran, but no new data was found or no output file was generated.',
                    'start_date': start_date
                }), 404

    except Exception as e:
        logger.error(f"SHFE pipeline failed: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'type': type(e).__name__
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)