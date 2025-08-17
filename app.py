import os
# Suppress TensorFlow/MediaPipe logs
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

import logging
logging.getLogger('mediapipe').setLevel(logging.ERROR)

import io
import json
import base64
import re
import secrets
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

import cv2
import mediapipe as mp
import numpy as np

# ------------------ App setup ------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_secret_key_here')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///users.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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
    return db.session.get(User, int(user_id))


# ------------------ Workout data ------------------
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
    start_date = end_date - timedelta(days=6)
    counts = { (start_date + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(7) }
    for entry in workout_data:
        date_str = entry.get('date')
        if date_str in counts:
            counts[date_str] += entry.get('count', 0)
    sorted_dates = list(counts.keys())
    sorted_counts = list(counts.values())
    return sorted_dates, sorted_counts

# ------------------ Globals ------------------
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

counter = 0
stage = None
is_exercise_active = False

# ------------------ Helpers ------------------
def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    radians = np.arctan2(c[1]-b[1], c[0]-b[0]) - np.arctan2(a[1]-b[1], a[0]-b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    return 360 - angle if angle > 180 else angle

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
            flash("Invalid email address", "error")
            return redirect(url_for('signup'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Please log in.", "error")
            return redirect(url_for('signup'))

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
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

# ------------------ Process frame with blue keypoints ------------------
@app.route('/process_frame', methods=['POST'])
def process_frame():
    global counter, stage
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({'error': 'Invalid JSON'}), 400
    data_url = payload.get('image')
    if not data_url or not data_url.startswith('data:image'):
        return jsonify({'error': 'No image provided'}), 400

    try:
        img_b64 = data_url.split(',')[1]
        img_bytes = base64.b64decode(img_b64)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({'error': 'Could not decode image'}), 400
    except Exception as e:
        return jsonify({'error': 'Image decode error', 'detail': str(e)}), 400

    try:
        with mp_pose.Pose(static_image_mode=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            results = pose.process(image_rgb)
            image_rgb.flags.writeable = True

            if results.pose_landmarks:
                # Draw blue keypoints and connections
                mp_drawing.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=(255,0,0), thickness=4, circle_radius=4),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=(255,0,0), thickness=2)
                )

                landmarks = results.pose_landmarks.landmark
                left_angle = right_angle = None

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

                # Rep logic
                if left_angle is not None and right_angle is not None:
                    if left_angle > 160 and right_angle > 160:
                        stage = "down"
                    if left_angle < 40 and right_angle < 40 and stage == "down":
                        counter += 1
                        stage = "up"

        # Encode back to base64
        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')

    except Exception as e:
        print("process_frame error:", e)
        return jsonify({'error': 'Processing error', 'detail': str(e)}), 500

    return jsonify({'counter': counter, 'stage': stage, 'frame': 'data:image/jpeg;base64,' + frame_b64})

# ------------------ Start & Stop exercise ------------------
@app.route('/start_exercise', methods=['POST'])
def start_exercise():
    global is_exercise_active
    is_exercise_active = True
    return jsonify({'status': 'Exercise started'})

@app.route('/stop_exercise', methods=['POST'])
def stop_exercise():
    global is_exercise_active, counter
    is_exercise_active = False
    today = str(date.today())
    existing_data = next((item for item in workout_data if item.get('date') == today), None)
    if existing_data:
        existing_data['count'] += counter
    else:
        workout_data.append({'date': today, 'count': counter})
    save_workout_data(workout_data)

    dates, counts = fetch_workout_data()
    plt.figure(figsize=(10, 5))
    plt.bar(dates, counts)
    plt.xlabel('Date')
    plt.ylabel('Workout Count')
    plt.title('Workout Count for Last 7 Days')
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    counter = 0
    return jsonify({'status': 'Exercise stopped', 'graph': image_base64})

# ------------------ API helpers ------------------
@app.route('/api/workout-data', methods=['GET'])
def get_workout_data():
    return jsonify(workout_data)

@app.route('/api/rep-count', methods=['GET'])
def get_rep_count():
    return jsonify({'count': counter})

@app.route('/status')
def get_status():
    global counter, stage
    return jsonify({'counter': counter, 'stage': stage})

# ------------------ Run server ------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
