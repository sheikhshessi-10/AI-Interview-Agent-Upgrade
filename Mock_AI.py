import streamlit as st
import openai
import speech_recognition as sr
from gtts import gTTS
import pygame
import os
import uuid
import matplotlib.pyplot as plt
import re
from colorama import init
import time
from threading import Thread
from dotenv import load_dotenv

# Initialize colorama and pygame
init(autoreset=True)
pygame.mixer.init()

# Load environment variables
load_dotenv()
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Streamlit page configuration
st.set_page_config(layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .stButton>button {
        border-radius: 30px;
        padding: 15px 50px;
        font-size: 20px;
        margin: 10px;
        border: none;
        background-color: #8F00FF;
        color: white;
        cursor: pointer;
        transition: transform 0.2s ease-in-out;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        opacity: 0.9;
    }
    .card {
        background: #ffffff;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Define image paths (use relative paths)
static_gif_path = "AI-talking-avatar.png"
animated_gif_path = "AI-talking-avatar.gif"

# Speech Recognition Setup
recognizer = sr.Recognizer()

# Initialize session state
for key in ["interview_complete", "transcript", "evaluation_scores", 
            "start_clicked", "paused", "mute", "greeted"]:
    if key not in st.session_state:
        st.session_state[key] = False if key in ["interview_complete", "start_clicked", "paused", "mute", "greeted"] else []

# Interview Tracks
interview_tracks = {
    "Data Scientist": [
        "Explain overfitting in machine learning.",
        "What is the difference between supervised and unsupervised learning?",
        "How do you handle imbalanced datasets?",
        "What is feature engineering?",
        "Explain the bias-variance tradeoff."
    ],
    "Software Engineer": [
        "What is your approach to debugging code?",
        "Explain multithreading vs multiprocessing.",
        "What is the concept of clean code?",
        "How do you ensure code security?",
        "Explain RESTful APIs."
    ],
}

# Text-to-Speech with GIF Function
def speak_with_gif(text, gif_placeholder, animated_gif_path, static_gif_path):
    try:
        if st.session_state["mute"]:
            return

        temp_audio_file = f"temp_speech_{uuid.uuid4().hex}.mp3"
        tts = gTTS(text=text, lang='en')
        tts.save(temp_audio_file)

        def play_audio():
            pygame.mixer.music.load(temp_audio_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()  # Unload the music after playing

        audio_thread = Thread(target=play_audio)
        audio_thread.start()

        time.sleep(1.5)
        gif_placeholder.image(animated_gif_path, use_container_width=True)
        audio_thread.join()

    except Exception as e:
        st.error(f"❌ Error during playback: {e}")
    finally:
        gif_placeholder.image(static_gif_path, use_container_width=True)
        
        # Add error handling for file removal
        try:
            if os.path.exists(temp_audio_file):
                os.remove(temp_audio_file)
        except PermissionError:
            st.warning(f"Could not remove temporary audio file: {temp_audio_file}")
        
        pygame.mixer.music.stop()

# Speech Input Function
def get_speech_input():
    with sr.Microphone() as source:
        st.info("🎙 Listening... Please speak your answer.")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
            text = recognizer.recognize_google(audio)
            st.success(f"✅ You : {text}")
            return text
        except sr.UnknownValueError:
            st.warning("🤔 Could not understand the audio. Please try speaking clearly.")
        except sr.RequestError:
            st.error("❌ Speech recognition service is unavailable.")
        except sr.WaitTimeoutError:
            st.warning("⏰ No speech detected. Please try again.")
    return ""

# GPT Chat Function
def chat_with_gpt(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional interviewer. Avoid greetings and keep it focused."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"❌ OpenAI Error: {e}")
        return "Error generating response."

# Follow-Up Function
def generate_followup_with_feedback(user_response):
    followup_prompt = f"""
    Based on the following interview answer, generate a follow-up question with subtle, natural feedback included.
    Do not explicitly state 'Follow-Up Question:' in your response. Keep it natural and conversational.
    Answer: {user_response}
    """
    return chat_with_gpt(followup_prompt)

# Evaluation Function
def evaluate_answers():
    evaluation_prompt = """
    Evaluate the following interview transcript. Provide structured feedback:
    
    1. Question: <Question>
       Answer: <User's Answer>
       Score: <Score out of 10>
       Feedback: <Brief one-line feedback>
    
    At the end, include:
    Overall Feedback: <Summary of overall performance>
    """
    for i, entry in enumerate(st.session_state["transcript"]):
        match = re.search(
            r"Q\d+: (.?)\n🗨 You: (.?)\n🔄 Follow-Up: (.?)\n🗨 You: (.?)$", 
            entry, re.DOTALL
        )
        if match:
            question = match.group(1)
            answer = match.group(2)
            evaluation_prompt += f"\n{i+1}. Question: {question}\nAnswer: {answer}\n"
    
    evaluation = chat_with_gpt(evaluation_prompt)
    scores = re.findall(r"Score:\s?(\d+)", evaluation)
    return evaluation, [int(s) for s in scores] if scores else [0] * len(st.session_state["transcript"])

# Evaluation Chart Function
def plot_evaluation_chart(scores):
    fig, ax = plt.subplots()
    questions = [f"Q{i+1}" for i in range(len(scores))]
    ax.bar(questions, scores, color="#4caf50")
    ax.set_title("Interview Evaluation Scores")
    ax.set_xlabel("Questions")
    ax.set_ylabel("Score (out of 10)")
    ax.set_ylim([0, 10])
    st.pyplot(fig)

# Main Application
def main():
    st.title("🎓 AI Mock Interview Platform")

    if not st.session_state["start_clicked"]:
        username = st.text_input("Enter Your Name:", "")
        track = st.selectbox("Select Your Interview Track:", list(interview_tracks.keys()))
        if st.button("Start Interview"):
            if username.strip():
                st.session_state["username"] = username
                st.session_state["track"] = track
                st.session_state["start_clicked"] = True
            else:
                st.error("Please enter your name before starting.")
    else:
        username = st.session_state["username"]
        track = st.session_state["track"]

        # Sidebar with controls
        with st.sidebar:
            gif_placeholder = st.empty()
            gif_placeholder.image(static_gif_path, use_container_width=True)
            
            cols = st.columns(3)
            with cols[0]:
                pause_btn = st.button("⏸")
            with cols[1]:
                mute_btn = st.button("🔇")
            with cols[2]:
                end_call_btn = st.button("❌")
            
            if pause_btn:
                st.session_state["paused"] = not st.session_state["paused"]
                st.info("⏸ Interview paused." if st.session_state["paused"] else "▶ Interview resumed.")
            if mute_btn:
                st.session_state["mute"] = not st.session_state["mute"]
                st.info("🔇 Audio muted." if st.session_state["mute"] else "🔊 Audio unmuted.")
            if end_call_btn:
                for key in ["interview_complete", "transcript", "evaluation_scores", 
                            "start_clicked", "paused", "mute", "greeted"]:
                    st.session_state[key] = False if key not in ["transcript", "evaluation_scores"] else []
                st.experimental_rerun()

        # Interview Process
        if not st.session_state["greeted"]:
            greeting = f"Hi, how are you, {username}? Welcome to the {track} interview."
            st.info(f"🤖 GPT : {greeting}")
            speak_with_gif(greeting, gif_placeholder, animated_gif_path, static_gif_path)
            st.session_state["greeted"] = True

        if not st.session_state["interview_complete"]:
            questions = interview_tracks[track]
            for i, question in enumerate(questions):
                while st.session_state["paused"]:
                    st.warning("⏸ Interview is paused. Click the pause button to resume.")
                    time.sleep(1)

                # Progress calculation
                progress = (i + 1) / len(questions)
                st.progress(progress)

                # Ask question
                speak_with_gif(question, gif_placeholder, animated_gif_path, static_gif_path)
                st.markdown(f'<div class="card"><strong>🤖 GPT:</strong> {question}</div>', unsafe_allow_html=True)

                # Get user response
                user_response = get_speech_input()
                if user_response == "" and st.session_state["paused"]:
                    continue

                # Generate follow-up
                followup = generate_followup_with_feedback(user_response)
                speak_with_gif(followup, gif_placeholder, animated_gif_path, static_gif_path)
                st.markdown(f'<div class="card"><strong>🤖 GPT:</strong> {followup}</div>', unsafe_allow_html=True)

                # Get follow-up response
                followup_response = get_speech_input()
                if followup_response == "" and st.session_state["paused"]:
                    continue

                # Record transcript
                block = (
                    f"Q{i+1}: {question}\n"
                    f"🗨 You: {user_response}\n"
                    f"🔄 Follow-Up: {followup}\n"
                    f"🗨 You: {followup_response}"
                )
                st.session_state["transcript"].append(block)

            # Farewell
            farewell = f"It was nice meeting you, {username}. Goodbye!"
            speak_with_gif(farewell, gif_placeholder, animated_gif_path, static_gif_path)
            st.info(f"🤖 GPT : {farewell}")
            st.session_state["interview_complete"] = True

        # Evaluation Section
        if st.session_state["interview_complete"]:
            st.success("✅ Interview complete! You can now proceed to evaluation.")
            if st.button("Evaluate My Performance"):
                with st.spinner("🔍 Evaluating your responses..."):
                    evaluation_report, scores = evaluate_answers()
                st.subheader("📄 Evaluation Report")
                st.write(evaluation_report)
                st.subheader("📊 Interview Evaluation Scores")
                plot_evaluation_chart(scores)

# Run the main application
if __name__ == "__main__":
    main()
