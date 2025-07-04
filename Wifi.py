# Basic Cross-Platform Wifi Manager
# Linux support requires nmcli (network-manager package) and must be run with root privileges
# install network-manager

from sys import platform
import os
import subprocess

class MacWifi():
    def __init__(self):
        self.SSID = ''
        self.password = ''
        wifi_interface = os.popen("networksetup -listallhardwareports | grep -A 1 Wi-Fi | grep Device | cut -d ' ' -f 2").read()
        self.wifi_interface = wifi_interface.strip()

    def create_new_connection(self, SSID, password):
        self.SSID = SSID
        self.password = password
        command = f'networksetup -addpreferredwirelessnetworkatindex {self.wifi_interface} "{self.SSID}" 0 WPA2 {self.password}'
        os.system(command)

    def connect(self):
        command = f'networksetup -setairportnetwork {self.wifi_interface} "{self.SSID}"'
        os.system(command)

    def delete_profile(self):
        command = f'networksetup -removepreferredwirelessnetwork {self.wifi_interface} "{self.SSID}"'
        os.system(command)

    def disconnect(self):
        os.system(f"networksetup -setairportpower {self.wifi_interface} off")

class LinuxWifi():
    def __init__(self):
        self.SSID = ''
        self.password = ''

        user_groups = os.popen("groups").read().strip().split(' ')

        if 'root' not in user_groups:
            raise Exception(f"User not authorized to control networking")

        try:
            subprocess.run(['nmcli', '--version'], check=True)
        except subprocess.CalledProcessError:
            raise Exception(f"ERROR: nmcli not found. Please install network-manager")

        wifi_interface = os.popen("nmcli -t -f device,type device | awk -F: '/wifi/ {print $1; exit}'").read()
        self.wifi_interface = wifi_interface.strip()

    def create_new_connection(self, SSID, password):
        self.SSID = SSID
        self.password = password

    def connect(self):
        command = f'nmcli device wifi connect "{self.SSID}" password "{self.password}" ifname {self.wifi_interface}'
        os.system(command)

    def delete_profile(self):
        command = f'nmcli connection delete "{self.SSID}"'
        os.system(command)

    def disconnect(self):
        os.system(f"nmcli device disconnect {self.wifi_interface}")

class WinWifi():
    def __init__(self):
        self.SSID = ''
        self.password = ''

    def create_new_connection(self, SSID, password):
        self.SSID = SSID
        self.password = password
        config = """<?xml version=\"1.0\"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>"""+self.SSID+"""</name>
    <SSIDConfig>
        <SSID>
            <name>"""+self.SSID+"""</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>"""+self.password+"""</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""
        file_path = os.path.expandvars(f'%TEMP%\\{self.SSID:s}.xml')
        command = f'netsh wlan add profile filename="{file_path:s}" interface=Wi-Fi'
        
        with open(file_path, 'w') as file:
            file.write(config)
        os.system(command)
    
    def connect(self):
        os.system("netsh wlan connect name=\""+self.SSID+"\" ssid=\""+self.SSID+"\" interface=Wi-Fi")
    
    def delete_profile(self):
        os.system(f'netsh wlan delete profile name="{self.SSID:s}" interface=Wi-Fi')
    
    def disconnect(self):
        os.system("netsh wlan disconnect interface=Wi-Fi")

def Wifi():
    if platform == 'win32':
        wc = WinWifi()
    elif platform == "darwin":
        wc = MacWifi()
    elif platform == "linux":
        wc = LinuxWifi()
    else:
        raise Exception(f"Unsupported operating system: {platform}")
    return wc