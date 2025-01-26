from flask import render_template, jsonify, request, session, Response
import re
from app import app
from app.homey_api import HomeyAPI
from app.gpt_assistant import GPTAssistant
import uuid
import whisper
from tempfile import NamedTemporaryFile
import os
from openai import OpenAI
from app.config import Config
import json
import requests

# Initialize Whisper model (you might want to do this at app startup)
whisper_model = whisper.load_model("base")

# Initialize OpenAI client
client = OpenAI(api_key=Config.OPENAI_API_KEY)

@app.before_request
def before_request():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

@app.route('/')
@app.route('/devices')
def devices():
    homey = HomeyAPI()
    all_devices = homey.get_formatted_devices()
    
    # Calculate total power and active devices
    total_power = 0
    active_devices = 0
    for device in all_devices:
        if 'measure_power' in device.get('capabilities', []):
            power = homey.get_capability(device['id'], 'measure_power')
            if power:
                total_power += power
        if 'onoff' in device.get('capabilities', []):
            state = homey.get_capability(device['id'], 'onoff')
            if state:
                active_devices += 1

    # Group devices by type
    device_groups = {
        'Lighting': [],
        'Sensors': [],
        'Media': [],
        'Climate': [],
        'Other': []
    }

    for device in all_devices:
        caps = device.get('capabilities', [])
        if device.get('is_sensor'):
            device_groups['Sensors'].append(device)
        elif 'speaker_playing' in caps:
            device_groups['Media'].append(device)
        elif 'measure_temperature' in caps:
            device_groups['Climate'].append(device)
        elif 'onoff' in caps and any(cap in caps for cap in ['dim', 'light_saturation', 'light_temperature']):
            device_groups['Lighting'].append(device)
        else:
            device_groups['Other'].append(device)

    return render_template('devices.html', 
                         device_groups=device_groups,
                         total_power=round(total_power),
                         active_devices=active_devices)

@app.route('/api/device/<device_id>/capability/<capability>', methods=['GET'])
def get_device_state(device_id, capability):
    try:
        homey = HomeyAPI()
        value = homey.get_capability(device_id, capability)
        if value is not None:
            return jsonify({'value': value})
        # Check if device exists and has the capability
        devices = homey.get_devices()
        if device_id not in devices:
            return jsonify({'error': f'Device {device_id} not found'}), 404
        device = devices[device_id]
        if capability not in device.get('capabilities', []):
            return jsonify({'error': f'Device {device_id} does not have capability {capability}'}), 400
        # If we get here, the device exists but returned no value
        return jsonify({'value': 0}), 200  # Return a default value
    except Exception as e:
        print(f"Error in get_device_state: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/device/<device_id>/capability/<capability>', methods=['PUT'])
def control_device(device_id, capability):
    try:
        value = request.json.get('value')
        if value is None:
            return jsonify({'error': 'No value provided'}), 400
            
        homey = HomeyAPI()
        success = homey.set_capability(device_id, capability, value)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': f'Failed to set {capability} for device {device_id}'}), 400
    except Exception as e:
        print(f"Error in control_device: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/voice')
def voice():
    return render_template('voice.html')

@app.route('/api/chat', methods=['POST'])
def process_chat():
    message = request.json.get('message')
    assistant = GPTAssistant(session_id=session['session_id'])
    result = assistant.process_command(message)
    return jsonify(result)

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    assistant = GPTAssistant(session_id=session['session_id'])
    assistant.clear_history()
    return jsonify({'success': True})

@app.route('/api/device/<device_id>/sensor-data')
def get_sensor_data(device_id):
    try:
        homey = HomeyAPI()
        sensor_data = homey.get_sensor_data(device_id)
        if sensor_data is not None:
            return jsonify(sensor_data)
        return jsonify({'error': 'Failed to get sensor data'}), 400
    except Exception as e:
        print(f"Error in get_sensor_data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe-audio', methods=['POST'])
def transcribe_audio():
    try:
        if not Config.OPENAI_API_KEY:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
            
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
            
        audio_file = request.files['audio']
        
        # Save the audio file temporarily
        with NamedTemporaryFile(delete=False, suffix='.webm') as tmp_file:
            audio_file.save(tmp_file.name)
            
            # Transcribe using OpenAI API
            with open(tmp_file.name, 'rb') as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="text"
                )
            
            # Clean up the temporary file
            os.unlink(tmp_file.name)
            
            return jsonify({
                'text': transcript.strip()
            })
            
    except Exception as e:
        print(f"Error in transcribe_audio: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/preferences')
def preferences():
    prefs = Config.get_preferences()
    prefs['ELEVENLABS_API_KEY'] = os.getenv('ELEVENLABS_API_KEY', '')
    return render_template('preferences.html', config=prefs)

@app.route('/api/preferences', methods=['POST'])
def update_preferences():
    try:
        data = request.get_json()
        response = jsonify({"success": True})
        # Set preferences in cookie for server-side access
        response.set_cookie('preferences', json.dumps(data))
        return response
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/generate-personality', methods=['POST'])
def generate_personality():
    try:
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "system",
                "content": """You are a creative assistant that generates unique and interesting chatbot personalities.
Generate a brief (2-4 sentences) personality description that would make a home automation assistant interesting and engaging and fun and unexpected.
Focus on combinations of traits that would make the interaction fun and useful.
Only return the personality description, nothing else."""
            }],
            temperature=0.9,
            max_tokens=20
        )
        
        personality = response.choices[0].message.content.strip()
        return jsonify({"personality": personality})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/speak', methods=['POST'])
def speak():
    try:
        text = request.json.get('text')
        #strip markup from text like hash vertical bars and other markup characters     
        text = re.sub(r'#', '', text)
        text = re.sub(r'[*_~`]', '', text)
        text = re.sub(r'\|', '', text)
        text = re.sub(r'\n', '', text)
        if not text:
            return jsonify({'error': 'No text provided'}), 400
            
        voice_id = request.json.get('voice_id') or Config.get_preferences().get('elevenlabs_voice_id')
        if not voice_id:
            return jsonify({'error': 'No voice ID configured'}), 400
        
        # Call ElevenLabs API
        response = requests.post(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}',
            headers={
                'Accept': 'audio/mpeg',
                'xi-api-key': os.getenv('ELEVENLABS_API_KEY', ''),
                'Content-Type': 'application/json'
            },
            json={
                'text': text,
                'model_id': 'eleven_turbo_v2',
                'voice_settings': {
                    'stability': 0.5,
                    'similarity_boost': 0.5
                }
            },
            stream=True
        )
        
        if not response.ok:
            error_msg = response.json().get('detail', {}).get('message', 'Speech generation failed')
            return jsonify({'error': error_msg}), response.status_code
        
        return Response(
            response.iter_content(chunk_size=8192),
            content_type='audio/mpeg'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500 