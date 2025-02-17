import os
import random
import re
import pickle
import joblib
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask_mysqldb import MySQL
import pytesseract  # For OCR (Image to text)
from PIL import Image, ImageDraw, ImageFont  # For image processing
import traceback

# For PDF reading and DOCX processing
from PyPDF2 import PdfReader
from docx import Document

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

# Folders for standard file uploads
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')  # Permanent storage
app.config['TEMP_UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'temp_uploads')  # Temporary for standard uploads

# Folders for community uploads (separate from standard uploads)
app.config['COMM_UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'community_uploads')  # Permanent community storage
app.config['TEMP_COMM_UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'temp_comm_uploads')  # Temporary community uploads

app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'png', 'jpg', 'txt', 'csv'}

# DRM: secure files folder set to the uploads directory
app.config['SECURE_FILES_FOLDER'] = os.path.join(app.static_folder, 'uploads')

# Initialize MYSQL
mysql = MySQL(app)

# Utility function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to check for sensitive data in files
def contains_sensitive_data(file_path):
    sensitive_keywords = ['Student ID', 'Confidential', 'Private']
    file_extension = file_path.rsplit('.', 1)[-1].lower()
    try:
        if file_extension in {'txt', 'csv'}:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        elif file_extension == 'pdf':
            reader = PdfReader(file_path)
            content = ''.join(page.extract_text() for page in reader.pages)
        elif file_extension in {'png', 'jpg', 'jpeg'}:
            try:
                img = Image.open(file_path)
                content = pytesseract.image_to_string(img)
                if content == "":
                    raise Exception("No text detected in image.")
            except Exception as e:
                return False, f"Error scanning image with Tesseract: {str(e)}"
        else:
            return False, "Unsupported file format"
        for keyword in sensitive_keywords:
            if keyword in content:
                return True, "Confidential"
        return False, "Public"
    except Exception as e:
        return False, f"Error: {str(e)}"

# Ensure a directory exists
def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# ----------------- Machine Learning Code -----------------

MODEL_FILE = "classification_model.pkl"

training_data = [
    # Study Notes
    ("Comprehensive notes on differential equations", "study_notes"),
    ("Lecture summary on artificial intelligence", "study_notes"),
    ("Handwritten notes covering organic chemistry reactions", "study_notes"),
    ("Summary of the key principles in Newtonian physics", "study_notes"),
    ("Flashcards for memorizing important dates in history", "study_notes"),
    ("Mind map of biological classifications", "study_notes"),
    ("Formula sheet for calculus and trigonometry", "study_notes"),
    ("A detailed explanation of genetic mutations", "study_notes"),
    ("Key takeaways from the lecture on supply chain management", "study_notes"),
    ("Short notes on the basics of object-oriented programming", "study_notes"),
    ("Physics revision notes for mechanics", "study_notes"),
    ("Algebra practice problems and solutions", "study_notes"),
    ("Summarized notes on electricity and magnetism", "study_notes"),
    ("Notes on data structures and algorithms", "study_notes"),
    ("Study notes on the history of ancient civilizations", "study_notes"),
    ("Summary of machine learning techniques and algorithms", "study_notes"),
    ("Revision notes on differential calculus", "study_notes"),
    ("Key notes on environmental science and sustainability", "study_notes"),
    ("Detailed notes on atomic theory and quantum mechanics", "study_notes"),

    # School Results
    ("Midterm results showing performance in mathematics", "school_results"),
    ("Breakdown of my test scores for all subjects", "school_results"),
    ("Official letter indicating academic standing for the semester", "school_results"),
    ("GPA calculation breakdown for the final term", "school_results"),
    ("Official grading report issued by the school", "school_results"),
    ("Summary of coursework grades for the entire year", "school_results"),
    ("Report showing my academic progress in different subjects", "school_results"),
    ("List of subjects with corresponding grades for the last term", "school_results"),
    ("Cumulative academic transcript with semester-wise results", "school_results"),
    ("Final report card with remarks from teachers", "school_results"),
    ("Annual academic performance report for 2024", "school_results"),
    ("Transcript showing my academic improvement", "school_results"),
    ("Semester report with grades in all major subjects", "school_results"),
    ("Report card for my high school graduation", "school_results"),
    ("Academic achievement report for a scholarship application", "school_results"),
    ("Performance evaluation for the last school year", "school_results"),
    ("Transcript detailing grades for all science courses", "school_results"),
    ("Grade report with teacher's comments on performance", "school_results"),
    ("Final marks sheet for my graduate school application", "school_results"),

    # Passwords and ID
    ("Securely stored document containing my passport details", "passwords_and_id"),
    ("Encrypted file with login credentials for multiple sites", "passwords_and_id"),
    ("A document listing all my recovery keys and authentication codes", "passwords_and_id"),
    ("Password manager export file for account security", "passwords_and_id"),
    ("A text file with my two-factor authentication backup codes", "passwords_and_id"),
    ("List of credentials used for work-related accounts", "passwords_and_id"),
    ("Scanned image of my driver's license and ID", "passwords_and_id"),
    ("File containing my bank account details and passwords", "passwords_and_id"),
    ("List of login credentials for my online classes", "passwords_and_id"),
    ("Student ID card scanned copy and personal identification", "passwords_and_id"),
    ("A text file with my banking account details and passwords", "passwords_and_id"),
    ("List of my personal email and social media account details", "passwords_and_id"),
    ("Personal file with account IDs and recovery questions", "passwords_and_id"),
    ("Secure file containing my social security number and ID", "passwords_and_id"),
    ("File containing passwords for my work-related logins", "passwords_and_id"),
    ("Backup document with my phone numbers and account PINs", "passwords_and_id"),
    ("Encrypted document with login information for my job portal", "passwords_and_id"),
    ("List of my login credentials for e-commerce websites", "passwords_and_id"),
    ("Secure backup file containing my online bank login", "passwords_and_id"),

    # Assignments
    ("Submitted coursework for programming class", "assignments"),
    ("My essay on environmental sustainability", "assignments"),
    ("Python coding project for machine learning", "assignments"),
    ("Homework questions for algebra", "assignments"),
    ("My essay on climate change", "assignments"),
    ("Completed assignment on linear regression analysis", "assignments"),
    ("Here is my homework on advanced calculus", "assignments"),
    ("My programming assignment for the C++ course", "assignments"),
    ("The essay on the impact of technology on society", "assignments"),
    ("Assignment submission on data privacy and security", "assignments"),
    ("Research paper on the effects of social media on youth", "assignments"),
    ("Group project on renewable energy sources", "assignments"),
    ("Completed assignment on statistical data analysis", "assignments"),
    ("Essay on artificial intelligence ethics", "assignments"),
    ("Assignment on web development using HTML, CSS, and JavaScript", "assignments"),
    ("Research paper on climate change adaptation strategies", "assignments"),
    ("C++ project involving basic file input/output", "assignments"),
    ("Final exam essay on modern educational technologies", "assignments"),
    ("Project on the study of data visualization techniques", "assignments"),
    ("Essay on the impacts of globalization on local economies", "assignments"),

    # Official Documents
    ("My university enrollment letter", "official_documents"),
    ("Receipt for tuition fee payment", "official_documents"),
    ("Certificate of completion for online course", "official_documents"),
    ("Student loan approval document", "official_documents"),
    ("Official letter from the university confirming my enrollment", "official_documents"),
    ("Tuition fee receipt for the current semester", "official_documents"),
    ("Certificate of completion for an online Python course", "official_documents"),
    ("Approval document for my student loan application", "official_documents"),
    ("Official transcript for my courses", "official_documents"),
    ("Letter from the university confirming my graduation", "official_documents"),
    ("Certificate of attendance for the data science workshop", "official_documents"),
    ("Confirmation letter from the university regarding my degree completion", "official_documents"),
    ("Application for student housing with the university", "official_documents"),
    ("Financial aid approval letter", "official_documents"),
    ("Letter of recommendation from a professor", "official_documents"),
    ("Application for student health insurance", "official_documents"),
    ("Admission offer letter from a graduate program", "official_documents"),
    ("Official transcript for the last academic year", "official_documents"),
    ("Proof of health insurance coverage for study abroad", "official_documents")
]

def train_model(force_retrain=False):
    if os.path.exists(MODEL_FILE) and not force_retrain:
        print("Model already exists. Skipping training.")
        return
    print("Training model...")
    random.shuffle(training_data)
    texts, labels = zip(*training_data)
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score
    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42
    )
    model_pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(stop_words='english', ngram_range=(1, 2))),
        ('classifier', LogisticRegression(max_iter=2000))
    ])
    model_pipeline.fit(train_texts, train_labels)
    test_predictions = model_pipeline.predict(test_texts)
    accuracy = accuracy_score(test_labels, test_predictions)
    print(f"Model trained with accuracy: {accuracy:.2%}")
    joblib.dump(model_pipeline, MODEL_FILE)
    print(f"Model saved to {MODEL_FILE}")

train_model(force_retrain=True)
model_pipeline = joblib.load(MODEL_FILE)
print("Model retrained and loaded successfully.")

def clean_text(text):
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()

def classify_file(filepath):
    file_extension = filepath.rsplit('.', 1)[1].lower()
    content = ""
    try:
        if file_extension == 'pdf':
            reader = PdfReader(filepath)
            for page in reader.pages:
                content += page.extract_text() or ""
        elif file_extension == 'txt':
            with open(filepath, 'r', errors='ignore') as file:
                content = file.read()
        elif file_extension == 'docx':
            doc = Document(filepath)
            for paragraph in doc.paragraphs:
                content += paragraph.text
        content = clean_text(content)
        classification = model_pipeline.predict([content])[0]
    except Exception as e:
        print(f"Error scanning file: {e}")
        classification = "study_notes"
    return classification

# ----------------- Logging & Middleware -----------------

def log_action(user_id, username, role, action, page_visited=None, file_name=None):
    cur = mysql.connection.cursor()
    try:
        sql = """
        INSERT INTO access_logs (user_id, username, role, action, page_visited, file_name, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        values = (user_id, username, role, action, page_visited if page_visited else None, file_name if file_name else None)
        cur.execute(sql, values)
        mysql.connection.commit()
    except Exception as e:
        print(f"Error logging action: {e}")
    finally:
        cur.close()

@app.before_request
def log_page_visit():
    if 'role' in session:
        user_id = session.get('user_id', None)
        username = session.get('username', 'Unknown')
        role = session.get('role', 'Unknown')
        route = request.path
        log_action(user_id, username, role, 'Page Visit', route, None)

# ----------------- Routes -----------------

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """Handles file upload, validates file type, and scans for sensitive data."""
    if "user_id" not in session:
        return redirect(url_for("login"))  # Ensure only logged-in users can upload
    user_id = session["user_id"]  # Get the logged-in user's ID
    user_role = session["role"]
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Save temporarily for scanning
            temp_path = os.path.join('static', 'temp_uploads', filename)
            ensure_directory_exists(os.path.dirname(temp_path))
            file.save(temp_path)
            # Scan for sensitive data
            has_sensitive_data, classification = contains_sensitive_data(temp_path)
            if has_sensitive_data:
                # Store as 'Pending Approval' with correct uploaded_by ID
                cur = mysql.connection.cursor()
                cur.execute("""
                    INSERT INTO files (file_name, file_path, uploaded_by, status) 
                    VALUES (%s, %s, %s, %s)
                """, (filename, os.path.join('temp_uploads', filename), user_id, 'Pending Approval'))
                mysql.connection.commit()
                cur.close()
                flash('The file contains sensitive data and is awaiting admin approval.')
                username = session.get('username', 'Unknown')
                log_action(user_id, username, user_role, "Sensitive File Uploaded", None, filename)
                if 'alerts' not in session:
                    session['alerts'] = []
                session['alerts'].append('A sensitive file has been uploaded and needs approval.')
                return redirect(request.url)
            else:
                try:
                    username = session.get('username', 'Unknown')
                    log_action(user_id, username, user_role, "File Uploaded", None, filename)
                except:
                    flash("Failed to log upload action.")
                # Move to permanent storage
                permanent_folder_path = os.path.join('static', 'uploads')
                ensure_directory_exists(permanent_folder_path)
                file_path = os.path.join(permanent_folder_path, filename)
                os.rename(temp_path, file_path)
                # Save as 'Public' with correct uploaded_by ID
                cur = mysql.connection.cursor()
                cur.execute("""
                    INSERT INTO files (file_name, file_path, uploaded_by, status) 
                    VALUES (%s, %s, %s, %s)
                """, (filename, os.path.join('uploads', filename), user_id, 'Public'))
                mysql.connection.commit()
                cur.close()
                flash(f'File "{filename}" uploaded successfully as Public.')
                return redirect(url_for('upload_file'))
        else:
            flash('File type not allowed')
            username = session.get('username', 'Unknown')
            log_action(user_id, username, user_role, "Failed File Upload Attempt", None)
            return redirect(request.url)

    return render_template('upload.html')

# Community Upload Route (combined with new community post creation)
@app.route('/community_upload', methods=['GET', 'POST'])
def community_upload():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    if request.method == 'POST':
        # Check required file and post data
        if 'file' not in request.files:
            flash('No file provided.')
            return redirect(request.url)
        file = request.files['file']
        manual_class = request.form.get('manual_class')
        post_title = request.form.get('post_title')
        post_content = request.form.get('post_content')
        if not manual_class or not post_title or not post_content:
            flash("Please fill out all fields: classification, title, and description.")
            return redirect(request.url)
        if file.filename == '':
            flash('No file selected.')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Save file temporarily for community uploads
            temp_path = os.path.join(app.config['TEMP_COMM_UPLOAD_FOLDER'], filename)
            ensure_directory_exists(os.path.dirname(temp_path))
            file.save(temp_path)
            auto_class = classify_file(temp_path)
            # If auto classification does not match student's selection, prompt for decision.
            if auto_class != manual_class:
                return render_template("community_reclassify.html",
                                       filename=filename,
                                       manual_class=manual_class,
                                       auto_class=auto_class,
                                       post_title=post_title,
                                       post_content=post_content)
            else:
                status = "Public"
                flash(f"File successfully classified as '{manual_class}' and posted to community blog.")
                # Move file to permanent community uploads
                permanent_path = os.path.join(app.config['COMM_UPLOAD_FOLDER'], filename)
                ensure_directory_exists(app.config['COMM_UPLOAD_FOLDER'])
                os.rename(temp_path, permanent_path)
                relative_path = os.path.join('community_uploads', filename)
            # Insert file info into files table and get its ID for preview link.
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO files (file_name, file_path, uploaded_by, status, classification)
                VALUES (%s, %s, %s, %s, %s)
            """, (filename, relative_path, user_id, status, manual_class))
            mysql.connection.commit()
            file_id = cur.lastrowid
            cur.close()
            # Create a preview link and embed file details into the post content.
            preview_link = ("<br><br><strong>File Posted:</strong> " + filename +
                            " - <a href='" + url_for('view_file', file_id=file_id) +
                            "' target='_blank'>Preview File</a>")
            post_content_with_file = post_content + preview_link
            cur = mysql.connection.cursor()
            cur.execute("""
                INSERT INTO community_posts (title, content, author_id)
                VALUES (%s, %s, %s)
            """, (post_title, post_content_with_file, user_id))
            mysql.connection.commit()
            cur.close()
            log_action(user_id, session.get('username','Unknown'), session.get('role','Unknown'),
                      "Community File Uploaded & Post Created", None, filename)
            return redirect(url_for('community_upload'))
        else:
            flash("File type not allowed.")
            return redirect(request.url)
    return render_template('community_upload.html')


# Route to process decision if classification mismatches (student must reclassify or accept auto)
@app.route('/community_decision', methods=['POST'])
def community_decision():
    decision = request.form.get("decision")
    filename = request.form.get("filename")
    manual_class = request.form.get("manual_class")
    auto_class = request.form.get("auto_class")
    post_title = request.form.get("post_title")
    post_content = request.form.get("post_content")
    user_id = session["user_id"]
    temp_path = os.path.join(app.config["TEMP_COMM_UPLOAD_FOLDER"], filename)
    if decision == "accept_auto":
        permanent_path = os.path.join(app.config["COMM_UPLOAD_FOLDER"], filename)
        ensure_directory_exists(app.config["COMM_UPLOAD_FOLDER"])
        if os.path.exists(temp_path):
            os.rename(temp_path, permanent_path)
        relative_path = os.path.join("community_uploads", filename)
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO files (file_name, file_path, uploaded_by, status, classification)
            VALUES (%s, %s, %s, %s, %s)
        """, (filename, relative_path, user_id, "Public", auto_class))
        mysql.connection.commit()
        file_id = cur.lastrowid
        cur.close()
        # Append file preview link to post content.
        preview_link = ("<br><br><strong>File Posted:</strong> " + filename +
                        " - <a href='" + url_for('view_file', file_id=file_id) +
                        "' target='_blank'>Preview File</a>")
        post_content_with_file = post_content + preview_link
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO community_posts (title, content, author_id)
            VALUES (%s, %s, %s)
        """, (post_title, post_content_with_file, user_id))
        mysql.connection.commit()
        cur.close()
        flash(f'File accepted with system classification: {auto_class} and posted to community blog.')
        log_action(user_id, session.get('username','Unknown'), session.get('role','Unknown'),
                   "Community Decision Accepted", None, filename)
        return redirect(url_for("community_upload"))
    elif decision == "reclassify":
        if os.path.exists(temp_path):
            os.remove(temp_path)
        flash("Please reclassify your file and upload again.")
        log_action(user_id, session.get('username','Unknown'), session.get('role','Unknown'),
                   "Community Decision Reclassified", None, filename)
        return redirect(url_for("community_upload"))
    else:
        flash("Invalid decision.")
        return redirect(url_for("community_upload"))



# ----------------- Community Posts & Comments Routes -----------------

def partial_mask_sensitive_data(text: str) -> str:
    """
    Masks NRIC and phone numbers so that only the last few digits/characters remain visible.
    E.g., S1234567D -> *****567D (keep last 4 chars), 91234567 -> ****4567 (keep last 4 digits).
    """
    if not text:
        return text

    # Mask NRIC (S1234567D -> *****567D)
    nric_pattern = r'(?i)\b[STFG]\d{7}[A-Z]\b'
    def replace_nric(match):
        nric = match.group(0)
        # Keep last 4 chars (e.g., '567D'), replace the rest with '*'
        masked_part = '*' * (len(nric) - 4) + nric[-4:]
        return masked_part

    masked_text = re.sub(nric_pattern, replace_nric, text)

    # Mask phone numbers (91234567 -> ****4567, +65 91234567 -> +65 ****4567)
    phone_pattern = r'(\+65\s?)?(\d{4})(\d{4})'
    def replace_phone(match):
        prefix = match.group(1) if match.group(1) else ""
        first_four = match.group(2)
        last_four = match.group(3)
        # Replace the first 4 digits with asterisks, keep the last 4
        return f"{prefix}{'*' * len(first_four)}{last_four}"

    masked_text = re.sub(phone_pattern, replace_phone, masked_text)

    return masked_text


def mask_for_role(text: str, user_role: str) -> str:
    """
    If user is 'admin', return the original text; otherwise, partially mask it.
    """
    if user_role == 'admin':
        return text
    else:
        return partial_mask_sensitive_data(text)



# List all community posts in a blog-style page
@app.route('/community_posts')
def community_posts():
    user_role = session.get('role', 'student')  # default to 'student' if not logged in

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT cp.id, cp.title, cp.content, cp.created_at, u.username 
        FROM community_posts cp 
        JOIN users u ON cp.author_id = u.id 
        ORDER BY cp.created_at DESC
    """)
    raw_posts = cur.fetchall()
    cur.close()

    masked_posts = []
    for post in raw_posts:
        post_id, title, content, created_at, author_name = post
        # Mask title/content unless user_role == 'admin'
        masked_title = mask_for_role(title, user_role)
        masked_content = mask_for_role(content, user_role)
        masked_posts.append((post_id, masked_title, masked_content, created_at, author_name))

    return render_template('community_posts.html', posts=masked_posts)

# Create a new community post
@app.route('/community_posts/new', methods=['GET', 'POST'])
def new_community_post():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        title = request.form.get("title")
        content = request.form.get("content")
        if not title or not content:
            flash("Title and content are required.")
            return redirect(request.url)
        user_id = session["user_id"]
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO community_posts (title, content, author_id) VALUES (%s, %s, %s)", (title, content, user_id))
        mysql.connection.commit()
        cur.close()
        log_action(user_id, session.get('username','Unknown'), session.get('role','Unknown'),
                   "Community Post Created", None, title)
        flash("Community post created successfully.")
        return redirect(url_for("community_posts"))
    return render_template("community_upload.html")

# View a single community post along with its comments; allow adding comments
@app.route('/community_posts/<int:post_id>', methods=['GET', 'POST'])
def view_community_post(post_id):
    user_role = session.get('role', 'student')

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT cp.id, cp.title, cp.content, cp.created_at, u.username 
        FROM community_posts cp 
        JOIN users u ON cp.author_id = u.id 
        WHERE cp.id = %s
    """, (post_id,))
    post_data = cur.fetchone()
    if not post_data:
        flash("Post not found.")
        return redirect(url_for("community_posts"))

    cur.execute("""
        SELECT c.id, c.content, c.created_at, u.username 
        FROM comments c 
        JOIN users u ON c.author_id = u.id 
        WHERE c.post_id = %s 
        ORDER BY c.created_at ASC
    """, (post_id,))
    comments_data = cur.fetchall()

    # Handle new comment
    if request.method == "POST":
        comment_text = request.form.get("comment")
        ...
        # Insert comment
        ...
        return redirect(request.url)

    cur.close()

    # Mask the post
    post_id, title, content, created_at, author_name = post_data
    masked_title = mask_for_role(title, user_role)
    masked_content = mask_for_role(content, user_role)
    masked_post = (post_id, masked_title, masked_content, created_at, author_name)

    # Mask each comment
    masked_comments = []
    for c in comments_data:
        c_id, c_content, c_created_at, c_author_name = c
        masked_c_content = mask_for_role(c_content, user_role)
        masked_comments.append((c_id, masked_c_content, c_created_at, c_author_name))

    return render_template("view_community_post.html", post=masked_post, comments=masked_comments)

# Delete a community post (allowed for admin & student)
@app.route('/community_posts/delete/<int:post_id>', methods=['POST'])
def delete_community_post(post_id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    role = session.get('role')
    if role not in ['admin', 'student']:
        flash("You do not have permission to delete posts.")
        return redirect(url_for("community_posts"))
    cur = mysql.connection.cursor()
    cur.execute("SELECT title FROM community_posts WHERE id = %s", (post_id,))
    post = cur.fetchone()
    if not post:
        flash("Post not found.")
        return redirect(url_for("community_posts"))
    cur.execute("DELETE FROM community_posts WHERE id = %s", (post_id,))
    mysql.connection.commit()
    cur.close()
    log_action(session.get('user_id'), session.get('username','Unknown'), role, "Community Post Deleted", None, post[0])
    flash("Post deleted successfully.")
    return redirect(url_for("community_posts"))

# ----------------- Other Routes (Audit Logs, Admin, Files, Login, etc.) -----------------

@app.route('/audit_logs')
def audit_logs():
    if session.get('role') != 'admin':
        flash('Unauthorized access!')
        return redirect(url_for('home'))
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            SELECT id, username, role, action, page_visited, file_name, timestamp 
            FROM access_logs 
            ORDER BY timestamp DESC
        """)
        ALLOWED_ROUTES = {"/upload", "/audit_logs", "/clear_audit_logs", "/admin",
                          "/admin/preview/<int:file_id>", "/files", "/view_file/<int:file_id>", "/login", "/logout", "/", "/community_upload","/community_posts","/community_posts/<int:post_id>"}
        logs = [
            {"id": row[0], "username": row[1], "role": row[2], "action": row[3],
             "route": row[4] if row[3] == "Page Visit" and row[4] in ALLOWED_ROUTES else None,
             "file": row[5] if "File" in row[3] else None,
             "timestamp": row[6]}
            for row in cur.fetchall()
            if row[3] != "Page Visit" or (row[3] == "Page Visit" and row[4] in ALLOWED_ROUTES)
        ]
    except Exception as e:
        print(f"Error fetching logs: {e}")
        logs = []
    finally:
        cur.close()
    return render_template('audit_logs.html', logs=logs)

@app.route('/clear_audit_logs', methods=['POST'])
def clear_audit_logs():
    if session.get('role') != 'admin':
        flash('Unauthorized access!')
        return redirect(url_for('home'))
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM access_logs")
    mysql.connection.commit()
    cur.close()
    flash('All audit logs have been cleared successfully.')
    return redirect(url_for('audit_logs'))


@app.route('/admin', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('role') != 'admin':
        flash('Unauthorized access!')
        return redirect(url_for('login'))

    # Get current admin info for logging
    user_id = session.get('user_id')
    username = session.get('username', 'Unknown')
    role = session.get('role', 'Unknown')

    cur = mysql.connection.cursor()
    if request.method == 'POST':
        file_id = request.form.get('file_id')
        action = request.form.get('action')

        if action not in ['approve', 'reject']:
            flash('Invalid action!')
            return redirect(url_for('admin_dashboard'))

        if action == 'approve':
            # Query file_name and file_path
            cur.execute("SELECT file_name, file_path FROM files WHERE id = %s", (file_id,))
            file_data = cur.fetchone()
            if not file_data:
                flash('File not found!')
                return redirect(url_for('admin_dashboard'))

            filename, temp_file_path = file_data
            perm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            if os.path.exists(os.path.join(app.static_folder, temp_file_path)):
                ensure_directory_exists(app.config['UPLOAD_FOLDER'])
                os.rename(os.path.join(app.static_folder, temp_file_path), perm_file_path)
                # Update the file status to "Confidential"
                cur.execute("""
                    UPDATE files 
                    SET status = 'Confidential', file_path = %s 
                    WHERE id = %s
                """, (os.path.join('uploads', filename), file_id))
                mysql.connection.commit()

                flash('File approved as Confidential.')

                # Log the approval
                log_action(user_id, username, role, "Approved File", None, filename)
            else:
                flash('File does not exist in temporary folder.')

        elif action == 'reject':
            # Query file_name and file_path
            cur.execute("SELECT file_name, file_path FROM files WHERE id = %s", (file_id,))
            file_data = cur.fetchone()
            if not file_data:
                flash('File not found!')
                return redirect(url_for('admin_dashboard'))

            filename, temp_file_path = file_data
            temp_file_path_full = os.path.join(app.static_folder, temp_file_path)

            if os.path.exists(temp_file_path_full):
                os.remove(temp_file_path_full)

            # Update the file status to "Rejected"
            cur.execute("UPDATE files SET status = 'Rejected' WHERE id = %s", (file_id,))
            mysql.connection.commit()

            flash('File rejected and deleted.')

            # Log the rejection
            log_action(user_id, username, role, "Rejected File", None, filename)

        cur.close()
        return redirect(url_for('admin_dashboard'))

    # For GET requests: show pending files
    cur.execute("SELECT * FROM files WHERE status = 'Pending Approval'")
    files = cur.fetchall()
    cur.close()

    return render_template('admin.html', files=files)


@app.route('/clear_all_alerts', methods=['POST'])
def clear_all_alerts():
    if session.get('role') != 'admin':
        flash('Unauthorized access!')
        return redirect(url_for('home'))
    session.pop('alerts', None)
    return redirect(request.referrer)

@app.route('/files')
def files():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    user_role = session["role"]

    cur = mysql.connection.cursor()

    if user_role == "admin":
        # Admin sees all files
        # Also join to users table to get role
        query = """
            SELECT f.id, f.file_name, f.file_path, f.uploaded_by, f.uploaded_at, 
                   f.status, f.uploaded_time, f.classification, u.role
            FROM files f
            JOIN users u ON f.uploaded_by = u.id
            WHERE f.status IN ('Confidential', 'Public', 'Pending Approval')
        """
        cur.execute(query)
    elif user_role == "staff":
        # Example logic: staff sees files from staff or students
        query = """
            SELECT f.id, f.file_name, f.file_path, f.uploaded_by, f.uploaded_at, 
                   f.status, f.uploaded_time, f.classification, u.role
            FROM files f
            JOIN users u ON f.uploaded_by = u.id
            WHERE u.role IN ('staff','student')
              AND f.status IN ('Confidential','Public','Pending Approval')
        """
        cur.execute(query)
    else:
        # Student sees only their own files
        query = """
            SELECT f.id, f.file_name, f.file_path, f.uploaded_by, f.uploaded_at, 
                   f.status, f.uploaded_time, f.classification, u.role
            FROM files f
            JOIN users u ON f.uploaded_by = u.id
            WHERE f.uploaded_by = %s
        """
        cur.execute(query, (user_id,))

    all_files = cur.fetchall()
    cur.close()

    # Build updated_files with the needed info
    updated_files = []
    for row in all_files:
        # row = (id, file_name, file_path, uploaded_by, uploaded_at, status, uploaded_time, classification, uploader_role)
        row_list = list(row)
        file_name = row_list[1]
        file_path = row_list[2]
        status    = row_list[5]
        # Adjust file path for display
        if status in ['Public', 'Confidential']:
            # point to "uploads"
            row_list[2] = url_for('static', filename='uploads/' + file_path.split(os.sep)[-1])
        elif status == 'Pending Approval':
            # point to "temp_uploads"
            row_list[2] = url_for('static', filename='temp_uploads/' + file_path.split(os.sep)[-1])
        updated_files.append(row_list)

    return render_template('files.html', files=updated_files)



@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    try:
        user_id = session.get('user_id')
        username = session.get('username', 'Unknown')
        role = session.get('role', 'Unknown')
        with mysql.connection.cursor() as cursor:
            cursor.execute("SELECT file_path FROM files WHERE id = %s", (file_id,))
            file = cursor.fetchone()
            if file:
                relative_file_path = file[0]
                file_name = os.path.basename(relative_file_path)
                base_upload_path = os.path.abspath("static/uploads")
                file_path = os.path.join(base_upload_path, file_name)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                        flash("File deleted successfully from filesystem!", "success")
                    except OSError as e:
                        flash(f"Error deleting file from disk: {str(e)}", "error")
                        return redirect(url_for('files'))
                else:
                    flash(f"File not found on filesystem: {file_path}", "error")
                cursor.execute("DELETE FROM files WHERE id = %s", (file_id,))
                mysql.connection.commit()
                log_action(user_id, username, role, "File Deleted", None, file_name)
            else:
                flash("File not found in database!", "error")
    except Exception as e:
        mysql.connection.rollback()
        flash(f"Error deleting file: {str(e)}", "error")
    return redirect(url_for('files'))

@app.route('/view_file/<int:file_id>')
def view_file(file_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", [file_id])
    file_data = cur.fetchone()
    cur.close()
    if file_data:
        # Unpack columns: id, file_name, file_path, uploaded_by, uploaded_at, status, uploaded_time, classification
        file_name = file_data[1]
        file_path = file_data[2]
        status = file_data[5]
        uploaded_by = file_data[3]
        classification = file_data[7]
        user_id = session.get('user_id', None)
        username = session.get('username', 'Guest')
        role = session.get('role', 'Guest')
        # If file is classified as passwords_and_id, only the uploader can view it.
        if classification == "passwords_and_id" and session.get('user_id') != uploaded_by:
            return "You do not have permission to view this file.", 403
        # Allow admin to preview even if pending
        if status == 'Pending Approval' and role != 'admin':
            log_action(user_id, username, role, "File Access Attempt", None, file_name)
            return "This file is awaiting approval."
        if status == 'Confidential' and role != 'admin':
            log_action(user_id, username, role, "Unauthorized File Access Attempt", None, file_name)
            return f"You do not have permission to view this file. {role}", 403
        # Always construct full path relative to the static folder
        full_file_path = os.path.join(app.static_folder, file_path)
        if os.path.exists(full_file_path):
            log_action(user_id, username, role, "File Viewed", None, file_name)
            if file_name.endswith('.pdf'):
                if status == 'Confidential':
                    return render_template("pdf_viewer.html", pdf_url=f"/static/{file_path}")
                else:
                    return send_file(full_file_path, as_attachment=True)
            else:
                return send_file(full_file_path, as_attachment=True)
        else:
            return "File not found.", 404
    return "File not found", 404



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, username, role, password_hash FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and password == user[3]:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[2]
            log_action(user[0], user[1], user[2], "User Login")
            if user[2] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user[2] == 'staff':
                return redirect(url_for('upload_file'))
            else:
                return redirect(url_for('community_posts'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    username = session.get('username', 'Unknown')
    role = session.get('role', 'Unknown')

    # Log the logout action
    log_action(user_id, username, role, "User Logout")

    # Clear session data
    session.pop('role', None)
    session.pop('user_id', None)
    session.pop('username', None)

    flash('You have been logged out.')
    return redirect(url_for('home'))


@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large_error(error):
    flash('File is too large! The maximum allowed size is 10MB.')
    return redirect(request.url)



@app.route('/')
def home():
    if 'role' not in session:
        return redirect(url_for('login'))
    else:
        flash('What would you like to do today? ')
        return render_template('home.html')



if __name__ == '__main__':
    app.run(debug=True)
