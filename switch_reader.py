from configuration_loader import ConfigurationLoader
from umqtt_simple2 import MQTTClient
from logger import MyLogger
from machine import Pin
import json
from time import sleep
from machine import Timer


class SwitchReader:
	def __init__(self, config_file='/config/switch.txt'):
		config_loader = ConfigurationLoader(config_file)
		configs = config_loader.load_configuration('mqtt_broker', 'mqtt_topic', 'mqtt_id', 'switch_pin', 'switch_update_period')
		self.config_file = config_file
		self.switch_update_period = float(configs['switch_update_period'])
		self.mqtt_client = MQTTClient(configs['mqtt_id'], configs['mqtt_broker'])
		self.mqtt_client.DEBUG = True
		self.mqtt_topic = configs['mqtt_topic']
		self.switch_pin_num = int(configs['switch_pin'])
		self.switch_pin = Pin(self.switch_pin_num, Pin.IN)
		self.id = configs['mqtt_id']
		self.mqtt_broker = configs['mqtt_broker']
		self.logger = MyLogger(False)
		self.logger.log('DEBUG', self.id, 'Connecting to {}...'.format(self.mqtt_broker))
		try:
			self.mqtt_client.connect()
			self.logger.log('INFO', self.id, 'Reconnected to {}'.format(self.mqtt_broker))
		except:
			self.logger.log('ERROR', self.id, 'Connection failure to {}'.format(self.mqtt_broker))
		self.last_switch_position = self.switch_pin.value()
		self.mqtt_messages_sent = 0
		self.debounce_time = 0.5
		self.timer = None
		self.init_timer()

	def init_timer(self):
		self.deinit_timer()
		self.timer = Timer(-1)
		self.timer.init(period=int(self.switch_update_period*1000), mode=Timer.ONE_SHOT, callback=lambda t: self.loop())

	def loop(self):
		self.read_switch()
		self.init_timer()

	def deinit_timer(self):
		if isinstance(self.timer, Timer):
			self.timer.deinit()
		self.timer = None

	def read_switch(self):
		switch_position = self.switch_pin.value()
		if switch_position != self.last_switch_position:
			self.last_switch_position = switch_position
			self.notify_hub()
			self.deinit_timer()
			sleep(self.debounce_time)

	def notify_hub(self):
		if not self._connected_to_broker():
			try:
				self.mqtt_client.connect()
				self.logger.log('INFO', self.id, 'Reconnected to {}'.format(self.mqtt_broker))
			except:
				self.logger.log('ERROR', self.id, 'Connection failure to {}'.format(self.mqtt_broker))

		try:
			'''
			if self.mqtt_messages_sent > 3:
				self.reset_mqtt_connection()
			'''
			self.mqtt_client.publish(topic=self.mqtt_topic, msg='pressed', qos=1)
			self.logger.log('INFO', self.id, 'hub successfully notified')
			self.mqtt_messages_sent += 1
			self.reset_mqtt_connection()
		except Exception as e:
			self.logger.log('ERROR', self.id, "Can't notify the hub; {}".format(e))

	def reset_mqtt_connection(self):
		self.mqtt_client.disconnect()
		sleep(0.1)
		self.mqtt_client.connect()
		self.mqtt_messages_sent = 0

	def _connected_to_broker(self):
		try:
			self.mqtt_client.ping()
			return True
		except:
			return False

	def edit_configuration(self, key, value):
		try:
			with open(self.config_file, 'rb') as file:
				configs = json.load(file)
		except Exception as e:
			self.logger.log('ERROR', self.__class__.__name__, "Can't open configuration file; {}".format(e))
			return False

		configs[key] = value

		try:
			with open(self.config_file, 'wb') as file:
				json.dump(configs, file)
		except Exception as e:
			self.logger.log('ERROR', self.__class__.__name__, "Can't save configuration; {}".format(e))
			return False

		return True
