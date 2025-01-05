#remember to pip install flask flask-mysql flask-wtf
# also pip install flask-mysqldb, python-magic-bin pip install PyPDF2 pytesseract Pillow




import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask_mysqldb import MySQL
import pytesseract  # For OCR
from PIL import Image  # For image processing

# Path to Tesseract executable (adjust this based on your system)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # For Windows

# Initialize Flask Application
app = Flask(__name__)

# App configurations
app.config['SECRET_KEY'] = 'yoursecretkey'
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'password'
app.config['MYSQL_DB'] = 'learnsafe'
app.config['MYSQL_PORT'] = 3306

app.config['UPLOAD_FOLDER'] = './uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'png', 'jpg', 'txt', 'csv'}

# Initialize MYSQL
mysql = MySQL(app)

# Utility function to check allowed file extensions
def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# New utility function to check for sensitive data in files
def contains_sensitive_data(file_path):
    """Checks file content for sensitive data (e.g., student ID numbers)."""
    sensitive_keywords = ['Student ID', 'Confidential', 'Private']
    file_extension = file_path.rsplit('.', 1)[-1].lower()

    try:
        # Handle plain text files
        if file_extension in {'txt', 'csv'}:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        # Handle PDF files (requires PyPDF2)
        elif file_extension == 'pdf':
            from PyPDF2 import PdfReader
            reader = PdfReader(file_path)
            content = ''.join(page.extract_text() for page in reader.pages)

        # Handle images with OCR (Tesseract)
        elif file_extension in {'png', 'jpg', 'jpeg'}:
            try:
                img = Image.open(file_path)
                content = pytesseract.image_to_string(img)  # OCR extraction
                if content == "":
                    raise Exception("No text detected in image.")
            except Exception as e:
                return False, f"Error scanning image with Tesseract: {str(e)}"  # Log specific error

        else:
            return False, "Unsupported file format"

        # Check for sensitive data in the extracted content
        for keyword in sensitive_keywords:
            if keyword in content:
                return True, "Confidential"

        return False, "Public"

    except Exception as e:
        return False, f"Error: {str(e)}"

# Route: File upload
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handles file upload, validates file type, and scans for sensitive data."""
    if request.method == 'POST':
        # Check if a file is uploaded
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        # Check if file is selected
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        # Validate file
        if file and allowed_file(file.filename):
            # Secure the filename
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Save file temporarily for validation
            file.save(file_path)

            # Scan the file for sensitive data
            has_sensitive_data, classification = contains_sensitive_data(file_path)
            if has_sensitive_data:
                flash(f'The file contains sensitive data and is classified as {classification}.')
                os.remove(file_path)  # Remove file if sensitive data is detected
                return redirect(request.url)

            # If valid, keep the file in the upload folder
            flash(f'File "{filename}" uploaded successfully with classification: {classification}.')
            return redirect(url_for('upload_file'))
        else:
            flash('File type not allowed')
            return redirect(request.url)

    return render_template('upload.html')

# Home Route
@app.route('/')
def home():
    """Renders the home page."""
    return render_template('home.html')

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with session management."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Query database for user
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()

        # Validate login credentials
        if user and check_password_hash(user[2], password):  # user[2] is the password_hash column
            session['user_id'] = user[0]
            session['role'] = user[3]
            return redirect(url_for('home'))
        else:
            return "Invalid username or password", 401
    return render_template('login.html')

# Error handler for file size exceedance
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large_error(error):
    flash('File is too large! The maximum allowed size is 10MB.')
    return redirect(request.url)

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
