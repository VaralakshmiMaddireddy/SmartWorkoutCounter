# 🏋️ Smart Workout Counter

This is a Flask-based application that uses MediaPipe, OpenCV, and SQLAlchemy to count workout repetitions (biceps curls) in real-time. It includes:

- User login/signup (with Google OAuth support)
- Live webcam workout tracking
- Pose detection & rep counting
- Workout graph visualization
- Fitness history dashboard

---

## 🚀 Features

- Real-time pose detection using MediaPipe
- Count bicep curl reps using angle detection
- Store workouts in a database
- View workout history and analytics
- Sign up/login functionality

---

## 🛠️ Tech Stack

- Backend: Flask, Python, SQLAlchemy
- Frontend: HTML, CSS, JavaScript, Bootstrap
- Pose Detection: OpenCV, MediaPipe
- Charts: Chart.js
- Database: SQLite (default), MySQL (optional)

---

## 📦 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/VaralakshmiMaddireddy/Smart-Workout-Counter.git
cd Smart-Workout-Counter

### 2. Create a Virtual Environment
Create a virtual environment using Python:

python -m venv venv

Activate the environment:

**On Windows**:
venv\Scripts\activate

**On macOS/Linux**:
source venv/bin/activate

### 3. Install Dependencies
pip install -r requirements.txt

### 4. Run the Application

After installing all dependencies and activating the virtual environment, start the Flask server by running:

python exercise_server.py

By default, the server will run on:
http://127.0.0.1:5000



Open this link in your browser to access the Smart Workout Counter dashboard.



