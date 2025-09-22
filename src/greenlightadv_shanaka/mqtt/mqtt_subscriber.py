"""
MQTT Subscriber for Physical System Data
========================================

Subscribes to MQTT topics to receive physical system data that can be
integrated into the greenhouse simulation.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Callable, List

import paho.mqtt.client as mqtt


class MQTTSubscriber:
    """Subscribes to MQTT topics for physical system data."""
    
    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        keep_alive: int = 60,
        qos: int = 0
    ):
        """
        Initialize MQTT Subscriber.
        
        Args:
            broker_host: MQTT broker hostname/IP
            broker_port: MQTT broker port
            username: Optional username for authentication
            password: Optional password for authentication  
            client_id: Optional client ID, auto-generated if None
            keep_alive: Connection keep-alive interval in seconds
            qos: Quality of Service level (0, 1, or 2)
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.keep_alive = keep_alive
        self.qos = qos
        
        # Create MQTT client
        self.client_id = client_id or f"greenlight_subscriber_{int(time.time())}"
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        
        # Set authentication if provided
        if username and password:
            self.client.username_pw_set(username, password)
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Connection state
        self.connected = False
        
        # Data storage
        self.received_data: Dict[str, Any] = {}
        self.last_received_time: Dict[str, float] = {}
        self.message_callbacks: Dict[str, Callable] = {}
        
        # Statistics
        self.messages_received = 0
        self.topics_subscribed: List[str] = []
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_subscribe = self._on_subscribe
        
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
    
    def subscribe(self, topic: str, qos: Optional[int] = None, callback: Optional[Callable] = None) -> bool:
        """
        Subscribe to MQTT topic.
        
        Args:
            topic: MQTT topic to subscribe to
            qos: Quality of Service level (uses default if None)
            callback: Optional callback function for this topic
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.connected:
            self.logger.warning("Not connected to MQTT broker, attempting to reconnect")
            if not self.connect():
                return False
        
        try:
            if qos is None:
                qos = self.qos
            
            # Set callback for this topic
            if callback:
                self.message_callbacks[topic] = callback
            
            # Subscribe to topic
            result = self.client.subscribe(topic, qos=qos)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                if topic not in self.topics_subscribed:
                    self.topics_subscribed.append(topic)
                self.logger.info(f"Subscribed to topic: {topic}")
                return True
            else:
                self.logger.error(f"Failed to subscribe to {topic}, error code: {result[0]}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error subscribing to {topic}: {e}")
            return False
    
    def subscribe_multiple(self, topics: List[str], qos: Optional[int] = None) -> Dict[str, bool]:
        """
        Subscribe to multiple topics.
        
        Args:
            topics: List of topics to subscribe to
            qos: Quality of Service level (uses default if None)
            
        Returns:
            Dictionary mapping topics to their subscription success status
        """
        results = {}
        for topic in topics:
            results[topic] = self.subscribe(topic, qos)
        return results
    
    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from MQTT topic.
        
        Args:
            topic: MQTT topic to unsubscribe from
            
        Returns:
            True if unsubscription successful, False otherwise
        """
        try:
            result = self.client.unsubscribe(topic)
            
            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                if topic in self.topics_subscribed:
                    self.topics_subscribed.remove(topic)
                if topic in self.message_callbacks:
                    del self.message_callbacks[topic]
                self.logger.info(f"Unsubscribed from topic: {topic}")
                return True
            else:
                self.logger.error(f"Failed to unsubscribe from {topic}, error code: {result[0]}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error unsubscribing from {topic}: {e}")
            return False
    
    def get_latest_data(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        Get latest data received for a topic.
        
        Args:
            topic: MQTT topic
            
        Returns:
            Latest data dictionary or None if no data received
        """
        return self.received_data.get(topic)
    
    def get_all_data(self) -> Dict[str, Any]:
        """
        Get all received data.
        
        Returns:
            Dictionary mapping topics to their latest data
        """
        return self.received_data.copy()
    
    def data_age(self, topic: str) -> Optional[float]:
        """
        Get age of latest data for a topic.
        
        Args:
            topic: MQTT topic
            
        Returns:
            Age in seconds or None if no data received
        """
        if topic in self.last_received_time:
            return time.time() - self.last_received_time[topic]
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get subscriber statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            "connected": self.connected,
            "client_id": self.client_id,
            "broker": f"{self.broker_host}:{self.broker_port}",
            "topics_subscribed": len(self.topics_subscribed),
            "topics_list": self.topics_subscribed,
            "messages_received": self.messages_received,
            "data_topics": list(self.received_data.keys())
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
    
    def _on_message(self, client, userdata, msg):
        """Callback for when message is received."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Try to parse as JSON
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                # If not JSON, store as string
                data = payload
            
            # Store data
            self.received_data[topic] = data
            self.last_received_time[topic] = time.time()
            self.messages_received += 1
            
            self.logger.debug(f"Received message on {topic}: {len(payload)} bytes")
            
            # Call topic-specific callback if available
            if topic in self.message_callbacks:
                try:
                    self.message_callbacks[topic](topic, data)
                except Exception as e:
                    self.logger.error(f"Error in callback for {topic}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    def _on_subscribe(self, client, userdata, mid, reason_code_list, properties=None):
        """Callback for when subscription is completed."""
        self.logger.debug(f"Subscription completed with message ID {mid}, QoS: {reason_code_list}")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()