import torch
import numpy as np
import logging
from ultralytics import YOLO
import os
import time

class DetectorEngine:
    def __init__(self, attack_range, hunting_config=None):
        self.character_model = None
        self.monster_model = None
        self.lie_model = None
        self.last_character_pos = None
        self.last_character_class = None
        self.last_character_time = 0
        self.attack_range = attack_range
        self.current_monster_model_path = None
        self.hunting_config = hunting_config or {}
        self.hunting_direction = self.hunting_config.get('hunting_direction', 'movement_only')
        self.monster_confidence = self.hunting_config.get('monster_confidence', 0.25)
    
    def initialize(self, character_model_path=None, monster_model_path=None):
        if not torch.cuda.is_available():
            logging.error("❌ GPU를 사용할 수 없습니다!")
            return False
        
        try:
            if character_model_path:
                if not os.path.exists(character_model_path) and character_model_path.endswith('.engine'):
                    pt_path = character_model_path.replace('.engine', '.pt')
                    if os.path.exists(pt_path):
                        character_model_path = pt_path
                        logging.info(f"⚠️ .engine 파일이 없어 .pt 파일 사용: {pt_path}")
                
                if os.path.exists(character_model_path):
                    self.character_model = YOLO(character_model_path, task='detect')
                    logging.info(f"✅ 캐릭터 모델 로드: {character_model_path}")
                else:
                    logging.error(f"❌ 캐릭터 모델 파일을 찾을 수 없습니다: {character_model_path}")
                    return False
            
            if monster_model_path:
                if not os.path.exists(monster_model_path) and monster_model_path.endswith('.engine'):
                    pt_path = monster_model_path.replace('.engine', '.pt')
                    if os.path.exists(pt_path):
                        monster_model_path = pt_path
                        logging.info(f"⚠️ .engine 파일이 없어 .pt 파일 사용: {pt_path}")
                
                if os.path.exists(monster_model_path):
                    self.monster_model = YOLO(monster_model_path, task='detect')
                    self.current_monster_model_path = monster_model_path
                    logging.info(f"✅ 몬스터 모델 로드: {monster_model_path}")
                else:
                    logging.error(f"❌ 몬스터 모델 파일을 찾을 수 없습니다: {monster_model_path}")
                    return False
            
            lie_engine = "char_models/lie/model/lie_best.engine"
            if not os.path.exists(lie_engine):
                lie_pt = lie_engine.replace('.engine', '.pt')
                if os.path.exists(lie_pt):
                    lie_engine = lie_pt
                    logging.info(f"⚠️ .engine 파일이 없어 .pt 파일 사용: {lie_pt}")
            
            if os.path.exists(lie_engine):
                self.lie_model = YOLO(lie_engine, task='detect')
                logging.info(f"✅ 거탐 모델 로드: {lie_engine}")
            
            gpu_name = torch.cuda.get_device_name()
            logging.info(f"✅ GPU 초기화 성공: {gpu_name}")
            
            self.warmup()
            return True
            
        except Exception as e:
            logging.error(f"초기화 실패: {e}")
            return False
    
    def update_monster_model(self, monster_model_path):
        if monster_model_path == self.current_monster_model_path:
            return True
        
        try:
            if monster_model_path:
                if not os.path.exists(monster_model_path) and monster_model_path.endswith('.engine'):
                    pt_path = monster_model_path.replace('.engine', '.pt')
                    if os.path.exists(pt_path):
                        monster_model_path = pt_path
                        logging.info(f"⚠️ .engine 파일이 없어 .pt 파일 사용: {pt_path}")
                
                if os.path.exists(monster_model_path):
                    self.monster_model = YOLO(monster_model_path, task='detect')
                    self.current_monster_model_path = monster_model_path
                    logging.info(f"✅ 몬스터 모델 업데이트: {monster_model_path}")
                    
                    dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
                    self.monster_model(dummy_image, device='cuda:0', verbose=False)
                    return True
                else:
                    logging.error(f"❌ 몬스터 모델 파일을 찾을 수 없습니다: {monster_model_path}")
                    return False
        except Exception as e:
            logging.error(f"몬스터 모델 업데이트 실패: {e}")
            return False
    
    def warmup(self):
        dummy_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
        try:
            if self.character_model:
                self.character_model(dummy_image, device='cuda:0', verbose=False)
            if self.monster_model:
                self.monster_model(dummy_image, device='cuda:0', verbose=False)
            if self.lie_model:
                self.lie_model(dummy_image, device='cuda:0', verbose=False)
            logging.info("✅ GPU 워밍업 완료")
        except:
            pass
    
    def detect(self, frame, movement_direction=None):
        if frame is None:
            return None
        
        result = {
            "character_pos": None,
            "character_class": None,
            "monsters_in_range": False,
            "monster_direction": None,
            "monsters_info": [],
            "has_class_1_monster": False,
            "monsters": []
        }
        
        try:
            char_results = self.character_model(frame, device='cuda:0', verbose=False)
            if char_results and char_results[0].boxes is not None and len(char_results[0].boxes) > 0:
                box_data = char_results[0].boxes.data[0]
                box = box_data[:4].cpu().numpy()
                center_x = int((box[0] + box[2]) / 2)
                center_y = int((box[1] + box[3]) / 2)
                result["character_pos"] = (center_x, center_y)
                result["character_class"] = int(box_data[5].cpu().numpy()) if len(box_data) > 5 else 0
                self.last_character_pos = result["character_pos"]
                self.last_character_class = result["character_class"]
                self.last_character_time = time.time()
            elif self.last_character_pos and (time.time() - self.last_character_time < 3.0):
                result["character_pos"] = self.last_character_pos
                result["character_class"] = self.last_character_class
            
            if result["character_pos"]:
                char_x, char_y = result["character_pos"]
                
                attack_width = self.attack_range.get('width', 150)
                attack_height = self.attack_range.get('height', 50)
                
                if self.hunting_direction == 'movement_only' and movement_direction:
                    if movement_direction == 'left':
                        attack_left = char_x - attack_width
                        attack_right = char_x
                    else:
                        attack_left = char_x
                        attack_right = char_x + attack_width
                else:
                    attack_left = char_x - attack_width
                    attack_right = char_x + attack_width
                
                attack_top = char_y - attack_height
                attack_bottom = char_y + attack_height
                
                monster_results = self.monster_model(frame, device='cuda:0', verbose=False)
                total_monsters = 0
                in_range_monsters = 0
                
                if monster_results and monster_results[0].boxes is not None:
                    for box in monster_results[0].boxes.data:
                        box_np = box[:4].cpu().numpy()
                        monster_left = box_np[0]
                        monster_top = box_np[1]
                        monster_right = box_np[2]
                        monster_bottom = box_np[3]
                        confidence = float(box[4].cpu().numpy())
                        monster_class = int(box[5].cpu().numpy()) if len(box) > 5 else 0
                        
                        if confidence < self.monster_confidence:
                            continue
                        
                        total_monsters += 1
                        
                        monster_center_x = int((monster_left + monster_right) / 2)
                        monster_center_y = int((monster_top + monster_bottom) / 2)
                        
                        monster_data = {
                            "bbox": [monster_left, monster_top, monster_right, monster_bottom],
                            "center": [monster_center_x, monster_center_y],
                            "confidence": confidence,
                            "class_id": monster_class
                        }
                        result["monsters"].append(monster_data)
                        
                        if monster_class == 1:
                            result["has_class_1_monster"] = True
                        
                        if not (monster_right < attack_left or 
                                monster_left > attack_right or 
                                monster_bottom < attack_top or 
                                monster_top > attack_bottom):
                            
                            direction = "left" if monster_center_x < char_x else "right"
                            distance = np.sqrt((monster_center_x - char_x)**2 + (monster_center_y - char_y)**2)
                            
                            if distance > 20:
                                in_range_monsters += 1
                                result["monsters_info"].append({
                                    "bbox": [monster_left, monster_top, monster_right, monster_bottom],
                                    "center": (monster_center_x, monster_center_y),
                                    "direction": direction,
                                    "distance": distance,
                                    "confidence": confidence,
                                    "class_id": monster_class
                                })
                                
                                result["monsters_in_range"] = True
                                result["monster_direction"] = direction
            
            result["character"] = {"screen_pos": result["character_pos"]} if result["character_pos"] else None
            
        except Exception as e:
            logging.error(f"탐지 오류: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    def detect_lie(self, frame):
        if not self.lie_model or frame is None:
            return False
        
        try:
            results = self.lie_model(frame, conf=0.8, device='cuda:0', verbose=False)
            return len(results) > 0 and results[0].boxes is not None and len(results[0].boxes) > 0
        except:
            return False