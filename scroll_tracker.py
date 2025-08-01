import cv2
import numpy as np
import time
import logging
import os

class ScrollTracker:
    def __init__(self):
        self.scroll_offset = {"x": 0, "y": 0}
        self.previous_landmarks_list = []
        self.initial_landmarks_list = []
        self.last_position_reset_time = 0
        self.landmark_templates = []
        self.scroll_enabled = False
        self.tracking_files = []
        self.scale_to_640 = 1.0
        self.active_template_index = 0
        
    def update_map_config(self, map_config):
        self.scroll_enabled = map_config.get("scroll_enabled", False)
        
        if "scroll_tracking_files" in map_config:
            self.tracking_files = map_config.get("scroll_tracking_files", [])
        elif "scroll_tracking_file" in map_config:
            tracking_file = map_config.get("scroll_tracking_file", "")
            self.tracking_files = [tracking_file] if tracking_file else []
        else:
            self.tracking_files = []
        
        minimap_info = map_config.get("minimap", {})
        self.scale_to_640 = minimap_info.get("scale_to_640", 1.0)
        
        if self.scroll_enabled and self.tracking_files:
            self.load_landmark_templates()
            self.reset_scroll_tracking()
            logging.info(f"📜 스크롤 추적 활성화: {len(self.landmark_templates)}개 템플릿")
        else:
            logging.info("📜 스크롤 추적 비활성화")
    
    def load_landmark_templates(self):
        self.landmark_templates = []
        
        for i, filename in enumerate(self.tracking_files):
            if os.path.exists(filename):
                template = cv2.imread(filename, cv2.IMREAD_COLOR)
                if template is not None:
                    self.landmark_templates.append(template)
                    h, w = template.shape[:2]
                    logging.info(f"🏔️ 랜드마크 템플릿 {i+1} 로드: {filename} {w}x{h}")
                else:
                    logging.warning(f"⚠️ 랜드마크 템플릿 {i+1} 로드 실패: {filename}")
            else:
                logging.warning(f"⚠️ 랜드마크 템플릿 {i+1} 없음: {filename}")
        
        self.previous_landmarks_list = [[] for _ in self.landmark_templates]
        self.initial_landmarks_list = [[] for _ in self.landmark_templates]
    
    def reset_scroll_tracking(self):
        self.scroll_offset = {"x": 0, "y": 0}
        self.previous_landmarks_list = [[] for _ in self.landmark_templates]
        self.initial_landmarks_list = [[] for _ in self.landmark_templates]
        self.last_position_reset_time = time.time()
        self.active_template_index = 0
        logging.info("📜 스크롤 오프셋 초기화")
    
    def detect_minimap_scroll(self, minimap_frame):
        if not self.scroll_enabled or not self.landmark_templates:
            return {"x": 0, "y": 0}
        
        try:
            current_time = time.time()
            
            current_landmarks_list = []
            valid_template_indices = []
            
            for i, template in enumerate(self.landmark_templates):
                landmarks = self.find_landmarks_in_minimap(minimap_frame, template)
                current_landmarks_list.append(landmarks)
                if landmarks:
                    valid_template_indices.append(i)
            
            if not valid_template_indices:
                return {"x": 0, "y": 0}
            
            self.active_template_index = valid_template_indices[0]
            
            for idx in valid_template_indices:
                current_landmarks = current_landmarks_list[idx]
                
                if len(self.initial_landmarks_list[idx]) == 0 and len(current_landmarks) > 0:
                    self.initial_landmarks_list[idx] = [f.copy() for f in current_landmarks]
                    self.last_position_reset_time = current_time
            
            if current_time - self.last_position_reset_time >= 1.0:
                for idx in valid_template_indices:
                    if len(self.initial_landmarks_list[idx]) > 0 and len(current_landmarks_list[idx]) > 0:
                        offset = self.calculate_offset_from_initial(
                            self.initial_landmarks_list[idx],
                            current_landmarks_list[idx]
                        )
                        if offset:
                            self.scroll_offset["x"] = offset["x"]
                            self.scroll_offset["y"] = offset["y"]
                            break
                
                self.last_position_reset_time = current_time
            
            for idx in valid_template_indices:
                if len(self.previous_landmarks_list[idx]) == 0:
                    self.previous_landmarks_list[idx] = current_landmarks_list[idx]
            
            scroll_delta = None
            for idx in valid_template_indices:
                if len(self.previous_landmarks_list[idx]) > 0 and len(current_landmarks_list[idx]) > 0:
                    delta = self.calculate_frame_scroll(
                        self.previous_landmarks_list[idx],
                        current_landmarks_list[idx]
                    )
                    if delta:
                        scroll_delta = delta
                        self.active_template_index = idx
                        break
            
            if scroll_delta:
                self.scroll_offset["x"] = float(self.scroll_offset.get("x", 0)) + scroll_delta["x"]
                self.scroll_offset["y"] = float(self.scroll_offset.get("y", 0)) + scroll_delta["y"]
                
                for idx in valid_template_indices:
                    self.previous_landmarks_list[idx] = current_landmarks_list[idx]
                
                return scroll_delta
            else:
                return {"x": 0, "y": 0}
            
        except Exception as e:
            logging.error(f"스크롤 감지 오류: {e}")
            return {"x": 0, "y": 0}
    
    def calculate_offset_from_initial(self, initial_landmarks, current_landmarks):
        matches = []
        match_distance = 150 / self.scale_to_640
        
        for init in initial_landmarks:
            ix, iy = init["center"]
            for curr in current_landmarks:
                cx, cy = curr["center"]
                dist = np.sqrt((cx - ix)**2 + (cy - iy)**2)
                if dist < match_distance:
                    matches.append({
                        "offset_x": float(cx - ix),
                        "offset_y": float(cy - iy),
                        "distance": float(dist),
                        "init_conf": float(init["confidence"]),
                        "curr_conf": float(curr["confidence"])
                    })
        
        if not matches:
            return None
        
        matches.sort(key=lambda m: (m["distance"], -m["init_conf"], -m["curr_conf"]))
        
        if len(matches) >= 2:
            offset_x_values = [m["offset_x"] for m in matches[:3]]
            offset_y_values = [m["offset_y"] for m in matches[:3]]
            offset_x = float(np.median(offset_x_values))
            offset_y = float(np.median(offset_y_values))
        else:
            offset_x = float(matches[0]["offset_x"])
            offset_y = float(matches[0]["offset_y"])
        
        return {"x": offset_x, "y": offset_y}
    
    def calculate_frame_scroll(self, previous_landmarks, current_landmarks):
        matches = []
        match_distance = 100 / self.scale_to_640
        
        for prev in previous_landmarks:
            px, py = prev["center"]
            for curr in current_landmarks:
                cx, cy = curr["center"]
                dist = np.sqrt((cx - px)**2 + (cy - py)**2)
                if dist < match_distance:
                    matches.append({
                        "scroll_x": float(cx - px),
                        "scroll_y": float(cy - py),
                        "distance": float(dist),
                        "prev_conf": float(prev["confidence"]),
                        "curr_conf": float(curr["confidence"])
                    })
        
        if not matches:
            return None
        
        matches.sort(key=lambda m: (m["distance"], -m["prev_conf"], -m["curr_conf"]))
        
        if len(matches) >= 2:
            scroll_x_values = [m["scroll_x"] for m in matches[:3]]
            scroll_y_values = [m["scroll_y"] for m in matches[:3]]
            scroll_x = float(np.median(scroll_x_values))
            scroll_y = float(np.median(scroll_y_values))
        else:
            scroll_x = float(matches[0]["scroll_x"])
            scroll_y = float(matches[0]["scroll_y"])
        
        max_scroll = 50 / self.scale_to_640
        if abs(scroll_x) > max_scroll or abs(scroll_y) > max_scroll:
            return None
        
        return {"x": scroll_x, "y": scroll_y}
    
    def find_landmarks_in_minimap(self, frame, template):
        if template is None:
            return []
        
        try:
            if frame is None or frame.size == 0:
                return []
            
            if not isinstance(frame, np.ndarray):
                frame = np.asarray(frame, dtype=np.uint8)
            
            landmarks = []
            template_h, template_w = template.shape[:2]
            
            if frame.shape[0] < template_h or frame.shape[1] < template_w:
                return []
            
            result = cv2.matchTemplate(frame, template, cv2.TM_CCOEFF_NORMED)
            threshold = 0.6
            locations = np.where(result >= threshold)
            
            y_coords, x_coords = locations
            for i in range(len(x_coords)):
                x, y = int(x_coords[i]), int(y_coords[i])
                
                if 0 <= y < result.shape[0] and 0 <= x < result.shape[1]:
                    center_x = int(np.clip(x + template_w // 2, 0, frame.shape[1] - 1))
                    center_y = int(np.clip(y + template_h // 2, 0, frame.shape[0] - 1))
                    confidence = float(result[y, x])
                    
                    is_duplicate = False
                    duplicate_distance = 30 / self.scale_to_640
                    for existing in landmarks:
                        ex_cx, ex_cy = existing["center"]
                        if abs(ex_cx - center_x) < duplicate_distance and abs(ex_cy - center_y) < duplicate_distance:
                            if confidence > existing["confidence"]:
                                existing["center"] = [center_x, center_y]
                                existing["confidence"] = confidence
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        landmarks.append({
                            "center": [center_x, center_y],
                            "confidence": confidence,
                            "bbox": [x, y, x + template_w, y + template_h]
                        })
            
            landmarks.sort(key=lambda p: p["confidence"], reverse=True)
            
            return landmarks[:5]
            
        except Exception as e:
            logging.error(f"랜드마크 검색 오류: {e}")
            return []
    
    def get_current_scroll_offset(self):
        return self.scroll_offset.copy()
    
    def get_active_landmarks_count(self):
        if self.active_template_index < len(self.initial_landmarks_list):
            return len(self.initial_landmarks_list[self.active_template_index])
        return 0