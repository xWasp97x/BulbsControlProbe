import network
from configuration_loader import ConfigurationLoader
from logger import MyLogger
import json
from time import sleep


class WifiManager:
	def __init__(self, config_file, networks_file):
		self.config_loader = ConfigurationLoader(config_file)
		self.wlan = network.WLAN(network.STA_IF)
		self.wlan.active(False)
		sleep(0.5)
		self.wlan.active(True)
		sleep(0.5)
		self.wlan.disconnect()
		configs = self.config_loader.load_configuration('check_delay', 'mqtt_conf_file')
		self.check_delay = int(configs['check_delay'])
		mqtt_conf_file = configs['mqtt_conf_file']
		self.logger = MyLogger(mqtt=True, mqtt_conf=mqtt_conf_file)
		self.networks_file = networks_file

	def scan(self):
		try:
			with open(self.networks_file, 'rb') as file:
				saved_networks = json.load(file)

			networks_ssids = list(saved_networks.keys())

		except Exception:
			try:
				self.logger.log('ERROR', 'WifiManager', 'Error loading networks file.')
			except OSError:
				None
			raise OSError("Error loading networks file.")

		try:
			scan_results = [str(result[0]) for result in self.wlan.scan()]
		except OSError:
			self.logger.log("ERROR", "WifiManager", "No networks!")
			scan_results = list()

		available_networks = [network for network in scan_results and networks_ssids]

		try:
			self.logger.log('INFO', 'WifiManager', 'Available networks: {}'.format(available_networks))
		except OSError:
			None

		return available_networks, saved_networks

	def connect(self, available_networks, networks):
		for network_ssid in available_networks:
			self.logger.log("DEBUG", 'WifiManager', 'Trying connection to {}'.format(network_ssid))
			self.wlan.connect(network_ssid, networks[network_ssid])
			while self.wlan.status() is network.STAT_CONNECTING:
				sleep(0.250)
			if self.wlan.status() == network.STAT_GOT_IP:
				return network_ssid

		return None

	def check_connection(self):
		if not self.wlan.status() is network.STAT_GOT_IP:
			available_networks, saved_networks = self.scan()
			ssid = self.connect(available_networks, saved_networks)
			try:
				if ssid:
					self.logger.log('INFO', 'WifiManager', 'Connected to: {}; IP:{}'.format(ssid, self.wlan.ifconfig()[0]))
				else:
					self.logger.log('ERROR', 'WifiManager', 'Not connected')
			except OSError as oe:
				print(str(oe))