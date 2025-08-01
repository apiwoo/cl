import cv2
import numpy as np
import threading
import time
import logging
from constants import YELLOW_DOT_RANGE

class YellowDotTracker:
    def __init__(self, screen_capture, map_config, scroll_tracker=None):
        self.screen_capture = screen_capture
        self.scroll_tracker = scroll_tracker
        self.running = False
        self.thread = None
        self.current_zone = None
        self.yellow_dot_pos = None
        self.lock = threading.Lock()
        self.update_map_config(map_config)
    
    def update_map_config(self, map_config):
        self.zones = map_config.get("zones", [])
        self.minimap_info = map_config.get("minimap", {})
        self.scale_to_640 = self.minimap_info.get("scale_to_640", 1.0)
        logging.info(f"노란점 추적기 맵 업데이트: {len(self.zones)}개 존")
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._track_loop, daemon=True)
        self.thread.start()
        logging.info("🟡 노란점 추적 시작")
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
    
    def get_current_zone(self):
        with self.lock:
            return self.current_zone
    
    def get_yellow_dot_position(self):
        with self.lock:
            return self.yellow_dot_pos
    
    def _track_loop(self):
        while self.running:
            try:
                minimap = self.screen_capture.get_minimap()
                if minimap is None:
                    time.sleep(0.016)
                    continue
                
                if self.scroll_tracker and self.scroll_tracker.scroll_enabled:
                    self.scroll_tracker.detect_minimap_scroll(minimap)
                
                yellow_pos = self._detect_yellow_dot(minimap)
                if yellow_pos:
                    x_640 = int(yellow_pos[0] * self.scale_to_640)
                    y_640 = int(yellow_pos[1] * self.scale_to_640)
                    
                    zone = self._get_zone_at_position(x_640, y_640)
                    
                    with self.lock:
                        self.yellow_dot_pos = (x_640, y_640)
                        if self.current_zone != zone:
                            logging.debug(f"Zone 변경: {self.current_zone} → {zone}")
                        self.current_zone = zone
                
            except Exception as e:
                logging.error(f"노란점 추적 오류: {e}")
            
            time.sleep(0.016)
    
    def _detect_yellow_dot(self, minimap):
        hsv = cv2.cvtColor(minimap, cv2.COLOR_BGR2HSV)
        
        lower_yellow = np.array(YELLOW_DOT_RANGE["lower"])
        upper_yellow = np.array(YELLOW_DOT_RANGE["upper"])
        
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest = max(contours, key=cv2.contourArea)
            M = cv2.moments(largest)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)
        
        return None
    
    def _get_zone_at_position(self, x, y):
        scroll_offset = {"x": 0, "y": 0}
        if self.scroll_tracker:
            scroll_offset = self.scroll_tracker.get_current_scroll_offset()
        
        for zone in self.zones:
            bbox = zone.get("bbox_640", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                
                scroll_x_640 = scroll_offset.get("x", 0) * self.scale_to_640
                scroll_y_640 = scroll_offset.get("y", 0) * self.scale_to_640
                
                ox1 = int(x1 + scroll_x_640)
                oy1 = int(y1 + scroll_y_640)
                ox2 = int(x2 + scroll_x_640)
                oy2 = int(y2 + scroll_y_640)
                
                if ox1 <= x <= ox2 and oy1 <= y <= oy2:
                    return zone["id"]
        return None