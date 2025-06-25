import os
import json


class StateManager:
    """Manages system states and configurations"""
    def __init__(self, config_dir):
        self.config_dir = config_dir
        
    def load(self, state_name):
        try:
            config_file = os.path.join(self.config_dir, f"{state_name}.json")
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                return config
            else:
                print(f"Config file not found for state: {state_name}")
                return None
        except Exception as e:
            print(f"Error loading config for state {state_name}: {e}")
            return None 