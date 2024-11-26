from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import firebase_admin
from firebase_admin import auth, credentials, firestore, storage

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Set a secret key for session management

# Initialize Firebase Admin SDK
cred = credentials.Certificate("launchpilot-e4bf7-firebase-adminsdk-3ex0e-e1f83b0889.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'launchpilot-e4bf7.appspot.com'  # Update with your actual bucket name
})

# Initialize Firestore and Firebase Storage
db = firestore.client()
bucket = storage.bucket()  # Initialize the storage bucket

@app.route('/')
def home():
    return redirect(url_for('signup_page'))

@app.route('/signup', methods=['GET', 'POST'])
def signup_page():
    if request.method == 'POST':
        name = request.form['name']  # Get the name
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return jsonify({"error": "Passwords do not match"}), 400

        try:
            # Create a new user in Firebase
            user = auth.create_user(email=email, password=password)

            # Store user data in Firestore
            user_data = {
                'name': name,
                'email': email,
            }
            db.collection('users').document(user.uid).set(user_data)  # Store the user's name and email

            # Store the user's name and email in the session
            session['username'] = name
            session['user_email'] = email

            return redirect(url_for('dashboard'))
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            # Authenticate the user using Firebase Authentication
            user = auth.get_user_by_email(email)

            # Retrieve user data from Firestore
            user_doc = db.collection('users').document(user.uid).get()
            if user_doc.exists:
                user_data = user_doc.to_dict()
                session['username'] = user_data['name']  # Store the username in session
                session['user_email'] = user_data['email']  # Optionally store email

                return redirect(url_for('dashboard'))
            else:
                return jsonify({"error": "User data not found in Firestore"}), 400

        except Exception as e:
            return jsonify({"error": str(e)}), 400

    return render_template('login.html')

@app.route('/auth/google', methods=['POST'])
def google_auth():
    token = request.json.get('id_token')

    try:
        # Verify the token with Firebase
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token['uid']
        email = decoded_token['email']

        # Check if the user already exists in your Firestore database
        user_doc = db.collection('users').document(uid).get()

        if not user_doc.exists:
            # Create a new record for the user if it doesn't exist
            user_data = {
                'name': email.split('@')[0],  # Use the part before '@' as the default name
                'email': email,
            }
            db.collection('users').document(uid).set(user_data)

        # Store user data in the session
        session['username'] = user_data['name']
        session['user_email'] = email

        return jsonify({"status": "success", "uid": uid, "email": email}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/dashboard')
def dashboard():
    username = session.get('username', 'Guest')  # Get the username or default to 'Guest'
    user_email = session['user_email']
    
    print(f"Username: {username}, User Email: {user_email}")  # Debugging line
    
    # Retrieve user projects
    user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()
    user_projects = []
    
    if user_doc:
        user_id = user_doc[0].id  # Get the user's Firestore document ID
        projects = db.collection('projects').document(user_id).collection('user_projects').get()
        
        for project in projects:
            project_data = project.to_dict()
            project_data['id'] = project.id  # Include the project ID
            user_projects.append(project_data)
        
        print(f"User Projects: {user_projects}")  # Debugging line
    else:
        print("User document not found.")  # Debugging line

    return render_template('dashboard.html', username=username, projects=user_projects)


@app.route('/project/<project_name>', methods=['GET'])
def project_details(project_name):
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "User not logged in"}), 401

        user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()

        if user_doc:
            user_id = user_doc[0].id
            user_projects_ref = db.collection('projects').document(user_id).collection('user_projects')
            project_doc = user_projects_ref.where('name', '==', project_name).limit(1).get()

            if project_doc:
                project = project_doc[0].to_dict()
                project['id'] = project_doc[0].id

                # Fetch posts related to the project
                user_posts_ref = db.collection('projects').document(user_id).collection('user_posts')
                posts_query = user_posts_ref.where('project_name', '==', project_name).stream()

                posts = []
                for post in posts_query:
                    post_dict = post.to_dict()
                    if post_dict not in posts:  # Avoid duplicates
                        posts.append(post_dict)

                # Debugging output
                print(f"Unique Posts for project '{project_name}' by user '{user_id}':")
                for post in posts:
                    print(post)

                return render_template('project_details.html', project=project, posts=posts)
            else:
                return jsonify({"error": "Project not found"}), 404
        else:
            return jsonify({"error": "User document not found"}), 404

    except Exception as e:
        app.logger.error(f"Error retrieving project details: {e}")
        return jsonify({"error": "Internal server error"}), 500




    # Get user details from the session
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    print(f"User Email: {user_email}")  # Debugging line

    # Retrieve the user document to get the user ID
    user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()
    
    if user_doc:
        user_id = user_doc[0].id  # Get the user's Firestore document ID
        print(f"User ID: {user_id}")  # Debugging line
        
        # Reference to the user's project collection
        user_projects_ref = db.collection('projects').document(user_id).collection('user_projects')

        # Query projects with the given name (case insensitive)
        projects = user_projects_ref.where('name', '==', project_name).stream()

        # Initialize a variable to hold the found project
        project = None

        # Debugging: Check the project_name before querying
        print("Debug: Searching for project with name:", project_name)

        # Iterate over the retrieved projects
        for proj in projects:
            project = proj.to_dict()
            project['id'] = proj.id  # Include the project ID for reference
            print("Debug: Found project:", project)  # Debugging output
            break  # Stop after finding the first match

        # If a project was found, render the template
        if project:
            print("Debug: Returning project details for:", project_name)  # Debugging output
            return render_template('project_details.html', project=project)
        else:
            print("Debug: Project not found for name:", project_name)  # Debugging output
            return jsonify({"error": "Project not found"}), 404
    else:
        print("User document not found.")  # Debugging line
        return jsonify({"error": "User document not found"}), 404

@app.route('/add_project', methods=['POST'])
def add_project():
    if 'username' not in session:
        return jsonify({"error": "User not logged in"}), 401

    project_name = request.form.get('projectName')
    project_link = request.form.get('projectLink')
    survey_link = request.form.get('surveyLink')
    category = request.form.get('category')
    project_image = request.files.get('projectImage')  # Get the image file from the request
    project_description = request.form.get('projectDescription')

    if not all([project_name, project_link, survey_link, category, project_image, project_description]):
        return jsonify({"error": "All fields are required"}), 400

    # Upload the image to Firebase Storage
    try:
        # Create a unique filename for the image
        image_filename = project_image.filename
        blob = bucket.blob(f'project_images/{image_filename}')  # Define a path in Firebase Storage
        blob.upload_from_file(project_image)  # Upload the file

        # Get the public URL of the uploaded image
        project_image_url = blob.public_url

        # Store project data in Firestore under the user's document
        user_email = session['user_email']
        user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()

        if user_doc:
            user_id = user_doc[0].id  # Get the user's Firestore document ID
            project_data = {
                'name': project_name,
                'project_description': project_description,  # Description is included here
                'link': project_link,
                'survey_link': survey_link,
                'category': category,
                'image_url': project_image_url
            }

            # Add to user's projects
            db.collection('projects').document(user_id).collection('user_projects').add(project_data)

            # Also add to the community collection
            community_project_data = {
                'user_id': user_id,  # Include user ID for reference
                **project_data  # Spread project_data to include all fields
            }
            db.collection('community_projects').add(community_project_data)

            return jsonify({"status": "success", "message": "Project added successfully!"}), 200
        else:
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/user_projects', methods=['GET'])
def user_projects():
    if 'username' not in session:
        return jsonify({"error": "User not logged in"}), 401

    user_email = session['user_email']
    user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()

    if user_doc:
        user_id = user_doc[0].id  # Get the user's Firestore document ID
        projects = db.collection('projects').document(user_id).collection('user_projects').get()
        
        user_projects = [proj.to_dict() for proj in projects]  # Convert documents to dictionaries
        return jsonify(user_projects), 200
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/logout')
def logout():
    session.clear()  # Clear the session
    return redirect(url_for('home'))

@app.route('/project/<project_name>/editor')
def project_editor(project_name):
    return render_template('editor.html', project_name=project_name)




@app.route('/save_post', methods=['POST'])
def save_post():
    post_title = request.form.get('title')
    post_content = request.form.get('content')
    post_image = request.files.get('image')
    post_date = request.form.get('date')
    project_name = request.form.get('project_name')

    if not all([post_title, post_content, post_image, post_date, project_name]):
        return jsonify({"error": "All fields are required"}), 400

    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()
    if user_doc:
        user_id = user_doc[0].id
        try:
            image_filename = post_image.filename
            blob = bucket.blob(f'post_images/{image_filename}')
            blob.upload_from_file(post_image)
            post_image_url = blob.public_url

            post_data = {
                'title': post_title,
                'content': post_content,
                'image_url': post_image_url,
                'date': post_date,
                'project_name': project_name
            }
            db.collection('projects').document(user_id).collection('user_posts').add(post_data)

            return jsonify({"status": "success", "message": "Post saved successfully"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "User not found"}), 404

@app.route('/post/<post_title>', methods=['GET'])
def view_post(post_title):
    user_email = session.get('user_email')
    if not user_email:
        return jsonify({"error": "User not logged in"}), 401

    # Retrieve the user document to get the user ID
    user_doc = db.collection('users').where('email', '==', user_email).limit(1).get()

    if user_doc:
        user_id = user_doc[0].id
        # Reference to the user's posts collection
        user_posts_ref = db.collection('projects').document(user_id).collection('user_posts')
        
        # Query the post by title
        post_query = user_posts_ref.where('title', '==', post_title).limit(1).get()

        if post_query:
            post_data = post_query[0].to_dict()

            # Fetch related posts (other posts from the same project)
            related_posts_query = user_posts_ref.where('title', '!=', post_title).get()
            related_posts = [doc.to_dict() for doc in related_posts_query]

            # Render the template with the post data and related posts
            return render_template('blog-content.html', post=post_data, related_posts=related_posts)
        else:
            return jsonify({"error": "Post not found"}), 404
    else:
        return jsonify({"error": "User document not found"}), 404 
    

@app.route('/community_dashboard')
def community_dashboard():
    return render_template('community.html')  # Render the community dashboard without login requirement


@app.route('/fetch_community_projects', methods=['GET'])
def fetch_community_projects():
    all_community_projects = []  # List to hold all community projects

    try:
        # Reference to the 'community_projects' collection
        community_projects_ref = db.collection('community_projects')
        
        # Fetch all community projects
        community_projects = community_projects_ref.stream()

        # Iterate through each document in the community_projects collection
        for project_doc in community_projects:
            project_details = project_doc.to_dict()  # Convert document to dictionary
            project_details['project_id'] = project_doc.id  # Include project ID for clarity
            all_community_projects.append(project_details)  # Add to the list

        # Debugging: Print the fetched community projects
        print("All Community Projects fetched:", all_community_projects)

    except Exception as e:
        print(f"Error fetching community projects: {e}")  # Print error message for debugging
        return jsonify({"error": "Failed to fetch community projects"}), 500

    return jsonify(all_community_projects)  # Return the list of projects as JSON


@app.route('/fetch_community_project', methods=['GET'])
def fetch_community_project():
    project_name = request.args.get('name')  # Get the project name from the query parameter

    # Reference the community_projects collection
    projects_ref = db.collection('community_projects')  
    query = projects_ref.where('name', '==', project_name).limit(1).stream()

    project_data = None  # Initialize project_data as None

    # Iterate through the query results
    for doc in query:
        project_data = doc.to_dict()  # Get the project data as a dictionary

    # Check if project_data was found
    if project_data:
        print("Fetched project data:", project_data)  # Print the project data to the console
        # Render the community-project.html template with the fetched project data
        return render_template('project-community.html', project=project_data)
    else:
        print("Project not found for name:", project_name)  # Print a message if the project is not found
        return jsonify({'error': 'Project not found'}), 404  # Return an error if project not found

if __name__ == '__main__':
    app.run(debug=True, port=5001)
