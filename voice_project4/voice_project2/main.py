from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
import speech_recognition as sr
from gtts import gTTS
import os
import re
import base64
import logging
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import random
from difflib import SequenceMatcher

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Replace with a secure key
DATABASE = 'users.db'
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

PARAGRAPHS = [
    "The quick brown fox jumps over the lazy dog.",
    "A journey of a thousand miles begins with a single step.",
    "To be or not to be, that is the question.",
    "The rain in Spain stays mainly in the plain.",
    "All that glitters is not gold."
]

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS scores (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        score INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users(id))''')
    conn.commit()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    logger.debug(f"Tables in the database: {cursor.fetchall()}")
    conn.close()

def clean_stammered_text(text):
    text = re.sub(r'\b(\w{1,2})-\1(\w*)\b', r'\1\2', text)
    text = re.sub(r'\b(\w+)\b(?:\s+\1\b)+', r'\1', text)
    return text

def calculate_score(original, recorded):
    similarity = SequenceMatcher(None, original.lower(), recorded.lower()).ratio()
    return int(similarity * 100)

@app.route('/')
def home():
    username = session.get('username')
    logger.debug("Serving home.html")
    return render_template('home.html', username=username)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    username = session.get('username')
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] >= 20:
            flash("User limit reached (20 users max). Cannot register new users.", "error")
            return redirect(url_for('signup'))
        try:
            cursor.execute("INSERT INTO users (name, email, username, password) VALUES (?, ?, ?, ?)",
                           (name, email, username, hashed_password))
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Email or Username already exists!", "error")
        finally:
            conn.close()
    return render_template('signup.html', username=username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    username = session.get('username')
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user[4], password):
            session['user_id'] = user[0]
            session['username'] = user[3]
            flash("Login successful!", "success")
            return redirect(url_for('english'))
        else:
            flash("Invalid email or password!", "error")
    return render_template('login.html', username=username)

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('home'))

@app.route('/english')
def english():
    if 'user_id' not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for('login'))
    username = session.get('username')
    random_paragraph = random.choice(PARAGRAPHS)
    logger.debug("Serving english.html")
    return render_template('english.html', username=username, paragraph=random_paragraph)

@app.route('/try')
def try_page():
    username = session.get('username')
    logger.debug("Serving voice_conversion.html")
    return render_template('voice_conversion.html', username=username)

@app.route('/leaderboard')
def leaderboard():
    username = session.get('username')
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username, MAX(s.score) as top_score
        FROM scores s
        JOIN users u ON s.user_id = u.id
        GROUP BY u.id, u.username
        ORDER BY top_score DESC
        LIMIT 10
    """)
    leaderboard_data = cursor.fetchall()
    conn.close()
    leaderboard_with_ranks = [(rank, username, score) for rank, (username, score) in enumerate(leaderboard_data, 1)]
    return render_template('leaderboard.html', username=username, leaderboard=leaderboard_with_ranks)

@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in first'}), 401
    if 'audio' not in request.files:
        logger.error("No audio file provided in request")
        return jsonify({'error': 'No audio file provided'}), 400
    audio_file = request.files['audio']
    paragraph = request.form.get('paragraph', '')
    audio_path = 'temp_audio.wav'
    try:
        logger.debug(f"Saving audio file to {audio_path}")
        audio_file.save(audio_path)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error("Audio file was not saved or is empty")
            return jsonify({'error': 'Audio file is empty or not saved'}), 500
        recognizer = sr.Recognizer()
        logger.debug("Processing audio with speech recognition")
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data)
                logger.debug(f"Transcribed text: {text}")
            except sr.UnknownValueError:
                text = "Could not understand audio"
                logger.warning("Speech recognition failed: Could not understand audio")
            except sr.RequestError as e:
                text = f"API request failed: {str(e)}"
                logger.error(f"Speech recognition API error: {str(e)}")
        cleaned_text = clean_stammered_text(text)
        logger.debug(f"Cleaned text: {cleaned_text}")
        preview_path = 'preview.mp3'
        logger.debug(f"Generating preview audio at {preview_path}")
        tts = gTTS(text=cleaned_text, lang='en')
        tts.save(preview_path)
        logger.debug("Encoding preview audio to base64")
        with open(preview_path, 'rb') as f:
            audio_data = f.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        score = None
        if paragraph:
            score = calculate_score(paragraph, cleaned_text)
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO scores (user_id, score) VALUES (?, ?)",
                           (session['user_id'], score))
            conn.commit()
            conn.close()
        logger.debug("Cleaning up temporary files")
        os.remove(audio_path)
        os.remove(preview_path)
        logger.debug("Returning successful response")
        response = {'text': cleaned_text, 'audio': audio_base64}
        if score is not None:
            response['score'] = score
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/process_realtime_audio', methods=['POST'])
def process_realtime_audio():
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in first'}), 401
    if 'audio' not in request.files:
        logger.error("No audio file provided in request")
        return jsonify({'error': 'No audio file provided'}), 400
    audio_file = request.files['audio']
    audio_path = 'temp_audio.wav'
    try:
        logger.debug(f"Saving audio file to {audio_path}")
        audio_file.save(audio_path)
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            logger.error("Audio file was not saved or is empty")
            return jsonify({'error': 'Audio file is empty or not saved'}), 500
        recognizer = sr.Recognizer()
        logger.debug("Processing real-time audio with speech recognition")
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)
            try:
                text = recognizer.recognize_google(audio_data)
                logger.debug(f"Transcribed text: {text}")
            except sr.UnknownValueError:
                text = "Could not understand audio"
                logger.warning("Speech recognition failed: Could not understand audio")
            except sr.RequestError as e:
                text = f"API request failed: {str(e)}"
                logger.error(f"Speech recognition API error: {str(e)}")
        cleaned_text = clean_stammered_text(text)
        logger.debug(f"Cleaned text: {cleaned_text}")
        preview_path = 'preview.mp3'
        logger.debug(f"Generating preview audio at {preview_path}")
        tts = gTTS(text=cleaned_text, lang='en')
        tts.save(preview_path)
        logger.debug("Encoding preview audio to base64")
        with open(preview_path, 'rb') as f:
            audio_data = f.read()
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        logger.debug("Cleaning up temporary files")
        os.remove(audio_path)
        os.remove(preview_path)
        logger.debug("Returning successful response")
        return jsonify({'text': cleaned_text, 'audio': audio_base64})
    except Exception as e:
        logger.error(f"Error processing real-time audio: {str(e)}", exc_info=True)
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True,port=9000)