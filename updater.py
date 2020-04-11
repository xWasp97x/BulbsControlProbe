from logger import MyLogger
from umqtt_simple2 import MQTTClient
import json
from configuration_loader import ConfigurationLoader
import os
import time
import network

LOOP_RATE = 60
assert LOOP_RATE > 40


class Updater:
	def __init__(self, config_file):
		config_loader = ConfigurationLoader(config_file)
		self.loop_rate = LOOP_RATE
		self.configs = config_loader.load_configuration('broker', 'id', 'updates_topic',
														'tag_file', 'updates_ack_topic',
														'installed_tag_topic', 'download_path')
		self.logger = MyLogger(mqtt=False)
		self.mqtt_client = MQTTClient(self.configs['id'], self.configs['broker'])
		self.mqtt_client.DEBUG = True
		self.mqtt_client.set_callback(self.read_message)
		self.installed_tag = self.load_installed_tag()
		self.updating = False
		self.new_tag = None

	def load_installed_tag(self) -> str:
		try:
			with open(self.configs['tag_file'], 'r') as file:
				tag = file.read().strip()
			self.logger.log('DEBUG', 'Updater', 'Loaded tag {}'.format(tag))
			return tag
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't load tag file; {}".format(e))
			return 'default'

	def wait_update(self):
		self.logger.log('DEBUG', 'Updater', 'Waiting for update...')
		if not self.check_mqtt_connection():
			self.mqtt_client.connect()
		self.mqtt_client.subscribe(self.configs['updates_topic'])
		self.logger.log('INFO', 'Updater', 'New update json received')

	def read_message(self, topic: str, msg: str) -> (str, []):
		try:
			self.logger.log('DEBUG', 'Updater', 'Reading new message in {}'.format(topic))
			if 'END' in msg:
				self.complete_update(self.new_tag)
				return None, None
			self.logger.log('DEBUG', 'Updater', 'Reading update json')
			msg_json = json.loads(msg)
			tag = msg_json['tag']
			files = msg_json['files']
			self.logger.log('DEBUG', 'Updater', 'Update json read')
			self.updating = True
			return tag, files
		except Exception as e:
			self.logger.log('ERROR', 'Updater', 'Error reading update json; {}'.format(e))
			return None, None

	def reset_retain(self, topic: str):
		self.mqtt_client.publish(topic=topic, msg='', retain=True)

	def send_update_ack(self):
		self.logger.log('DEBUG', 'Updater', 'Sending update ACK...')
		ip = self.local_ip()
		topic = self.configs['updates_ack_topic']
		msg = {'ip': ip}
		msg_json = json.dumps(msg)
		try:
			self.mqtt_client.publish(topic=topic, msg=msg_json)
			self.logger.log('DEBUG', "Update ACK sent")
		except Exception as e:
			self.logger.log('ERROR', "Can't send update ACK")

	def local_ip(self) -> str:
		w = network.WLAN()
		if not w.isconnected():
			return None
		ip = w.ifconfig()[0]
		return ip

	def apply_update(self, tag: str):
		download_path = self.configs['download_path']
		files = os.listdir(download_path)
		filesnames = files
		files = [download_path + file for file in filesnames]
		self.logger.log('INFO', 'Updater', 'Applying update {}...'.format(tag))
		for idx, file in enumerate(files):
			filename = filesnames[idx]
			self.logger.log('DEBUG', 'Updater', 'Updating {}...'.format(filename))
			os.rename(file, filename)
			self.logger.log('DEBUG', 'Updater', '{} updated.'.format(filename))

	def complete_update(self, tag: str):
		self.apply_update(tag)
		self.logger.log('INFO', 'Updater', 'Update from {} to {} completed'.format(self.installed_tag, tag))
		self.update_installed_tag(tag)
		self.send_installed_tag()
		self.clean_download_folder()
		self.logger.log('WARNING', 'Updater', 'Rebooting in 3 seconds to apply the update...')
		time.sleep(3)
		self.logger.log('WARNING', 'Updater', 'Rebooting...')

	def update_installed_tag(self, tag):
		self.logger.log('DEBUG', "Updating installed tag")
		self.installed_tag = tag
		try:
			with open(self.configs['tag_file'], 'w') as file:
				file.write(tag)
			self.logger.log('DEBUG', "Installed tag updated")
		except Exception as e:
			self.logger.log('ERROR', "Can't update installed tag file; {}".format(e))

	def check_mqtt_connection(self):
		try:
			self.mqtt_client.ping()
			return True
		except:
			return False

	def send_installed_tag(self):
		self.logger.log('DEBUG', 'Updater', 'Sending installed tag...')
		topic = self.configs['installed_tag_topic']
		msg = {'ip': self.local_ip(), 'tag': self.installed_tag}
		msg_json = json.dumps(msg)
		try:
			self.mqtt_client.publish(topic=topic, msg=msg_json)
			self.logger.log('DEBUG', 'Updater', 'Installed tag sent')
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't send installed tag; {}".format(e))

	def clean_download_folder(self):
		self.logger.log('DEBUG', 'Updater', 'Cleaning download folder...')
		download_path = self.configs['download_path']
		files = os.listdir(download_path)
		filesnames = files
		files = [download_path + file for file in filesnames]
		for idx, file in enumerate(files):
			filename = filesnames[idx]
			self.logger.log('DEBUG', 'Updater', 'Deleting {}...'.format(filename))
			os.remove(file)
			self.logger.log('DEBUG', 'Updater', '{} deleted.'.format(filename))

	def loop(self):
		ip = self.local_ip()
		personal_topic = ip + '_updates'
		while True:
			self.send_installed_tag()
			self.mqtt_client.subscribe(topic=personal_topic, socket_timeout=3)
			if self.updating:
				self.mqtt_client.subscribe(topic=personal_topic, socket_timeout=30)
