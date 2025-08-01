import time
import logging
import threading
import random
import ctypes
from ctypes import wintypes
from abc import ABC, abstractmethod

user32 = ctypes.windll.user32

VK_CODES = {
    'left': 0x25,
    'up': 0x26,
    'right': 0x27,
    'down': 0x28,
    'alt': 0x12,
    'shift': 0x10,
    'ctrl': 0x11,
    'a': 0x41,
    'b': 0x42,
    'c': 0x43,
    'd': 0x44,
    'e': 0x45,
    'f': 0x46,
    'g': 0x47,
    'h': 0x48,
    'i': 0x49,
    'j': 0x4A,
    'k': 0x4B,
    'l': 0x4C,
    'm': 0x4D,
    'n': 0x4E,
    'o': 0x4F,
    'p': 0x50,
    'q': 0x51,
    'r': 0x52,
    's': 0x53,
    't': 0x54,
    'u': 0x55,
    'v': 0x56,
    'w': 0x57,
    'x': 0x58,
    'y': 0x59,
    'z': 0x5A,
    '0': 0x30,
    '1': 0x31,
    '2': 0x32,
    '3': 0x33,
    '4': 0x34,
    '5': 0x35,
    '6': 0x36,
    '7': 0x37,
    '8': 0x38,
    '9': 0x39,
    'space': 0x20,
    'enter': 0x0D,
    'backspace': 0x08,
    'tab': 0x09,
    'escape': 0x1B,
    'esc': 0x1B,
    'delete': 0x2E,
    'insert': 0x2D,
    'home': 0x24,
    'end': 0x23,
    'pageup': 0x21,
    'pagedown': 0x22,
    'f1': 0x70,
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
    'f10': 0x79,
    'f11': 0x7A,
    'f12': 0x7B,
    '-': 0xBD,
    '=': 0xBB,
    '[': 0xDB,
    ']': 0xDD,
    ';': 0xBA,
    "'": 0xDE,
    '`': 0xC0,
    '\\': 0xDC,
    ',': 0xBC,
    '.': 0xBE,
    '/': 0xBF
}

class BaseController(ABC):
    @abstractmethod
    def press_key(self, key, duration=0.05):
        pass
    
    @abstractmethod
    def press_and_hold(self, key):
        pass
    
    @abstractmethod
    def release_key(self, key):
        pass
    
    @abstractmethod
    def release_all_keys(self):
        pass
    
    @abstractmethod
    def move_mouse(self, x, y, duration=0):
        pass
    
    @abstractmethod
    def click_mouse(self, x=None, y=None):
        pass
    
    @abstractmethod
    def start_listener(self, on_press_callback):
        pass
    
    @abstractmethod
    def stop_listener(self):
        pass

class PyAutoGuiController(BaseController):
    def __init__(self):
        import pyautogui
        self.pyautogui = pyautogui
        self.pyautogui.PAUSE = 0
        self.pyautogui.FAILSAFE = False
        self.pressed_keys = set()
        self.listener = None
        self.listener_thread = None
        
    def press_key(self, key, duration=0.05):
        self.pyautogui.keyDown(key)
        time.sleep(random.uniform(0.03, 0.05))
        time.sleep(duration)
        self.pyautogui.keyUp(key)
        time.sleep(random.uniform(0.03, 0.05))
        
    def press_and_hold(self, key):
        if key not in self.pressed_keys:
            self.pyautogui.keyDown(key)
            time.sleep(random.uniform(0.03, 0.05))
            self.pressed_keys.add(key)
            
    def release_key(self, key):
        if key in self.pressed_keys:
            self.pyautogui.keyUp(key)
            time.sleep(random.uniform(0.03, 0.05))
            self.pressed_keys.remove(key)
            
    def release_all_keys(self):
        for key in list(self.pressed_keys):
            self.pyautogui.keyUp(key)
            time.sleep(random.uniform(0.03, 0.05))
        self.pressed_keys.clear()
        
        keys_to_release = ['left', 'right', 'up', 'down', 'shift', 'alt', 'a', 's']
        for key in keys_to_release:
            try:
                self.pyautogui.keyUp(key)
                time.sleep(random.uniform(0.03, 0.05))
            except:
                pass
                
    def move_mouse(self, x, y, duration=0):
        self.pyautogui.moveTo(x, y, duration=duration)
        
    def click_mouse(self, x=None, y=None):
        if x is not None and y is not None:
            self.pyautogui.click(x, y)
        else:
            self.pyautogui.click()
            
    def start_listener(self, on_press_callback):
        try:
            from pynput import keyboard
            
            def on_press(key):
                try:
                    if key == keyboard.Key.f8:
                        on_press_callback('f8')
                except:
                    pass
                    
            self.listener = keyboard.Listener(on_press=on_press)
            self.listener.start()
        except ImportError:
            self._fallback_listener(on_press_callback)
            
    def _fallback_listener(self, on_press_callback):
        def check_f8():
            while self.listener_thread:
                if user32.GetAsyncKeyState(VK_CODES['f8']) & 0x8000:
                    on_press_callback('f8')
                    time.sleep(0.5)
                time.sleep(0.05)
                
        self.listener_thread = threading.Thread(target=check_f8, daemon=True)
        self.listener_thread.start()
        
    def stop_listener(self):
        if self.listener:
            try:
                self.listener.stop()
            except:
                pass
        self.listener_thread = None

class WindowsApiController(BaseController):
    def __init__(self):
        self.pressed_keys = set()
        self.listener_thread = None
        self.listener_callback = None
        
    def _get_vk_code(self, key):
        return VK_CODES.get(key.lower(), ord(key.upper()) if len(key) == 1 else 0)
        
    def press_key(self, key, duration=0.05):
        vk = self._get_vk_code(key)
        if vk:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(random.uniform(0.03, 0.05))
            time.sleep(duration)
            user32.keybd_event(vk, 0, 2, 0)
            time.sleep(random.uniform(0.03, 0.05))
            
    def press_and_hold(self, key):
        if key not in self.pressed_keys:
            vk = self._get_vk_code(key)
            if vk:
                user32.keybd_event(vk, 0, 0, 0)
                time.sleep(random.uniform(0.03, 0.05))
                self.pressed_keys.add(key)
                
    def release_key(self, key):
        if key in self.pressed_keys:
            vk = self._get_vk_code(key)
            if vk:
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(random.uniform(0.03, 0.05))
                self.pressed_keys.remove(key)
                
    def release_all_keys(self):
        for key in list(self.pressed_keys):
            vk = self._get_vk_code(key)
            if vk:
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(random.uniform(0.03, 0.05))
        self.pressed_keys.clear()
        
        keys_to_release = ['left', 'right', 'up', 'down', 'shift', 'alt', 'a', 's']
        for key in keys_to_release:
            vk = self._get_vk_code(key)
            if vk:
                user32.keybd_event(vk, 0, 2, 0)
                time.sleep(random.uniform(0.03, 0.05))
                
    def move_mouse(self, x, y, duration=0):
        if duration > 0:
            current_x = ctypes.c_long()
            current_y = ctypes.c_long()
            user32.GetCursorPos(ctypes.byref(current_x), ctypes.byref(current_y))
            
            steps = int(duration * 100)
            for i in range(steps):
                progress = (i + 1) / steps
                new_x = int(current_x.value + (x - current_x.value) * progress)
                new_y = int(current_y.value + (y - current_y.value) * progress)
                user32.SetCursorPos(new_x, new_y)
                time.sleep(duration / steps)
        else:
            user32.SetCursorPos(int(x), int(y))
            
    def click_mouse(self, x=None, y=None):
        if x is not None and y is not None:
            user32.SetCursorPos(int(x), int(y))
            
        user32.mouse_event(2, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(4, 0, 0, 0, 0)
        
    def start_listener(self, on_press_callback):
        self.listener_callback = on_press_callback
        
        def listener_loop():
            while self.listener_thread:
                if user32.GetAsyncKeyState(VK_CODES['f8']) & 0x8000:
                    self.listener_callback('f8')
                    time.sleep(0.5)
                time.sleep(0.05)
                
        self.listener_thread = threading.Thread(target=listener_loop, daemon=True)
        self.listener_thread.start()
        
    def stop_listener(self):
        self.listener_thread = None

class KeyController:
    def __init__(self, input_method='pyautogui'):
        self.input_method = input_method
        
        if input_method == 'windows_api':
            self.controller = WindowsApiController()
            logging.info("🔒 Windows API 입력 모드 활성화")
        else:
            self.controller = PyAutoGuiController()
            logging.info("🎮 PyAutoGUI 입력 모드 활성화")
            
        self.key_count = 0
        self.start_time = time.time()
        self.last_log_time = time.time()
        
        self.last_shift_time = 0
        self.shift_cooldown = 2.0
        
        self.stats_thread = threading.Thread(target=self._stats_logger, daemon=True)
        self.stats_thread.start()
        
    def _increment_count(self, count=1):
        self.key_count += count
        
    def _stats_logger(self):
        while True:
            time.sleep(60)
            current_time = time.time()
            elapsed_seconds = current_time - self.start_time
            
            if elapsed_seconds > 0:
                total_count = self.key_count
                per_second = total_count / elapsed_seconds
                per_minute = per_second * 60
                per_hour = per_minute * 60
                
                logging.info(f"📊 키입력 통계 - 전체: {total_count:,}회 | "
                           f"초당: {per_second:.1f}회 | "
                           f"분당: {per_minute:,.0f}회 | "
                           f"시간당: {per_hour:,.0f}회")
                           
    def is_shift_ready(self):
        current_time = time.time()
        return current_time - self.last_shift_time >= self.shift_cooldown
        
    def press_key(self, key, duration=0.05):
        if key == 'shift':
            current_time = time.time()
            if current_time - self.last_shift_time < self.shift_cooldown:
                return
            self.last_shift_time = current_time
            
        self.controller.press_key(key, duration)
        self._increment_count(2)
        logging.debug(f"키 입력: {key} ({duration*1000:.0f}ms)")
        
    def press_and_hold(self, key):
        self.controller.press_and_hold(key)
        self._increment_count(1)
        logging.debug(f"키 누름: {key}")
        
    def release_key(self, key):
        self.controller.release_key(key)
        self._increment_count(1)
        logging.debug(f"키 해제: {key}")
        
    def release_all_keys(self):
        logging.info("🔑 모든 키 해제")
        self.controller.release_all_keys()
        
    def get_pressed_keys(self):
        return self.controller.pressed_keys.copy()
        
    def move_mouse(self, x, y, duration=0):
        self.controller.move_mouse(x, y, duration)
        
    def click_mouse(self, x=None, y=None):
        self.controller.click_mouse(x, y)
        
    def start_listener(self, on_press_callback):
        self.controller.start_listener(on_press_callback)
        
    def stop_listener(self):
        self.controller.stop_listener()