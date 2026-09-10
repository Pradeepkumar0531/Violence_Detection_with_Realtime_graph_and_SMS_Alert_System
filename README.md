### Violence Detection System with   Graph and SMS Alert

An AI-powered surveillance system that detects violent activities from video streams in real time and automatically sends alerts when suspicious behavior is detected.

This project combines Computer Vision, Deep Learning,   Visualization, and Alert Automation to simulate an intelligent CCTV monitoring system.

📌 Project Overview

Traditional CCTV systems require continuous human monitoring and often fail to respond quickly to incidents.

This project introduces a Violence Detection System that:

Processes video streams continuously Detects violent activities using a deep learning model Generates a live violence probability graph Sends SMS alerts automatically when violence exceeds a threshold

The system is designed as a prototype for smart surveillance environments.

✨ Features

✅ violence detection from video input 

✅ Violence probability scoring (0–1 scale)

✅ Live graph visualization synchronized with video playback

✅ Automated SMS alerts using threshold-based triggering

✅ Interactive frontend dashboard 

✅ Deep learning–based video understanding

🏗️ System Architecture

Video Input 
↓ 
Frame Extraction (OpenCV)
↓
VideoMAE Violence Detection Model 
↓
Violence Probability Score 
↓
Graph Visualization
↓
Threshold Evaluation 
↓
SMS Alert System

🧠 Tech Stack

Frontend :React, Chart.js

Backend: Python, FastAPI

Dataset: RWF-2000 Violence Detection Dataset

Alert System: Twilio SMS API

📊 Model Information Model Used VideoMAE (Fine-tuned)

Detection Output 0.0 – 0.70 = Non violence 0.71 - 1.0 = Violence

Backend Setup: pip install -r requirements.txt

Run backend:

uvicorn main:app --reload Frontend Setup cd frontend

npm install

npm run dev ▶️ Running the Project

Start backend:

uvicorn main:app --reload

Start frontend:

npm run dev

Open:

http://localhost:5173

Upload or stream video and monitor live violence detection.

📈   Graph

The frontend displays:

Live violence probability Dynamic threshold line Alert status


Key Observations:

High Recall for Violence (92%)

   → Most violent events are successfully detected

False Positives Present (79 cases)

   → Some normal activities are misclassified as violence

Low Missed Violence (17 cases)

   → Critical events are rarely missed

Model Performance:

Accuracy: 76%

Violence: 0.79

Non-Violence: 0.72

Confusion Matrix Summary:

TP (Violence detected correctly): 183

TN (Non-violence correct): 121

FP (False alarms): 79

FN (Missed violence): 17

🔮 Future Improvements Support live CCTV streams Edge deployment Multi-camera monitoring Face recognition integration Email and push notifications Improved detection using larger datasets

📄 License This project is developed for academic and educational purposes.
