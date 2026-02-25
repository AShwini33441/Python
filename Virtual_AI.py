import pyttsx3
import speech_recognition as sr
import datetime
import webbrowser
import os
import wikipedia
from googlesearch import search
import requests
from bs4 import BeautifulSoup
import cv2
import openai 
from dotenv import load_dotenv
import threading
import tkinter as tk
from PIL import Image, ImageTk, ImageSequence
import queue
import pywhatkit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os as _os
load_dotenv()
WEBHOOK_TOKEN = _os.getenv('WEBHOOK_TOKEN')
# OpenAI availability flag and control via env
OPENAI_AVAILABLE = True
OPENAI_DISABLED = _os.getenv('OPENAI_DISABLED', '').lower() in ('1', 'true', 'yes')

# Global queue for communication between threads
avatar_queue = queue.Queue()
input_queue = queue.Queue()

class Assistant3DInterface(threading.Thread):
    """Tkinter window showing a looping animated GIF as a 3D assistant avatar with input/output."""
    def __init__(self, gif_path="assistant_avatar.gif"):
        super().__init__(daemon=True)
        self.gif_path = gif_path

    def run(self):
        root = tk.Tk()
        root.title("Virtual 3D Assistant")
        root.geometry("320x480")
        root.resizable(False, False)
        lbl = tk.Label(root)
        lbl.pack(expand=True)

        # Load GIF
        gif = Image.open(self.gif_path)
        frames = [ImageTk.PhotoImage(frame.copy().convert("RGBA")) for frame in ImageSequence.Iterator(gif)]

        def update(ind):
            frame = frames[ind]
            lbl.configure(image=frame)
            ind = (ind + 1) % len(frames)
            root.after(60, update, ind)

        # Entry for text input
        entry = tk.Entry(root, font=("Arial", 14))
        entry.pack(fill="x", padx=10, pady=5)
        entry.focus_set()

        def on_speak():
            cmd = entry.get().strip()
            if cmd:
                input_queue.put(cmd)
                entry.delete(0, tk.END)

        btn = tk.Button(root, text="Speak", command=on_speak, font=("Arial", 12))
        btn.pack(pady=5)

        def check_queue():
            try:
                msg = avatar_queue.get_nowait()
                if msg == "speaking":
                    root.config(bg="yellow")
                elif msg == "idle":
                    root.config(bg="SystemButtonFace")
            except queue.Empty:
                pass
            root.after(100, check_queue)

        root.after(0, update, 0)
        root.after(0, check_queue)
        root.mainloop()

# Modify speak to notify the avatar
def speak(text):
    try:
        avatar_queue.put("speaking")
    except Exception:
        pass
    engine.say(text)
    engine.runAndWait()
    try:
        avatar_queue.put("idle")
    except Exception:
        pass

# Modified take_command to check for GUI input first
def take_command():
    """Listen for a voice command or take from GUI entry."""
    try:
        # Check if there's a command from the GUI
        cmd = input_queue.get_nowait()
        return cmd.lower()
    except queue.Empty:
        pass

    # If not, fall back to voice
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)
    try:
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}\n")
        return query.lower()
    except Exception as e:
        print("Could not understand audio, please say that again.")
        speak("Could not understand audio, please say that again.")
        return None

# Initialize the text-to-speech engine
engine = pyttsx3.init()

def speak(text):
    """Convert text to speech."""
    engine.say(text)
    engine.runAndWait()


def get_openai_response(prompt):
    return call_openai_chat(prompt, max_tokens=150)


def greet_user():
    """Greet the user based on the time of day."""
    hour = datetime.datetime.now().hour
    if 0 <= hour < 12:
        speak("Good morning!")
    elif 12 <= hour < 18:
        speak("Good afternoon!")
    else:
        speak("Good evening!")
    speak("I am your virtual assistant. How can I help you?")

def google_search_and_answer(query):
    """Search Google and provide an answer to the user's question."""
    try:
        speak(f"Searching Google for {query}")
        # Use googlesearch to get the top result
        for url in search(query, num_results=1):
            # Fetch the content of the top result
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Extract text from the first paragraph
            paragraphs = soup.find_all('p')
            if paragraphs:
                answer = paragraphs[0].get_text()
                speak("Here is what I found:")
                speak(answer)
                return
        speak("I couldn't find a suitable answer to your question.")
    except Exception as e:
        speak("An error occurred while searching. Please try again later.")
        print(e)

def capture_image():
    """Capture an image from the webcam and save it."""
    try:
        speak("Accessing the webcam. Please wait.")
        cap = cv2.VideoCapture(0)  # Open the default webcam (index 0)
        if not cap.isOpened():
            speak("Unable to access the webcam.")
            return

        speak("Press 's' to save the image or 'q' to quit without saving.")
        while True:
            ret, frame = cap.read()
            if not ret:
                speak("Failed to capture an image. Please try again.")
                break

            cv2.imshow("Webcam - Press 's' to save or 'q' to quit", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('s'):  # Save the image
                file_name = "captured_image.jpg"
                cv2.imwrite(file_name, frame)
                speak(f"Image saved as {file_name}.")
                break
            elif key == ord('q'):  # Quit without saving
                speak("Exiting without saving the image.")
                break

        cap.release()
        cv2.destroyAllWindows()
    except Exception as e:
        speak("An error occurred while accessing the webcam.")
        print(e)

def get_weather(city):
    """Fetch the weather forecast for a given city and show a weather map."""
    api_key = "158195ae7e04d80559a85d50be6c9aad"  # Replace with your OpenWeatherMap API key
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"  # Use "imperial" for Fahrenheit
    }

    try:
        response = requests.get(base_url, params=params)
        data = response.json()

        if data["cod"] == 200:
            weather = data["weather"][0]["description"]
            temperature = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]

            forecast = (
                f"The weather in {city} is currently {weather} with a temperature of {temperature}°C. "
                f"The humidity is {humidity}% and the wind speed is {wind_speed} meters per second."
            )
            speak(forecast)

            # Show weather map in browser
            map_url = f"https://www.accuweather.com/en/in/national/satellite{city}+weather+map"
            speak("Showing the weather map for the city.")
            webbrowser.open(map_url)
        else:
            speak(f"Sorry, I couldn't find weather information for {city}. Please check the city name.")
    except Exception as e:
        speak("An error occurred while fetching the weather data. Please try again later.")
        print(e)

def get_weather_text(city):
    """Return weather forecast text for a given city (no speaking or browser)."""
    api_key = "158195ae7e04d80559a85d50be6c9aad"  # Replace with your OpenWeatherMap API key
    base_url = "http://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"
    }
    try:
        response = requests.get(base_url, params=params)
        data = response.json()
        if data.get("cod") == 200:
            weather = data["weather"][0]["description"]
            temperature = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            wind_speed = data["wind"]["speed"]
            forecast = (
                f"The weather in {city} is currently {weather} with a temperature of {temperature}°C. "
                f"The humidity is {humidity}% and the wind speed is {wind_speed} meters per second."
            )
            return forecast
        return f"Sorry, I couldn't find weather information for {city}."
    except Exception as e:
        print(e)
        return "An error occurred while fetching the weather data."

def generate_response(prompt):
    """Generate a human-like response using OpenAI's GPT."""
    try:
        if OPENAI_DISABLED:
            return "AI services are currently disabled (OPENAI_DISABLED)."
        if not OPENAI_AVAILABLE:
            return "AI services are temporarily unavailable due to quota or API errors."

        return call_openai_chat(prompt, max_tokens=150, temperature=0.7)
    except Exception as e:
        print("Error generating response:", e)
        return "I'm sorry, I couldn't process that."


def call_openai_chat(prompt, max_tokens=150, temperature=0.7, retries=3, backoff_base=1.5):
    """Call OpenAI Chat API with retries and backoff. Detects quota/rate-limit issues and disables OpenAI on persistent failure.

    Returns: text response (str)
    """
    global OPENAI_AVAILABLE
    for attempt in range(1, retries + 1):
        try:
            completion = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            err_str = str(e).lower()
            print(f"OpenAI call failed (attempt {attempt}/{retries}):", e)

            # If error suggests quota/rate limit, try a couple times then disable
            if 'quota' in err_str or 'insufficient_quota' in err_str or '429' in err_str or 'rate limit' in err_str:
                # if last attempt, mark unavailable
                if attempt == retries:
                    print('OpenAI quota or rate-limit detected. Disabling OpenAI calls until manual reset.')
                    OPENAI_AVAILABLE = False
                    return "AI services are temporarily unavailable due to quota limits. Please check your OpenAI billing or set `OPENAI_DISABLED` to use a local fallback."
                else:
                    sleep_time = backoff_base ** attempt
                    time.sleep(sleep_time)
                    continue
            else:
                # For other transient errors, use exponential backoff and retry
                if attempt == retries:
                    print('OpenAI API persistent error. Falling back to default message.')
                    return "I'm sorry, I couldn't process that right now."
                else:
                    sleep_time = backoff_base ** attempt
                    time.sleep(sleep_time)
                    continue


def take_command():
    """Listen for a voice command and return it as text."""
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.pause_threshold = 1
        audio = r.listen(source)
    try:
        print("Recognizing...")
        query = r.recognize_google(audio, language='en-in')
        print(f"User said: {query}\n")
        return query.lower()
    except Exception as e:
        print("Could not understand audio, please say that again.")
        speak("Could not understand audio, please say that again.")
        return None

class Assistant3DInterface(threading.Thread):
    """A simple Tkinter window showing a looping animated GIF as a 3D assistant avatar."""
    def __init__(self, gif_path="assistant_avatar.gif"):
        super().__init__(daemon=True)
        self.gif_path = gif_path

    def run(self):
        root = tk.Tk()
        root.title("Virtual 3D Assistant")
        root.geometry("320x400")
        root.resizable(False, False)
        lbl = tk.Label(root)
        lbl.pack(expand=True)

        # Load GIF
        gif = Image.open(self.gif_path)
        frames = [ImageTk.PhotoImage(frame.copy().convert("RGBA")) for frame in ImageSequence.Iterator(gif)]

        def update(ind):
            frame = frames[ind]
            lbl.configure(image=frame)
            ind = (ind + 1) % len(frames)
            root.after(60, update, ind)

        root.after(0, update, 0)
        root.mainloop()

def show_intro_page():
    """Display an introduction interface page before starting the assistant."""
    intro_root = tk.Tk()
    intro_root.title("Welcome to Virtual 3D Assistant")
    intro_root.geometry("500x420")
    intro_root.resizable(False, False)

    # Welcome label
    lbl_title = tk.Label(intro_root, text="Virtual 3D Assistant", font=("Arial", 22, "bold"))
    lbl_title.pack(pady=15)

    lbl_intro = tk.Label(
        intro_root,
        text=(
            "Hello! I am your Virtual 3D Assistant.\n"
            "I am here to make your daily tasks easier and more interactive.\n\n"
            "Features:\n"
            "• Weather Forecast: Get real-time weather updates for any city.\n"
            "• Time & Date: Ask for the current time.\n"
            "• Web Search: Search Google or Wikipedia for instant answers.\n"
            "• Music Player: Play your favorite music from your computer.\n"
            "• File Management: Create or delete text files by voice.\n"
            "• Webcam: Capture images using your webcam.\n"
            "• System Control: Open websites, close tabs, or even shut down your PC.\n"
            "• Conversational AI: Chat with me for information or just for fun!\n\n"
            "Click Start to begin your experience."
        ),
        font=("Arial", 12),
        justify="left",
        anchor="w",
        wraplength=460
    )
    lbl_intro.pack(padx=20, pady=10, fill="both")

    def start_assistant():
        intro_root.destroy()

    btn_start = tk.Button(intro_root, text="Start", font=("Arial", 14), command=start_assistant)
    btn_start.pack(pady=20)

    intro_root.mainloop()

def send_whatsapp_message(phone_number, message, time_hour, time_minute):
    """
    Send a WhatsApp message at a specific time.
    phone_number: str, e.g. '+911234567890'
    message: str
    time_hour: int (24-hour format)
    time_minute: int
    """
    pywhatkit.sendwhatmsg(phone_number, message, time_hour, time_minute)

def send_instagram_message(username, password, recipient, message):
    """
    Automate Instagram DM sending.
    username: your Instagram username
    password: your Instagram password
    recipient: recipient's Instagram username
    message: message to send
    """
    driver = webdriver.Chrome()  # Make sure chromedriver is in PATH
    driver.get("https://www.instagram.com/")
    time.sleep(3)

    # Login
    driver.find_element(By.NAME, "username").send_keys(username)
    driver.find_element(By.NAME, "password").send_keys(password + Keys.RETURN)
    time.sleep(5)

    # Go to DM
    driver.get(f"https://www.instagram.com/direct/inbox/")
    time.sleep(5)

    # Search for recipient
    driver.find_element(By.XPATH, "//button[contains(text(),'Send Message')]").click()
    time.sleep(2)
    search_box = driver.find_element(By.NAME, "queryBox")
    search_box.send_keys(recipient)
    time.sleep(2)
    driver.find_element(By.XPATH, f"//div[text()='{recipient}']").click()
    time.sleep(2)
    driver.find_element(By.XPATH, "//div[text()='Next']").click()
    time.sleep(2)

    # Send message
    text_area = driver.find_element(By.TAG_NAME, "textarea")
    text_area.send_keys(message)
    text_area.send_keys(Keys.RETURN)
    time.sleep(2)
    driver.quit()


# --- Dialogflow / Google Assistant webhook helpers ---
app = Flask(__name__)

def google_search_text(query):
    """Return a short text answer from the top Google result (no speaking)."""
    try:
        for url in search(query, num_results=1):
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            paragraphs = soup.find_all('p')
            if paragraphs:
                return paragraphs[0].get_text()
        return "I couldn't find a suitable answer."
    except Exception as e:
        print(e)
        return "An error occurred while searching."

def wiki_summary_text(query):
    try:
        summary = wikipedia.summary(query, sentences=2)
        return f"According to Wikipedia: {summary}"
    except Exception as e:
        print(e)
        return "I couldn't find results on Wikipedia."

def time_text():
    return datetime.datetime.now().strftime("The time is %H:%M:%S")


@app.route('/webhook', methods=['POST'])
def dialogflow_webhook():
    """A simple Dialogflow-compatible webhook. Maps intents to assistant functions and returns JSON responses."""
    # Basic token validation: Dialogflow can send a custom header 'X-Webhook-Token' or include it via
    # a header set in your gateway. This prevents public access when exposing with ngrok.
    token = request.headers.get('X-Webhook-Token')
    if WEBHOOK_TOKEN and token != WEBHOOK_TOKEN:
        return jsonify({'fulfillmentText': 'Unauthorized webhook request.'}), 401

    req = request.get_json(silent=True, force=True)
    try:
        intent = req.get('queryResult', {}).get('intent', {}).get('displayName', '')
        params = req.get('queryResult', {}).get('parameters', {})
        if intent.lower().startswith('getweather') or 'weather' in intent.lower():
            city = params.get('geo-city') or params.get('city') or params.get('location')
            if city:
                text = get_weather_text(city)
            else:
                text = 'Which city would you like the weather for?'
        elif 'wikipedia' in intent.lower() or 'wiki' in intent.lower():
            query = params.get('any') or params.get('topic') or req.get('queryResult', {}).get('queryText', '')
            text = wiki_summary_text(query)
        elif 'google_search' in intent.lower() or 'search' in intent.lower():
            query = params.get('any') or req.get('queryResult', {}).get('queryText', '')
            text = google_search_text(query)
        elif 'time' in intent.lower():
            text = time_text()
        else:
            # Fallback to OpenAI/GPT for conversational responses
            user_query = req.get('queryResult', {}).get('queryText', '')
            text = generate_response(user_query)

        # Build Dialogflow v2 response with Google Assistant payload to ensure spoken reply
        response_json = {
            'fulfillmentText': text,
            'payload': {
                'google': {
                    'expectUserResponse': False,
                    'richResponse': {
                        'items': [
                            {
                                'simpleResponse': {
                                    'textToSpeech': text
                                }
                            }
                        ]
                    }
                }
            }
        }
        return jsonify(response_json)
    except Exception as e:
        print('Webhook error:', e)
        return jsonify({'fulfillmentText': "Sorry, something went wrong processing that request."})

def start_webhook_server(host='0.0.0.0', port=5000):
    """Start the Flask webhook server in a background thread."""
    def run():
        app.run(host=host, port=port, debug=False)
    t = threading.Thread(target=run, daemon=True)
    t.start()

def main():
    # Show introduction page first
    show_intro_page()

    # Start the 3D assistant interface in a separate thread
    avatar_gif = r"c:\Users\LENOVO\OneDrive\Desktop\python\assistant_avatar.gif"  # Place your animated GIF in the same directory
    if os.path.exists(avatar_gif):
        Assistant3DInterface(avatar_gif).start()
    else:
        print(f"Avatar GIF '{avatar_gif}' not found. 3D interface will not be shown.")

    # Start the Dialogflow / Google Assistant webhook server so Actions/Dialogflow can call this assistant
    try:
        start_webhook_server(host='0.0.0.0', port=5000)
        print("Webhook server started on port 5000 (use ngrok to expose it to the internet).")
    except Exception as e:
        print("Failed to start webhook server:", e)

    greet_user()
    while True:
        command = take_command()
        if command is None:
            continue

        # Handle specific commands
        if "weather" in command or "forecast" in command:
            speak("Which city's weather would you like to know?")
            city = take_command()
            if city:
                get_weather(city)
        elif "time" in command:
            current_time = datetime.datetime.now().strftime("%H:%M:%S")
            speak(f"The time is {current_time}")
        elif "open youtube" in command:
            speak("Opening YouTube")
            webbrowser.open("https://www.youtube.com")
        elif "open google" in command:
            speak("Opening Google")
            webbrowser.open("https://www.google.com")
        elif "search google" in command:
            speak("What should I search for?")
            query = take_command()
            if query:
                google_search_and_answer(query)
        elif "search wikipedia" in command:
            speak("What should I search on Wikipedia?")
            query = take_command()
            if query:
                speak(f"Searching Wikipedia for {query}")
                try:
                    summary = wikipedia.summary(query, sentences=2)
                    speak("According to Wikipedia")
                    speak(summary)
                except wikipedia.exceptions.DisambiguationError:
                    speak("There are multiple results for this query. Please be more specific.")
                except wikipedia.exceptions.PageError:
                    speak("I couldn't find any results for this query.")
        elif "play music" in command:
            music_dir = "C:\\Users\\LENOVO\\Music"  # Update this path to your music folder
            songs = os.listdir(music_dir)
            if songs:
                os.startfile(os.path.join(music_dir, songs[0]))
            else:
                speak("No music files found in the directory.")
        elif "create file" in command:
            speak("What should I name the file?")
            file_name = take_command()
            if file_name:
                with open(f"{file_name}.txt", "w") as file:
                    speak(f"File {file_name}.txt has been created.")
        elif "delete file" in command:
            speak("Which file should I delete?")
            file_name = take_command()
            if file_name:
                try:
                    os.remove(f"{file_name}.txt")
                    speak(f"File {file_name}.txt has been deleted.")
                except FileNotFoundError:
                    speak("File not found.")
        elif "close tab" in command:
            speak("Closing the current tab.")
            os.system("taskkill /im chrome.exe /f")  # Example for closing Chrome tabs
        elif "shutdown system" in command:
            speak("Shutting down the system.")
            os.system("shutdown /s /t 1")
        elif "use webcam" in command or "capture image" in command:
            capture_image()
        elif "send whatsapp" in command:
            speak("Please provide the phone number with country code.")
            phone_number = take_command()
            speak("What is the message?")
            message = take_command()
            speak("At what hour should I send the message? Please say the hour in 24-hour format.")
            hour = take_command()
            speak("At what minute?")
            minute = take_command()
            try:
                send_whatsapp_message(phone_number, message, int(hour), int(minute))
                speak("WhatsApp message scheduled successfully.")
            except Exception as e:
                speak("Failed to send WhatsApp message.")
                print(e)
        elif "exit" in command or "quit" in command:
            speak("Goodbye! Have a great day!")
            break
        else:
            # Use OpenAI GPT for conversational responses
            response = generate_response(command)
            speak(response)

if __name__ == "__main__":
    main()