import streamlit as st
import requests
import json
import os
import openai
from datetime import datetime
from gtts import gTTS
import tempfile
import speech_recognition as sr
import streamlit.components.v1 as components
from jinja2 import Template
import pygame
import threading
import time
import re

# Set up the page layout and appearance.
st.set_page_config(layout="wide")

# Prepare API keys and other configurations needed for communicating with external services.
from config import OPENAI_API_KEY, NEWSAPI_KEY
openai.api_key = OPENAI_API_KEY

# Define some variables that we’ll use throughout the program.
PREFERENCES_FILE = 'preferences.json'
FEEDBACK_FILE = 'feedback.json'
NEWS_CATEGORIES = [
    'Business', 'Entertainment', 'General', 'Health', 'Science', 'Sports', 'Technology'
]

# Initialize Pygame’s mixer so we can play audio.
pygame.mixer.init()

# Below are various helper functions for tasks like loading/saving preferences, 
# retrieving feedback, calling APIs for news articles, and generating audio summaries.

def load_preferences():
    # Load the user’s saved preferences, if they exist.
    if os.path.exists(PREFERENCES_FILE):
        with open(PREFERENCES_FILE, 'r') as f:
            return json.load(f)
    return None

def save_preferences(preferences):
    # Save the user’s preferences to a file for future use.
    with open(PREFERENCES_FILE, 'w') as f:
        json.dump(preferences, f)

def load_feedback():
    # Load any feedback previously given by the user.
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'r') as f:
            return json.load(f)
    return []

def save_feedback(feedback_list):
    # Save the updated feedback list back to the file.
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(feedback_list, f)

def store_feedback(feedback, preferences):
    # Record new feedback along with the user’s chosen categories.
    feedback_list = load_feedback()
    feedback_entry = {
        'timestamp': datetime.now().isoformat(),
        'feedback': feedback,
        'preferences': preferences.get('categories', [])
    }
    feedback_list.append(feedback_entry)
    save_feedback(feedback_list)
    print(f"Feedback stored: {feedback_entry}")

def analyze_feedback():
    # Evaluate past feedback to see which categories got positive or negative reactions.
    feedback_list = load_feedback()
    category_feedback = {}
    for entry in feedback_list:
        feedback_value = 1 if entry['feedback'] == 'positive' else -1
        for category in entry['preferences']:
            if category not in category_feedback:
                category_feedback[category] = {'score': 0, 'count': 0}
            category_feedback[category]['score'] += feedback_value
            category_feedback[category]['count'] += 1
    return category_feedback

def get_news_articles(categories, articles_per_category=5):
    # Fetch top news headlines from the specified categories using the NewsAPI.
    all_articles = []
    for category in categories:
        url = (
            f'https://newsapi.org/v2/top-headlines?'
            f'category={category.lower()}&'
            f'language=en&'
            f'pageSize={articles_per_category}&'
            f'apiKey={NEWSAPI_KEY}'
        )
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for article in data['articles']:
                article['category'] = category
                all_articles.append(article)
    return all_articles

def adjust_prompt_based_on_feedback(base_prompt, feedback_analysis):
    # Tune the prompt for the language model based on user feedback trends.
    overall_score = sum([cat['score'] for cat in feedback_analysis.values()])
    if overall_score < 0:
        # If feedback is generally negative, make summaries shorter and simpler.
        adjusted_prompt = base_prompt + "\nPlease make the summary concise and easy to understand."
    elif overall_score > 0:
        # If feedback is positive, allow more detailed summaries.
        adjusted_prompt = base_prompt + "\nFeel free to include important details."
    else:
        # If it’s neutral, just use the base prompt.
        adjusted_prompt = base_prompt
    return adjusted_prompt

def summarize_articles(articles, feedback_analysis):
    # Use the language model to summarize each article’s content.
    summaries = []
    for article in articles:
        content = article.get('content') or article.get('description') or ''
        if content:
            base_prompt = (
                f"Summarize the following article in 150 words:\n"
                f"Title: {article['title']}\nContent: {content}"
            )
            adjusted_prompt = adjust_prompt_based_on_feedback(base_prompt, feedback_analysis)
            try:
                response = openai.ChatCompletion.create(
                    model='gpt-3.5-turbo',
                    messages=[{"role": "user", "content": adjusted_prompt}],
                    max_tokens=300,
                    temperature=0,
                    request_timeout=10
                )
                summary = response.choices[0].message['content'].strip()
                article_full_text = content
            except Exception as e:
                print(f"Error summarizing article: {e}")
                summary = "Summary not available."
                article_full_text = content
        else:
            # In case the article has no content to summarize.
            print(f"No content available for article: {article['title']}")
            summary = "Summary not available."
            article_full_text = "Full text not available."
        summaries.append({
            'title': article['title'],
            'summary': summary,
            'full_text': article_full_text,
            'url': article['url'],
            'image': article.get('urlToImage'),
            'category': article.get('category', 'General')
        })
    return summaries

def generate_news_anchor_audio(text):
    # Convert text into a short audio segment. Keep it brief to avoid long processing times.
    max_length = 500
    text = text[:max_length]
    tts = gTTS(text=text, lang='en', slow=False)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
        tts.save(tmp.name)
        return tmp.name

def generate_news_anchor_audio_chunks(text, chunk_size=500):
    # Break longer text into smaller chunks so it can be processed easily by TTS.
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    audio_files = []
    for idx, chunk in enumerate(chunks):
        tts = gTTS(text=chunk, lang='en', slow=False)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'_{idx}.mp3')
        tts.save(tmp_file.name)
        audio_files.append(tmp_file.name)
    return audio_files

def play_audio(audio_file, interrupt_event):
    # Play the provided audio file and allow for interruption if needed.
    pygame.mixer.music.load(audio_file)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        if interrupt_event.is_set():
            pygame.mixer.music.stop()
            break
        time.sleep(0.1)

def play_audio_sequence(audio_files, interrupt_event):
    # Play a sequence of audio files one after another, stopping if interrupted.
    for audio_file in audio_files:
        if interrupt_event.is_set():
            break
        pygame.mixer.music.load(audio_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if interrupt_event.is_set():
                pygame.mixer.music.stop()
                break
            time.sleep(0.1)

def display_news_anchor_panel(video_url):
    # This is where you could display a video news anchor if desired.
    pass

def interpret_user_intent(user_input, categories, headlines):
    # Understand what the user wants based on their speech or text input.
    numbered_headlines = [f"{idx+1}: {headline}" for idx, headline in enumerate(headlines)]
    prompt = (
        f"You are an assistant for a personalized newspaper application. "
        f"The user's selected news categories are: {', '.join(categories)}. "
        f"The headlines are: {', '.join(numbered_headlines)}. "
        f"Your task is to interpret the user's intent based on their input and output a JSON object with an 'action' and relevant parameters. "
        f"Possible actions are: 'select_category', 'select_headline', 'get_full_article', 'unknown'. "
        f"For example, if the user says 'Tell me about Technology', your response should be {{'action': 'select_category', 'category': 'Technology'}}. "
        f"If the user says 'I want to hear more about headline number two', your response should be {{'action': 'select_headline', 'headline': '2'}}. "
        f"User says: \"{user_input}\" "
        f"Your response should be a JSON object with keys 'action' and any relevant parameters, and nothing else."
    )
    try:
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0,
            request_timeout=10
        )
        assistant_reply = response.choices[0].message['content'].strip()
        print(f"Assistant raw reply: {assistant_reply}")
        json_match = re.search(r'\{.*?\}', assistant_reply, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
            intent = json.loads(json_text)
            return intent
        else:
            print("No JSON object found in assistant's reply.")
            return {'action': 'unknown'}
    except Exception as e:
        print(f"Error interpreting user input: {e}")
        return {'action': 'unknown'}

def get_voice_input(timeout=5):
    # Listen for user speech and convert it into text using Google’s speech recognition.
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info("Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=timeout)
            user_input = recognizer.recognize_google(audio)
            print(f"User said: {user_input}")
            return user_input
    except Exception as e:
        print(f"Voice Input Error: {e}")
        return None

def handle_user_interaction(categories, summaries):
    # Main loop to manage voice interactions after the greeting.
    st.info("Voice interaction started. Say 'exit' to stop.")
    last_headlines = None
    last_category = None
    while True:
        user_input = get_voice_input()
        if user_input:
            if "exit" in user_input.lower():
                # If the user says 'exit', provide a friendly goodbye and end the loop.
                farewell_text = "Goodbye! Feel free to call me anytime."
                farewell_audio = generate_news_anchor_audio(farewell_text)
                play_audio(farewell_audio, threading.Event())
                break
            if not last_category:
                # If we haven’t yet settled on a category, try to interpret what the user wants.
                assistant_intent = interpret_user_intent(user_input, categories, [])
                print(f"Assistant intent: {assistant_intent}")
                if assistant_intent['action'] == 'select_category':
                    category = assistant_intent.get('category')
                    if category and category in categories:
                        # Provide the headlines for the chosen category.
                        last_category = category
                        articles_in_category = [article for article in summaries if article['category'] == category]
                        headlines = [article['title'] for article in articles_in_category]
                        last_headlines = headlines
                        headlines_text = f"Here are the top headlines in {category}: " + " ".join([f"{idx +1}: {headline}." for idx, headline in enumerate(headlines)])
                        response_audio_file = generate_news_anchor_audio(headlines_text)
                        play_audio(response_audio_file, threading.Event())
                    else:
                        # If the category isn’t recognized or not part of the user’s chosen categories.
                        response_text = "I'm sorry, I didn't catch that category. Please choose from your selected categories."
                        response_audio_file = generate_news_anchor_audio(response_text)
                        play_audio(response_audio_file, threading.Event())
                else:
                    # Prompt the user to pick a category.
                    response_text = "Please tell me which category you'd like to hear about."
                    response_audio_file = generate_news_anchor_audio(response_text)
                    play_audio(response_audio_file, threading.Event())
            else:
                # We have a category selected, so now the user can choose a headline.
                assistant_intent = interpret_user_intent(user_input, categories, last_headlines or [])
                print(f"Assistant intent: {assistant_intent}")
                if assistant_intent['action'] == 'select_headline':
                    # If the user wants a specific headline, provide its summary and possibly full text.
                    headline_index = assistant_intent.get('headline')
                    if headline_index:
                        try:
                            idx = int(headline_index) - 1
                            articles_in_category = [article for article in summaries if article['category'] == last_category]
                            article = articles_in_category[idx]
                            summary_text = f"Here is a summary of headline {headline_index}: {article['summary']}. Would you like the full article?"
                            summary_chunks = generate_news_anchor_audio_chunks(summary_text)
                            play_audio_sequence(summary_chunks, threading.Event())
                            # After the summary, listen again to see if they want the full article.
                            user_response = get_voice_input()
                            if user_response and 'yes' in user_response.lower():
                                full_text = f"Here is the full article: {article['full_text']}"
                                full_text_chunks = generate_news_anchor_audio_chunks(full_text)
                                play_audio_sequence(full_text_chunks, threading.Event())
                            else:
                                acknowledgment_text = "Alright, let me know if you need anything else."
                                acknowledgment_audio_file = generate_news_anchor_audio(acknowledgment_text)
                                play_audio(acknowledgment_audio_file, threading.Event())
                        except (IndexError, ValueError):
                            # If the user’s headline number doesn’t exist.
                            response_text = "I'm sorry, that headline number is not valid. Please choose a valid headline number."
                            response_audio_file = generate_news_anchor_audio(response_text)
                            play_audio(response_audio_file, threading.Event())
                    else:
                        # If they said they want a headline but didn’t provide a number.
                        response_text = "Which headline number are you interested in?"
                        response_audio_file = generate_news_anchor_audio(response_text)
                        play_audio(response_audio_file, threading.Event())
                elif assistant_intent['action'] == 'select_category':
                    # If the user wants to switch categories, reset and start over.
                    last_category = None
                    last_headlines = None
                    continue
                else:
                    # If we don’t understand, prompt them to pick a headline number.
                    response_text = "Please mention the headline number you're interested in."
                    response_audio_file = generate_news_anchor_audio(response_text)
                    play_audio(response_audio_file, threading.Event())
        else:
            # If we didn't catch any user input.
            prompt_text = "I didn't hear anything. Could you please repeat?"
            prompt_audio_file = generate_news_anchor_audio(prompt_text)
            play_audio(prompt_audio_file, threading.Event())

def main():
    global preferences
    preferences = load_preferences()

    # Create a nicer-looking sidebar with helpful info and options.
    st.sidebar.markdown(
        """
        <style>
            .sidebar .sidebar-content {
                font-family: 'Arial', sans-serif;
                background-color: #2c3e50;
                color: white;
            }
            .sidebar h2 {
                font-size: 24px;
                color: #f1c40f;
                text-align: center;
                margin-bottom: 15px;
                font-weight: bold;
            }
            .sidebar hr {
                border: none;
                border-top: 2px solid #ecf0f1;
                margin: 10px 0;
            }
            .sidebar p {
                font-size: 16px;
                line-height: 1.5;
                color: #ecf0f1;
                padding: 0 10px;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.sidebar.title("👤 Personalized Newspaper")
    st.sidebar.write("An AI-powered personalized news experience.")
    st.sidebar.markdown("### Features")
    st.sidebar.write("""
    - **Personalized News Retrieval**: Fetch news from your favorite categories using advanced retrieval methods.
    - **Summarized Content**: Utilize Large Language Models (LLMs) to provide concise summaries of news articles.
    - **AI News Reporter Assistant**: Experience interactive news reporting through prompt-engineered AI assistants.
    - **Adaptive Learning**: Improve news recommendations based on your feedback and interactions.
    """)

    # If no preferences are found, prompt the user for their name and chosen categories.
    if preferences is None or 'name' not in preferences or 'categories' not in preferences:
        user_name = st.text_input("Enter your name", "")
        selected_categories = st.multiselect("Choose news categories:", NEWS_CATEGORIES)
        if st.button("Save Preferences") and user_name and selected_categories:
            preferences = {
                'name': user_name,
                'categories': selected_categories,
                'last_updated': datetime.now().isoformat()
            }
            save_preferences(preferences)
            st.success("Preferences saved! Reload the page.")
            st.experimental_rerun()
    else:
        # Check past feedback to tailor the experience.
        feedback_analysis = analyze_feedback()

        # Sort categories by their feedback scores, so more positively received categories appear first.
        sorted_categories = sorted(
            preferences['categories'],
            key=lambda x: feedback_analysis.get(x, {}).get('score', 0),
            reverse=True
        )

        # Display a warm, personalized welcome message.
        st.markdown(
            f"""
            <div style="text-align: center; margin: 20px 0;">
                <h1 style="font-size: 36px; color: #1abc9c; font-family: 'Georgia', serif;">
                    Welcome back, {preferences['name']}!
                </h1>
                <p style="font-size: 18px; color: #7f8c8d; font-family: 'Arial', sans-serif;">
                    Your personalized newspaper is ready with the latest news updates.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Provide a quick way for users to give feedback on their news experience.
        st.write("Please provide your feedback on your personalized newspaper:")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("👍 Thumbs Up"):
                feedback = 'positive'
                store_feedback(feedback, preferences)
                st.success("Thank you for your feedback!")

        with col2:
            if st.button("👎 Thumbs Down"):
                feedback = 'negative'
                store_feedback(feedback, preferences)
                st.success("Thank you for your feedback!")

        # Fetch articles from the user’s preferred categories and summarize them.
        articles = get_news_articles(sorted_categories)
        summaries = summarize_articles(articles, feedback_analysis)

        # Choose the first article’s summary as the “main headline.”
        if summaries:
            main_headline = {
                'title': summaries[0]['title'],
                'summary': summaries[0]['summary'],
                'image': summaries[0].get('image', None)
            }
        else:
            main_headline = {
                'title': "No articles available",
                'summary': "No summary available",
                'image': None
            }

        # Organize articles by category for the displayed newspaper layout.
        sections = [
            {
                'title': cat,
                'articles': [art for art in summaries if art['category'] == cat]
            } for cat in sorted_categories
        ]

        # Load and render the HTML template for the newspaper view.
        with open('template.html', 'r', encoding='utf-8') as f:
            template = Template(f.read())
        html_content = template.render(
            newspaper_title="The Daily News",
            issue_details=f"{datetime.now().strftime('%A, %B %d, %Y')}",
            main_headline=main_headline,
            sections=sections
        )
        components.html(html_content, height=1500, scrolling=True)

        # Greet the user and invite them to choose a category to start with.
        greeting = (
            f"Good morning {preferences['name']}, I'm your AI News Reporter Emily. "
            f"Today is {datetime.now().strftime('%A, %B %d')}, and your personalized newspaper has been generated. "
            f"Your preferred news categories are {', '.join(sorted_categories)}. "
            "Let me know which category should I start reporting with first."
        )
        greeting_audio_file = generate_news_anchor_audio(greeting)
        display_news_anchor_panel(None)

        # Play the greeting, then wait for user interaction.
        play_audio(greeting_audio_file, threading.Event())

        # Begin handling voice commands.
        handle_user_interaction(sorted_categories, summaries)

if __name__ == "__main__":
    main()
