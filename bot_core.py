import time
import logging
import threading
import queue
import pygetwindow as gw
import json
import os
import random

from screen_capture import ScreenCapture
from detector_engine import DetectorEngine
from yellow_dot_tracker import YellowDotTracker
from zone_action_manager import ZoneActionManager
from hunting_system import HuntingSystem
from scroll_tracker import ScrollTracker
from buff_system import BuffSystem
from alert_system import AlertSystem
from key_controller import KeyController
from class1_monster_handler import Class1MonsterHandler

class BotCore:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.paused = False
        self.pause_lock = threading.Lock()
        self.keyboard_listener = None
        
        self.current_map_index = 0
        self.map_configs = []
        self.maps_data = None
        self.current_map_config = None
        self.zone1_last_time = 0
        self.zone1_cooldown = 10.0
        
        self.frame_queue = queue.Queue(maxsize=2)
        self.frame_thread = None
        
        self.previous_character_class = None
        
        self.cached_no_hunt_status = None
        self.last_yellow_pos = None
        
        self.cached_no_teleport_status = None
        self.last_teleport_check_pos = None
        
        self.latest_detection = None
        self.detection_lock = threading.Lock()
        
        self.stop_position = None
        self.stop_time = 0
        self.is_auto_moving = False
        
        self.alert_queue = queue.PriorityQueue()
        
        self.use_teleport = self.config.get('hunting_config', {}).get('use_teleport', False)
        
        self.class1_detected_flag = False
        self.class1_flag_lock = threading.Lock()
        
        self.last_random_key_time = 0
        self.random_key_interval = 0.3
        
        self.initialize_systems()
        
    def initialize_systems(self):
        self.setup_game_window()
        
        self.load_map_configs()
        self.current_map_config = self.map_configs[0]
        
        minimap_info = self.current_map_config.get("minimap", {})
        self.screen_capture = ScreenCapture(minimap_info)
        
        input_method = self.config.get('input_method', 'pyautogui')
        self.key_controller = KeyController(input_method)
        
        attack_range = self.config.get('attack_range', {'width': 200, 'height': 50})
        hunting_config = self.config.get('hunting_config', {})
        self.detector_engine = DetectorEngine(attack_range, hunting_config)
        
        character_model_path = self.config.get('character_info', {}).get('model_path')
        monster_model_path = self.get_current_monster_model_path()
        
        if not self.detector_engine.initialize(character_model_path, monster_model_path):
            logging.error("GPU/TensorRT 초기화 실패. 프로그램을 종료합니다.")
            import sys
            sys.exit(1)
        
        self.scroll_tracker = ScrollTracker()
        self.scroll_tracker.update_map_config(self.current_map_config)
        
        self.yellow_dot_tracker = YellowDotTracker(
            self.screen_capture,
            self.current_map_config,
            self.scroll_tracker
        )
        
        self.zone_action_manager = ZoneActionManager(
            self.current_map_config,
            self.key_controller
        )
        
        self.buff_system = BuffSystem(
            self.config['buff_config_path'],
            self.key_controller
        )
        
        self.hunting_system = HuntingSystem(
            self.key_controller,
            self.buff_system,
            self.config.get('attack_keys', {'attack': {'key': 'a', 'delay': 1000}}),
            self.config.get('attack_range', {'width': 200, 'height': 50}),
            self.config.get('hunting_config', {}),
            self
        )
        self.hunting_system.set_detection_function(self.get_latest_detection)
        
        character_info = self.config.get('character_info', {})
        alert_num = character_info.get('alert_audio', 'char/1.mp3').replace('char/', '').replace('.mp3', '')
        self.alert_system = AlertSystem(
            alert_num,
            self.screen_capture,
            self.detector_engine
        )
        
        self.class1_handler = Class1MonsterHandler(self)
        
        self.setup_keyboard_listener()
        
        logging.info("✅ 모든 시스템 초기화 완료")
    
    @property
    def is_paused(self):
        with self.pause_lock:
            return self.paused
    
    @property 
    def cfg(self):
        return self.config
    
    @property
    def detector(self):
        return self.detector_engine
    
    def get_current_monster_model_path(self):
        current_map_idx = self.map_sequence[self.current_map_index % len(self.map_sequence)]
        map_info = self.maps_data["maps"][current_map_idx - 1]
        monster_model_name = map_info.get("monstermodelname", map_info.get("name", "default"))
        
        engine_path = f"maple_models/{monster_model_name}/model/{monster_model_name}_best.engine"
        pt_path = f"maple_models/{monster_model_name}/model/{monster_model_name}_best.pt"
        
        if os.path.exists(engine_path):
            return engine_path
        elif os.path.exists(pt_path):
            logging.info(f"⚠️ .engine 파일이 없어 .pt 파일 사용: {pt_path}")
            return pt_path
        else:
            return engine_path
    
    def setup_game_window(self):
        logging.info("🎮 게임 창 설정 중...")
        wins = gw.getWindowsWithTitle("Mapleland")
        if not wins:
            logging.error("Mapleland 창을 찾을 수 없습니다.")
            import sys
            sys.exit(1)
        
        game_window = wins[0]
        if game_window.width != 1920 or game_window.height != 1080:
            try:
                game_window.resizeTo(1920, 1080)
                time.sleep(0.5)
                logging.info("게임 창 크기 조정 완료")
            except:
                logging.warning("게임 창 크기 조정 실패")
        
        try:
            game_window.activate()
            time.sleep(0.5)
            
            center_x = game_window.left + game_window.width // 2
            center_y = game_window.top + game_window.height // 2
            self.key_controller.click_mouse(center_x, center_y)
            time.sleep(0.3)
            
            logging.info("게임 창 활성화 완료")
        except:
            logging.warning("게임 창 활성화 실패")
    
    def load_map_configs(self):
        with open(os.path.join("configs", "maps.json"), "r", encoding="utf-8") as f:
            self.maps_data = json.load(f)
        
        self.map_sequence = self.config['map_sequence']
        
        for map_idx in self.map_sequence:
            map_info = self.maps_data["maps"][map_idx - 1]
            config_file = os.path.join("configs", map_info["config_file"])
            with open(config_file, "r", encoding="utf-8") as f:
                self.map_configs.append(json.load(f))
    
    def setup_keyboard_listener(self):
        def on_f8_press(key):
            if key == 'f8':
                self.toggle_pause()
        
        self.key_controller.start_listener(on_f8_press)
    
    def toggle_pause(self):
        with self.pause_lock:
            self.paused = not self.paused
            current_paused_state = self.paused
            
            if self.paused:
                logging.info("⏸️ 일시정지")
                self.key_controller.release_all_keys()
                if hasattr(self, 'class1_handler'):
                    self.class1_handler.check_priority_mode_activation(is_paused=True)
            else:
                logging.info("▶️ 재시작")
                
                try:
                    if hasattr(self, 'class1_handler'):
                        if self.class1_handler.class_1_detected:
                            self.class1_handler._stop_class_1_alert()
                            self.class1_handler.class_1_detected = False
                            self.class1_handler.class_1_alert_played = False
                        
                        self.class1_handler.check_priority_mode_activation(is_paused=False)
                except Exception as e:
                    logging.error(f"class1_handler 처리 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                
                try:
                    yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
                    
                    if yellow_pos:
                        x, _ = yellow_pos
                        
                        current_keys = self.key_controller.get_pressed_keys()
                        
                        if x < 320:
                            self.key_controller.press_and_hold('right')
                            time.sleep(0.05)
                            logging.info("🚶 재시작: 오른쪽으로 이동")
                        else:
                            self.key_controller.press_and_hold('left')
                            time.sleep(0.05)
                            logging.info("🚶 재시작: 왼쪽으로 이동")
                        
                        time.sleep(0.1)
                        self.key_controller.press_key('alt', 0.05)
                        
                        if self.use_teleport:
                            time.sleep(0.2)
                            self.key_controller.press_key('shift', 0.05)
                            logging.info("🌀 재시작: 텔레포트 사용")
                    else:
                        logging.error("yellow_pos가 None! 노란점을 찾을 수 없음")
                except Exception as e:
                    logging.error(f"이동 방향 설정 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
    
    def switch_map(self):
        self.current_map_index = (self.current_map_index + 1) % len(self.map_configs)
        self.current_map_config = self.map_configs[self.current_map_index]
        
        minimap_info = self.current_map_config.get("minimap", {})
        self.screen_capture.update_minimap_info(minimap_info)
        
        self.scroll_tracker.update_map_config(self.current_map_config)
        self.yellow_dot_tracker.update_map_config(self.current_map_config)
        self.zone_action_manager.update_map_config(self.current_map_config)
        
        new_monster_model_path = self.get_current_monster_model_path()
        self.detector_engine.update_monster_model(new_monster_model_path)
        
        self.cached_no_hunt_status = None
        self.last_yellow_pos = None
        
        self.cached_no_teleport_status = None
        self.last_teleport_check_pos = None
        
        self.stop_position = None
        self.stop_time = 0
        self.is_auto_moving = False
        
        self.class1_handler.reset()
        
        logging.info(f"🗺️ 맵 전환: {self.current_map_config.get('display_name', 'Unknown')}")
        
        time.sleep(0.5)
        yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
        if yellow_pos:
            x, _ = yellow_pos
            if x < 320:
                self.key_controller.press_and_hold('right')
                logging.info("🚶 맵 전환 후 초기 이동: 오른쪽으로")
            else:
                self.key_controller.press_and_hold('left')
                logging.info("🚶 맵 전환 후 초기 이동: 왼쪽으로")
            
            time.sleep(0.1)
            self.key_controller.press_key('alt', 0.05)
    
    
    def start_frame_processor(self):
        def frame_processor():
            frame_count = 0
            while self.running:
                try:
                    frame_count += 1
                    
                    if self.is_paused:
                        time.sleep(0.1)
                        continue
                        
                    main_frame = self.screen_capture.get_main_frame()
                    if main_frame is not None:
                        pressed_keys = self.key_controller.get_pressed_keys()
                        movement_direction = None
                        if 'left' in pressed_keys:
                            movement_direction = 'left'
                        elif 'right' in pressed_keys:
                            movement_direction = 'right'
                        
                        detection = self.detector_engine.detect(main_frame, movement_direction)
                        
                        with self.detection_lock:
                            self.latest_detection = detection
                        
                        if detection and detection.get("has_class_1_monster"):
                            with self.class1_flag_lock:
                                if not self.class1_detected_flag:
                                    self.class1_detected_flag = True
                                    logging.info("🚨 클래스1 몬스터 감지 - 플래그 설정")
                            
                            self.alert_queue.put((1, time.time(), {'type': 'class1_monster', 'data': detection}))
                    
                    time.sleep(0.016)
                except Exception as e:
                    logging.error(f"프레임 처리 오류: {e}")
                    import traceback
                    traceback.print_exc()
        
        self.frame_thread = threading.Thread(target=frame_processor, daemon=True)
        self.frame_thread.start()
        logging.info("🖼️ 프레임 처리 스레드 시작")
    
    def start_alert_processor(self):
        def alert_processor_func():
            logging.info("🚨 알림 처리 스레드 실행 시작")
            while self.running:
                try:
                    if self.is_paused:
                        time.sleep(0.1)
                        continue
                        
                    priority, timestamp, task = self.alert_queue.get(timeout=0.1)
                    logging.info(f"🚨 알림 큐에서 작업 가져옴: {task['type']}")
                    
                    if task['type'] == 'class1_monster':
                        queue_size_before = self.alert_queue.qsize()
                        temp_items = []
                        try:
                            while not self.alert_queue.empty():
                                item = self.alert_queue.get_nowait()
                                if item[2]['type'] != 'class1_monster':
                                    temp_items.append(item)
                        except queue.Empty:
                            pass
                        
                        for item in temp_items:
                            self.alert_queue.put(item)
                        
                        detection_results = task['data']
                        logging.info("🚨 클래스1 몬스터 처리 시작")
                        self.class1_handler.handle_class1_detection(
                            detection_results,
                            self.get_latest_minimap,
                            self.get_latest_main
                        )
                        
                        with self.class1_flag_lock:
                            self.class1_detected_flag = False
                            logging.info("🚨 클래스1 처리 완료 - 플래그 해제")
                
                except queue.Empty:
                    pass
                except Exception as e:
                    logging.error(f"알림 처리 오류: {e}")
                    import traceback
                    traceback.print_exc()
        
        alert_thread = threading.Thread(target=alert_processor_func, daemon=True)
        alert_thread.start()
        logging.info("🚨 알림 처리 스레드 시작")
    
    def get_latest_detection(self):
        try:
            acquired = self.detection_lock.acquire(timeout=1.0)
            if not acquired:
                return None, None
            
            result = None, self.latest_detection
            self.detection_lock.release()
            return result
        except Exception as e:
            logging.error(f"get_latest_detection 오류: {e}")
            if self.detection_lock.locked():
                self.detection_lock.release()
            return None, None
    
    def get_cached_detection(self):
        with self.detection_lock:
            return self.latest_detection
    
    def get_latest_minimap(self):
        return self.screen_capture.get_minimap()
    
    def get_latest_main(self):
        return self.screen_capture.get_main_frame()
    
    def is_in_no_hunt_zone(self, no_hunt_zones):
        yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
        if not yellow_pos:
            return False
        
        if self.last_yellow_pos == yellow_pos and self.cached_no_hunt_status is not None:
            return self.cached_no_hunt_status
        
        self.last_yellow_pos = yellow_pos
        
        x, y = yellow_pos
        for i, box in enumerate(no_hunt_zones):
            if len(box) == 4:
                x1, y1, x2, y2 = box
                if x1 <= x <= x2 and y1 <= y <= y2:
                    self.cached_no_hunt_status = True
                    return True
        
        self.cached_no_hunt_status = False
        return False
    
    def is_in_no_teleport_zone(self):
        yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
        if not yellow_pos:
            return False
        
        if self.last_teleport_check_pos == yellow_pos and self.cached_no_teleport_status is not None:
            return self.cached_no_teleport_status
        
        self.last_teleport_check_pos = yellow_pos
        
        no_teleport_zones = self.current_map_config.get('no_teleport_boxes', [])
        if not no_teleport_zones:
            self.cached_no_teleport_status = False
            return False
        
        x, y = yellow_pos
        for box in no_teleport_zones:
            if len(box) == 4:
                x1, y1, x2, y2 = box
                if x1 <= x <= x2 and y1 <= y <= y2:
                    self.cached_no_teleport_status = True
                    return True
        
        self.cached_no_teleport_status = False
        return False
    
    def run(self):
        self.running = True
        self.start_alert_processor()
        
        logging.info("📷 화면 캡처 시작 중...")
        if not self.screen_capture.start():
            logging.error("❌ 화면 캡처 시작 실패")
            return
        
        time.sleep(1.0)
        
        self.yellow_dot_tracker.start()
        self.alert_system.start()
        self.start_frame_processor()
        
        time.sleep(0.5)
        
        logging.info("💊 초기 버프 사용")
        self.buff_system.use_initial_buffs()
        
        logging.info("🚶 초기 이동 시작")
        yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
        if yellow_pos:
            x, _ = yellow_pos
            if x < 320:
                self.key_controller.press_and_hold('right')
                logging.info("🚶 초기 이동: 오른쪽으로 이동")
            else:
                self.key_controller.press_and_hold('left')
                logging.info("🚶 초기 이동: 왼쪽으로 이동")
            
            time.sleep(0.1)
            self.key_controller.press_key('alt', 0.05)
        
        logging.info("🚀 봇 시작!")
        logging.info("F8: 일시정지/재개")
        
        try:
            self.main_loop()
        except KeyboardInterrupt:
            logging.info("사용자 중단")
        finally:
            self.cleanup()
    
    def main_loop(self):
        log_counter = 0
        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue
            
            try:
                log_counter += 1
                
                if log_counter % 300 == 0:
                    yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
                    if yellow_pos:
                        no_hunt_count = len(self.current_map_config.get('no_hunt_boxes', []))
                        logging.debug(f"📍 노란점 위치: {yellow_pos}, 사냥불가: {no_hunt_count}개")
                        if self.scroll_tracker.scroll_enabled:
                            offset = self.scroll_tracker.get_current_scroll_offset()
                            logging.debug(f"📜 스크롤 오프셋: x={offset['x']:.1f}, y={offset['y']:.1f}")
                
                with self.class1_flag_lock:
                    if self.class1_detected_flag:
                        time.sleep(0.01)
                        continue
                
                if self.class1_handler.is_processing_class1:
                    time.sleep(0.01)
                    continue
                
                current_zone = self.yellow_dot_tracker.get_current_zone()
                
                if current_zone and self.zone_action_manager.is_trigger_zone(current_zone):
                    if not self.zone_action_manager.is_forced_movement_active:
                        self.zone_action_manager.start_forced_movement()
                
                if self.zone_action_manager.is_forced_movement_active:
                    if current_zone and self.zone_action_manager.is_target_zone(current_zone):
                        self.zone_action_manager.stop_forced_movement()
                    else:
                        self.zone_action_manager.execute_forced_movement_actions()
                        time.sleep(0.01)
                        continue
                
                if current_zone == 1:
                    current_time = time.time()
                    
                    is_class1_processing = self.class1_handler.is_processing_class1
                    is_class1_ignoring = current_time - self.class1_handler.class1_ignore_time < self.class1_handler.CLASS1_IGNORE_DURATION
                    has_class1_monster = detection and detection.get('has_class_1_monster', False)
                    
                    if is_class1_processing:
                        logging.info(f"🚫 Zone 1 - 클래스1 처리 중, 맵 전환 대기")
                    elif is_class1_ignoring:
                        remaining = self.class1_handler.CLASS1_IGNORE_DURATION - (current_time - self.class1_handler.class1_ignore_time)
                        logging.debug(f"🚫 Zone 1 - 클래스1 무시 중 ({remaining:.0f}초 남음), 맵 전환 대기")
                    elif has_class1_monster:
                        logging.info(f"🚫 Zone 1 - 클래스1 몬스터 존재, 맵 전환 대기")
                    elif current_time - self.zone1_last_time >= self.zone1_cooldown:
                        logging.info(f"✅ Zone 1 - 맵 전환 조건 충족")
                        self.switch_map()
                        self.zone1_last_time = current_time
                        self.scroll_tracker.reset_scroll_tracking()
                
                detection = self.get_cached_detection()
                
                if detection:
                    character_class = detection.get('character_class')
                    pressed_keys = self.key_controller.get_pressed_keys()
                    
                    if character_class is not None:
                        if character_class == 1:
                            if 'up' not in pressed_keys:
                                self.key_controller.press_and_hold('up')
                                logging.debug("🔧 클래스1: UP키 누름")
                        
                        if self.previous_character_class == 1 and character_class == 0:
                            if 'up' in pressed_keys:
                                self.key_controller.release_key('up')
                                logging.debug("🔧 클래스1→0 전환: UP키 해제")
                        
                        self.previous_character_class = character_class
                
                character_detected = detection and detection.get('character_pos') is not None
                
                no_hunt_zones = self.current_map_config.get('no_hunt_boxes', [])
                is_no_hunt_zone = self.is_in_no_hunt_zone(no_hunt_zones)
                
                character_class = detection.get('character_class') if detection else None
                
                if not is_no_hunt_zone and character_class != 1:
                    if detection and detection.get('monsters_in_range'):
                        is_ignoring_class1 = False
                        if hasattr(self, 'class1_handler') and hasattr(self.class1_handler, 'class1_ignore_time'):
                            current_time = time.time()
                            if current_time - self.class1_handler.class1_ignore_time < self.class1_handler.CLASS1_IGNORE_DURATION:
                                is_ignoring_class1 = True
                                remaining = self.class1_handler.CLASS1_IGNORE_DURATION - (current_time - self.class1_handler.class1_ignore_time)
                                if log_counter % 100 == 0:
                                    logging.debug(f"⏰ 클래스1 무시 중 (남은 시간: {remaining:.0f}초)")
                        
                        monsters_info = detection.get('monsters_info', [])
                        has_class1 = detection.get('has_class_1_monster', False)
                        
                        should_hunt = False
                        if is_ignoring_class1:
                            should_hunt = True
                            logging.debug("✅ 클래스1 무시 중 - 사냥 가능")
                        elif not has_class1:
                            should_hunt = True
                            logging.debug("✅ 클래스1 없음 - 사냥 가능")
                        
                        if should_hunt:
                            if self.hunting_system.check_hunting_condition(detection):
                                logging.info(f"⚔️ 사냥 조건 충족! 무시중: {is_ignoring_class1}, 클래스1: {has_class1}")
                                self.hunting_system.start_hunt(detection)
                            else:
                                if log_counter % 100 == 0:
                                    logging.debug("❌ check_hunting_condition이 False 반환")
                
                if current_zone:
                    self.zone_action_manager.execute_zone_action(current_zone)
                
                if not self.hunting_system.is_hunting and character_class != 1:
                    self.buff_system.check_and_use_buffs()
                
                if self.use_teleport and not self.hunting_system.is_hunting and not self.zone_action_manager.is_forced_movement_active:
                    if not self.is_in_no_teleport_zone():
                        if random.random() < 0.5 and self.key_controller.is_shift_ready():
                            self.key_controller.press_key('shift', 0.05)
                
                current_time = time.time()
                if not self.hunting_system.is_hunting and not self.is_paused and current_time - self.last_random_key_time >= self.random_key_interval:
                    if random.random() < 0.5:
                        random_key = 'alt' if random.random() < 0.5 else 'z'
                        self.key_controller.press_key(random_key, 0.05)
                        self.last_random_key_time = current_time
                
                yellow_pos = self.yellow_dot_tracker.get_yellow_dot_position()
                if yellow_pos:
                    current_time = time.time()
                    
                    if (self.stop_position and self.stop_position == yellow_pos and current_time - self.stop_time >= 3.0) or not character_detected:
                        if not self.hunting_system.is_hunting and not self.buff_system.check_and_use_buffs() and not self.zone_action_manager.is_forced_movement_active:
                            if not self.is_auto_moving:
                                self.is_auto_moving = True
                                x, _ = yellow_pos
                                
                                self.key_controller.release_all_keys()
                                
                                if x < 320:
                                    self.key_controller.press_and_hold('right')
                                    logging.info("🚶 자동 이동: 오른쪽으로 이동" + (" (캐릭터 미탐지)" if not character_detected else ""))
                                else:
                                    self.key_controller.press_and_hold('left')
                                    logging.info("🚶 자동 이동: 왼쪽으로 이동" + (" (캐릭터 미탐지)" if not character_detected else ""))
                                
                                time.sleep(0.1)
                                self.key_controller.press_key('alt', 0.05)
                    else:
                        if character_detected and self.stop_position != yellow_pos:
                            self.stop_position = yellow_pos
                            self.stop_time = current_time
                            if self.is_auto_moving:
                                self.is_auto_moving = False
                                logging.info("✅ 캐릭터 이동 감지 - 자동 이동 종료")
                
            except Exception as e:
                logging.error(f"메인 루프 오류: {e}")
            
            time.sleep(0.01)
    
    def cleanup(self):
        self.running = False
        
        self.key_controller.stop_listener()
        
        self.screen_capture.stop()
        self.yellow_dot_tracker.stop()
        self.alert_system.stop()
        self.key_controller.release_all_keys()
        
        logging.info("✅ 정리 완료")