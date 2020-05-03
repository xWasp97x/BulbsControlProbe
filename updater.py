from logger import MyLogger
from umqtt_simple2 import MQTTClient
import json
from configuration_loader import ConfigurationLoader
import os
import time
import network
from machine import Timer, reset
import socket

LOOP_RATE = 60
assert LOOP_RATE > 40

# TODO: check "updating" attribute usefulness


class Updater:
	def __init__(self, config_file):
		config_loader = ConfigurationLoader(config_file)
		self.configs = config_loader.load_configuration('broker', 'id', 'tag_file', 'installed_tag_topic',
														'download_path')
		self.logger = MyLogger(mqtt=False)
		self.mqtt_client = MQTTClient(self.configs['id'], self.configs['broker'])
		self.mqtt_client.DEBUG = True
		self.mqtt_client.set_callback(self.read_message)
		self.installed_tag = self.load_installed_tag()
		self.updating = False
		self.new_tag = None
		self.timer = None
		self.message_read = False
		self.ip = self.local_ip()
		self.personal_topic = self.ip + '_updates'
		self.init_download_folder()
		self.loop()

	def init_download_folder(self):
		self.logger.log('DEBUG', 'Updater', 'Creating download folder')
		download_path = self.configs['download_path']
		try:
			os.mkdir(download_path)
		except:
			try:
				files = os.listdir(download_path)
				for file in files:
					os.remove(download_path + file)
			except:
				return False
		return True

	def receive_files(self, files):
		self.logger.log('DEBUG', 'Updater', 'Receiving: ' + ' '.join(files))
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't create server socket; {}".format_map(e))
			return False
		try:
			try:
				s.bind(('', 50000))
			except Exception as e:
				self.logger.log('ERROR', 'Updater', "Can't bind the socket; {}".format(e))
				return False
			s.listen(1)
			for file in files:
				conn, _ = s.accept()
				if not self.receive_file(file, conn):
					raise Exception("Can't receive " + file)
			self.logger.log('DEBUG', 'Updater', 'Files received.')
			return True
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't receive files; {}".format(e))
			return False
		finally:
			try:
				s.close()
			except:
				pass

	def receive_file(self, file, conn):
		complete_path = self.configs['download_path'] + file
		self.logger.log('DEBUG', 'Updater', 'Saving {} in {}'.format(file, complete_path))
		with open(complete_path, 'wb') as f:
			try:
				while True:
					data = conn.recv(100)
					if not data:
						break
					f.write(data)
			except Exception as e:
				self.logger.log('ERROR', 'Updater', 'Error receiving a chunk')
				return False
			finally:
				conn.close()
		self.logger.log('DEBUG', 'Updater', file + ' received.')
		return True

	def init_timer(self):
		self.timer = Timer(-1)
		self.timer.init(period=LOOP_RATE*1000, mode=Timer.ONE_SHOT, callback=lambda t: self.loop())

	def deinit_timer(self):
		if isinstance(self.timer, Timer):
			self.timer.deinit()
		self.timer = None

	def load_installed_tag(self) -> str:
		try:
			with open(self.configs['tag_file'], 'r') as file:
				tag = file.read().strip()
			self.logger.log('DEBUG', 'Updater', 'Loaded tag {}'.format(tag))
			return tag
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't load tag file, creating it; {}".format(e))
			with open(self.configs['tag_file'], 'w') as file:
				file.write('default')
			return 'default'

	def read_message(self, topic: str, msg: str, *args):
		try:
			self.message_read = True
			if len(msg) == 0:
				return
			self.logger.log('DEBUG', 'Updater', 'Reading update json')
			try:
				msg_json = json.loads(msg)
			except ValueError as ve:
				self.logger.log('ERROR', 'Updater', 'Error reading message, message: {}; {}'.format(msg, ve))
			tag = msg_json['tag']
			files = msg_json['files']
			self.logger.log('DEBUG', 'Updater', 'Update json read')
			self.updating = True
			if self.receive_files(files):
				self.complete_update(tag)
		except Exception as e:
			self.logger.log('ERROR', 'Updater', 'Error reading update json; {}'.format(e))

	def reset_retain(self, topic: str):
		self.mqtt_client.publish(topic=topic, msg='', retain=True)

	def local_ip(self) -> str:
		w = network.WLAN()
		while not w.isconnected():
			self.logger.log('WARNING', 'Updater', 'Waiting WiFi connection to retrieve loacal ip...')
			time.sleep(1)
		ip = w.ifconfig()[0]
		return ip

	def apply_update(self, tag: str):
		download_path = self.configs['download_path']
		files = os.listdir(self.download_folder())
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
		self.reset_retain(self.personal_topic)
		self.logger.log('WARNING', 'Updater', 'Rebooting in 3 seconds to apply the update...')
		time.sleep(3)
		self.logger.log('WARNING', 'Updater', 'Rebooting...')
		reset()

	def update_installed_tag(self, tag):
		self.logger.log('DEBUG', "Updating installed tag")
		self.installed_tag = tag
		try:
			with open(self.configs['tag_file'], 'w') as file:
				file.write(tag)
			self.logger.log('DEBUG', "Installed tag updated")
		except Exception as e:
			self.logger.log('ERROR', "Can't update installed tag file; {}".format(e))

	def connected_to_broker(self):
		try:
			self.mqtt_client.ping(5)
			return True
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't ping the broker; {}".format(e))
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

	def download_folder(self):
		return self.configs['download_path'][:-1]

	def clean_download_folder(self):
		self.logger.log('DEBUG', 'Updater', 'Cleaning download folder...')
		download_path = self.configs['download_path']
		files = os.listdir(self.download_folder())
		filesnames = files
		files = [download_path + file for file in filesnames]
		for idx, file in enumerate(files):
			filename = filesnames[idx]
			self.logger.log('DEBUG', 'Updater', 'Deleting {}...'.format(filename))
			os.remove(file)
			self.logger.log('DEBUG', 'Updater', '{} deleted.'.format(filename))

	def connect_to_broker(self) -> bool:
		try:
			if not self.connected_to_broker():
				self.mqtt_client.connect()
			else:
				return True
			time.sleep(1)
			if not self.connected_to_broker():
				self.logger.log('ERROR', 'Updater', "Can't connect to the broker")
			else:
				self.logger.log('INFO', 'Updater', 'Connected to the broker')
				return True
		except Exception as e:
			self.logger.log('ERROR', 'Updater', "Can't connect to the broker; {}".format(e))
		return False

	def wait_msg(self):
		timeout = 3
		tries = int(timeout/0.5)  # 100ms/try
		self.logger.log('DEBUG', 'Updater', 'Waiting for message...')
		i = 0
		while i < tries and not self.message_read:
			self.mqtt_client.check_msg()
			time.sleep(0.5)
		if not self.message_read:
			self.logger.log('WARNING', 'Updater', 'Timeout waiting for message.')

	def loop(self):
		if not self.connect_to_broker():
			self.logger.log('ERROR', 'Updater', 'Not connected to broker, skipping...')
			return
		self.send_installed_tag()
		self.mqtt_client.subscribe(topic=self.personal_topic, socket_timeout=3)
		self.message_read = False
		self.wait_msg()
		self.init_timer()
