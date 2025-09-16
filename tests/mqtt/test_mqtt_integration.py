"""
Integration tests for MQTT functionality
========================================

Tests MQTT publisher/subscriber with mosquitto broker.
"""

import unittest
import time
import json
import subprocess
import socket
from threading import Event
from greenlightadv_shanaka.mqtt import MQTTPublisher, MQTTSubscriber, TopicManager


def is_mosquitto_running(host="localhost", port=1883):
    """Check if mosquitto broker is running."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def start_mosquitto():
    """Start mosquitto broker for testing."""
    try:
        # Try to start mosquitto with test config
        config_content = """
# Test mosquitto configuration
port 1883
allow_anonymous true
listener 1883 0.0.0.0
persistence false
"""
        with open('/tmp/test_mosquitto.conf', 'w') as f:
            f.write(config_content)
        
        # Start mosquitto
        proc = subprocess.Popen([
            'mosquitto', '-c', '/tmp/test_mosquitto.conf'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait a moment for startup
        time.sleep(1)
        
        if is_mosquitto_running():
            return proc
        else:
            proc.terminate()
            return None
    except Exception as e:
        print(f"Failed to start mosquitto: {e}")
        return None


class TestMQTTIntegration(unittest.TestCase):
    """Integration tests for MQTT components."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures."""
        cls.mosquitto_proc = None
        
        # Check if mosquitto is already running
        if not is_mosquitto_running():
            print("Starting mosquitto broker for tests...")
            cls.mosquitto_proc = start_mosquitto()
            
            if not cls.mosquitto_proc:
                raise unittest.SkipTest("Cannot start mosquitto broker")
        
        # Wait a bit more for broker to be ready
        time.sleep(2)
        
        if not is_mosquitto_running():
            raise unittest.SkipTest("Mosquitto broker not accessible")
        
        print("Mosquitto broker is running")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up class-level test fixtures."""
        if cls.mosquitto_proc:
            print("Stopping mosquitto broker...")
            cls.mosquitto_proc.terminate()
            cls.mosquitto_proc.wait()
    
    def setUp(self):
        """Set up test fixtures."""
        self.broker_host = "localhost"
        self.broker_port = 1883
        self.test_topic = "test/greenhouse/data"
        
    def test_publisher_connection(self):
        """Test MQTT publisher connection."""
        publisher = MQTTPublisher(
            broker_host=self.broker_host,
            broker_port=self.broker_port
        )
        
        # Test connection
        connected = publisher.connect()
        self.assertTrue(connected)
        self.assertTrue(publisher.connected)
        
        # Test disconnection
        publisher.disconnect()
        self.assertFalse(publisher.connected)
    
    def test_subscriber_connection(self):
        """Test MQTT subscriber connection."""
        subscriber = MQTTSubscriber(
            broker_host=self.broker_host,
            broker_port=self.broker_port
        )
        
        # Test connection
        connected = subscriber.connect()
        self.assertTrue(connected)
        self.assertTrue(subscriber.connected)
        
        # Test disconnection
        subscriber.disconnect()
        self.assertFalse(subscriber.connected)
    
    def test_publish_subscribe(self):
        """Test publishing and subscribing to messages."""
        # Set up publisher and subscriber
        publisher = MQTTPublisher(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id="test_publisher"
        )
        
        subscriber = MQTTSubscriber(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id="test_subscriber"
        )
        
        # Connect both
        self.assertTrue(publisher.connect())
        self.assertTrue(subscriber.connect())
        
        # Subscribe to test topic
        received_event = Event()
        received_data = {}
        
        def on_message(topic, data):
            received_data['topic'] = topic
            received_data['data'] = data
            received_event.set()
        
        subscriber.subscribe(self.test_topic, callback=on_message)
        time.sleep(0.5)  # Allow subscription to complete
        
        # Publish test data
        test_data = {
            "temperature": 25.5,
            "humidity": 60.0,
            "timestamp": time.time()
        }
        
        success = publisher.publish(self.test_topic, test_data)
        self.assertTrue(success)
        
        # Wait for message
        message_received = received_event.wait(timeout=5)
        self.assertTrue(message_received, "Message not received within timeout")
        
        # Verify received data
        self.assertEqual(received_data['topic'], self.test_topic)
        self.assertEqual(received_data['data']['temperature'], 25.5)
        self.assertEqual(received_data['data']['humidity'], 60.0)
        
        # Clean up
        publisher.disconnect()
        subscriber.disconnect()
    
    def test_topic_manager_integration(self):
        """Test TopicManager with real MQTT."""
        topic_manager = TopicManager("test_greenhouse")
        
        publisher = MQTTPublisher(
            broker_host=self.broker_host,
            broker_port=self.broker_port
        )
        
        subscriber = MQTTSubscriber(
            broker_host=self.broker_host,
            broker_port=self.broker_port
        )
        
        # Connect
        self.assertTrue(publisher.connect())
        self.assertTrue(subscriber.connect())
        
        # Subscribe to climate topic
        climate_topic = topic_manager.get_topic("climate")
        received_data = {}
        received_event = Event()
        
        def on_climate_data(topic, data):
            received_data[topic] = data
            received_event.set()
        
        subscriber.subscribe(climate_topic, callback=on_climate_data)
        time.sleep(0.5)
        
        # Create mock simulation data
        mock_gl_data = {
            'x': {
                'tAir': [[0, 22.5]],
                'vpAir': [[0, 1800]],
                'co2Air': [[0, 900]]
            }
        }
        
        # Map and publish data
        mapped_data = topic_manager.map_gl_data_to_mqtt(mock_gl_data, 1)
        
        for topic, data in mapped_data.items():
            if topic == climate_topic:
                success = publisher.publish(topic, data)
                self.assertTrue(success)
                break
        
        # Wait for message
        message_received = received_event.wait(timeout=5)
        self.assertTrue(message_received)
        
        # Verify received climate data
        self.assertIn(climate_topic, received_data)
        climate_data = received_data[climate_topic]
        self.assertIn("air_temperature", climate_data)
        self.assertEqual(climate_data["air_temperature"], 22.5)
        
        # Clean up
        publisher.disconnect()
        subscriber.disconnect()
    
    def test_bulk_publish(self):
        """Test bulk publishing functionality."""
        publisher = MQTTPublisher(
            broker_host=self.broker_host,
            broker_port=self.broker_port
        )
        
        self.assertTrue(publisher.connect())
        
        # Prepare bulk data
        bulk_data = {
            "test/topic1": {"value": 1, "unit": "°C"},
            "test/topic2": {"value": 2, "unit": "%"},
            "test/topic3": {"value": 3, "unit": "ppm"}
        }
        
        # Publish bulk data
        results = publisher.publish_bulk(bulk_data)
        
        # Verify all publishes succeeded
        for topic, success in results.items():
            self.assertTrue(success, f"Failed to publish to {topic}")
        
        # Check statistics
        stats = publisher.get_statistics()
        self.assertEqual(stats["messages_published"], 3)
        
        publisher.disconnect()


if __name__ == '__main__':
    unittest.main()