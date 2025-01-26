from openai import OpenAI
from app.config import Config
from app.homey_api import HomeyAPI
import json
from collections import defaultdict
import logging
from flask import request

# Module-level conversation store
conversation_store = defaultdict(list)

class GPTAssistant:
    def __init__(self, session_id='default'):
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == 'your-openai-api-key':
            raise ValueError("OpenAI API key not configured")
            
        self.session_id = session_id
        self.homey = HomeyAPI()
        self.devices = self.homey.get_formatted_devices()
        self.client = OpenAI(api_key=Config.OPENAI_API_KEY)
        self.preferences = self._load_preferences()
        # Add initial overview to conversation history
        self.conversation_history = [{
            "role": "system",
            "content": self._create_system_prompt()
        }, {
            "role": "assistant",
            "content": self._create_welcome_message()
        }]

    @property
    def conversation_history(self):
        return conversation_store[self.session_id]

    @conversation_history.setter
    def conversation_history(self, value):
        conversation_store[self.session_id] = value

    def clear_history(self):
        conversation_store[self.session_id] = []

    def get_sensor_value(self, device_id, capability):
        """Get the current value of a sensor capability"""
        try:
            value = self.homey.get_capability(device_id, capability)
            return value
        except Exception as e:
            logging.error(f"Error getting sensor value: {str(e)}")
            return None

    def get_device_by_name(self, name):
        """Find a device by its name (case insensitive partial match)"""
        name = name.lower()
        for device in self.devices:
            if name in device['name'].lower():
                return device
        return None

    def _load_preferences(self):
        """Load preferences from localStorage via Flask session"""
        try:
            stored = request.cookies.get('preferences')
            if stored:
                return json.loads(stored)
        except Exception:
            pass
        return Config.get_preferences()

    def _create_system_prompt(self):
        devices_info = []
        for device in self.devices:
            name = device['name']
            device_id = device['id']
            capabilities = device['capabilities']
            if capabilities:
                # Add current values for sensor capabilities
                sensor_info = []
                for cap in capabilities:
                    if any(sensor_type in cap for sensor_type in ['measure', 'meter', 'alarm']):
                        value = self.get_sensor_value(device_id, cap)
                        if value is not None:
                            # Format the value based on type
                            if 'temperature' in cap:
                                sensor_info.append(f"{cap}={value}°C")
                            elif 'humidity' in cap:
                                sensor_info.append(f"{cap}={value}%")
                            elif 'power' in cap:
                                sensor_info.append(f"{cap}={value}W")
                            else:
                                sensor_info.append(f"{cap}={value}")
                
                devices_info.append(f"- {name}: ID={device_id}, capabilities={capabilities}" + 
                                  (f", current values: {', '.join(sensor_info)}" if sensor_info else ""))
        
        return f"""You are a home automation assistant with a {self.preferences['chatbot_personality']} personality. 
Format your responses using Markdown for better readability.
Use code blocks with language tags when showing values or data.
Use tables when comparing multiple values.
Use bullet points for lists of options or devices.

You can control these devices and read their sensors:

{chr(10).join(devices_info)}

When asked about sensor values, I will fetch the current values for you.
When asked about temperature, specify which sensor you're reading from.
Use the provided functions to control devices. 
Respond in a {self.preferences['chatbot_personality']} manner while being concise and clear."""

    def _create_welcome_message(self):
        """Create a welcome message with device overview"""
        device_groups = {
            'Lighting': [],
            'Sensors': [],
            'Media': [],
            'Climate': [],
            'Other': []
        }
        
        for device in self.devices:
            caps = device.get('capabilities', [])
            if any(cap.startswith('measure_') for cap in caps):
                device_groups['Sensors'].append(device)
            elif 'speaker_playing' in caps:
                device_groups['Media'].append(device)
            elif any(cap in ['measure_temperature', 'target_temperature'] for cap in caps):
                device_groups['Climate'].append(device)
            elif 'onoff' in caps and any(cap in caps for cap in ['dim', 'light_saturation']):
                device_groups['Lighting'].append(device)
            else:
                device_groups['Other'].append(device)
        
        message = "Hello! I'm your home assistant. Here's what I can control:\n\n"
        
        for group, devices in device_groups.items():
            if devices:
                message += f"📱 {group}:\n"
                for device in devices:
                    caps = [cap for cap in device['capabilities'] if not cap.startswith('has_')]
                    message += f"- {device['name']} ({', '.join(caps)})\n"
                message += "\n"
        
        message += "You can ask me to:\n"
        message += "- Control devices (e.g., 'turn on the living room lights')\n"
        message += "- Check sensors (e.g., 'what's the temperature outside?')\n"
        message += "- Monitor power usage (e.g., 'how much power are we using?')\n"
        message += "- Control media players (e.g., 'pause the music in the kitchen')\n"
        
        return message

    def _get_available_functions(self):
        return [{
            "name": "control_device",
            "description": "Control a home automation device",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The ID of the device to control"
                    },
                    "capability": {
                        "type": "string",
                        "description": "The capability to use (e.g., 'onoff', 'dim')"
                    },
                    "value": {
                        "type": ["boolean", "number"],
                        "description": "The value to set (boolean for onoff, float 0-1 for dim)"
                    }
                },
                "required": ["device_id", "capability", "value"]
            }
        }, {
            "name": "get_sensor_value",
            "description": "Get the current value of a sensor",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The ID of the device to read from"
                    },
                    "capability": {
                        "type": "string",
                        "description": "The sensor capability to read (e.g., 'measure_temperature', 'measure_power')"
                    }
                },
                "required": ["device_id", "capability"]
            }
        }]

    def _execute_function(self, function_name, function_args):
        if function_name == "control_device":
            success = self.homey.set_capability(
                function_args["device_id"],
                function_args["capability"],
                function_args["value"]
            )
            return success
        elif function_name == "get_sensor_value":
            value = self.get_sensor_value(
                function_args["device_id"],
                function_args["capability"]
            )
            return {"value": value}
        return False

    def process_command(self, message):
        try:
            if not message.strip():
                return {"error": "Empty message"}

            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": message
            })

            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=self.conversation_history,
                functions=self._get_available_functions(),
                function_call="auto",
                temperature=0.7,
                max_tokens=150
            )

            # Handle the response
            response_message = response.choices[0].message
            
            # Check if the model wants to call a function
            if hasattr(response_message, "function_call") and response_message.function_call:
                function_name = response_message.function_call.name
                function_args = json.loads(response_message.function_call.arguments)
                
                # Execute the function
                function_response = self._execute_function(function_name, function_args)
                
                # Add function call and result to conversation
                self.conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "function_call": {
                        "name": function_name,
                        "arguments": response_message.function_call.arguments
                    }
                })
                self.conversation_history.append({
                    "role": "function",
                    "name": function_name,
                    "content": json.dumps({"success": function_response})
                })
                
                print(self.conversation_history)
                # Get final response
                second_response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=self.conversation_history,
                    temperature=0.7,
                    max_tokens=150
                )
                assistant_message = second_response.choices[0].message.content
            else:
                assistant_message = response_message.content

            # Strip whitespace if content exists
            assistant_message = assistant_message.strip() if assistant_message else ""

            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            # Keep conversation history manageable
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]

            return {"response": assistant_message}

        except Exception as e:
            logging.error(f"Error in process_command: {str(e)}")
            return {"error": f"Sorry, I encountered an error: {str(e)}"} 