import cv2
import numpy as np
import json
import os
import time
import mss
import pygetwindow as gw
from scroll_tracker import ScrollTracker
from constants import YELLOW_DOT_RANGE

class ScrollDebugger:
    def __init__(self):
        self.game_window = None
        self.map_config = None
        self.scroll_tracker = ScrollTracker()
        self.minimap_info = {}
        self.zones = []
        self.running = True
        self.last_console_time = 0
        self.console_interval = 0.5
        
    def find_game_window(self):
        wins = gw.getWindowsWithTitle("Mapleland")
        if not wins:
            print("❌ Mapleland 창을 찾을 수 없습니다.")
            return False
        
        self.game_window = wins[0]
        print(f"✅ 게임 창 찾음: {self.game_window.width}x{self.game_window.height}")
        
        if self.game_window.width != 1920 or self.game_window.height != 1080:
            print("⚠️ 게임 창 크기가 1920x1080이 아닙니다. 조정 중...")
            self.game_window.resizeTo(1920, 1080)
            time.sleep(0.5)
        
        return True
    
    def load_maps_list(self):
        maps_file = "configs/maps.json"
        if not os.path.exists(maps_file):
            print("❌ maps.json 파일이 없습니다.")
            return []
        
        with open(maps_file, "r", encoding="utf-8") as f:
            maps_data = json.load(f)
        
        return maps_data.get("maps", [])
    
    def select_map(self):
        maps = self.load_maps_list()
        if not maps:
            print("❌ 사용 가능한 맵이 없습니다.")
            return None
        
        print("\n🗺️ 맵 선택")
        print("-" * 30)
        for i, map_info in enumerate(maps, 1):
            print(f"{i}) {map_info.get('id')} - {map_info.get('name', 'Unknown')}")
        
        while True:
            try:
                choice = input(f"선택 (1-{len(maps)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(maps):
                    return maps[idx]
                print("❌ 잘못된 선택입니다.")
            except ValueError:
                print("❌ 숫자를 입력하세요.")
    
    def load_map_config(self, map_info):
        config_file = os.path.join("configs", map_info["config_file"])
        if not os.path.exists(config_file):
            print(f"❌ 설정 파일이 없습니다: {config_file}")
            return False
        
        with open(config_file, "r", encoding="utf-8") as f:
            self.map_config = json.load(f)
        
        self.minimap_info = self.map_config.get("minimap", {})
        self.zones = self.map_config.get("zones", [])
        
        self.scroll_tracker.update_map_config(self.map_config)
        
        print(f"\n✅ 맵 설정 로드: {self.map_config.get('display_name', 'Unknown')}")
        print(f"   미니맵 위치: ({self.minimap_info['left']}, {self.minimap_info['top']})")
        print(f"   미니맵 크기: {self.minimap_info['width']}x{self.minimap_info['height']}")
        print(f"   640 스케일: {self.minimap_info.get('scale_to_640', 1.0):.2f}x")
        print(f"   존 개수: {len(self.zones)}개")
        
        scroll_enabled = self.map_config.get("scroll_enabled", False)
        
        if "scroll_tracking_files" in self.map_config:
            scroll_files = self.map_config.get("scroll_tracking_files", [])
        elif "scroll_tracking_file" in self.map_config:
            scroll_file = self.map_config.get("scroll_tracking_file", "")
            scroll_files = [scroll_file] if scroll_file else []
        else:
            scroll_files = []
        
        if scroll_enabled:
            print(f"\n📜 스크롤 추적: 활성화")
            for i, file in enumerate(scroll_files):
                print(f"   추적 파일 {i+1}: {file}")
                if not os.path.exists(file):
                    print(f"   ⚠️ 추적 파일 {i+1}이 없습니다!")
        else:
            print(f"\n📜 스크롤 추적: 비활성화")
        
        return True
    
    def capture_minimap(self):
        with mss.mss() as sct:
            monitor = {
                "left": self.game_window.left + self.minimap_info["left"],
                "top": self.game_window.top + self.minimap_info["top"],
                "width": self.minimap_info["width"],
                "height": self.minimap_info["height"]
            }
            shot = sct.grab(monitor)
            frame = np.array(shot)
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    
    def detect_yellow_dot(self, minimap):
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
    
    def get_zone_at_position(self, x, y, scroll_offset):
        scale_to_640 = self.minimap_info.get("scale_to_640", 1.0)
        x_640 = int(x * scale_to_640)
        y_640 = int(y * scale_to_640)
        
        scroll_x_640 = scroll_offset.get("x", 0) * scale_to_640
        scroll_y_640 = scroll_offset.get("y", 0) * scale_to_640
        
        for zone in self.zones:
            bbox = zone.get("bbox_640", [])
            if len(bbox) == 4:
                x1, y1, x2, y2 = bbox
                
                ox1 = int(x1 + scroll_x_640)
                oy1 = int(y1 + scroll_y_640)
                ox2 = int(x2 + scroll_x_640)
                oy2 = int(y2 + scroll_y_640)
                
                if ox1 <= x_640 <= ox2 and oy1 <= y_640 <= oy2:
                    return zone["id"]
        return None
    
    def draw_zones(self, display, scale_factor, scroll_offset):
        scale_to_640 = self.minimap_info.get("scale_to_640", 1.0)
        
        for zone in self.zones:
            bbox_640 = zone.get("bbox_640", [])
            if len(bbox_640) != 4:
                continue
            
            scroll_x_640 = scroll_offset.get("x", 0) * scale_to_640
            scroll_y_640 = scroll_offset.get("y", 0) * scale_to_640
            
            x1 = int((bbox_640[0] + scroll_x_640) / scale_to_640)
            y1 = int((bbox_640[1] + scroll_y_640) / scale_to_640)
            x2 = int((bbox_640[2] + scroll_x_640) / scale_to_640)
            y2 = int((bbox_640[3] + scroll_y_640) / scale_to_640)
            
            x1_scaled = x1 * scale_factor
            y1_scaled = y1 * scale_factor
            x2_scaled = x2 * scale_factor
            y2_scaled = y2 * scale_factor
            
            color = (0, 255, 0)
            cv2.rectangle(display, (x1_scaled, y1_scaled), (x2_scaled, y2_scaled), color, 2)
            
            zone_id = zone.get("id", "?")
            text_x = x1_scaled + 5
            text_y = y1_scaled + 20
            
            cv2.rectangle(display, (text_x - 2, text_y - 15), 
                         (text_x + 25, text_y + 5), (0, 0, 0), -1)
            cv2.putText(display, f"Z{zone_id}", (text_x, text_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    def run(self):
        if not self.find_game_window():
            return
        
        map_info = self.select_map()
        if not map_info:
            return
        
        if not self.load_map_config(map_info):
            return
        
        cv2.namedWindow("Scroll Debug", cv2.WINDOW_NORMAL)
        
        print("\n🔍 스크롤 추적 디버깅 시작!")
        print("R 키: 스크롤 초기화")
        print("ESC 키: 종료")
        print("-" * 50)
        
        scale_factor = 4
        frame_count = 0
        scale_to_640 = self.minimap_info.get("scale_to_640", 1.0)
        
        while self.running:
            try:
                current_time = time.time()
                minimap = self.capture_minimap()
                
                if self.scroll_tracker.scroll_enabled:
                    self.scroll_tracker.detect_minimap_scroll(minimap)
                
                scroll_offset = self.scroll_tracker.get_current_scroll_offset()
                
                display = cv2.resize(minimap, (minimap.shape[1] * scale_factor, 
                                              minimap.shape[0] * scale_factor), 
                                    interpolation=cv2.INTER_NEAREST)
                
                scale_to_640 = self.minimap_info.get("scale_to_640", 1.0)
                self.draw_zones(display, scale_factor, scroll_offset)
                
                dot_pos = self.detect_yellow_dot(minimap)
                current_zone = None
                
                if dot_pos:
                    x, y = dot_pos
                    x_scaled = int(x * scale_factor)
                    y_scaled = int(y * scale_factor)
                    
                    cv2.circle(display, (x_scaled, y_scaled), 8, (0, 255, 255), -1)
                    cv2.circle(display, (x_scaled, y_scaled), 10, (0, 0, 0), 2)
                    
                    current_zone = self.get_zone_at_position(x, y, scroll_offset)
                    
                    info_text = f"Yellow: ({x}, {y}) | Zone: {current_zone if current_zone else 'None'}"
                    cv2.rectangle(display, (10, 10), (400, 40), (0, 0, 0), -1)
                    cv2.putText(display, info_text, (15, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                else:
                    cv2.putText(display, "Yellow Dot: Not Found", (15, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                scroll_text = f"Scroll: ({scroll_offset.get('x', 0):.1f}, {scroll_offset.get('y', 0):.1f})"
                cv2.putText(display, scroll_text, (15, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                scroll_640_text = f"Scroll(640): ({scroll_offset.get('x', 0) * scale_to_640:.1f}, {scroll_offset.get('y', 0) * scale_to_640:.1f})"
                cv2.putText(display, scroll_640_text, (15, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 1)
                
                if self.scroll_tracker.scroll_enabled:
                    active_template = self.scroll_tracker.active_template_index + 1
                    total_templates = len(self.scroll_tracker.landmark_templates)
                    active_landmarks = self.scroll_tracker.get_active_landmarks_count()
                    
                    status_text = f"Tracking: ON | Template: {active_template}/{total_templates} | Landmarks: {active_landmarks}"
                    cv2.putText(display, status_text, (15, 120),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 1)
                    
                    landmarks_info = []
                    for i, landmarks in enumerate(self.scroll_tracker.initial_landmarks_list):
                        count = len(landmarks)
                        landmarks_info.append(f"T{i+1}:{count}")
                    
                    templates_text = f"Templates: {' '.join(landmarks_info)}"
                    cv2.putText(display, templates_text, (15, 145),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 100), 1)
                else:
                    status_text = "Tracking: OFF"
                    cv2.putText(display, status_text, (15, 120),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 255, 100), 1)
                
                frame_count += 1
                fps_text = f"Frame: {frame_count}"
                cv2.putText(display, fps_text, (15, 170),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                
                if current_time - self.last_console_time >= self.console_interval:
                    timestamp = time.strftime("%H:%M:%S")
                    scroll_x_640 = scroll_offset.get("x", 0) * scale_to_640
                    scroll_y_640 = scroll_offset.get("y", 0) * scale_to_640
                    
                    template_info = ""
                    if self.scroll_tracker.scroll_enabled:
                        active = self.scroll_tracker.active_template_index + 1
                        template_info = f" | 템플릿: {active}/{len(self.scroll_tracker.landmark_templates)}"
                    
                    if dot_pos:
                        print(f"[{timestamp}] 노란점: ({dot_pos[0]}, {dot_pos[1]}) | "
                              f"존: {current_zone} | "
                              f"스크롤(원본): ({scroll_offset.get('x', 0):.1f}, {scroll_offset.get('y', 0):.1f}) | "
                              f"스크롤(640): ({scroll_x_640:.1f}, {scroll_y_640:.1f}){template_info}")
                    else:
                        print(f"[{timestamp}] 노란점: 없음 | "
                              f"스크롤(원본): ({scroll_offset.get('x', 0):.1f}, {scroll_offset.get('y', 0):.1f}) | "
                              f"스크롤(640): ({scroll_x_640:.1f}, {scroll_y_640:.1f}){template_info}")
                    
                    self.last_console_time = current_time
                
                cv2.imshow("Scroll Debug", display)
                
                key = cv2.waitKey(1) & 0xFF
                if key == 27:
                    print("\n종료합니다...")
                    break
                elif key == ord('r') or key == ord('R'):
                    self.scroll_tracker.reset_scroll_tracking()
                    print("\n📜 스크롤 추적 초기화!")
                
            except Exception as e:
                print(f"❌ 오류: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.1)
        
        cv2.destroyAllWindows()

if __name__ == "__main__":
    debugger = ScrollDebugger()
    debugger.run()