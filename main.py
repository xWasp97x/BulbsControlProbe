import esp
import wifi_manager
from updater import Updater
from machine import Timer
from switch_reader import SwitchReader
esp.osdebug(None)


wifi = wifi_manager.WifiManager('/config/wifi.txt', '/config/networks.txt')
wifi.check_connection()
wifi_timer = Timer(-1)
wifi_timer.init(period=wifi.check_delay*1000, mode=Timer.PERIODIC, callback=lambda t: wifi.check_connection())


updater = Updater('/config/updater.txt')
#updater_timer = Timer(-1)
#updater_timer.init(period=updater.loop_rate*1000, mode=Timer.PERIODIC, callback=lambda t: updater.loop())


switch = SwitchReader('/config/switch.txt')
#updater_timer = Timer(-1)
#updater_timer.init(period=switch.switch_update_period, mode=Timer.PERIODIC, callback=lambda t: switch.read_switch())
