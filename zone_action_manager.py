import time
import logging

class ZoneActionManager:
    def __init__(self, map_config, key_controller):
        self.key_controller = key_controller
        self.zone_actions = {}
        self.zone_cooldowns = {}
        self.last_action_times = {}
        self.default_cooldown = 1.0
        
        self.forced_movement_enabled = False
        self.forced_movement_config = {}
        self.is_forced_movement_active = False
        self.forced_movement_last_action_time = 0
        
        self.update_map_config(map_config)
    
    def update_map_config(self, map_config):
        self.zone_actions = {}
        for key, value in map_config.get("zone_actions", {}).items():
            self.zone_actions[int(key)] = value
        
        self.zone_cooldowns = {}
        for key, value in map_config.get("zone_cooldowns", {}).items():
            self.zone_cooldowns[int(key)] = float(value)
        
        self.last_action_times = {}
        
        self.forced_movement_config = map_config.get("forced_movement_config", {})
        self.forced_movement_enabled = self.forced_movement_config.get("enabled", False)
        
        logging.info(f"Zone 액션 업데이트: {len(self.zone_actions)}개 존")
        if self.forced_movement_enabled:
            logging.info(f"⚡ 강제이동 모드 활성화: 트리거존 {self.forced_movement_config.get('trigger_zones', [])} → 목표존 {self.forced_movement_config.get('target_zone', 1)}")
    
    def start_forced_movement(self):
        if not self.is_forced_movement_active:
            self.is_forced_movement_active = True
            self.key_controller.release_all_keys()
            logging.info("⚡ 강제이동 모드 시작!")
    
    def stop_forced_movement(self):
        if self.is_forced_movement_active:
            self.is_forced_movement_active = False
            self.key_controller.release_all_keys()
            logging.info("⚡ 강제이동 모드 종료!")
    
    def is_trigger_zone(self, zone_id):
        if not self.forced_movement_enabled:
            return False
        trigger_zones = self.forced_movement_config.get("trigger_zones", [])
        return zone_id in trigger_zones
    
    def is_target_zone(self, zone_id):
        if not self.forced_movement_enabled:
            return False
        target_zone = self.forced_movement_config.get("target_zone", 1)
        return zone_id == target_zone
    
    def execute_forced_movement_actions(self):
        if not self.is_forced_movement_active:
            return
        
        current_time = time.time()
        interval = self.forced_movement_config.get("repeat_interval", 1000) / 1000.0
        
        if current_time - self.forced_movement_last_action_time < interval:
            return
        
        actions = self.forced_movement_config.get("repeat_actions", [])
        
        for i, action in enumerate(actions):
            if i > 0:
                time.sleep(0.01)
            
            action_type = action.get('action')
            key = action.get('key')
            
            if key in ['LEFT', 'RIGHT', 'UP', 'DOWN', 'ALT', 'SHIFT']:
                key = key.lower()
            
            if action_type == 'sleep':
                delay = action.get('delay', 1000) / 1000.0
                time.sleep(delay)
            elif action_type == 'up':
                self.key_controller.release_key(key)
            elif action_type == 'down':
                self.key_controller.press_and_hold(key)
            elif action_type == 'tap':
                delay = action.get('delay', 50) / 1000.0
                self.key_controller.press_key(key, delay)
        
        self.forced_movement_last_action_time = current_time
    
    def execute_zone_action(self, zone_id):
        if self.is_forced_movement_active:
            return False
            
        if zone_id not in self.zone_actions:
            return False
        
        current_time = time.time()
        last_time = self.last_action_times.get(zone_id, 0)
        cooldown = self.zone_cooldowns.get(zone_id, self.default_cooldown)
        
        if current_time - last_time < cooldown:
            return False
        
        actions = self.zone_actions[zone_id]
        logging.debug(f"Zone {zone_id} 액션 실행")
        
        for i, action in enumerate(actions):
            if i > 0:
                time.sleep(0.01)
            
            action_type = action.get('action')
            key = action.get('key')
            
            if key in ['LEFT', 'RIGHT', 'UP', 'DOWN', 'ALT', 'SHIFT']:
                key = key.lower()
            
            if action_type == 'sleep':
                delay = action.get('delay', 1000) / 1000.0
                time.sleep(delay)
            elif action_type == 'up':
                self.key_controller.release_key(key)
            elif action_type == 'down':
                self.key_controller.press_and_hold(key)
            elif action_type == 'tap':
                delay = action.get('delay', 50) / 1000.0
                self.key_controller.press_key(key, delay)
        
        self.last_action_times[zone_id] = current_time
        return True