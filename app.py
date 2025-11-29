import os
import google.generativeai as genai
from flask import Flask, request, jsonify, render_template
from PIL import Image
from dotenv import load_dotenv
import json
import requests

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

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
            "image_url": "temporary_placeholder_will_be_overwritten"
        }
    ]
    """
)

# --- Helper Function for Image Search ---
def get_recipe_image(query):
    """Searches Pexels for an image matching the query."""
    # Use a generic placeholder if API key is missing
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
        # Pexels search query should generally be in English for best results
        response = requests.get(PEXELS_URL, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        data = response.json()
        
        if 'photos' in data and len(data['photos']) > 0:
            return data['photos'][0]['src']['medium']
        else:
            return "https://placehold.co/600x400?text=No+Image+Found"
            
    except Exception as e:
        print(f"Error fetching image: {e}")
        return "https://placehold.co/600x400?text=Error"

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400

    file = request.files['image']

    # Get settings from the form data sent by the frontend
    language = request.form.get('language', 'English')
    units = request.form.get('units', 'Metric')

    # Use the Bulgarian word "Български" in the prompt for localization
    prompt_language = "Български" if language == "Bulgarian" else "English"

    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        image = Image.open(file)

        # Build the dynamic prompt including the settings
        prompt = f"""
        Analyze this image and identify the ingredients.
        Based on these ingredients, suggest 2 distinct recipes.
        
        **CRITICAL INSTRUCTION: Generate the entire output (Title, Description, Ingredients, and Instructions) entirely in {prompt_language}.**
        
        SETTINGS:
        - Units: Use the {units} system for all measurements (e.g. if Metric use grams/Celsius, if Imperial use cups/pounds/Fahrenheit).
        
        Return the response in the specific JSON format defined in your system instructions.
        """
        
        # 1. Ask Gemini for recipes
        response = model.generate_content([prompt, image])
        
        # Parse the JSON response
        recipes = json.loads(response.text)
        
        # 2. Loop through recipes and fetch images for each
        for recipe in recipes:
            # Note: We keep the search query in English for better image results
            search_query = f"{recipe['title']} food dish"
            recipe['image_url'] = get_recipe_image(search_query)

        return jsonify(recipes)

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'error': f'An internal error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    # Setting debug=True is fine for local development
    app.run(debug=True)