import threading
import time
import cv2
import numpy as np
import pygame
import logging
import os
import glob

class AlertSystem:
    def __init__(self, alert_num, screen_capture, detector_engine):
        self.alert_num = alert_num
        self.character_audio = f"char/{alert_num}.mp3"
        self.screen_capture = screen_capture
        self.detector_engine = detector_engine
        self.running = False
        self.thread = None
        
        self.lie_active = False
        self.lie_thread = None
        self.lie_frame_count = 0
        
        self.red_dot_active = False
        self.red_dot_thread = None
        
        self.class1_active = False
        self.class1_thread = None
        
        self.chat_alert_cooldown = 10.0
        self.last_chat_alert_time = 0
        self.chat_check_frame_count = 0
        
        self.templates = {}
        self.load_templates()
        
        pygame.mixer.init()
    
    def load_templates(self):
        if os.path.exists('change.png'):
            self.templates['change'] = cv2.imread('change.png')
            logging.info(f"✅ change 템플릿 로드")
        
        if os.path.exists('zero.png'):
            self.templates['zero'] = cv2.imread('zero.png')
            logging.info(f"✅ zero 템플릿 로드")
        
        self.templates['item'] = []
        item_folder = 'item'
        if os.path.exists(item_folder):
            image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.bmp']
            for ext in image_extensions:
                for img_path in glob.glob(os.path.join(item_folder, ext)):
                    template = cv2.imread(img_path)
                    if template is not None:
                        self.templates['item'].append(template)
                        logging.info(f"✅ item 템플릿 로드: {os.path.basename(img_path)}")
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._alert_loop, daemon=True)
        self.thread.start()
        logging.info("🚨 알림 시스템 시작")
    
    def stop(self):
        self.running = False
        self.stop_lie_alert()
        self.stop_red_dot_alert()
        self.stop_class1_alert()
        if self.thread:
            self.thread.join()
    
    def _analyze_chat_region(self, region_image):
        hsv = cv2.cvtColor(region_image, cv2.COLOR_BGR2HSV)
        
        color_ranges = {
            "분홍": ([156, 11, 177], [176, 111, 255]),
            "파랑": ([95, 0, 173], [115, 98, 255]),
            "녹색": ([50, 205, 146], [70, 255, 246]),
            "노랑": ([20, 205, 205], [40, 255, 255]),
            "회색": ([0, 0, 114], [180, 50, 214]),
            "흰색": ([0, 0, 205], [180, 50, 255])
        }
        
        total_pixels = region_image.shape[0] * region_image.shape[1]
        color_percentages = {}
        
        for color_name, (lower, upper) in color_ranges.items():
            lower = np.array(lower)
            upper = np.array(upper)
            mask = cv2.inRange(hsv, lower, upper)
            pixel_count = cv2.countNonZero(mask)
            percentage = (pixel_count / total_pixels) * 100
            color_percentages[color_name] = percentage
        
        return color_percentages
    
    def _check_chat_alert_condition(self, color_dist):
        if color_dist["분홍"] > 20:
            return False
        if color_dist["파랑"] > 20:
            return False
        if color_dist["노랑"] > 2:
            return False
        if color_dist["회색"] > 7:
            return False
        
        if color_dist["노랑"] > 0.1 or color_dist["분홍"] > 0.1 or color_dist["파랑"] > 0.1:
            return False
        
        if color_dist["흰색"] >= 0.5 or color_dist["녹색"] >= 1:
            return True
        
        return False
    
    def _detect_chat(self, main_frame):
        chat_x1, chat_y1 = 6, 806
        chat_x2, chat_y2 = 1061, 939
        chat_width = chat_x2 - chat_x1
        chat_height = chat_y2 - chat_y1
        
        region_height = chat_height // 5
        
        chat_area = main_frame[chat_y1:chat_y2, chat_x1:chat_x2]
        
        for i in range(5):
            y_center = (i * region_height) + (region_height // 2)
            y_start = y_center - 10
            y_end = y_center + 10
            
            if y_start < 0:
                y_start = 0
            if y_end > chat_height:
                y_end = chat_height
            
            region_img = chat_area[y_start:y_end, :, :]
            
            color_dist = self._analyze_chat_region(region_img)
            
            if self._check_chat_alert_condition(color_dist):
                return True
        
        return False
    
    def _alert_loop(self):
        last_change_time = 0
        last_item_time = 0
        last_zero_time = 0
        cooldown = 5.0
        zero_cooldown = 600.0
        
        while self.running:
            try:
                current_time = time.time()
                
                main_frame = self.screen_capture.get_main_frame()
                minimap = self.screen_capture.get_minimap()
                
                if main_frame is not None:
                    self.lie_frame_count += 1
                    if self.lie_frame_count >= 3:
                        self.lie_frame_count = 0
                        if self.detector_engine.detect_lie(main_frame):
                            if not self.lie_active:
                                self.start_lie_alert()
                        else:
                            if self.lie_active:
                                self.stop_lie_alert()
                    
                    if 'change' in self.templates and self.templates['change'] is not None:
                        if self._match_template(main_frame, self.templates['change']):
                            if current_time - last_change_time > cooldown:
                                self.play_alert("change.mp3")
                                last_change_time = current_time
                    
                    if 'zero' in self.templates and self.templates['zero'] is not None:
                        if self._detect_zero(main_frame):
                            if current_time - last_zero_time > zero_cooldown:
                                self.play_alert("zero.mp3")
                                last_zero_time = current_time
                    
                    if 'item' in self.templates and self.templates['item']:
                        item_found = False
                        for item_template in self.templates['item']:
                            if self._match_template(main_frame, item_template):
                                item_found = True
                                break
                        
                        if item_found:
                            if current_time - last_item_time > cooldown:
                                self.play_alert("item.mp3")
                                last_item_time = current_time
                    
                    self.chat_check_frame_count += 1
                    if self.chat_check_frame_count >= 30:
                        self.chat_check_frame_count = 0
                        if self._detect_chat(main_frame):
                            if current_time - self.last_chat_alert_time > self.chat_alert_cooldown:
                                self.play_alert("chat.mp3")
                                self.last_chat_alert_time = current_time
                                logging.info("💬 채팅 알림 감지")
                
                if minimap is not None:
                    if self._detect_red_dot(minimap):
                        if not self.red_dot_active:
                            self.start_red_dot_alert()
                    else:
                        if self.red_dot_active:
                            self.stop_red_dot_alert()
                
            except Exception as e:
                logging.error(f"알림 감지 오류: {e}")
            
            time.sleep(0.016)
    
    def _match_template(self, image, template):
        if image is None or template is None:
            return False
        
        try:
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            return max_val >= 0.8
        except:
            return False
    
    def _detect_zero(self, frame):
        if frame is None or 'zero' not in self.templates or self.templates['zero'] is None:
            return False
        
        try:
            zero_roi = frame[1038:1062, 1700:1718]
            
            if zero_roi.shape[0] < 24 or zero_roi.shape[1] < 18:
                return False
            
            result = cv2.matchTemplate(zero_roi, self.templates['zero'], cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            return max_val >= 0.8
            
        except:
            return False
    
    def _detect_red_dot(self, minimap):
        hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
        
        lower_red1 = np.array([0, 200, 200])
        upper_red1 = np.array([5, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        
        lower_red2 = np.array([175, 200, 200])
        upper_red2 = np.array([180, 255, 255])
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        
        mask = cv2.bitwise_or(mask1, mask2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if 4 <= area <= 100:
                return True
        
        return False
    
    def play_alert(self, sound_file):
        try:
            if os.path.exists(self.character_audio):
                pygame.mixer.music.load(self.character_audio)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            
            if os.path.exists(sound_file):
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.play()
                logging.info(f"🔊 알림 재생: {sound_file}")
        except Exception as e:
            logging.error(f"알림 재생 실패: {e}")
    
    def play_alert_once(self, sound_file):
        try:
            if os.path.exists(self.character_audio):
                pygame.mixer.music.load(self.character_audio)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.1)
            
            if os.path.exists(sound_file):
                pygame.mixer.music.load(sound_file)
                pygame.mixer.music.play()
                logging.info(f"🔊 알림 1회 재생: {sound_file}")
        except Exception as e:
            logging.error(f"알림 재생 실패: {e}")
    
    def stop_all_alerts(self):
        try:
            pygame.mixer.music.stop()
        except:
            pass
    
    def start_lie_alert(self):
        if not self.lie_active:
            self.lie_active = True
            self.lie_thread = threading.Thread(target=self._lie_alert_loop, daemon=True)
            self.lie_thread.start()
            logging.info("🔍 거탐 알림 시작")
    
    def stop_lie_alert(self):
        if self.lie_active:
            self.lie_active = False
            if self.lie_thread:
                self.lie_thread.join()
            logging.info("🔍 거탐 알림 중지")
    
    def _lie_alert_loop(self):
        while self.lie_active:
            self.play_alert("lie.mp3")
            time.sleep(3.0)
    
    def start_red_dot_alert(self):
        if not self.red_dot_active:
            self.red_dot_active = True
            self.red_dot_thread = threading.Thread(target=self._red_dot_alert_loop, daemon=True)
            self.red_dot_thread.start()
            logging.info("🔴 빨간점 알림 시작")
    
    def stop_red_dot_alert(self):
        if self.red_dot_active:
            self.red_dot_active = False
            if self.red_dot_thread:
                self.red_dot_thread.join()
            logging.info("🔴 빨간점 알림 중지")
    
    def _red_dot_alert_loop(self):
        while self.red_dot_active:
            self.play_alert("user.mp3")
            time.sleep(10.0)
    
    def start_class1_alert(self):
        if not self.class1_active:
            self.class1_active = True
            self.play_alert_once("alert.mp3")
            logging.info("🚨 클래스1 몬스터 알림 재생")
    
    def stop_class1_alert(self):
        if self.class1_active:
            self.class1_active = False
            self.stop_all_alerts()
            logging.info("🚨 클래스1 몬스터 알림 중지")