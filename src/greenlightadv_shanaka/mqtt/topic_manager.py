"""
Topic Manager for MQTT Greenhouse Data
======================================

Manages MQTT topic structure and data formatting for greenhouse simulation data.
Provides meaningful variable names and organized topic hierarchy.
"""

import json
import time
from typing import Dict, Any, List


class TopicManager:
    """Manages MQTT topic naming and data structure for greenhouse simulation."""
    
    def __init__(self, greenhouse_id: str = "greenhouse_01"):
        """
        Initialize TopicManager.
        
        Args:
            greenhouse_id: Unique identifier for this greenhouse instance
        """
        self.greenhouse_id = greenhouse_id
        self.base_topic = f"greenlight/{greenhouse_id}"
        
        # Define topic categories and their variables
        self.topic_mapping = {
            "climate": {
                "description": "Greenhouse climate variables",
                "variables": {
                    "air_temperature": {"unit": "°C", "description": "Air temperature"},
                    "air_humidity": {"unit": "%", "description": "Relative humidity"},
                    "air_co2": {"unit": "ppm", "description": "CO2 concentration"},
                    "vapor_pressure": {"unit": "Pa", "description": "Vapor pressure"},
                    "canopy_temperature": {"unit": "°C", "description": "Canopy temperature"},
                }
            },
            "energy": {
                "description": "Energy consumption and generation",
                "variables": {
                    "heating_power": {"unit": "W", "description": "Heating system power"},
                    "lighting_power": {"unit": "W", "description": "Lighting system power"},
                    "total_energy": {"unit": "MJ", "description": "Total energy consumption"},
                    "pipe_temperature": {"unit": "°C", "description": "Heating pipe temperature"},
                }
            },
            "crop": {
                "description": "Crop growth and yield data",
                "variables": {
                    "leaf_area_index": {"unit": "m²/m²", "description": "Leaf area index"},
                    "dry_weight": {"unit": "kg/m²", "description": "Dry weight of crop"},
                    "fresh_weight": {"unit": "kg/m²", "description": "Fresh weight of crop"},
                    "fruit_harvest": {"unit": "kg/m²", "description": "Harvested fruit weight"},
                }
            },
            "soil": {
                "description": "Soil temperature layers",
                "variables": {
                    "soil_temp_layer1": {"unit": "°C", "description": "Soil temperature layer 1"},
                    "soil_temp_layer2": {"unit": "°C", "description": "Soil temperature layer 2"},
                    "soil_temp_layer3": {"unit": "°C", "description": "Soil temperature layer 3"},
                    "soil_temp_layer4": {"unit": "°C", "description": "Soil temperature layer 4"},
                    "soil_temp_layer5": {"unit": "°C", "description": "Soil temperature layer 5"},
                }
            },
            "environment": {
                "description": "External environmental conditions",
                "variables": {
                    "outdoor_temperature": {"unit": "°C", "description": "Outdoor temperature"},
                    "outdoor_humidity": {"unit": "%", "description": "Outdoor humidity"},
                    "wind_speed": {"unit": "m/s", "description": "Wind speed"},
                    "solar_radiation": {"unit": "W/m²", "description": "Solar radiation"},
                    "sky_temperature": {"unit": "°C", "description": "Sky temperature"},
                }
            },
            "control": {
                "description": "Control system variables",
                "variables": {
                    "ventilation_rate": {"unit": "m³/s", "description": "Ventilation rate"},
                    "heating_valve": {"unit": "%", "description": "Heating valve position"},
                    "lighting_control": {"unit": "%", "description": "Lighting intensity"},
                    "co2_injection": {"unit": "mg/s", "description": "CO2 injection rate"},
                }
            },
            "simulation": {
                "description": "Simulation metadata",
                "variables": {
                    "time_step": {"unit": "s", "description": "Current simulation time step"},
                    "simulation_time": {"unit": "days", "description": "Simulation time since start"},
                    "real_time": {"unit": "s", "description": "Real system timestamp"},
                    "step_number": {"unit": "-", "description": "Current step number"},
                }
            }
        }
    
    def get_topic(self, category: str, variable: str = None) -> str:
        """
        Get MQTT topic for a specific category/variable.
        
        Args:
            category: Category name (e.g., 'climate', 'energy')
            variable: Optional specific variable name
            
        Returns:
            Full MQTT topic string
        """
        if variable:
            return f"{self.base_topic}/{category}/{variable}"
        return f"{self.base_topic}/{category}"
    
    def get_all_topics(self) -> List[str]:
        """Get list of all available topics."""
        topics = []
        for category, info in self.topic_mapping.items():
            for variable in info["variables"].keys():
                topics.append(self.get_topic(category, variable))
        return topics
    
    def map_gl_data_to_mqtt(self, gl_data: Dict[str, Any], step: int) -> Dict[str, Dict[str, Any]]:
        """
        Map GreenLight simulation data to MQTT topic structure.
        
        Args:
            gl_data: GreenLight simulation data dictionary
            step: Current simulation step
            
        Returns:
            Dictionary mapping topics to their data
        """
        mapped_data = {}
        current_time = time.time()
        
        # Extract latest values from time series data
        def get_latest_value(data, key):
            """Extract the latest value from GreenLight time series data."""
            if key in data['x'] and len(data['x'][key]) > 0:
                return float(data['x'][key][-1][-1])  # Last time point, last value
            return None
        
        # Climate data
        climate_data = {
            "air_temperature": get_latest_value(gl_data, 'tAir'),
            "air_humidity": self._calculate_humidity(get_latest_value(gl_data, 'vpAir'), 
                                                   get_latest_value(gl_data, 'tAir')),
            "air_co2": get_latest_value(gl_data, 'co2Air'),
            "vapor_pressure": get_latest_value(gl_data, 'vpAir'),
            "canopy_temperature": get_latest_value(gl_data, 'tCan'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["climate"]["variables"]
        }
        mapped_data[self.get_topic("climate")] = climate_data
        
        # Energy data
        energy_data = {
            "heating_power": get_latest_value(gl_data, 'hBoilPipe'),
            "lighting_power": get_latest_value(gl_data, 'qLampIn'),
            "pipe_temperature": get_latest_value(gl_data, 'tGroPipe'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["energy"]["variables"]
        }
        mapped_data[self.get_topic("energy")] = energy_data
        
        # Crop data
        crop_data = {
            "leaf_area_index": get_latest_value(gl_data, 'lai'),
            "dry_weight": get_latest_value(gl_data, 'cLeaf'),
            "fruit_harvest": get_latest_value(gl_data, 'mcFruitHar'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["crop"]["variables"]
        }
        mapped_data[self.get_topic("crop")] = crop_data
        
        # Soil data
        soil_data = {
            "soil_temp_layer1": get_latest_value(gl_data, 'tSo1'),
            "soil_temp_layer2": get_latest_value(gl_data, 'tSo2'),
            "soil_temp_layer3": get_latest_value(gl_data, 'tSo3'),
            "soil_temp_layer4": get_latest_value(gl_data, 'tSo4'),
            "soil_temp_layer5": get_latest_value(gl_data, 'tSo5'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["soil"]["variables"]
        }
        mapped_data[self.get_topic("soil")] = soil_data
        
        # Environment data
        env_data = {
            "outdoor_temperature": get_latest_value(gl_data, 'tOut'),
            "wind_speed": get_latest_value(gl_data, 'wind'),
            "solar_radiation": get_latest_value(gl_data, 'iGlob'),
            "sky_temperature": get_latest_value(gl_data, 'tSky'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["environment"]["variables"]
        }
        mapped_data[self.get_topic("environment")] = env_data
        
        # Control data
        control_data = {
            "ventilation_rate": get_latest_value(gl_data, 'fVentRoof'),
            "heating_valve": get_latest_value(gl_data, 'uBoil'),
            "lighting_control": get_latest_value(gl_data, 'lampOn'),
            "co2_injection": get_latest_value(gl_data, 'mcExtAir'),
            "timestamp": current_time,
            "unit_info": self.topic_mapping["control"]["variables"]
        }
        mapped_data[self.get_topic("control")] = control_data
        
        # Simulation metadata
        sim_data = {
            "step_number": step,
            "simulation_time": get_latest_value(gl_data, 'time'),
            "real_time": current_time,
            "timestamp": current_time,
            "unit_info": self.topic_mapping["simulation"]["variables"]
        }
        mapped_data[self.get_topic("simulation")] = sim_data
        
        return mapped_data
    
    def _calculate_humidity(self, vapor_pressure: float, temperature: float) -> float:
        """
        Calculate relative humidity from vapor pressure and temperature.
        
        Args:
            vapor_pressure: Vapor pressure in Pa
            temperature: Temperature in °C
            
        Returns:
            Relative humidity as percentage
        """
        if vapor_pressure is None or temperature is None:
            return None
            
        # Magnus formula for saturation vapor pressure
        saturation_vp = 610.78 * (10 ** ((7.5 * temperature) / (237.3 + temperature)))
        return min(100.0, (vapor_pressure / saturation_vp) * 100.0)
    
    def format_message(self, data: Dict[str, Any]) -> str:
        """
        Format data as JSON message for MQTT.
        
        Args:
            data: Data dictionary to format
            
        Returns:
            JSON formatted string
        """
        return json.dumps(data, indent=2)
    
    def get_topic_info(self) -> Dict[str, Any]:
        """Get information about all available topics and their structure."""
        return {
            "greenhouse_id": self.greenhouse_id,
            "base_topic": self.base_topic,
            "categories": self.topic_mapping,
            "total_topics": len(self.get_all_topics())
        }