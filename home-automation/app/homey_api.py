import requests
from app.config import Config

class HomeyAPI:
    def __init__(self):
        self.base_url = f"http://{Config.HOMEY_IP}/api/manager/devices/device"
        self.headers = {"Authorization": f"Bearer {Config.HOMEY_API_KEY}"}

    def get_devices(self):
        response = requests.get(self.base_url, headers=self.headers)
        if response.status_code == 200:
            return response.json()
        print(f"Error getting devices: {response.status_code} - {response.text}")
        return None

    def get_formatted_devices(self):
        devices = self.get_devices()
        if not devices:
            return []
        
        formatted_devices = []
        for device_id, device_info in devices.items():
            capabilities = device_info.get('capabilities', [])
            # Check if device is primarily a sensor
            is_sensor = any(cap.startswith('measure_') for cap in capabilities)
            
            formatted_devices.append({
                'id': device_id,
                'name': device_info.get('name', 'Unknown'),
                'capabilities': capabilities,
                'capabilitiesObj': device_info.get('capabilitiesObj', {}),
                'is_sensor': is_sensor
            })
            print(f"Device {device_info.get('name')} capabilities: {capabilities}")
        return formatted_devices

    def get_capability(self, device_id, capability):
        # First, verify the device has this capability
        devices = self.get_devices()
        if not devices or device_id not in devices:
            print(f"Device {device_id} not found")
            return None
            
        device = devices[device_id]
        if capability not in device.get('capabilities', []):
            print(f"Device {device_id} does not have capability {capability}")
            return None

        # Get the capability value
        url = f"{self.base_url}/{device_id}/capability/{capability}"
        print(f"Requesting capability value from: {url}")
        response = requests.get(url, headers=self.headers)
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        if response.status_code == 200:
            value = response.json()
            # Handle null values
            if value is None:
                print(f"Received null value for device {device_id} capability {capability}")
                return 0  # Return a default value
            return value
        return None

    def set_capability(self, device_id, capability, value):
        # First, verify the device has this capability
        devices = self.get_devices()
        if not devices or device_id not in devices:
            print(f"Device {device_id} not found")
            return False
            
        device = devices[device_id]
        if capability not in device.get('capabilities', []):
            print(f"Device {device_id} does not have capability {capability}")
            return False

        # Set the capability value
        url = f"{self.base_url}/{device_id}/capability/{capability}"  # Changed to singular capability
        data = {"value": value}
        print(f"Setting capability value at: {url}")
        print(f"Data: {data}")
        response = requests.put(url, headers=self.headers, json=data)
        print(f"Response status: {response.status_code}")
        print(f"Response content: {response.text}")
        
        return response.status_code == 200 

    def get_sensor_data(self, device_id):
        """Get all sensor measurements for a device"""
        devices = self.get_devices()
        if not devices or device_id not in devices:
            print(f"Device {device_id} not found")
            return None
            
        device = devices[device_id]
        sensor_data = {}
        
        # List of measurement capabilities to check
        measurement_prefixes = ['measure_', 'meter_', 'wind_']
        
        for capability in device.get('capabilities', []):
            if any(capability.startswith(prefix) for prefix in measurement_prefixes):
                value = self.get_capability(device_id, capability)
                if value is not None:
                    # Get the unit from capabilitiesObj if available
                    unit = device.get('capabilitiesObj', {}).get(capability, {}).get('units', '')
                    title = device.get('capabilitiesObj', {}).get(capability, {}).get('title', capability)
                    sensor_data[capability] = {
                        'value': value,
                        'unit': unit,
                        'title': title
                    }
        
        return sensor_data 