"""
Unit tests for MQTT Topic Manager
=================================

Tests the topic management and data mapping functionality.
"""

import unittest
import json
import time
from greenlightadv_shanaka.mqtt.topic_manager import TopicManager


class TestTopicManager(unittest.TestCase):
    """Test cases for TopicManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.greenhouse_id = "test_greenhouse"
        self.topic_manager = TopicManager(self.greenhouse_id)
    
    def test_initialization(self):
        """Test TopicManager initialization."""
        self.assertEqual(self.topic_manager.greenhouse_id, self.greenhouse_id)
        self.assertEqual(self.topic_manager.base_topic, f"greenlight/{self.greenhouse_id}")
        self.assertIsInstance(self.topic_manager.topic_mapping, dict)
    
    def test_get_topic(self):
        """Test topic generation."""
        # Test category-only topic
        topic = self.topic_manager.get_topic("climate")
        expected = f"greenlight/{self.greenhouse_id}/climate"
        self.assertEqual(topic, expected)
        
        # Test category with variable topic
        topic = self.topic_manager.get_topic("climate", "air_temperature")
        expected = f"greenlight/{self.greenhouse_id}/climate/air_temperature"
        self.assertEqual(topic, expected)
    
    def test_get_all_topics(self):
        """Test getting all available topics."""
        topics = self.topic_manager.get_all_topics()
        self.assertIsInstance(topics, list)
        self.assertTrue(len(topics) > 0)
        
        # Check that all topics follow expected format
        for topic in topics:
            self.assertTrue(topic.startswith(f"greenlight/{self.greenhouse_id}/"))
    
    def test_map_gl_data_to_mqtt(self):
        """Test mapping GreenLight data to MQTT structure."""
        # Create mock GreenLight data
        mock_gl_data = {
            'x': {
                'tAir': [[0, 20.5], [60, 21.0]],  # Air temperature
                'vpAir': [[0, 1500], [60, 1600]],  # Vapor pressure
                'co2Air': [[0, 800], [60, 850]],  # CO2
                'tCan': [[0, 19.0], [60, 19.5]],  # Canopy temperature
                'hBoilPipe': [[0, 5000], [60, 5200]],  # Heating power
                'qLampIn': [[0, 2000], [60, 2100]],  # Lighting power
                'tGroPipe': [[0, 40], [60, 41]],  # Pipe temperature
                'lai': [[0, 2.5], [60, 2.6]],  # Leaf area index
                'cLeaf': [[0, 0.5], [60, 0.52]],  # Dry weight
                'mcFruitHar': [[0, 1000], [60, 1050]],  # Fruit harvest
                'tSo1': [[0, 15], [60, 15.2]],  # Soil layer 1
                'tOut': [[0, 5], [60, 6]],  # Outdoor temperature
                'wind': [[0, 2.5], [60, 2.7]],  # Wind speed
                'iGlob': [[0, 300], [60, 320]],  # Solar radiation
                'tSky': [[0, -5], [60, -4.8]],  # Sky temperature
                'time': [[0, 100], [60, 100.0007]]  # Simulation time
            }
        }
        
        step = 1
        mapped_data = self.topic_manager.map_gl_data_to_mqtt(mock_gl_data, step)
        
        # Check that all expected categories are present
        expected_categories = ["climate", "energy", "crop", "soil", "environment", "control", "simulation"]
        for category in expected_categories:
            topic = self.topic_manager.get_topic(category)
            self.assertIn(topic, mapped_data)
        
        # Check climate data structure
        climate_topic = self.topic_manager.get_topic("climate")
        climate_data = mapped_data[climate_topic]
        
        self.assertIn("air_temperature", climate_data)
        self.assertIn("vapor_pressure", climate_data)
        self.assertIn("air_co2", climate_data)
        self.assertIn("timestamp", climate_data)
        self.assertIn("unit_info", climate_data)
        
        # Check that values are extracted correctly (should be last values)
        self.assertEqual(climate_data["air_temperature"], 21.0)
        self.assertEqual(climate_data["vapor_pressure"], 1600)
        self.assertEqual(climate_data["air_co2"], 850)
    
    def test_calculate_humidity(self):
        """Test humidity calculation."""
        # Test with valid values
        humidity = self.topic_manager._calculate_humidity(1500, 20)
        self.assertIsInstance(humidity, float)
        self.assertTrue(0 <= humidity <= 100)
        
        # Test with None values
        humidity = self.topic_manager._calculate_humidity(None, 20)
        self.assertIsNone(humidity)
        
        humidity = self.topic_manager._calculate_humidity(1500, None)
        self.assertIsNone(humidity)
    
    def test_format_message(self):
        """Test message formatting."""
        test_data = {
            "temperature": 20.5,
            "humidity": 65.2,
            "timestamp": time.time()
        }
        
        formatted = self.topic_manager.format_message(test_data)
        self.assertIsInstance(formatted, str)
        
        # Check that it's valid JSON
        parsed = json.loads(formatted)
        self.assertEqual(parsed["temperature"], 20.5)
        self.assertEqual(parsed["humidity"], 65.2)
    
    def test_get_topic_info(self):
        """Test getting topic information."""
        info = self.topic_manager.get_topic_info()
        
        self.assertIn("greenhouse_id", info)
        self.assertIn("base_topic", info)
        self.assertIn("categories", info)
        self.assertIn("total_topics", info)
        
        self.assertEqual(info["greenhouse_id"], self.greenhouse_id)
        self.assertIsInstance(info["total_topics"], int)
        self.assertTrue(info["total_topics"] > 0)
    
    def test_topic_mapping_structure(self):
        """Test that topic mapping has required structure."""
        for category, info in self.topic_manager.topic_mapping.items():
            self.assertIn("description", info)
            self.assertIn("variables", info)
            self.assertIsInstance(info["variables"], dict)
            
            for var_name, var_info in info["variables"].items():
                self.assertIn("unit", var_info)
                self.assertIn("description", var_info)
                self.assertIsInstance(var_info["unit"], str)
                self.assertIsInstance(var_info["description"], str)


if __name__ == '__main__':
    unittest.main()