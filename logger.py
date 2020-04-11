from umqtt_simple2 import MQTTClient
from machine import RTC
import sys
from configuration_loader import ConfigurationLoader


class MyLogger:
	def __init__(self, mqtt=False, mqtt_conf="/conf/mqtt_conf.txt"):
		self.mqtt = mqtt

		if mqtt:
			config_loader = ConfigurationLoader(mqtt_conf)
			broker = config_loader.load_configuration('mqtt_broker')['mqtt_broker']
			self.publisher = MQTTClient('logger', broker)
			self.publisher.DEBUG = True
			self.publisher.MSG_QUEUE_MAX = 0

		self.rtc = RTC()
		self.colors = {"DEBUG": "\033[0m", "RESET": "\033[0m", "WARNING": "\033[35m", "ERROR": "\033[33m",
					   "CRITICAL": "\033[31m", "INFO": "\033[32m"}

	def log(self, level, caller, *message):
		timestamp_tuple = self.rtc.datetime()
		timestamp = "{}/{}/{} {}:{}:{}".format(timestamp_tuple[2], timestamp_tuple[1], timestamp_tuple[0], timestamp_tuple[4], timestamp_tuple[5], timestamp_tuple[6])
		if message:
			log = "{} [{}]: [{}] {}".format(timestamp, level, caller, message[0])
		else:
			message = caller
			log = "{} [{}]: {}".format(timestamp, level, message)

		try:
			sys.stdout.write(self.colors[level])
			print(log)
			sys.stdout.write(self.colors["RESET"])
			if level != 'DEBUG' and level != 'INFO' and self.mqtt:
				self._send_over_mqtt("log"+level, log)
		except:
			print(log)

	def _send_over_mqtt(self, topic, log):
		try:
			self.publisher.ping()
			self.publisher.publish(topic, log, qos=1)
		except:
			try:
				self.publisher.connect()
				self.publisher.publish(topic, log, qos=1)
			except:
				None
