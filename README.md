# AIPersonalizedAnchorDesk

An AI-powered personalized newspaper application that fetches news from your favorite categories, summarizes them using Large Language Models (LLMs), and interacts with you through a prompt-engineered AI News Reporter Assistant. The application adapts based on your feedback, refining its summaries and content delivery over time.

## Features

- **Personalized News Retrieval**: Fetch news from your selected categories using the NewsAPI.
- **Summarized Content**: Utilize LLMs (e.g., GPT-3.5-turbo) to create concise, adaptive summaries of news articles.
- **AI News Reporter Assistant**: Experience an interactive, voice-driven interface that leverages prompt engineering to interpret requests, provide structured summaries, and maintain a natural conversational flow.
- **Adaptive Learning**: Continuously improve based on user feedback, adjusting both the detail in summaries and the priority of categories.
- **Prompt Engineering**: Fine-tuned prompts guide the LLM’s responses, ensuring reliable interpretation of user commands and dynamically refined summaries that respond to user preferences.

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- [OpenAI API Key](https://platform.openai.com/signup)
- [NewsAPI Key](https://newsapi.org/)

### Installation

1. **Clone the Repository**
   
   ```bash
   git clone https://github.com/your-username/AIPersonalizedAnchorDesk.git
   cd AIPersonalizedAnchorDesk

2. **(Optional) Create and Activate a Virtual Environment**
   
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. **Install Dependencies**
   
   ```bash
   pip install -r requirements.txt
   
4. **Set Up API Keys**
   
   ```bash
   OPENAI_API_KEY = 'YOUR_OPENAI_API_KEY'
   NEWSAPI_KEY = 'YOUR_NEWSAPI_KEY'

5. **Access the Application**
   
   ```bash
   streamlit run app.py

6. Access the Application
   Open your web browser and navigate to the URL provided by Streamlit (usually http://localhost:8501).









