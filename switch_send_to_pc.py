from Wifi import Wifi
from tkHyperlinkManager import HyperlinkManager
from functools import partial
from sys import exit, platform
from enum import Enum
import webbrowser
import os
import sys
import json

try:
    import cv2
except ModuleNotFoundError:
    print('OpenCV module Not Found')
    print('  install via pip:')
    print('    python -m pip install opencv-python')
    exit(-1)

try:
    import appdirs
except ModuleNotFoundError:
    print('appdirs module Not Found')
    print('  install via pip:')
    print('    python -m pip install appdirs')
    exit(-1)

try:
    import tkinter as tk
    from tkinter import ttk
except ModuleNotFoundError:
    print('tkinter module Not Found')
    print('  install via pip:')
    print('    python -m pip install tk')
    exit(-1)

try:
    from PIL import Image
    from PIL import ImageTk
except ModuleNotFoundError:
    print('Pillow module Not Found')
    print('  install via pip:')
    print('    python -m pip install Pillow')
    exit(-1)

if platform == 'win32':
    from win.videoinput_wrapper import VideoInputWrapper

def get_resource_path(filename):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, filename)
    else:
        return filename

class ConnectSwitchWifi:
    def __init__(self,root):
        self.root = root
        self.cap = None
        self.loop = False
        self.index = -1
        self.device_name = ''
        self.detect = cv2.QRCodeDetector()
        self.last_qr_value = ''
        self.states = Enum('State', ['SETUP', 'SSID', 'URL', 'IDLE'])
        self.log_types = Enum('Log', ['INFO', 'WARNING', 'ERROR', 'HYPERLINK'])
        self.app_name = "ConnectSwitchWiFi"
        self.app_author = "Lokno"
        self.wc = Wifi()
        self.wifi_profile_created = False
        self.wifi_connection = False

        try:
            root.iconbitmap(get_resource_path("icon.ico"))
        except tk.TclError:
            pass

        # delay before connecting after adding a new profile
        self.delay_connect = 3000 # ms
        # delay before detecting the QR code encoding the url
        self.delay_detect_url = 1000 # ms
        # delay before opening a web browser
        self.delay_browser = 3000 # ms

        config = self.load_config()

        self.log_box = tk.Text(self.root, height=6, width=60, state="disabled")
        self.log_box.tag_config("red", foreground="red")
        self.log_box.tag_config("orange", foreground="orange")

        self.hyperlink= HyperlinkManager(self.log_box)

        self.state = self.states.SETUP
        if 'device_index' in config:
            self.log('Loaded saved settings.',self.log_types.INFO)
            self.index = config['device_index']
            self.device_name = config['device_name']
            self.state = self.states.SSID

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        root.title("Connect To Switch")

        self.selected_device = tk.StringVar()

        self.device_frame = tk.Frame(self.root,pady=5)
        
        if platform == 'win32':
            videoinput = VideoInputWrapper()
            self.devices = videoinput.get_device_list()
            device_count = len(self.devices)
            self.device_name_to_index = {d:i for i,d in enumerate(self.devices)}
            self.log(f'Found {device_count} devices.',self.log_types.INFO)

            if self.state != self.states.SETUP:
                if self.device_name not in self.device_name_to_index or device_count <= self.index:
                    self.log(f'ERROR: Saved Settings Invalid. Returning to setup...', self.log_types.ERROR)
                    self.state == self.states.SETUP
                elif self.device_name_to_index[self.device_name] != self.index:
                    self.log(f'WARNING: Saved Settings Invalid. Going with saved name...', self.log_types.WARNING)
                    self.index = self.device_name_to_index[self.device_name]

            self.device_dropdown = ttk.Combobox(self.device_frame, textvariable=self.selected_device, values=self.devices, state="readonly")
            self.device_dropdown.pack(padx=5,side=tk.LEFT)
            self.device_dropdown.bind("<<ComboboxSelected>>", self.update)

            self.config_button = tk.Button(self.device_frame, text="Configure...", command=self.reset)
            self.config_button.pack(side=tk.LEFT)
            
            if self.state == self.states.SETUP:
                self.config_button.config(state="disabled")
                self.selected_device.set("Select a device")
            else:
                self.selected_device.set(self.device_name)
                self.device_dropdown.config(state="disabled")
        else:
            if self.state == self.states.SETUP:
                self.config_button.config(state="disabled")
                self.log(f'Device labeling not supported on your platform.\nPress submit to use default device...',self.log_types.INFO)
                self.selected_device.set("0")
            else:
                self.selected_device.set(str(self.index))
                self.selected_device.set(self.device_name)

            self.device_entry = tk.Entry(self.device_frame, textvariable=self.selected_device)
            self.device_entry.pack(padx=5,side=tk.LEFT)

            self.switch_button = tk.Button(self.device_frame, text="Switch Device", command=self.update)
            self.switch_button.pack(padx=5,side=tk.LEFT)

            self.config_button = tk.Button(self.device_frame, text="Configure...", command=self.reset)
            self.config_button.pack(padx=5,side=tk.LEFT)

        self.connect_button = tk.Button(self.device_frame, text="Connect", command=self.connect)
        self.connect_button.pack(padx=5,side=tk.LEFT)
        
        if self.state != self.states.SETUP:
            self.connect_button.config(state="disabled")

        self.device_frame.pack(side=tk.TOP)

        img = Image.new("RGB", (640, 480), "black")
        self.blank_img = ImageTk.PhotoImage(image=img)
        self.feed_label = tk.Label(self.root)
        self.feed_label.config(image=self.blank_img, bg="black")
        self.feed_label.pack()

        self.log_box.pack()

        if self.state == self.states.SSID:
            self.log('Searching for QR with WiFi connection info...',self.log_types.INFO)

        if self.state != self.states.SETUP:
            root.after(0, self.update)

    def connect(self):
        if self.cap is not None and self.cap.isOpened():
            self.connect_button.config(state="disabled")
            if self.wifi_connection: # Disconnect
                self.disconnect()
                self.connect_button.config(state="normal",text="Connect")
            else:
                if self.state == self.states.SETUP:
                    self.device_dropdown.config(state="disabled")
                    self.config_button.config(state="normal")
                elif self.state != self.states.SSID:
                    self.log('Searching for QR with WiFi connection info...',self.log_types.INFO)
                self.state = self.states.SSID
        else:
            self.log('ERROR: No capture device is open.',self.log_types.ERROR)

    def disconnect(self):
        if self.wifi_connection:
            self.log(f'Disconnecting from WiFi...',self.log_types.INFO)
            self.wc.disconnect()
            self.wifi_connection = False
        if self.wifi_profile_created:
            self.log(f'Deleting WiFi profile...',self.log_types.INFO)
            self.wc.delete_profile()
            self.wifi_profile_created = False

    def reset(self):
        self.disconnect()
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            self.cap = None
        self.log('Reset. Select a new device...',self.log_types.INFO)
        self.index = -1
        self.device_name = ''
        self.device_dropdown.config(state="normal")
        self.state = self.states.SETUP
        self.loop = False
        self.feed_label.config(image=self.blank_img, bg="black")
        self.config_button.config(state="disabled")
        self.connect_button.config(state="normal",text="Connect")

        if platform == 'win32':
            self.selected_device.set("Select a device")
        else:
            self.selected_device.set("0")
            self.switch_button.config(state="normal")

    def clear_config(self):
        data_dir = appdirs.user_data_dir(self.app_name, self.app_author)
        data_file = os.path.join(data_dir, "config.json")
        if os.path.exists(data_file):
            os.remove(data_file)
    
    def store_config(self,data):
        data_dir = appdirs.user_data_dir(self.app_name, self.app_author)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        data_file = os.path.join(data_dir, "config.json")
        with open(data_file, "w") as f:
            f.write(json.dumps(data))
    
    def load_config(self):
        data_dir = appdirs.user_data_dir(self.app_name, self.app_author)
        data_file = os.path.join(data_dir, "config.json")
        if not os.path.exists(data_file):
            return {}
        with open(data_file, "r") as f:
            return json.loads(f.read())

    def on_closing(self):
        self.loop = False
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
        self.disconnect()
        self.root.destroy()

    def validate(self):
        if platform == 'win32':
            return self.selected_device.get() != ""
        else:
            return self.validate_int(self.selected_device.get())

    def validate_int(self, string):
        try:
            int_val = int(string)
            if 0 <= int_val <= 100:
                return True
            else:
                return False
        except ValueError:
            return False

    def update(self, *args):
        if self.validate():
            if self.cap is not None and self.cap.isOpened():
                self.cap.release()

            device_name = self.selected_device.get()

            if platform == 'win32':
                self.index = self.device_name_to_index[device_name]
            else:
                self.index = int(device_name)
                device_name = f'device {self.index}'

            self.cap = cv2.VideoCapture(self.index)

            if not self.cap.isOpened():
                self.log(f'ERROR: Could not open {device_name}', self.log_types.ERROR)
                return

            if platform == 'win32':
                self.device_name = device_name

            self.log(f'Switched to {device_name}',self.log_types.INFO)
    
            thumbnail_height=int(640*self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)/self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

            self.loop = True
            while self.loop:
                ret, frame = self.cap.read()
    
                if not ret:
                    continue
    
                #gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                frame = self.handle_connection(frame)

                frame = cv2.resize(frame, (640, thumbnail_height))
                img = Image.fromarray(frame)
                img = ImageTk.PhotoImage(image=img)
    
                self.feed_label.config(image=img)
                self.feed_label.image = img
    
                self.root.update()

        elif platform != 'win32':
            self.log(f'Not a valid device index', self.log_types.ERROR)

    def handle_connection(self,frame):
        if self.state not in [self.states.SETUP,self.states.IDLE]:
            value, points, _ = self.detect.detectAndDecode(frame)
            if value:
                feature_count = len(points)
                for i in range(feature_count):
                    point_count = len(points[i])
                    for j in range(point_count):
                        nextPointIndex = (j+1) % point_count
                        a = tuple(map(int, points[i][j]))
                        b = tuple(map(int, points[i][nextPointIndex]))
                        cv2.line(frame, a, b, (255,0,0), 5)
                if value != self.last_qr_value:
                    self.last_qr_value = value
                    if self.state == self.states.SSID and value.startswith('WIFI'):
                        ssid_str,_,pw_str = self.decode_ssid(value)
                        self.log('Connection info received.', self.log_types.INFO)
                        self.log(f'SSID: {ssid_str}; Password: {pw_str}', self.log_types.INFO)

                        self.log(f'Adding profile for ssid {ssid_str:s}.', self.log_types.INFO)
                        self.wc.create_new_connection(ssid_str, pw_str)
                        self.wifi_profile_created = True
                        self.state = self.states.IDLE
                        self.root.after(self.delay_connect,self.request_connection)
                    elif self.state == self.states.URL and value.startswith('http'):
                        self.log('Hosted URL Received. Opening web browser...', self.log_types.INFO)
                        device_name = self.device_name if platform == 'win32' else ''
                        self.store_config({'device_name':device_name,'device_index':self.index})
                        self.log('Stored video capture settings.',self.log_types.INFO)
                        self.url = value
                        self.state = self.states.IDLE
                        self.root.after(self.delay_browser,self.open_browser)
                    else:
                        self.log('WARNING: Unexpected QR payload found.',self.log_types.WARNING)

        return frame

    def request_connection(self):
        self.log(f'Requesting connection...',self.log_types.INFO)
        self.wc.connect()
        self.root.after(self.delay_detect_url,self.check_for_url)

    def check_for_url(self):
        self.log('Searching for QR with URL...',self.log_types.INFO)
        self.state = self.states.URL

    def open_browser(self):
        self.log('Opening browser to URL...',self.log_types.INFO)
        self.log(self.url,self.log_types.INFO)
        webbrowser.open(self.url)
        self.wifi_connection = True
        self.connect_button.config(state="normal",text="Disconnect")
        
    def decode_ssid(self,s):
        ssid_str = None
        type_str = None
        pw_str = None
        for p in s.split(';'):
            items = p.split(':')
            if p.startswith('WIFI') and len(items) == 3:
                ssid_str = items[2]
            elif p.startswith('T') and len(items) == 2:
                type_str = items[1]
            elif p.startswith('P') and len(items) == 2:
                pw_str = items[1]
        return ssid_str,type_str,pw_str

    def log(self,msg,type_name):
        self.log_box.config(state="normal")
        if type_name == self.log_types.ERROR:
            self.log_box.insert(tk.END, msg + '\n', "red")
        elif type_name == self.log_types.WARNING:
            self.log_box.insert(tk.END, msg + '\n', "orange")
        elif msg.startswith('http'):
            self.log_box.insert(tk.END,msg,self.hyperlink.add(partial(webbrowser.open,msg)))
            self.log_box.insert(tk.END, '\n')
        else:
            self.log_box.insert(tk.END, msg + '\n')
        self.log_box.config(state="disabled")
        self.log_box.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    live_feed = ConnectSwitchWifi(root)
    root.mainloop()