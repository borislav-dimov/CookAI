# CookAI

CookAI is an **AI-powered cooking assistant** that transforms a photo of your available ingredients into creative, personalized recipes.  
Built with **Google Gemini** for AI reasoning and **Pexels** for image processing, CookAI helps you decide *what to cook* using exactly what you already have.

---

## Features

- **Upload or snap a photo** of your ingredients  
- Uses **Google Gemini** for image and text processing (AI recipe generation)  
- Fetches and processes images using **Pexels**  
- Outputs ingredient lists and creative recipes based on what you have  

---

## Installation
### 1. Clone the Repository

```bash
git clone [https://github.com/borislav-dimov/CookAI.git](https://github.com/borislav-dimov/CookAI.git)
cd CookAI
```
4. Install Dependencies
```bash
pip install -r requirements.txt
```
5. Configure Environment Variables
Create a .env file in the project root and add:
```bash
GEMINI_API_KEY=your_gemini_api_key_here
PEXELS_API_KEY=your_pexels_api_key_here
```

6. Run the Application
```bash
python app.py
```
Open your browser at:
http://127.0.0.1:5000/

## License
This project is licensed under the AGPL-3.0 License — see the LICENSE file for details.
