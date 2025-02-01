from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import cv2
import mediapipe as mp
import numpy as np
import threading
from flask_migrate import Migrate
import os
import json
from datetime import date, datetime, timedelta
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)
CORS(app)
migrate = Migrate(app, db)

# MediaPipe setup
mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

# Global variables
camera = None
is_exercise_active = False
counter = 0 
stage = None

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    total_count = db.Column(db.Integer, default=0)  # New field to store total exercise count

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Initialize workout data file
WORKOUT_DATA_FILE = 'workout_data.json'

# Load existing workout data from JSON file
def load_workout_data():
    if os.path.exists(WORKOUT_DATA_FILE):
        with open(WORKOUT_DATA_FILE, 'r') as f:
            return json.load(f)
    return []

# Save workout data to JSON file
def save_workout_data(data):
    with open(WORKOUT_DATA_FILE, 'w') as f:
        json.dump(data, f)

# Load workout data into memory
workout_data = load_workout_data()

# Function to fetch workout data for the last 7 days
def fetch_workout_data():
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    # Prepare counts dictionary for the last 7 days
    counts = { (end_date - timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(7) }

    # Fill counts with existing workout data
    for entry in workout_data:
        date_str = entry['date']
        if start_date.strftime('%Y-%m-%d') <= date_str <= end_date.strftime('%Y-%m-%d'):
            counts[date_str] += entry['count']

    # Sort dates and counts
    sorted_dates = sorted(counts.keys())
    sorted_counts = [counts[date] for date in sorted_dates]

    return sorted_dates, sorted_counts

# Route for the home page
@app.route('/')
def home():
    return render_template('Signup Form.html')

@app.route('/signup', methods=['POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists')
            return redirect(url_for('home'))
        
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already exists')
            return redirect(url_for('home'))
        
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created successfully')
        return redirect(url_for('home'))

def calculate_angle(a, b, c):
    a = np.array(a)  # First
    b = np.array(b)  # Mid
    c = np.array(c)  # End

    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360 - angle
    return angle

def run_pose_detection():
    global counter, stage, is_exercise_active
    is_exercise_active = True
    cap = cv2.VideoCapture(0)
    with mp_pose.Pose(min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose:
        while cap.isOpened() and is_exercise_active:
            ret, frame = cap.read()
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False

            # Make detection
            results = pose.process(image)

            # Recolor back to BGR
            image.flags.writeable = True
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            try:
                landmarks = results.pose_landmarks.landmark
                shoulder = [landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].x, landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y]
                elbow = [landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].x, landmarks[mp_pose.PoseLandmark.LEFT_ELBOW.value].y]
                wrist = [landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].x, landmarks[mp_pose.PoseLandmark.LEFT_WRIST.value].y]

                # Calculate angle
                angle = calculate_angle(shoulder, elbow, wrist)

                # Visualize angle
                cv2.putText(image, str(angle), tuple(np.multiply(elbow, [640, 480]).astype(int)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)

                # Curl counter logic
                if angle > 160:
                    stage = "down"
                if angle < 30 and stage == 'down':
                    stage = "up"
                    counter += 1
                    print(f"Counter incremented: {counter}")

            except:
                pass

            # Render curl counter
            cv2.rectangle(image, (0, 0), (225, 73), (245, 117, 16), -1)
            cv2.putText(image, 'REPS', (15, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(image, str(counter), (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, 'STAGE', (65, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(image, stage, (60, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2, cv2.LINE_AA)

            mp_drawing.draw_landmarks(image, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                                      mp_drawing.DrawingSpec(color=(245, 117, 66), thickness=2, circle_radius=2),
                                      mp_drawing.DrawingSpec(color=(245, 66, 230), thickness=2, circle_radius=2))

            cv2.imshow('Mediapipe Feed', image)

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
    else:
        return jsonify({"status": "Exercise already active"})

@app.route('/status', methods=['GET'])
def status():
    global counter, stage
    return jsonify({'counter': counter, 'stage': stage})

@app.route('/stop_exercise', methods=['POST'])
def stop_exercise():
    global is_exercise_active, counter
    is_exercise_active = False
    today = str(date.today())

    # Check if today's data already exists
    existing_data = next((item for item in workout_data if item['date'] == today), None)
    if existing_data:
        existing_data['count'] += counter  # Update total count
    else:
        workout_data.append({'date': today, 'count': counter})  # Create new entry

    # Save updated workout data to file
    save_workout_data(workout_data)

    # Generate and return graph for the last 7 days
    dates, counts = fetch_workout_data()

    plt.figure(figsize=(10, 5))
    plt.bar(dates, counts, color='blue')
    plt.xlabel('Date')
    plt.ylabel('Workout Count')
    plt.title('Workout Count for Last 7 Days')

    # Save to a BytesIO object and encode it in base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    # Reset counter for the next session
    counter = 0
    return jsonify({'status': 'Exercise stopped', 'graph': image_base64})

@app.route('/api/workout-data', methods=['GET'])
def get_workout_data():
    return jsonify(workout_data)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create the database tables
    app.run(debug=True)
