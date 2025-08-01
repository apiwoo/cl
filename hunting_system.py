import time
import logging
import random

class HuntingSystem:
    def __init__(self, key_controller, buff_system, attack_keys, attack_range, hunting_config, bot_core=None):
        self.key_controller = key_controller
        self.buff_system = buff_system
        self.attack_keys = attack_keys
        self.attack_range = attack_range
        self.hunting_config = hunting_config
        self.bot_core = bot_core
        self.is_hunting = False
        self.original_direction = None
        self.get_detection_func = None
        
        self.hunting_direction = hunting_config.get('hunting_direction', 'movement_only')
        self.look_at_monster = hunting_config.get('look_at_monster', True)
        self.attack_hold_mode = hunting_config.get('attack_hold_mode', True)
        self.use_teleport = hunting_config.get('use_teleport', False)
        
        self.monster_present_frames = 0
        self.monster_absent_frames = 0
    
    def set_detection_function(self, func):
        self.get_detection_func = func
    
    def _is_ignoring_class1(self):
        if not self.bot_core or not hasattr(self.bot_core, 'class1_handler'):
            return False
        
        current_time = time.time()
        ignore_time = self.bot_core.class1_handler.class1_ignore_time
        duration = self.bot_core.class1_handler.CLASS1_IGNORE_DURATION
        
        return current_time - ignore_time < duration
    
    def check_hunting_condition(self, detection):
        if not detection:
            return False
            
        character_class = detection.get('character_class')
        
        if character_class == 1:
            self.monster_present_frames = 0
            return False
        
        if not self._is_ignoring_class1():
            if detection.get('has_class_1_monster'):
                self.monster_present_frames = 0
                return False
        else:
            if detection.get('monsters_in_range'):
                monsters_info = detection.get('monsters_info', [])
                normal_monsters = [m for m in monsters_info if m.get('class_id', 0) != 1]
                if not normal_monsters:
                    self.monster_present_frames = 0
                    return False
            
        if detection.get('monsters_in_range'):
            self.monster_present_frames += 1
            self.monster_absent_frames = 0
            
            if self.monster_present_frames >= 2 and not self.is_hunting:
                return True
            else:
                return False
        else:
            self.monster_absent_frames += 1
            self.monster_present_frames = 0
            return False
    
    def start_hunt(self, detection):
        if self.is_hunting or not detection:
            return
        
        character_class = detection.get('character_class')
        if character_class == 1:
            return
        
        monsters_info = detection.get('monsters_info', [])
        
        if not monsters_info:
            self.is_hunting = False
            return
        
        if self._is_ignoring_class1():
            normal_monsters = [m for m in monsters_info if m.get('class_id', 0) != 1]
            if not normal_monsters:
                logging.info("⚠️ 일반 몬스터 없음 (클래스1만 존재) - 사냥 시작 중단")
                return
            logging.info(f"⚔️ 사냥 시작 (일반 몬스터 {len(normal_monsters)}마리, 클래스1 무시 중)")
        else:
            if detection.get('has_class_1_monster'):
                logging.info("⚠️ 클래스1 몬스터 감지 - 일반 사냥 중단")
                return
            
            class_1_count = sum(1 for m in monsters_info if m.get('class_id') == 1)
            if class_1_count > 0:
                logging.info("⚠️ 클래스1 몬스터 포함 - 일반 사냥 중단")
                return
            
            logging.info(f"⚔️ 사냥 시작 (몬스터 {len(monsters_info)}마리)")
        
        self.is_hunting = True
        
        current_keys = self.key_controller.get_pressed_keys()
        if 'left' in current_keys:
            self.original_direction = 'left'
        elif 'right' in current_keys:
            self.original_direction = 'right'
        else:
            self.original_direction = None
        
        last_hunting_direction = None
        
        try:
            if self.attack_hold_mode:
                last_hunting_direction = self._hunt_with_hold_mode(monsters_info)
            else:
                last_hunting_direction = self._hunt_with_tap_mode(monsters_info)
        finally:
            if not (self.bot_core and self.bot_core.is_paused):
                if self.original_direction and self.original_direction != last_hunting_direction:
                    if last_hunting_direction and last_hunting_direction in self.key_controller.get_pressed_keys():
                        self.key_controller.release_key(last_hunting_direction)
                    
                    if self.original_direction not in self.key_controller.get_pressed_keys():
                        self.key_controller.press_and_hold(self.original_direction)
            
            self.buff_system.check_and_use_buffs()
            self.is_hunting = False
            self.monster_present_frames = 0
            self.monster_absent_frames = 0
            logging.info("✅ 사냥 완료")
    
    def _try_teleport(self, probability):
        if not self.use_teleport:
            return
        
        if self.bot_core and self.bot_core.is_in_no_teleport_zone():
            return
            
        if random.random() < probability:
            if not self.key_controller.is_shift_ready():
                return
                
            attack_info = list(self.attack_keys.values())[0]
            attack_key = attack_info['key']
            
            if self.attack_hold_mode and attack_key in self.key_controller.get_pressed_keys():
                self.key_controller.release_key(attack_key)
                time.sleep(0.05)
                logging.debug(f"🔓 텔레포트 전 공격키({attack_key}) 해제")
            
            self.key_controller.press_key('shift', 0.05)
            logging.debug(f"🌀 텔레포트 시전 (확률 {int(probability*100)}%)")
            
            if self.attack_hold_mode and self.is_hunting:
                time.sleep(0.3)
                if attack_key not in self.key_controller.get_pressed_keys():
                    self.key_controller.press_and_hold(attack_key)
                    logging.debug(f"🔄 텔레포트 후 공격키({attack_key}) 재시작")
    
    def _hunt_with_hold_mode(self, initial_monsters):
        attack_info = list(self.attack_keys.values())[0]
        attack_key = attack_info['key']
        
        current_direction = None
        pressed_keys = self.key_controller.get_pressed_keys()
        
        if 'left' in pressed_keys:
            current_direction = 'left'
        elif 'right' in pressed_keys:
            current_direction = 'right'
        
        monster_absent_count = 0
        first_attack_done = False
        loop_count = 0
        
        if attack_key not in pressed_keys:
            try:
                self.key_controller.press_and_hold(attack_key)
            except Exception as e:
                logging.error(f"press_and_hold 오류: {e}")
                return current_direction
        
        while self.is_hunting:
            loop_count += 1
            
            if self.bot_core and self.bot_core.is_paused:
                logging.info("⏸️ 일시정지 - 사냥 중단")
                break
            
            if self.get_detection_func:
                try:
                    _, detection = self.get_detection_func()
                except Exception as e:
                    logging.error(f"get_detection_func 호출 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    break
                
                if detection is None:
                    time.sleep(0.016)
                    continue
                
                character_class = detection.get('character_class')
                if character_class == 1:
                    logging.info("⚠️ 캐릭터 클래스 1 감지 - 사냥 중지")
                    break
                
                if not self._is_ignoring_class1():
                    if detection.get('has_class_1_monster'):
                        logging.info("⚠️ 클래스1 몬스터 감지 - 사냥 중지")
                        break
                
                if detection.get('monsters_in_range'):
                    monsters_info = detection.get('monsters_info', [])
                    
                    if self._is_ignoring_class1():
                        normal_monsters = [m for m in monsters_info if m.get('class_id', 0) != 1]
                        if not normal_monsters:
                            break
                        monster_absent_count = 0
                    else:
                        class_1_monsters = [m for m in monsters_info if m.get('class_id') == 1]
                        if class_1_monsters:
                            logging.info("⚠️ 클래스1 몬스터 감지 - 사냥 중지")
                            break
                        monster_absent_count = 0
                    
                    if first_attack_done and len(monsters_info) <= 1:
                        self._try_teleport(0.7)
                    
                    if self.look_at_monster and monsters_info:
                        target_direction = self._get_best_direction(monsters_info, current_direction)
                        
                        if target_direction and current_direction != target_direction:
                            pressed_keys = self.key_controller.get_pressed_keys()
                            
                            if current_direction and current_direction in pressed_keys:
                                self.key_controller.release_key(current_direction)
                            
                            if target_direction not in pressed_keys:
                                self.key_controller.press_and_hold(target_direction)
                                current_direction = target_direction
                                logging.debug(f"🎯 방향 전환: {current_direction}")
                    
                    first_attack_done = True
                else:
                    monster_absent_count += 1
                    
                    if monster_absent_count >= 3:
                        self._try_teleport(0.7)
                        break
            else:
                time.sleep(0.5)
                break
            
            time.sleep(0.016)
        
        if attack_key in self.key_controller.get_pressed_keys():
            self.key_controller.release_key(attack_key)
        
        return current_direction
    
    def _hunt_with_tap_mode(self, initial_monsters):
        attack_info = list(self.attack_keys.values())[0]
        attack_key = attack_info['key']
        
        current_direction = None
        pressed_keys = self.key_controller.get_pressed_keys()
        
        if 'left' in pressed_keys:
            current_direction = 'left'
        elif 'right' in pressed_keys:
            current_direction = 'right'
        
        monster_absent_count = 0
        first_attack_done = False
        loop_count = 0
        
        while self.is_hunting:
            loop_count += 1
            
            if self.bot_core and self.bot_core.is_paused:
                logging.info("⏸️ 일시정지 - 사냥 중단")
                break
                
            if self.get_detection_func:
                _, detection = self.get_detection_func()
                
                if detection is None:
                    time.sleep(0.016)
                    continue
                
                character_class = detection.get('character_class')
                if character_class == 1:
                    logging.info("⚠️ 캐릭터 클래스 1 감지 - 사냥 중지")
                    break
                
                if not self._is_ignoring_class1():
                    if detection.get('has_class_1_monster'):
                        logging.info("⚠️ 클래스1 몬스터 감지 - 사냥 중지")
                        break
                
                if detection.get('monsters_in_range'):
                    monsters_info = detection.get('monsters_info', [])
                    
                    if self._is_ignoring_class1():
                        normal_monsters = [m for m in monsters_info if m.get('class_id', 0) != 1]
                        if not normal_monsters:
                            break
                        monster_absent_count = 0
                    else:
                        class_1_monsters = [m for m in monsters_info if m.get('class_id') == 1]
                        if class_1_monsters:
                            logging.info("⚠️ 클래스1 몬스터 감지 - 사냥 중지")
                            break
                        monster_absent_count = 0
                    
                    if self.look_at_monster and monsters_info:
                        target_direction = self._get_best_direction(monsters_info, current_direction)
                        
                        if target_direction and current_direction != target_direction:
                            pressed_keys = self.key_controller.get_pressed_keys()
                            
                            if current_direction and current_direction in pressed_keys:
                                self.key_controller.release_key(current_direction)
                            
                            if target_direction not in pressed_keys:
                                self.key_controller.press_and_hold(target_direction)
                                current_direction = target_direction
                                logging.debug(f"🎯 방향 전환: {current_direction}")
                    
                    base_delay = attack_info.get('delay', 1000) / 1000.0
                    attack_delay = base_delay + random.uniform(-0.1, 0.1)
                    
                    self.key_controller.press_key(attack_key)
                    
                    if first_attack_done and len(monsters_info) <= 1:
                        self._try_teleport(0.7)
                    
                    first_attack_done = True
                    
                    time.sleep(attack_delay)
                else:
                    monster_absent_count += 1
                    
                    if monster_absent_count >= 3:
                        self._try_teleport(0.7)
                        break
            else:
                logging.warning("⚠️ 탐지 함수 없음 - 한 번만 공격")
                self.key_controller.press_key(attack_key)
                break
        
        return current_direction
    
    def _get_best_direction(self, monsters_info, current_direction=None):
        if not monsters_info:
            return None
        
        if self._is_ignoring_class1():
            target_monsters = monsters_info
        else:
            target_monsters = [m for m in monsters_info if m.get('class_id', 0) != 1]
        
        if not target_monsters:
            return None
        
        left_count = sum(1 for m in target_monsters if m['direction'] == 'left')
        right_count = sum(1 for m in target_monsters if m['direction'] == 'right')
        
        if current_direction == 'left' and left_count > 0:
            return 'left'
        elif current_direction == 'right' and right_count > 0:
            return 'right'
        
        if left_count > right_count:
            return 'left'
        elif right_count > left_count:
            return 'right'
        else:
            closest_monster = min(target_monsters, key=lambda m: m.get('distance', float('inf')))
            return closest_monster.get('direction', None)