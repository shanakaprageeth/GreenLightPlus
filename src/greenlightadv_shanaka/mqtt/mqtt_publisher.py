"""
MQTT Publisher for GreenLight Simulation Data
=============================================

Publishes greenhouse simulation data to MQTT topics in real-time.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Callable

import paho.mqtt.client as mqtt


class MQTTPublisher:
    """Publishes greenhouse simulation data to MQTT broker."""
    
    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        keep_alive: int = 60,
        qos: int = 0,
        retain: bool = False
    ):
        """
        Initialize MQTT Publisher.
        
        Args:
            broker_host: MQTT broker hostname/IP
            broker_port: MQTT broker port
            username: Optional username for authentication
            password: Optional password for authentication  
            client_id: Optional client ID, auto-generated if None
            keep_alive: Connection keep-alive interval in seconds
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain messages
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.keep_alive = keep_alive
        self.qos = qos
        self.retain = retain
        
        # Create MQTT client
        self.client_id = client_id or f"greenlight_publisher_{int(time.time())}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        
        # Set authentication if provided
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Connection state
        self.connected = False
        self.connect_attempts = 0
        self.max_connect_attempts = 5
        
        # Statistics
        self.messages_published = 0
        self.messages_failed = 0
        self.last_publish_time = None
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        
    def connect(self) -> bool:
        """
        Connect to MQTT broker.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, self.keep_alive)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.connected:
                self.logger.info("Successfully connected to MQTT broker")
                self.connect_attempts = 0
                return True
            else:
                self.logger.error("Failed to connect to MQTT broker within timeout")
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        if self.connected:
            self.logger.info("Disconnecting from MQTT broker")
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def publish(self, topic: str, payload: Dict[str, Any], qos: Optional[int] = None, retain: Optional[bool] = None) -> bool:
        """
        Publish data to MQTT topic.
        
        Args:
            topic: MQTT topic to publish to
            payload: Data to publish (will be JSON encoded)
            qos: Quality of Service level (uses default if None)
            retain: Whether to retain message (uses default if None)
            
        Returns:
            True if publish successful, False otherwise
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, attempting to reconnect")
            if not self.connect():
                return False
        
        try:
            # Use defaults if not specified
            if qos is None:
                qos = self.qos
            if retain is None:
                retain = self.retain
            
            # Convert payload to JSON
            if isinstance(payload, dict):
                json_payload = json.dumps(payload)
            else:
                json_payload = str(payload)
            
            # Publish message
            result = self.client.publish(topic, json_payload, qos=qos, retain=retain)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.messages_published += 1
                self.last_publish_time = time.time()
                self.logger.debug(f"Published to {topic}: {len(json_payload)} bytes")
                return True
            else:
                self.messages_failed += 1
                self.logger.error(f"Failed to publish to {topic}, error code: {result.rc}")
                return False
                
        except Exception as e:
            self.messages_failed += 1
            self.logger.error(f"Error publishing to {topic}: {e}")
            return False
    
    def publish_bulk(self, topic_data_map: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """
        Publish multiple topics at once.
        
        Args:
            topic_data_map: Dictionary mapping topics to their data
            
        Returns:
            Dictionary mapping topics to their publish success status
        """
        results = {}
        for topic, data in topic_data_map.items():
            results[topic] = self.publish(topic, data)
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get publisher statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "connected": self.connected,
            "client_id": self.client_id,
            "broker": f"{self.broker_host}:{self.broker_port}",
            "messages_published": self.messages_published,
            "messages_failed": self.messages_failed,
            "last_publish_time": self.last_publish_time,
            "success_rate": (self.messages_published / max(1, self.messages_published + self.messages_failed)) * 100
        }
    
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when client connects to broker."""
        if rc == 0:
            self.connected = True
            self.logger.info("Connected to MQTT broker")
        else:
            self.connected = False
            self.logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_disconnect(self, client, userdata, flags, rc, properties=None):
        """Callback for when client disconnects from broker."""
        self.connected = False
        if rc != 0:
            self.logger.warning(f"Unexpected disconnection from MQTT broker, return code: {rc}")
        else:
            self.logger.info("Disconnected from MQTT broker")
    
    def _on_publish(self, client, userdata, mid, reason_code=None, properties=None):
        """Callback for when message is published."""
        self.logger.debug(f"Message {mid} published successfully")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()