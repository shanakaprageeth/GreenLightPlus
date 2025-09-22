"""
MQTT Simulation Manager for Real-time Greenhouse Simulation
===========================================================

Manages real-time simulation with MQTT integration, allowing synchronization
with physical systems and configurable time steps.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from .mqtt_publisher import MQTTPublisher
from .mqtt_subscriber import MQTTSubscriber
from .topic_manager import TopicManager


class MQTTSimulationManager:
    """Manages real-time greenhouse simulation with MQTT integration."""
    
    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        greenhouse_id: str = "greenhouse_01",
        username: Optional[str] = None,
        password: Optional[str] = None,
        real_time: bool = True,
        time_step_seconds: float = 900.0,  # 15 minutes default
        sync_with_real_time: bool = True
    ):
        """
        Initialize MQTT Simulation Manager.
        
        Args:
            broker_host: MQTT broker hostname/IP
            broker_port: MQTT broker port
            greenhouse_id: Unique identifier for this greenhouse
            username: Optional MQTT username
            password: Optional MQTT password
            real_time: Whether to run simulation in real-time
            time_step_seconds: Simulation time step in seconds
            sync_with_real_time: Whether to sync simulation with real system time
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.greenhouse_id = greenhouse_id
        self.real_time = real_time
        self.time_step_seconds = time_step_seconds
        self.sync_with_real_time = sync_with_real_time
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize MQTT components
        self.topic_manager = TopicManager(greenhouse_id)
        
        self.publisher = MQTTPublisher(
            broker_host=broker_host,
            broker_port=broker_port,
            username=username,
            password=password,
            client_id=f"greenlight_sim_pub_{greenhouse_id}"
        )
        
        self.subscriber = MQTTSubscriber(
            broker_host=broker_host,
            broker_port=broker_port,
            username=username,
            password=password,
            client_id=f"greenlight_sim_sub_{greenhouse_id}"
        )
        
        # Simulation state
        self.simulation_start_time = None
        self.last_step_time = None
        self.step_count = 0
        self.paused = False
        
        # Physical system data
        self.physical_data: Dict[str, Any] = {}
        self.physical_data_callbacks: Dict[str, Callable] = {}
        
        # Statistics
        self.published_messages = 0
        self.received_messages = 0
        
    def start(self) -> bool:
        """
        Start MQTT simulation manager.
        
        Returns:
            True if successfully started, False otherwise
        """
        try:
            self.logger.info(f"Starting MQTT simulation manager for {self.greenhouse_id}")
            
            # Connect to MQTT broker
            if not self.publisher.connect():
                self.logger.error("Failed to connect publisher to MQTT broker")
                return False
                
            if not self.subscriber.connect():
                self.logger.error("Failed to connect subscriber to MQTT broker")
                return False
            
            # Subscribe to physical system data topics
            self._setup_physical_data_subscriptions()
            
            # Publish initial topic information
            self._publish_topic_info()
            
            self.simulation_start_time = time.time()
            self.last_step_time = self.simulation_start_time
            
            self.logger.info("MQTT simulation manager started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting MQTT simulation manager: {e}")
            return False
    
    def stop(self):
        """Stop MQTT simulation manager."""
        self.logger.info("Stopping MQTT simulation manager")
        
        # Publish final statistics
        self._publish_simulation_status("stopped")
        
        # Disconnect from MQTT broker
        self.publisher.disconnect()
        self.subscriber.disconnect()
        
        self.logger.info("MQTT simulation manager stopped")
    
    def publish_simulation_data(self, gl_data: Dict[str, Any], step: int) -> bool:
        """
        Publish simulation data to MQTT topics.
        
        Args:
            gl_data: GreenLight simulation data
            step: Current simulation step
            
        Returns:
            True if all data published successfully, False otherwise
        """
        try:
            # Map simulation data to MQTT topics
            topic_data = self.topic_manager.map_gl_data_to_mqtt(gl_data, step)
            
            # Add timing information
            current_time = time.time()
            if self.simulation_start_time:
                elapsed_time = current_time - self.simulation_start_time
                for topic, data in topic_data.items():
                    data["simulation_elapsed_seconds"] = elapsed_time
                    data["real_time_factor"] = self._calculate_real_time_factor(step)
            
            # Publish all topics
            results = self.publisher.publish_bulk(topic_data)
            
            # Count successful publications
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            self.published_messages += success_count
            self.step_count = step
            
            if success_count == total_count:
                self.logger.debug(f"Published {success_count} topics for step {step}")
                return True
            else:
                self.logger.warning(f"Published {success_count}/{total_count} topics for step {step}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error publishing simulation data: {e}")
            return False
    
    def get_physical_system_data(self) -> Dict[str, Any]:
        """
        Get latest physical system data from MQTT.
        
        Returns:
            Dictionary with physical system data
        """
        return self.subscriber.get_all_data()
    
    def wait_for_next_step(self, current_step: int) -> bool:
        """
        Wait for next simulation step based on real-time synchronization.
        
        Args:
            current_step: Current simulation step number
            
        Returns:
            True to continue simulation, False to stop
        """
        if not self.real_time or self.paused:
            return True
        
        if not self.sync_with_real_time:
            # Simple time-based delay
            time.sleep(self.time_step_seconds)
            return True
        
        # Calculate target time for next step
        if self.last_step_time is None:
            self.last_step_time = time.time()
            return True
        
        target_time = self.last_step_time + self.time_step_seconds
        current_time = time.time()
        
        if current_time < target_time:
            sleep_time = target_time - current_time
            self.logger.debug(f"Waiting {sleep_time:.2f}s for next step")
            time.sleep(sleep_time)
        elif current_time > target_time + self.time_step_seconds:
            # We're running behind, log warning
            delay = current_time - target_time
            self.logger.warning(f"Simulation running {delay:.2f}s behind real time")
        
        self.last_step_time = time.time()
        return True
    
    def set_time_step(self, time_step_seconds: float):
        """
        Set simulation time step.
        
        Args:
            time_step_seconds: New time step in seconds
        """
        self.time_step_seconds = time_step_seconds
        self.logger.info(f"Time step set to {time_step_seconds} seconds")
        
        # Publish updated configuration
        self._publish_configuration()
    
    def pause_simulation(self):
        """Pause the simulation."""
        self.paused = True
        self.logger.info("Simulation paused")
        self._publish_simulation_status("paused")
    
    def resume_simulation(self):
        """Resume the simulation."""
        self.paused = False
        self.last_step_time = time.time()  # Reset timing
        self.logger.info("Simulation resumed")
        self._publish_simulation_status("running")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get simulation manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        current_time = time.time()
        elapsed_time = current_time - self.simulation_start_time if self.simulation_start_time else 0
        
        return {
            "greenhouse_id": self.greenhouse_id,
            "simulation_running": not self.paused,
            "real_time_mode": self.real_time,
            "time_step_seconds": self.time_step_seconds,
            "elapsed_time_seconds": elapsed_time,
            "simulation_steps": self.step_count,
            "published_messages": self.published_messages,
            "received_messages": self.subscriber.messages_received,
            "publisher_stats": self.publisher.get_statistics(),
            "subscriber_stats": self.subscriber.get_statistics(),
            "real_time_factor": self._calculate_real_time_factor(self.step_count)
        }
    
    def _setup_physical_data_subscriptions(self):
        """Set up subscriptions for physical system data."""
        # Subscribe to physical system input topics
        physical_topics = [
            f"physical/{self.greenhouse_id}/sensors/+",
            f"physical/{self.greenhouse_id}/actuators/+",
            f"physical/{self.greenhouse_id}/environment/+",
            f"physical/{self.greenhouse_id}/control/+"
        ]
        
        for topic in physical_topics:
            self.subscriber.subscribe(topic, callback=self._on_physical_data)
    
    def _on_physical_data(self, topic: str, data: Any):
        """
        Callback for receiving physical system data.
        
        Args:
            topic: MQTT topic
            data: Received data
        """
        self.physical_data[topic] = data
        self.received_messages += 1
        self.logger.debug(f"Received physical data on {topic}")
        
        # Call registered callbacks
        for pattern, callback in self.physical_data_callbacks.items():
            if pattern in topic:
                try:
                    callback(topic, data)
                except Exception as e:
                    self.logger.error(f"Error in physical data callback: {e}")
    
    def _publish_topic_info(self):
        """Publish information about available topics."""
        topic_info = self.topic_manager.get_topic_info()
        info_topic = f"{self.topic_manager.base_topic}/info/topics"
        self.publisher.publish(info_topic, topic_info)
    
    def _publish_configuration(self):
        """Publish current simulation configuration."""
        config = {
            "greenhouse_id": self.greenhouse_id,
            "real_time_mode": self.real_time,
            "time_step_seconds": self.time_step_seconds,
            "sync_with_real_time": self.sync_with_real_time,
            "timestamp": time.time()
        }
        config_topic = f"{self.topic_manager.base_topic}/info/configuration"
        self.publisher.publish(config_topic, config)
    
    def _publish_simulation_status(self, status: str):
        """
        Publish simulation status.
        
        Args:
            status: Status string ('running', 'paused', 'stopped')
        """
        status_data = {
            "status": status,
            "timestamp": time.time(),
            "step_count": self.step_count,
            "elapsed_time": time.time() - self.simulation_start_time if self.simulation_start_time else 0
        }
        status_topic = f"{self.topic_manager.base_topic}/info/status"
        self.publisher.publish(status_topic, status_data)
    
    def _calculate_real_time_factor(self, step: int) -> float:
        """
        Calculate real-time factor (simulation time / real time).
        
        Args:
            step: Current simulation step
            
        Returns:
            Real-time factor
        """
        if not self.simulation_start_time or step == 0:
            return 1.0
        
        elapsed_real_time = time.time() - self.simulation_start_time
        elapsed_sim_time = step * self.time_step_seconds
        
        if elapsed_real_time > 0:
            return elapsed_sim_time / elapsed_real_time
        return 1.0
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()