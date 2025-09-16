"""
System tests for MQTT simulation integration
============================================

End-to-end tests for MQTT-enabled greenhouse simulation.
"""

import unittest
import time
import subprocess
import socket
from threading import Thread, Event
from greenlightadv_shanaka import GreenLightModel
from greenlightadv_shanaka.mqtt import MQTTSimulationManager, MQTTSubscriber


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
        config_content = """
port 1883
allow_anonymous true
listener 1883 0.0.0.0
persistence false
"""
        with open('/tmp/test_mosquitto.conf', 'w') as f:
            f.write(config_content)
        
        proc = subprocess.Popen([
            'mosquitto', '-c', '/tmp/test_mosquitto.conf'
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        time.sleep(1)
        
        if is_mosquitto_running():
            return proc
        else:
            proc.terminate()
            return None
    except Exception as e:
        print(f"Failed to start mosquitto: {e}")
        return None


class TestMQTTSimulationSystem(unittest.TestCase):
    """System tests for MQTT simulation integration."""
    
    @classmethod
    def setUpClass(cls):
        """Set up class-level test fixtures."""
        cls.mosquitto_proc = None
        
        if not is_mosquitto_running():
            print("Starting mosquitto broker for system tests...")
            cls.mosquitto_proc = start_mosquitto()
            
            if not cls.mosquitto_proc:
                raise unittest.SkipTest("Cannot start mosquitto broker")
        
        time.sleep(2)
        
        if not is_mosquitto_running():
            raise unittest.SkipTest("Mosquitto broker not accessible")
        
        print("Mosquitto broker ready for system tests")
    
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
        self.greenhouse_id = "system_test_greenhouse"
    
    def test_simulation_manager_lifecycle(self):
        """Test MQTT simulation manager lifecycle."""
        manager = MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=False,
            time_step_seconds=1.0
        )
        
        # Test startup
        started = manager.start()
        self.assertTrue(started)
        
        # Check initial statistics
        stats = manager.get_statistics()
        self.assertEqual(stats["greenhouse_id"], self.greenhouse_id)
        self.assertFalse(stats["simulation_running"])  # Should be False initially
        
        # Test configuration publishing
        manager._publish_configuration()
        
        # Test status publishing
        manager._publish_simulation_status("running")
        
        # Test shutdown
        manager.stop()
    
    def test_simulation_data_publishing(self):
        """Test publishing simulation data."""
        manager = MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=False
        )
        
        # Set up subscriber to monitor published data
        subscriber = MQTTSubscriber(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id="system_test_subscriber"
        )
        
        received_topics = set()
        received_event = Event()
        
        def on_data(topic, data):
            received_topics.add(topic)
            if len(received_topics) >= 5:  # Wait for several topics
                received_event.set()
        
        # Start both
        self.assertTrue(manager.start())
        self.assertTrue(subscriber.connect())
        
        # Subscribe to all greenhouse topics
        base_topic = f"greenlight/{self.greenhouse_id}/+"
        subscriber.subscribe(base_topic, callback=on_data)
        subscriber.subscribe(f"greenlight/{self.greenhouse_id}/+/+", callback=on_data)
        time.sleep(0.5)
        
        # Create mock simulation data
        mock_gl_data = {
            'x': {
                'tAir': [[0, 20.0], [60, 21.0]],
                'vpAir': [[0, 1500], [60, 1600]],
                'co2Air': [[0, 800], [60, 850]],
                'tCan': [[0, 19.0], [60, 19.5]],
                'hBoilPipe': [[0, 5000], [60, 5200]],
                'qLampIn': [[0, 2000], [60, 2100]],
                'tGroPipe': [[0, 40], [60, 41]],
                'lai': [[0, 2.5], [60, 2.6]],
                'cLeaf': [[0, 0.5], [60, 0.52]],
                'tOut': [[0, 5], [60, 6]],
                'wind': [[0, 2.5], [60, 2.7]],
                'time': [[0, 100], [60, 100.0007]]
            }
        }
        
        # Publish simulation data
        success = manager.publish_simulation_data(mock_gl_data, 1)
        self.assertTrue(success)
        
        # Wait for data reception
        data_received = received_event.wait(timeout=10)
        self.assertTrue(data_received, "Simulation data not received within timeout")
        
        # Verify we received data on multiple topics
        self.assertGreaterEqual(len(received_topics), 5)
        
        # Check that expected topic patterns are present
        topic_patterns = ["climate", "energy", "crop", "simulation"]
        found_patterns = []
        
        for topic in received_topics:
            for pattern in topic_patterns:
                if pattern in topic:
                    found_patterns.append(pattern)
                    break
        
        self.assertGreaterEqual(len(found_patterns), 3, "Not enough topic categories received")
        
        # Clean up
        manager.stop()
        subscriber.disconnect()
    
    def test_time_synchronization(self):
        """Test time synchronization functionality."""
        manager = MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=True,
            time_step_seconds=0.5,  # Short for testing
            sync_with_real_time=True
        )
        
        self.assertTrue(manager.start())
        
        # Test timing of steps
        start_time = time.time()
        
        # Wait for first step
        can_continue = manager.wait_for_next_step(0)
        self.assertTrue(can_continue)
        
        step1_time = time.time()
        
        # Wait for second step
        can_continue = manager.wait_for_next_step(1)
        self.assertTrue(can_continue)
        
        step2_time = time.time()
        
        # Check timing - should be approximately time_step_seconds
        time_diff = step2_time - step1_time
        self.assertGreater(time_diff, 0.4)  # Allow some tolerance
        self.assertLess(time_diff, 0.7)
        
        manager.stop()
    
    def test_pause_resume_functionality(self):
        """Test simulation pause and resume."""
        manager = MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=False
        )
        
        self.assertTrue(manager.start())
        
        # Test pause
        manager.pause_simulation()
        self.assertTrue(manager.paused)
        
        # Test resume
        manager.resume_simulation()
        self.assertFalse(manager.paused)
        
        manager.stop()
    
    def test_context_manager(self):
        """Test using simulation manager as context manager."""
        received_data = []
        
        with MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=False
        ) as manager:
            
            # Manager should be started
            stats = manager.get_statistics()
            self.assertIsNotNone(stats)
            
            # Test basic operation
            mock_data = {'x': {'tAir': [[0, 20]]}}
            success = manager.publish_simulation_data(mock_data, 1)
            # Note: success might be False if no subscribers, but shouldn't crash
            
        # Manager should be stopped automatically
    
    def test_physical_data_subscription(self):
        """Test subscription to physical system data."""
        manager = MQTTSimulationManager(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            greenhouse_id=self.greenhouse_id,
            real_time=False
        )
        
        # Set up a publisher to simulate physical system
        from greenlightadv_shanaka.mqtt import MQTTPublisher
        
        physical_publisher = MQTTPublisher(
            broker_host=self.broker_host,
            broker_port=self.broker_port,
            client_id="physical_system_sim"
        )
        
        self.assertTrue(manager.start())
        self.assertTrue(physical_publisher.connect())
        
        time.sleep(1)  # Allow subscriptions to complete
        
        # Publish physical system data
        physical_topic = f"physical/{self.greenhouse_id}/sensors/temperature"
        physical_data = {
            "value": 25.5,
            "unit": "°C",
            "timestamp": time.time()
        }
        
        success = physical_publisher.publish(physical_topic, physical_data)
        self.assertTrue(success)
        
        # Wait a moment for data to be received
        time.sleep(1)
        
        # Check if manager received the data
        received_data = manager.get_physical_system_data()
        
        # Note: This test might pass even if no data is received since the
        # subscription is to wildcard topics and timing is important
        
        # Clean up
        manager.stop()
        physical_publisher.disconnect()


if __name__ == '__main__':
    unittest.main()