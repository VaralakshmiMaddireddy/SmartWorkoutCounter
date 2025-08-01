from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin

import cv2
import mediapipe as mp
import numpy as np
import threading
import os
import json
import io
import base64
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
import secrets
from authlib.jose import jwt
from flask import session

import re
from authlib.integrations.flask_client import OAuth
from dotenv import load_dotenv

# ------------------ Setup ------------------
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
CORS(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

oauth = OAuth(app)

# ------------------ Google OAuth ------------------
google = oauth.register(
    name='google',
    client_id='YOUR_GOOGLE_CLIENT_ID',
    client_secret='YOUR_GOOGLE_CLIENT_SECRET',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile',
    }
)

# ------------------ Models ------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    total_count = db.Column(db.Integer, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ------------------ Workout Data ------------------
WORKOUT_DATA_FILE = 'workout_data.json'

def load_workout_data():
    if os.path.exists(WORKOUT_DATA_FILE):
        with open(WORKOUT_DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_workout_data(data):
    with open(WORKOUT_DATA_FILE, 'w') as f:
        json.dump(data, f)

workout_data = load_workout_data()

def fetch_workout_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=6)  # Last 7 days including today

    # Create date keys in chronological order
    counts = {
        (start_date + timedelta(days=i)).strftime('%Y-%m-%d'): 0
        for i in range(7)
    }

    # Aggregate counts for each date
    for entry in workout_data:
        date_str = entry['date']
        if date_str in counts:
            counts[date_str] += entry['count']

    # Return sorted lists
    sorted_dates = list(counts.keys())
    sorted_counts = list(counts.values())

    return sorted_dates, sorted_counts


# ------------------ Routes ------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return "Invalid email address"

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Email already registered. Please log in."

        new_user = User(username=username, email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', name=current_user.username)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.')
    return redirect(url_for('login'))

# ------------------ OAuth Callbacks ------------------
@app.route('/login/google')
def login_google():
    nonce = secrets.token_urlsafe(16)
    session['nonce'] = nonce
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri, nonce=nonce)

@app.route('/authorize/google')
def authorize_google():
    token = google.authorize_access_token()
    user_info = google.parse_id_token(token)
    email = user_info['email']
    username = user_info.get('name', email)
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(username=username, email=email)
        db.session.add(user)
        db.session.commit()
    login_user(user)
    return redirect(url_for('dashboard'))

# ------------------ Exercise Code ------------------
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose
camera = None
is_exercise_active = False
counter = 0
stage = None

def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle

def run_pose_detection():
    global counter, stage, is_exercise_active
    is_exercise_active = True
    cap = cv2.VideoCapture(0)

    with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        left_stage = None
        right_stage = None
        curl_started = False  # Track if a rep is in progress

        while cap.isOpened() and is_exercise_active:
            ret, frame = cap.read()
            if not ret:
                break

            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = pose.process(image)
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            try:
                if results.pose_landmarks:
                    landmarks = results.pose_landmarks.landmark

                    # Initialize both angles
                    left_angle = None
                    right_angle = None

                    # LEFT ARM
                    if all(landmarks[i].visibility > 0.5 for i in [
                        mp_pose.PoseLandmark.LEFT_SHOULDER.value,
                        mp_pose.PoseLandmark.LEFT_ELBOW.value,
                        mp_pose.PoseLandmark.LEFT_WRIST.value]):
                        shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x,
                                    landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                        elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x,
                                 landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                        wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x,
                                 landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]
                        left_angle = calculate_angle(shoulder, elbow, wrist)
                        cv2.putText(image, f'L: {int(left_angle)}', 
                                    tuple(np.multiply(elbow, [frame.shape[1], frame.shape[0]]).astype(int)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                    # RIGHT ARM
                    if all(landmarks[i].visibility > 0.5 for i in [
                        mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
                        mp_pose.PoseLandmark.RIGHT_ELBOW.value,
                        mp_pose.PoseLandmark.RIGHT_WRIST.value]):
                        shoulder = [landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].x,
                                    landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y]
                        elbow = [landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].x,
                                 landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW.value].y]
                        wrist = [landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].x,
                                 landmarks[mp_pose.PoseLandmark.RIGHT_WRIST.value].y]
                        right_angle = calculate_angle(shoulder, elbow, wrist)
                        cv2.putText(image, f'R: {int(right_angle)}', 
                                    tuple(np.multiply(elbow, [frame.shape[1], frame.shape[0]]).astype(int)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    # Rep logic — one rep only when both arms are fully curled
                    if (left_angle is not None and right_angle is not None):
                        if left_angle > 160 and right_angle > 160:
                            curl_started = True
                        if left_angle < 40 and right_angle < 40 and curl_started:
                            counter += 1
                            curl_started = False

                    # Draw count on screen
                    cv2.rectangle(image, (0, 0), (250, 60), (0, 0, 0), -1)
                    cv2.putText(image, f'Reps: {counter}', (10, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)

                    # Draw landmarks in blue
                    mp_drawing.draw_landmarks(
                        image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                        mp_drawing.DrawingSpec(color=(255, 255, 0), thickness=2, circle_radius=3),
                        mp_drawing.DrawingSpec(color=(0, 255, 255), thickness=2, circle_radius=2)
                    )

            except Exception as e:
                print("Pose error:", e)

            cv2.imshow('Live Pose Detection', image)
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()


@app.route('/start_exercise', methods=['POST'])
def start_exercise():
    global is_exercise_active
    if not is_exercise_active:
        threading.Thread(target=run_pose_detection).start()
        return jsonify({"status": "Exercise started"})
    return jsonify({"status": "Exercise already active"})

@app.route('/stop_exercise', methods=['POST'])
def stop_exercise():
    global is_exercise_active, counter
    is_exercise_active = False
    today = str(date.today())
    existing_data = next((item for item in workout_data if item['date'] == today), None)
    if existing_data:
        existing_data['count'] += counter
    else:
        workout_data.append({'date': today, 'count': counter})
    save_workout_data(workout_data)

    dates, counts = fetch_workout_data()
    plt.figure(figsize=(10, 5))
    plt.bar(dates, counts, color='blue')
    plt.xlabel('Date')
    plt.ylabel('Workout Count')
    plt.title('Workout Count for Last 7 Days')
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    counter = 0
    return jsonify({'status': 'Exercise stopped', 'graph': image_base64})

@app.route('/api/workout-data', methods=['GET'])
def get_workout_data():
    return jsonify(workout_data)

@app.route('/api/rep-count', methods=['GET'])
def get_rep_count():
    return jsonify({'count': counter})

@app.route('/status')
def get_status():
    global counter, stage
    return jsonify({
        'counter': counter,
        'stage': stage
    })

# ------------------ Run Server ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
