import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    HOMEY_IP = os.getenv('HOMEY_IP')
    HOMEY_API_KEY = os.getenv('HOMEY_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    SECRET_KEY = os.getenv('SECRET_KEY')
    HOMEY_URL = os.getenv('HOMEY_URL', 'http://192.168.0.108')

    @classmethod
    def validate_config(cls):
        required_vars = ['HOMEY_IP', 'HOMEY_API_KEY', 'OPENAI_API_KEY', 'SECRET_KEY']
        missing_vars = [var for var in required_vars if not getattr(cls, var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    @staticmethod
    def init_app(app):
        Config.validate_config()
        pass

    @classmethod
    def get_preferences(cls):
        """Get preferences with default values"""
        return {
            'chatbot_personality': os.getenv('CHATBOT_PERSONALITY', 'friendly and helpful'),
            'elevenlabs_voice_id': os.getenv('ELEVENLABS_VOICE_ID', '')
        } 