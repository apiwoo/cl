import time
import json
import logging

class BuffSystem:
    def __init__(self, buff_config_path, key_controller):
        self.key_controller = key_controller
        self.buffs = []
        self.last_cast_times = {}
        self.load_buff_config(buff_config_path)
    
    def load_buff_config(self, config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.buffs = config.get("buffs", [])
                
                for buff in self.buffs:
                    if buff.get("enabled", True):
                        self.last_cast_times[buff["name"]] = 0
                
                logging.info(f"✅ 버프 설정 로드: {len(self.buffs)}개")
        except Exception as e:
            logging.error(f"버프 설정 로드 실패: {e}")
    
    def use_initial_buffs(self):
        logging.info("💊 초기 버프 사용 시작")
        
        current_time = time.time()
        
        for buff in self.buffs:
            if not buff.get("enabled", True):
                continue
            
            name = buff["name"]
            key = buff["key"]
            after_delay = buff.get("after_delay", 0.1)
            
            logging.info(f"  - {name} ({key})")
            self.key_controller.press_key(key)
            self.last_cast_times[name] = current_time
            time.sleep(after_delay)
        
        logging.info("✅ 초기 버프 완료")
    
    def check_and_use_buffs(self):
        current_time = time.time()
        buffs_to_use = []
        
        for buff in self.buffs:
            if not buff.get("enabled", True):
                continue
            
            name = buff["name"]
            interval = buff.get("interval_minutes", 1) * 60
            
            if current_time - self.last_cast_times.get(name, 0) >= interval:
                buffs_to_use.append(buff)
        
        if not buffs_to_use:
            return False
        
        logging.info(f"💊 {len(buffs_to_use)}개 버프 사용 필요")
        
        for buff in buffs_to_use:
            name = buff["name"]
            key = buff["key"]
            after_delay = buff.get("after_delay", 0.1)
            
            logging.info(f"💊 버프 사용: {name} ({key})")
            self.key_controller.press_key(key)
            self.last_cast_times[name] = current_time
            time.sleep(after_delay)
        
        return True