import os
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, session, flash
from PIL import Image
from dotenv import load_dotenv
import json
import requests
import uuid
from datetime import datetime
# NEW: Import security tools for password hashing
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
# CRITICAL: Flask sessions and flash messages require a secret key
app.secret_key = 'your_super_secret_key_here' 

# --- New User/Scan Data Structure (Centralized Database Mock) ---
# USERS: {username: {id: str, password_hash: str, scans: {scan_id: scan_data}}}
USERS = {}

# --- Localization/Translation Data ---
TRANSLATIONS = {
    "English": {
        # Navigation/UI Labels
        "nav_account": "Account",
        "nav_scan": "Scan",
        "nav_upload": "Upload",
        "nav_settings": "Settings",
        "logout": "Log Out",
        
        # Account Page (UPDATED TEXT FOR NEW LOGIN FLOW)
        "welcome_title": "Welcome to ChefAI",
        "login_prompt": "Enter a username and password to log in or create an account.",
        "username_placeholder": "Your Username",
        "password_placeholder": "Password", # NEW
        "login_button": "Log In / Register",
        "greeting_hello": "Hello,",
        "scans_saved": "scans saved.",
        "app_settings_title": "App Settings",
        "scan_history": "Scan History",
        "no_history": "No scan history found. Start scanning new recipes!",
        "error_login": "Invalid username or password. Please try again.", # NEW KEY
        
        # Index Page (Camera & Overlays)
        "settings_title": "Settings",
        "mode_title": "Theme Mode",
        "units_title": "Measurement Units",
        "language_title": "Recipe Language",
        "mode_light": "Light",
        "mode_dark": "Dark",
        "units_metric": "Metric",
        "units_imperial": "Imperial",
        "lang_english": "English",
        "lang_bulgarian": "Български",
        "analyzing": "Analyzing Photo",
        "api_error": "Analysis Failed: ",
        "start_cooking": "Start Cooking",
        "step_word": "Step",
        "back_word": "Back",
        "next_word": "Next",
        "finish_word": "Finish",
    },
    "Bulgarian": {
        # Navigation/UI Labels
        "nav_account": "Профил",
        "nav_scan": "Сканирай",
        "nav_upload": "Качи",
        "nav_settings": "Настройки",
        "logout": "Изход",
        
        # Account Page (UPDATED TEXT FOR NEW LOGIN FLOW)
        "welcome_title": "Добре дошли в ChefAI",
        "login_prompt": "Въведете потребителско име и парола, за да влезете или да създадете акаунт.",
        "username_placeholder": "Вашето потребителско име",
        "password_placeholder": "Парола", # NEW
        "login_button": "Вход / Регистрация",
        "greeting_hello": "Здравейте,",
        "scans_saved": "запазени сканирания.",
        "app_settings_title": "Настройки на приложението",
        "scan_history": "История на сканиранията",
        "no_history": "Няма намерена история на сканиранията. Започнете да сканирате нови рецепти!",
        "error_login": "Невалидно потребителско име или парола. Моля, опитайте отново.", # NEW KEY

        # Index Page (Camera & Overlays)
        "settings_title": "Настройки",
        "mode_title": "Тема",
        "units_title": "Мерни единици",
        "language_title": "Език на рецептата",
        "mode_light": "Светъл",
        "mode_dark": "Тъмен",
        "units_metric": "Метрична",
        "units_imperial": "Имперска",
        "lang_english": "English",
        "lang_bulgarian": "Български",
        "analyzing": "Анализиране на снимка",
        "api_error": "Неуспешен анализ: ",
        "start_cooking": "Започни готвене",
        "step_word": "Стъпка",
        "back_word": "Назад",
        "next_word": "Напред",
        "finish_word": "Край",
    }
}
# ---------------------------------------------


# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# PEXELS Configuration
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PEXELS_URL = "https://api.pexels.com/v1/search"

# --- Gemini Configuration ---
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    safety_settings=safety_settings,
    generation_config=generation_config,
    # System Instruction sets the base role and required JSON format
    system_instruction="""
    You are ChefAI. Analyze the image provided to identify ingredients and suggest 2 distinct recipes.
    
    You must return the response in this specific JSON format:
    [
        {
            "title": "Recipe Name",
            "description": "Short description",
            "ingredients": ["List", "of", "ingredients"],
            "instructions": ["Step 1", "Step 2"],
            "time_minutes": 45,       // NEW: Total time in minutes
            "skill_level": "Medium",  // NEW: Must be 'Easy', 'Medium', or 'Hard'
            "image_url": "temporary_placeholder_will_be_overwritten"
        }
    ]
    """
)

# -----------------------------------------------------
# --- HELPER FUNCTIONS (NEW/UPDATED) ---
# -----------------------------------------------------

def get_user_settings():
    """Retrieves user settings (like mode and language) from session or defaults."""
    # Note: These values should correspond to what is set via the UI/settings page
    return {
        'mode': session.get('mode', 'light'),
        'language': session.get('language', 'English')
    }

def format_scans_for_template(scans_dict):
    """Converts the internal USERS[username]['scans'] dictionary to a list suitable for the template."""
    scan_list_summary = []
    # Prepare a list of summary data for the dashboard
    for scan_id, data in scans_dict.items():
        scan_list_summary.append({
            "id": scan_id,
            "date": data["date"],
            "title": data["summary_title"],
            "notes": data["summary_notes"],
            "image_url": data["summary_image"]
        })
    # Sort by timestamp (newest first)
    scan_list_summary.sort(key=lambda x: scans_dict[x['id']]["timestamp"], reverse=True)
    return scan_list_summary


def get_user_context(username=None):
    """
    Returns a tuple (user_data, user_settings) for template rendering.
    If username is None or the user is not found/logged in, returns a default non-logged-in context.
    """
    # 1. Get settings
    settings = get_user_settings()
    
    # 2. Determine login status
    current_username = session.get('username')
    is_logged_in = session.get('logged_in', False)
    
    # Use the passed username if context is being forced (e.g., login failure)
    if username is None and is_logged_in:
        username = current_username
        
    if username and username in USERS and is_logged_in:
        # Logged-in context
        user_data = {
            'is_logged_in': True,
            'username': username,
            'id': USERS[username]['id']
        }
    else:
        # Non-logged-in context (used for the login page and on login failure)
        user_data = {
            'is_logged_in': False,
            'username': None,
            'id': None
        }
        
    return user_data, settings

# --- Helper Function for Image Search ---
def get_recipe_image(query):
    """Searches Pexels for an image matching the query."""
    if not PEXELS_API_KEY:
        return "https://placehold.co/600x400?text=No+API+Key"

    headers = {
        "Authorization": PEXELS_API_KEY
    }
    
    params = {
        "query": query,
        "per_page": 1,
        "orientation": "landscape"
    }
    
    try:
        response = requests.get(PEXELS_URL, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if 'photos' in data and len(data['photos']) > 0:
            return data['photos'][0]['src']['medium']
        else:
            return "https://placehold.co/600x400?text=No+Image+Found"
            
    except Exception as e:
        print(f"Error fetching image: {e}")
        return "https://placehold.co/600x400?text=Error"


# -----------------------------------------------------
# --- SCAN DATA HANDLER ---
# -----------------------------------------------------

def save_new_scan(recipes):
    """Saves the recipe data to the current user's scan history."""
    username = session.get('username')
    if not username or username not in USERS:
        return None # Cannot save scan if user is not logged in

    scan_id = str(uuid.uuid4()) # Generate a unique ID
    
    # Store the entire recipe list generated by Gemini
    USERS[username]["scans"][scan_id] = {
        "date": datetime.now().strftime("%b %d, %Y"),
        "timestamp": datetime.now().timestamp(),
        "recipes": recipes,
        "summary_title": recipes[0]['title'], # Use the first recipe for the dashboard summary
        "summary_notes": recipes[0]['description'],
        "summary_image": recipes[0]['image_url']
    }
    return scan_id


# -----------------------------------------------------
# --- AUTHENTICATION ROUTES (UPDATED) ---
# -----------------------------------------------------

@app.route('/login-or-register', methods=['POST'])
def login_or_register():
    """Handles both user login and registration based on username existence."""
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 1. Handle missing fields or failed login attempts
    if not username or not password:
        # Get the non-logged-in context for rendering the page
        user, userSettings = get_user_context(None)
        
        return render_template('account.html', 
                               user=user, 
                               userSettings=userSettings,
                               scans=[],
                               error_message=True, # Pass the error flag
                               active_tab='account')

    # Check if user already exists
    if username in USERS:
        # --- LOGIN ATTEMPT ---
        user_data = USERS[username]
        
        # Check password against stored hash
        if check_password_hash(user_data['password_hash'], password):
            # Success
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('account_page'))
        else:
            # Failure (Invalid Password)
            # Get the non-logged-in context for rendering the page
            user, userSettings = get_user_context(None)
            
            return render_template('account.html', 
                                   user=user, 
                                   userSettings=userSettings, 
                                   scans=[],
                                   error_message=True, # Pass the error flag
                                   active_tab='account')
            
    else:
        # --- REGISTRATION ATTEMPT ---
        
        # 1. Securely Hash the Password
        hashed_password = generate_password_hash(password)
        
        # 2. Save New User Data
        user_id = str(uuid.uuid4())
        USERS[username] = {
            'password_hash': hashed_password,
            'id': user_id,
            'scans': {} # Initialize empty scan history
        }
        
        # 3. Log the new user in immediately
        session['logged_in'] = True
        session['username'] = username
        
        return redirect(url_for('account_page'))


@app.route('/logout')
def logout():
    # Clear the session
    session.pop('logged_in', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('account_page'))

# -----------------------------------------------------
# --- MAIN APPLICATION ROUTES (UPDATED) ---
# -----------------------------------------------------

@app.route('/')
def index_page():
    # Get user context for consistent settings access
    user, userSettings = get_user_context()
    translations = TRANSLATIONS.get(userSettings['language'], TRANSLATIONS['English'])
    
    return render_template(
        'index.html', 
        active_tab='scan', 
        userSettings=userSettings,
        t=translations # Passed translations
    )

@app.route('/account')
def account_page():
    # Get current user state and settings
    user, userSettings = get_user_context()
    translations = TRANSLATIONS.get(userSettings['language'], TRANSLATIONS['English'])
    
    scan_list_summary = []
    if user['is_logged_in']:
        user_scans = USERS[user['username']]["scans"]
        scan_list_summary = format_scans_for_template(user_scans)
    
    return render_template(
        'account.html', 
        active_tab='account', 
        user=user, 
        scans=scan_list_summary,
        userSettings=userSettings,
        t=translations 
    )

@app.route('/scan_details/<scan_id>')
def scan_details_page(scan_id):
    """Renders the full recipe details for a specific historical scan."""
    # Get user context and settings
    user, userSettings = get_user_context()
    translations = TRANSLATIONS.get(userSettings['language'], TRANSLATIONS['English'])
    
    current_username = user.get("username")
    
    if not user.get("is_logged_in") or current_username not in USERS:
        flash('Please log in to view your scan history.', 'warning')
        return redirect(url_for('account_page'))
        
    # Get scan from the specific user's scan dictionary
    scan = USERS[current_username]["scans"].get(scan_id)
    
    if not scan:
        # User requested an ID that doesn't exist
        abort(404) 

    return render_template(
        'scan_details.html', 
        scan_data=scan,
        active_tab='account',
        userSettings=userSettings,
        t=translations # Passed translations
    )

@app.route('/settings')
def settings_page():
    # Get user context and settings
    user, userSettings = get_user_context()
    
    return render_template('settings.html', userSettings=userSettings)

@app.route('/analyze', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']
    # You should be reading language/units from the session/userSettings now, 
    # but we'll use the form data if available for simplicity in this flow.
    language = request.form.get('language', 'English')
    units = request.form.get('units', 'Metric')
    prompt_language = "Български" if language == "Bulgarian" else "English"

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        image = Image.open(file)

        # 1. Build the dynamic prompt including the settings
        prompt = f"""
        Analyze this image and identify the ingredients.
        Based on these ingredients, suggest 2 distinct recipes.
        
        **CRITICAL INSTRUCTION: Generate the entire output (Title, Description, Ingredients, and Instructions) entirely in {prompt_language}.**
        
        SETTINGS:
        - Units: Use the {units} system for all measurements (e.g. if Metric use grams/Celsius, if Imperial use cups/pounds/Fahrenheit).
        
        Return the response in the specific JSON format defined in your system instructions.
        """
        
        # 2. Ask Gemini for recipes (THE ACTUAL API CALL)
        response = model.generate_content([prompt, image])
        
        # Robust JSON parsing to handle malformed output from the model
        try:
            recipes = json.loads(response.text)
        except json.JSONDecodeError as json_e:
            # Print the faulty JSON to the Flask console for debugging
            print("\n--- JSON PARSE ERROR ---")
            print(f"Error: {json_e}")
            print("Raw Model Output:")
            print(response.text)
            print("------------------------\n")
            
            return jsonify({
                'error': f'The AI generated malformed output. Please try again with a clearer image or different settings. Details: {json_e.msg}'
            }), 500

        # 3. Loop through recipes and fetch images
        for recipe in recipes:
            search_query = f"{recipe['title']} food dish"
            recipe['image_url'] = get_recipe_image(search_query)

        # 4. Save the full scan if the user is logged in
        new_scan_id = None
        if session.get("logged_in"):
            if recipes and isinstance(recipes, list):
                new_scan_id = save_new_scan(recipes)
        
        # Send back the recipes AND the new scan ID if available
        return jsonify({
            "recipes": recipes, 
            "scan_id": new_scan_id 
        })

    except Exception as e:
        print(f"Server Error: {e}")
        error_message = f'An internal error occurred: {str(e)}. Check your API key or image format.'
        return jsonify({'error': error_message}), 500

if __name__ == '__main__':
    app.run(debug=True)