import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask_mysqldb import MySQL
import pytesseract  # For OCR (Image to text)
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

# Update this part in your app configuration
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')  # Permanent storage in static folder
app.config['TEMP_UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'temp_uploads')  # Temporary folder for admin review


app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # Limit to 10MB
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'png', 'jpg', 'txt', 'csv'}

# Initialize MYSQL
mysql = MySQL(app)

# Utility function to check allowed file extensions
def allowed_file(filename):
    """Check if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Function to check for sensitive data in files
def contains_sensitive_data(file_path):
    """Checks file content for sensitive data (e.g., student ID numbers, confidential info)."""
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
# Route: File upload
# Route: File upload
# Route: File upload
# Route: File upload
# Route: File upload
# Function to ensure directory exists
# Function to ensure directory exists
def ensure_directory_exists(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


# Route: File upload
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

            # Save the file temporarily before scanning for sensitive data
            temp_path = os.path.join('static', 'temp_uploads', filename)  # Temp file location
            ensure_directory_exists(os.path.dirname(temp_path))  # Ensure temp directory exists
            file.save(temp_path)

            # Now, pass the file path to the contains_sensitive_data function
            has_sensitive_data, classification = contains_sensitive_data(temp_path)

            # If sensitive data is found, save to the database for approval
            if has_sensitive_data:
                # Log the file upload attempt
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO files (file_name, file_path, uploaded_by, status) VALUES (%s, %s, %s, %s)",
                            (filename, os.path.join('temp_uploads', filename), 1, 'Pending Approval'))  # Store relative path
                mysql.connection.commit()
                cur.close()

                flash(f'The file contains sensitive data and is awaiting admin approval for classification.')
                return redirect(request.url)
            else:
                # Ensure the permanent uploads directory exists
                permanent_folder_path = os.path.join('static', 'uploads')
                ensure_directory_exists(permanent_folder_path)  # Ensure permanent folder exists

                # If file is Public, store it in static/uploads
                file_path = os.path.join(permanent_folder_path, filename)  # Public file location
                os.rename(temp_path, file_path)  # Move file to permanent folder

                # Save file record to DB as Public
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO files (file_name, file_path, uploaded_by, status) VALUES (%s, %s, %s, %s)",
                            (filename, os.path.join('uploads', filename), 1, 'Public'))  # Store relative path
                mysql.connection.commit()
                cur.close()

                flash(f'File "{filename}" uploaded successfully as Public.')
                return redirect(url_for('upload_file'))

        else:
            flash('File type not allowed')
            return redirect(request.url)

    return render_template('upload.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if session.get('role') != 'admin':
        flash('Unauthorized access!')
        return redirect(url_for('login'))

    # Fetch files with 'Pending Approval' status
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE status = 'Pending Approval'")
    files_to_approve = cur.fetchall()
    cur.close()

    if request.method == 'POST':
        file_id = request.form['file_id']
        action = request.form['action']

        # Ensure action is valid (either approve or reject)
        if action not in ['approve', 'reject']:
            flash('Invalid action!')
            return redirect(url_for('admin'))

        cur = mysql.connection.cursor()

        if action == 'approve':
            # Get file info from the database
            cur.execute("SELECT file_name, file_path FROM files WHERE id = %s", [file_id])
            file_data = cur.fetchone()
            if not file_data:
                flash('File not found!')
                return redirect(url_for('admin'))

            filename = file_data[0]
            temp_file_path = file_data[1]
            perm_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # Check if the file exists in the temporary folder
            if os.path.exists(os.path.join(app.static_folder, temp_file_path)):
                # Ensure the destination folder exists
                ensure_directory_exists(app.config['UPLOAD_FOLDER'])

                # Move the file from temp to permanent folder
                os.rename(os.path.join(app.static_folder, temp_file_path), perm_file_path)

                # Update file status in the database to 'Confidential' (or 'Public', depending on your rules)
                cur.execute("UPDATE files SET status = 'Confidential', file_path = %s WHERE id = %s", [os.path.join('uploads', filename), file_id])
                mysql.connection.commit()

                flash('File approved as Confidential.')
            else:
                flash('File does not exist in temporary folder.')

        elif action == 'reject':
            # Get file path from the database
            cur.execute("SELECT file_path FROM files WHERE id = %s", [file_id])
            file_data = cur.fetchone()
            if not file_data:
                flash('File not found!')
                return redirect(url_for('admin'))

            temp_file_path = file_data[0]

            # Delete the rejected file from temp folder
            temp_file_path_full = os.path.join(app.static_folder, temp_file_path)
            if os.path.exists(temp_file_path_full):
                os.remove(temp_file_path_full)

            # Update file status to 'Rejected' in the database
            cur.execute("UPDATE files SET status = 'Rejected' WHERE id = %s", [file_id])
            mysql.connection.commit()

            flash('File rejected and deleted.')

        cur.close()
        return redirect(url_for('admin'))

    return render_template('admin.html', files=files_to_approve)
# Route: Admin Preview (before approval/rejection)
@app.route('/admin/preview/<int:file_id>')
def preview_file(file_id):
    """Allow admin to preview the file before approval/rejection."""
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, file_path, status FROM files WHERE id = %s", (file_id,))
    file_data = cur.fetchone()
    cur.close()

    if not file_data:
        flash('File not found!')
        return redirect(url_for('admin'))

    file_name, file_path, status = file_data

    # Construct the full file path depending on the file's status
    if status == 'Pending Approval':
        # File is in temp_uploads if it is pending approval
        full_file_path = os.path.join(app.static_folder, file_path)  # Ensure this path is joined correctly
    elif status == 'Confidential' or status == 'Public':
        # Approved files (Confidential/Public) are in uploads
        full_file_path = os.path.join(app.static_folder, 'uploads', file_path)  # Files are in the uploads folder
    else:
        flash('Invalid file status!')
        return redirect(url_for('admin'))

    if not os.path.exists(full_file_path):
        flash('File not found!')
        return redirect(url_for('admin'))

    return send_file(full_file_path, as_attachment=False)


@app.route('/files')
def files():
    """Displays all uploaded files with their status (Confidential/Public/Pending Approval)."""
    cur = mysql.connection.cursor()

    # Query to select files that are either 'Confidential', 'Public', or 'Pending Approval'
    cur.execute("SELECT * FROM files WHERE status IN ('Confidential', 'Public', 'Pending Approval')")
    all_files = cur.fetchall()

    cur.close()

    updated_files = []
    for file in all_files:
        file_data = list(file)  # Convert tuple to list for modification
        file_name = file_data[1]  # Assuming index 1 is file_name
        file_path = file_data[2]  # Assuming index 2 is file_path
        status = file_data[5]     # Assuming index 5 is status

        # Update the file path based on the status
        if status == 'Public' or status == 'Confidential':
            # For approved files, adjust the file path to start from "uploads" folder
            file_data[2] = url_for('static', filename='uploads/' + file_path.split(os.sep)[-1])  # Correct the path here
        elif status == 'Pending Approval':
            # Pending approval files should have their file path in temp_uploads
            file_data[2] = url_for('static', filename='temp_uploads/' + file_path.split(os.sep)[-1])

        updated_files.append(file_data)  # Add modified file to updated list

    return render_template('files.html', files=updated_files)



# Route: View a specific file (after approval)
@app.route('/view_file/<int:file_id>')
def view_file(file_id):
    """View a file based on its ID."""
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files WHERE id = %s", [file_id])
    file_data = cur.fetchone()
    cur.close()

    if file_data:
        file_name, file_path, status = file_data[1], file_data[2], file_data[5]

        # Check if the file is pending approval, and show a message
        if status == 'Pending Approval':
            return "This file is awaiting approval."

        # If the file is approved, construct the correct full file path
        if status == 'Confidential' or status == 'Public':
            # Ensure file_path starts with 'uploads' if not already
            if not file_path.startswith('uploads'):
                full_file_path = os.path.join(app.static_folder, 'uploads', file_path)
            else:
                full_file_path = os.path.join(app.static_folder, file_path)

        else:
            return "File not found", 404

        # If the file exists, send it as a response
        if os.path.exists(full_file_path):
            return send_file(full_file_path, as_attachment=True)  # Send file as download
        else:
            return "File not found", 404

    return "File not found", 404


# Temporary login route (for testing purposes)
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with session management (placeholder)"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == 'admin' and password == '123':
            session['role'] = 'admin'
            return redirect(url_for('admin'))
        elif username == 'staff' and password == '123':
            session['role'] = 'staff'
            return redirect(url_for('upload_file'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))

    return render_template('login.html')

# Logout Route
@app.route('/logout')
def logout():
    """Logs out the current user."""
    session.pop('role', None)
    flash('You have been logged out.')
    return redirect(url_for('home'))

# Error handler for file size exceedance
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large_error(error):
    flash('File is too large! The maximum allowed size is 10MB.')
    return redirect(request.url)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
