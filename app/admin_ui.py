"""Admin UI: Web interface for document uploads, OAuth connections, and campaign management.

FR-KB-001: Admin UI for document uploads and Typeform connection
FR-CRM-001: HubSpot OAuth connection interface
FR-CRM-002: Salesforce OAuth connection interface

This module provides:
- Document upload interface
- OAuth connection flow for Typeform, HubSpot, Salesforce
- Campaign creation and management
- Integration dashboard
"""

from __future__ import annotations

import os
import json
from typing import Dict, Any
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from app.typeform_integration import TypeformOAuth, authenticate_typeform, complete_typeform_oauth, ingest_typeform, list_typeform_forms
from app.hubspot_integration import HubSpotOAuth, authenticate_hubspot, complete_hubspot_oauth
from app.salesforce_integration import SalesforceOAuth, authenticate_salesforce, complete_salesforce_oauth
from app.campaign_manager import create_campaign, trigger_campaign, get_campaign_stats, CampaignManager
from app.convert import convert_file
from app.ingest_snippet import ingest_chunks

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24).hex())

# Upload configuration
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "/tmp/sdr_uploads")
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'pptx', 'xlsx', 'csv', 'json', 'html'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DB_URL = os.getenv("DATABASE_URL")


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Dashboard Home
@app.route('/')
def dashboard():
    """Admin dashboard home."""
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>SDR Agent Admin</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            .card { border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 20px 0; }
            .status { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; }
            .status.connected { background: #d4edda; color: #155724; }
            .status.disconnected { background: #f8d7da; color: #721c24; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .upload-zone { border: 2px dashed #ccc; padding: 40px; text-align: center; border-radius: 8px; margin: 20px 0; }
            a { color: #007bff; text-decoration: none; }
            a:hover { text-decoration: underline; }
        </style>
    </head>
    <body>
        <h1>🤖 SDR Agent Admin</h1>
        
        <div class="card">
            <h2>📊 Integrations Status</h2>
            <table width="100%">
                <tr>
                    <td><strong>Typeform</strong></td>
                    <td><span class="status {{ typeform_status }}">{{ typeform_text }}</span></td>
                    <td>
                        {% if typeform_status == 'disconnected' %}
                            <a href="{{ url_for('oauth_typeform') }}"><button>Connect</button></a>
                        {% else %}
                            <a href="{{ url_for('typeform_forms') }}"><button>Manage Forms</button></a>
                        {% endif %}
                    </td>
                </tr>
                <tr>
                    <td><strong>HubSpot</strong></td>
                    <td><span class="status {{ hubspot_status }}">{{ hubspot_text }}</span></td>
                    <td>
                        {% if hubspot_status == 'disconnected' %}
                            <a href="{{ url_for('oauth_hubspot') }}"><button>Connect</button></a>
                        {% endif %}
                    </td>
                </tr>
                <tr>
                    <td><strong>Salesforce</strong></td>
                    <td><span class="status {{ salesforce_status }}">{{ salesforce_text }}</span></td>
                    <td>
                        {% if salesforce_status == 'disconnected' %}
                            <a href="{{ url_for('oauth_salesforce') }}"><button>Connect</button></a>
                        {% endif %}
                    </td>
                </tr>
            </table>
        </div>
        
        <div class="card">
            <h2>📁 Document Upload</h2>
            <form method="POST" action="{{ url_for('upload_document') }}" enctype="multipart/form-data">
                <div class="upload-zone">
                    <input type="file" name="file" accept=".pdf,.docx,.txt,.pptx,.xlsx,.csv,.json,.html" required>
                    <p>Supported: PDF, DOCX, TXT, PPTX, XLSX, CSV, JSON, HTML</p>
                </div>
                <label>
                    <input type="checkbox" name="auto_ingest" checked> Auto-ingest to knowledge base
                </label><br><br>
                <button type="submit">Upload & Process</button>
            </form>
        </div>
        
        <div class="card">
            <h2>🎯 Campaigns</h2>
            <a href="{{ url_for('campaigns') }}"><button>Manage Campaigns</button></a>
            <a href="{{ url_for('create_campaign_form') }}"><button>Create New Campaign</button></a>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div style="padding: 10px; margin: 10px 0; background: {% if category == 'error' %}#f8d7da{% else %}#d4edda{% endif %}; border-radius: 4px;">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </body>
    </html>
    '''
    
    # Check integration status
    typeform_token = TypeformOAuth.get_token()
    hubspot_token = HubSpotOAuth.get_token()
    salesforce_token = SalesforceOAuth.get_token()
    
    return render_template_string(template,
        typeform_status='connected' if typeform_token else 'disconnected',
        typeform_text='Connected' if typeform_token else 'Not Connected',
        hubspot_status='connected' if hubspot_token else 'disconnected',
        hubspot_text='Connected' if hubspot_token else 'Not Connected',
        salesforce_status='connected' if salesforce_token else 'disconnected',
        salesforce_text='Connected' if salesforce_token else 'Not Connected'
    )


# Document Upload
@app.route('/upload', methods=['POST'])
def upload_document():
    """Handle document upload and ingestion."""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))
    
    if not allowed_file(file.filename):
        flash('File type not allowed', 'error')
        return redirect(url_for('dashboard'))
    
    # Save file
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    try:
        # Convert to chunks
        result = convert_file(filepath, out_dir=UPLOAD_FOLDER)
        
        # Auto-ingest if requested
        if request.form.get('auto_ingest'):
            chunks_ingested = ingest_chunks(result["chunks_path"], database_url=DB_URL)
            flash(f'✅ File uploaded and ingested! {chunks_ingested} chunks added to knowledge base.', 'success')
        else:
            flash(f'✅ File uploaded and processed! {result["n_chunks"]} chunks created.', 'success')
        
    except Exception as e:
        flash(f'❌ Error processing file: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))


# OAuth: Typeform
@app.route('/oauth/typeform')
def oauth_typeform():
    """Initiate Typeform OAuth flow."""
    auth_url = authenticate_typeform()
    return redirect(auth_url)


@app.route('/oauth/typeform/callback')
def oauth_typeform_callback():
    """Handle Typeform OAuth callback."""
    code = request.args.get('code')
    if not code:
        flash('OAuth failed: No code received', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        complete_typeform_oauth(code)
        flash('✅ Typeform connected successfully!', 'success')
    except Exception as e:
        flash(f'❌ OAuth error: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))


# OAuth: HubSpot
@app.route('/oauth/hubspot')
def oauth_hubspot():
    """Initiate HubSpot OAuth flow."""
    auth_url = authenticate_hubspot()
    return redirect(auth_url)


@app.route('/oauth/hubspot/callback')
def oauth_hubspot_callback():
    """Handle HubSpot OAuth callback."""
    code = request.args.get('code')
    if not code:
        flash('OAuth failed: No code received', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        complete_hubspot_oauth(code)
        flash('✅ HubSpot connected successfully!', 'success')
    except Exception as e:
        flash(f'❌ OAuth error: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))


# OAuth: Salesforce
@app.route('/oauth/salesforce')
def oauth_salesforce():
    """Initiate Salesforce OAuth flow."""
    auth_url = authenticate_salesforce()
    return redirect(auth_url)


@app.route('/oauth/salesforce/callback')
def oauth_salesforce_callback():
    """Handle Salesforce OAuth callback."""
    code = request.args.get('code')
    if not code:
        flash('OAuth failed: No code received', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        complete_salesforce_oauth(code)
        flash('✅ Salesforce connected successfully!', 'success')
    except Exception as e:
        flash(f'❌ OAuth error: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))


# Typeform Forms
@app.route('/typeform/forms')
def typeform_forms():
    """List Typeform forms."""
    try:
        forms = list_typeform_forms()
        
        template = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Typeform Forms</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
                button { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
                button:hover { background: #0056b3; }
                a { color: #007bff; text-decoration: none; }
            </style>
        </head>
        <body>
            <h1>📝 Typeform Forms</h1>
            <p><a href="{{ url_for('dashboard') }}">← Back to Dashboard</a></p>
            
            <table>
                <tr>
                    <th>Form Title</th>
                    <th>ID</th>
                    <th>Actions</th>
                </tr>
                {% for form in forms %}
                <tr>
                    <td>{{ form.title }}</td>
                    <td><code>{{ form.id }}</code></td>
                    <td>
                        <form method="POST" action="{{ url_for('ingest_typeform_form') }}" style="display: inline;">
                            <input type="hidden" name="form_id" value="{{ form.id }}">
                            <button type="submit">Ingest to KB</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </table>
        </body>
        </html>
        '''
        
        return render_template_string(template, forms=forms)
        
    except Exception as e:
        flash(f'Error fetching forms: {str(e)}', 'error')
        return redirect(url_for('dashboard'))


@app.route('/typeform/ingest', methods=['POST'])
def ingest_typeform_form():
    """Ingest Typeform responses."""
    form_id = request.form.get('form_id')
    
    try:
        result = ingest_typeform(form_id)
        flash(f'✅ Ingested {result["responses_count"]} responses ({result["chunks_count"]} chunks)', 'success')
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
    
    return redirect(url_for('typeform_forms'))


# Campaigns
@app.route('/campaigns')
def campaigns():
    """List campaigns."""
    campaigns_list = CampaignManager.list_campaigns()
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Campaigns</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
            button { background: #007bff; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
            button:hover { background: #0056b3; }
            .status { padding: 4px 12px; border-radius: 12px; font-size: 12px; }
            .status.active { background: #d4edda; color: #155724; }
            .status.draft { background: #fff3cd; color: #856404; }
            a { color: #007bff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>🎯 Campaigns</h1>
        <p><a href="{{ url_for('dashboard') }}">← Back to Dashboard</a></p>
        <a href="{{ url_for('create_campaign_form') }}"><button>+ Create Campaign</button></a>
        
        <table>
            <tr>
                <th>Name</th>
                <th>CRM Source</th>
                <th>Trigger Type</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
            {% for campaign in campaigns_list %}
            <tr>
                <td>{{ campaign.name }}</td>
                <td>{{ campaign.crm_source }}</td>
                <td>{{ campaign.trigger_type }}</td>
                <td><span class="status {{ campaign.status }}">{{ campaign.status }}</span></td>
                <td>
                    <form method="POST" action="{{ url_for('trigger_campaign_route', campaign_id=campaign.id) }}" style="display: inline;">
                        <button type="submit">Trigger</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    '''
    
    return render_template_string(template, campaigns_list=campaigns_list)


@app.route('/campaigns/create', methods=['GET', 'POST'])
def create_campaign_form():
    """Create campaign form."""
    if request.method == 'POST':
        try:
            campaign_id = create_campaign(
                name=request.form.get('name'),
                description=request.form.get('description'),
                crm_source=request.form.get('crm_source'),
                trigger_type=request.form.get('trigger_type', 'manual'),
                max_prospects=int(request.form.get('max_prospects', 100))
            )
            flash(f'✅ Campaign created! ID: {campaign_id}', 'success')
            return redirect(url_for('campaigns'))
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'error')
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Create Campaign</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
            label { display: block; margin-top: 15px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 8px; margin-top: 5px; border: 1px solid #ddd; border-radius: 4px; }
            button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; margin-top: 20px; }
            button:hover { background: #0056b3; }
            a { color: #007bff; text-decoration: none; }
        </style>
    </head>
    <body>
        <h1>Create Campaign</h1>
        <p><a href="{{ url_for('campaigns') }}">← Back to Campaigns</a></p>
        
        <form method="POST">
            <label>Campaign Name</label>
            <input type="text" name="name" required>
            
            <label>Description</label>
            <textarea name="description" rows="3"></textarea>
            
            <label>CRM Source</label>
            <select name="crm_source" required>
                <option value="hubspot">HubSpot</option>
                <option value="salesforce">Salesforce</option>
            </select>
            
            <label>Trigger Type</label>
            <select name="trigger_type">
                <option value="manual">Manual</option>
                <option value="scheduled">Scheduled</option>
                <option value="event">Event</option>
            </select>
            
            <label>Max Prospects per Trigger</label>
            <input type="number" name="max_prospects" value="100">
            
            <button type="submit">Create Campaign</button>
        </form>
    </body>
    </html>
    '''
    
    return render_template_string(template)


@app.route('/campaigns/<int:campaign_id>/trigger', methods=['POST'])
def trigger_campaign_route(campaign_id: int):
    """Trigger a campaign."""
    try:
        result = trigger_campaign(campaign_id, triggered_by="admin_ui")
        flash(f'✅ Campaign triggered! Imported {result["prospects_imported"]} prospects.', 'success')
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
    
    return redirect(url_for('campaigns'))


# API Endpoints for programmatic access
@app.route('/api/upload', methods=['POST'])
def api_upload():
    """API endpoint for document upload."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)
    
    result = convert_file(filepath, out_dir=UPLOAD_FOLDER)
    
    if request.args.get('auto_ingest', 'true').lower() == 'true':
        chunks_ingested = ingest_chunks(result["chunks_path"], database_url=DB_URL)
        result["chunks_ingested"] = chunks_ingested
    
    return jsonify(result)


@app.route('/api/campaigns', methods=['GET', 'POST'])
def api_campaigns():
    """API endpoint for campaigns."""
    if request.method == 'POST':
        data = request.json
        campaign_id = create_campaign(**data)
        return jsonify({"campaign_id": campaign_id})
    else:
        campaigns_list = CampaignManager.list_campaigns()
        return jsonify(campaigns_list)


if __name__ == '__main__':
    # Development server
    port = int(os.getenv("ADMIN_UI_PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
