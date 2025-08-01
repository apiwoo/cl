import time
import random
import logging
import threading
import os
import cv2
import numpy as np
import pygetwindow as gw
import mss

class Class1MonsterHandler:
    def __init__(self, bot_core=None):
        self.bot_core = bot_core
        
        self.single_key = 'a'
        if bot_core and hasattr(bot_core, 'cfg'):
            attack_keys = bot_core.cfg.get('attack_keys', {})
            if attack_keys:
                self.single_key = list(attack_keys.values())[0].get('key', 'a')
        
        self.class_1_detected = False
        self.class_1_alert_played = False
        self.alert_audio_file = "alert.mp3"
        
        self.class_1_alert_thread = None
        self.class_1_alert_stop_flag = threading.Event()
        
        self.class_1_priority_mode = False
        self.class_1_priority_start_time = None
        self.PRIORITY_MODE_DURATION = 180.0
        self.was_paused = False
        
        self.attack_range = 150
        if bot_core and hasattr(bot_core, 'config'):
            self.attack_range = bot_core.config.get('attack_range', {}).get('width', 150)
        
        self.is_processing_class1 = False
        self.last_successful_alert_time = 0
        self.ALERT_COOLDOWN = 300.0
        
        self.last_hunt_complete_time = 0
        self.HUNT_COMPLETE_COOLDOWN = 5.0
        
        self.class1_ignore_time = 0
        self.CLASS1_IGNORE_DURATION = 180.0
        
        logging.info("🚨 클래스1 몬스터 핸들러 초기화 완료")
    
    def handle_class1_detection(self, detection_results, minimap_frame_getter, main_frame_getter):
        logging.info("🚨 handle_class1_detection 호출됨")
        if not detection_results.get("has_class_1_monster", False):
            logging.warning("⚠️ has_class_1_monster가 False")
            return False
        
        current_time = time.time()
        
        if current_time - self.class1_ignore_time < self.CLASS1_IGNORE_DURATION:
            remaining = self.CLASS1_IGNORE_DURATION - (current_time - self.class1_ignore_time)
            logging.info(f"⏰ 클래스1 무시 중 (남은 시간: {remaining:.0f}초)")
            return False
        
        if self.is_processing_class1:
            logging.info("🔄 클래스1 몬스터 처리 중 - 중복 처리 방지")
            return False
        
        self.is_processing_class1 = True
        
        try:
            if current_time - self.last_successful_alert_time >= self.ALERT_COOLDOWN:
                logging.info("🚨🚨🚨 클래스 1 몬스터 감지! 알림 시작 및 자동 일시정지")
                self.class_1_detected = True
                self._start_class_1_alert()
                
                if self.bot_core and not self.bot_core.is_paused:
                    self.bot_core.toggle_pause()
                    self.was_paused = True
                
                alert_success = self._find_and_click_alert()
                
                if alert_success:
                    logging.info("✅ alert 처리 성공 - 5분 쿨다운 시작")
                    self.last_successful_alert_time = time.time()
                    self.class1_ignore_time = time.time()
                    logging.info(f"⏰ 클래스1 몬스터 3분간 무시 시작")
                else:
                    logging.info("❌ alert 처리 실패 - F8을 눌러 수동 재시작하세요")
            else:
                remaining = self.ALERT_COOLDOWN - (current_time - self.last_successful_alert_time)
                logging.info(f"⏰ 클래스1 alert 쿨다운 중 (남은 시간: {remaining:.0f}초)")
        
        finally:
            self.is_processing_class1 = False
            
            if self.bot_core:
                with self.bot_core.class1_flag_lock:
                    self.bot_core.class1_detected_flag = False
                    logging.info("🚨 클래스1 플래그 해제")
            
            if self.was_paused and self.bot_core:
                logging.info(f"🔍 [CLASS1] 재시작 전 - is_paused: {self.bot_core.is_paused}")
                if self.bot_core.is_paused:
                    logging.info("🔄 클래스1 처리 완료 - 봇 재시작")
                    self.bot_core.toggle_pause()
                    logging.info(f"🔍 [CLASS1] toggle_pause 후 - is_paused: {self.bot_core.is_paused}")
                else:
                    logging.warning("🔍 [CLASS1] 이미 paused가 False 상태!")
                self.was_paused = False
        
        return True
    
    def check_priority_mode_activation(self, is_paused=None):
        logging.info(f"🔍 [PRIORITY] check_priority_mode_activation 시작")
        logging.info(f"🔍 [PRIORITY] was_paused: {self.was_paused}, is_paused 파라미터: {is_paused}")
        
        if is_paused is None and self.bot_core:
            logging.warning("🔍 [PRIORITY] is_paused 파라미터 없음 - 데드락 방지를 위해 스킵")
            return
            
        if self.was_paused and self.bot_core and not is_paused:
            self.was_paused = False
            self.class_1_priority_mode = True
            self.class_1_priority_start_time = time.time()
            logging.info(f"🎯 우선사냥 모드 활성화! {self.PRIORITY_MODE_DURATION}초간 클래스 1 우선 사냥")
            self._stop_class_1_alert()
        else:
            logging.info(f"🔍 [PRIORITY] 우선사냥 모드 활성화 조건 미충족")
        
        logging.info(f"🔍 [PRIORITY] check_priority_mode_activation 완료")
    
    def _is_in_priority_mode(self):
        if not self.class_1_priority_mode:
            return False
        
        if self.class_1_priority_start_time is None:
            return False
        
        elapsed = time.time() - self.class_1_priority_start_time
        if elapsed > self.PRIORITY_MODE_DURATION:
            logging.info(f"⏰ 우선사냥 모드 종료 (경과 시간: {elapsed:.1f}초)")
            self.class_1_priority_mode = False
            self.class_1_priority_start_time = None
            return False
        
        return True
    
    def _start_class_1_alert(self):
        if self.class_1_alert_played:
            logging.info("🔕 클래스 1 몬스터 알림이 이미 재생됨")
            return
        
        logging.info("🚨 클래스 1 몬스터 알림 시작 (1회)")
        
        self.class_1_alert_played = True
        
        if self.bot_core and hasattr(self.bot_core, 'alert_system'):
            self.bot_core.alert_system.start_class1_alert()
    
    def _stop_class_1_alert(self):
        self.class_1_detected = False
        self.class_1_alert_played = False
        self.class_1_alert_thread = None
        self.class_1_alert_stop_flag.set()
        
        if self.bot_core and hasattr(self.bot_core, 'alert_system'):
            self.bot_core.alert_system.stop_class1_alert()
        
        logging.info("🔕 클래스 1 몬스터 알림 중지")
    
    def _find_and_click_alert(self):
        try:
            wins = gw.getWindowsWithTitle("Mapleland")
            if not wins:
                logging.error("❌ Mapleland 창을 찾을 수 없습니다.")
                return False
            
            game_window = wins[0]
            window_x = game_window.left
            window_y = game_window.top
            
            alert_files = [
                ("alert.png", 0.8),
                ("alert1.png", 0.9)
            ]
            
            max_attempts = 5
            
            for attempt in range(max_attempts):
                if attempt > 0:
                    logging.info(f"🚶 alert 찾기 {attempt+1}번째 시도 - 좌측으로 이동 중...")
                    self.bot_core.key_controller.press_and_hold('left')
                    time.sleep(1.0)
                    self.bot_core.key_controller.press_key('shift', 0.1)
                    time.sleep(0.3)
                    self.bot_core.key_controller.release_key('left')
                    time.sleep(0.3)
                
                for alert_path, threshold in alert_files:
                    if not os.path.exists(alert_path):
                        logging.warning(f"⚠️ {alert_path} 파일 없음")
                        continue
                    
                    alert_template = cv2.imread(alert_path, cv2.IMREAD_COLOR)
                    if alert_template is None:
                        logging.error(f"❌ {alert_path} 로드 실패")
                        continue
                    
                    with mss.mss() as sct:
                        monitor = {
                            "left": game_window.left,
                            "top": game_window.top,
                            "width": game_window.width,
                            "height": game_window.height
                        }
                        screenshot = sct.grab(monitor)
                        screenshot_np = np.array(screenshot)
                        screenshot_bgr = cv2.cvtColor(screenshot_np, cv2.COLOR_BGRA2BGR)
                    
                    result = cv2.matchTemplate(screenshot_bgr, alert_template, cv2.TM_CCOEFF_NORMED)
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    
                    if max_val >= threshold:
                        template_h, template_w = alert_template.shape[:2]
                        
                        abs_x = max_loc[0] + game_window.left
                        abs_y = max_loc[1] + game_window.top
                        game_x = max_loc[0]
                        game_y = max_loc[1]
                        
                        click_x = abs_x + random.randint(5, template_w - 5)
                        click_y = abs_y + random.randint(5, template_h - 5)
                        click_game_x = click_x - window_x
                        click_game_y = click_y - window_y
                        
                        self.bot_core.key_controller.move_mouse(click_x, click_y, duration=random.uniform(0.1, 0.2))
                        self.bot_core.key_controller.click_mouse()
                        logging.info(f"✅ {alert_path} 클릭 완료: 게임내({click_game_x}, {click_game_y})")
                        
                        logging.info("⏳ 2초 대기 중...")
                        time.sleep(2.0)
                        
                        if not os.path.exists("accept.png"):
                            logging.warning("⚠️ accept.png 파일 없음")
                            return False
                        
                        accept_template = cv2.imread("accept.png", cv2.IMREAD_COLOR)
                        if accept_template is None:
                            logging.error("❌ accept.png 로드 실패")
                            return False
                        
                        with mss.mss() as sct:
                            screenshot2 = sct.grab(monitor)
                            screenshot2_np = np.array(screenshot2)
                            screenshot2_bgr = cv2.cvtColor(screenshot2_np, cv2.COLOR_BGRA2BGR)
                        
                        accept_result = cv2.matchTemplate(screenshot2_bgr, accept_template, cv2.TM_CCOEFF_NORMED)
                        accept_min_val, accept_max_val, accept_min_loc, accept_max_loc = cv2.minMaxLoc(accept_result)
                        
                        if accept_max_val >= 0.4:
                            accept_h, accept_w = accept_template.shape[:2]
                            
                            accept_abs_x = accept_max_loc[0] + game_window.left
                            accept_abs_y = accept_max_loc[1] + game_window.top
                            accept_game_x = accept_max_loc[0]
                            accept_game_y = accept_max_loc[1]
                            
                            accept_click_x = accept_abs_x + random.randint(5, accept_w - 5)
                            accept_click_y = accept_abs_y + random.randint(5, accept_h - 5)
                            accept_click_game_x = accept_click_x - window_x
                            accept_click_game_y = accept_click_y - window_y
                            
                            self.bot_core.key_controller.move_mouse(accept_click_x, accept_click_y, duration=random.uniform(0.1, 0.2))
                            self.bot_core.key_controller.click_mouse()
                            logging.info(f"✅ accept.png 클릭 완료: 게임내({accept_click_game_x}, {accept_click_game_y})")
                            return True
                        else:
                            logging.error(f"❌ accept.png 찾지 못함 (신뢰도: {accept_max_val:.2f} < 0.4)")
                            return False
                    else:
                        logging.debug(f"❌ {alert_path} 찾지 못함 (신뢰도: {max_val:.2f} < {threshold})")
            
            logging.error(f"❌ {max_attempts}번 시도 후에도 alert를 찾지 못했습니다.")
            return False
                
        except Exception as e:
            logging.error(f"❌ alert 처리 오류: {e}")
            return False
    
    def _prioritize_class_1_monster(self, results, minimap_frame_getter, main_frame_getter):
        max_attempts = 50
        attempt = 0
        last_direction = None
        no_class1_frames = 0
        
        logging.info(f"🎯 클래스 1 몬스터 우선 처치 모드 시작 (공격 범위: {self.attack_range}px)")
        
        while attempt < max_attempts:
            attempt += 1
            
            monsters = results.get("monsters", [])
            class_1_monsters = [m for m in monsters if m.get("class_id") == 1]
            
            if not class_1_monsters:
                no_class1_frames += 1
                logging.debug(f"🔍 클래스1 몬스터 없음 프레임: {no_class1_frames}/3")
                
                if no_class1_frames >= 3:
                    logging.info("✅ 3프레임 연속 클래스 1 몬스터 없음 - 처치 완료")
                    return True
            else:
                no_class1_frames = 0
                
                closest_class_1 = min(class_1_monsters, key=lambda m: m["center"][0])
                
                char_pos = results.get("character", {}).get("screen_pos") if results.get("character") else results.get("character_pos")
                if not char_pos:
                    return False
                
                monster_x = closest_class_1["center"][0]
                char_x = char_pos[0]
                distance = abs(monster_x - char_x)
                
                if distance <= self.attack_range:
                    direction = "right" if monster_x > char_x else "left"
                    self.bot_core.key_controller.press_and_hold(direction)
                    self.bot_core.key_controller.press_key(self.single_key)
                    self.bot_core.key_controller.release_key(direction)
                else:
                    direction = "right" if monster_x > char_x else "left"
                    
                    if direction != last_direction or attempt == 1:
                        logging.info(f"🎯 클래스 1 몬스터 추적: {direction} 방향 (거리: {distance}px)")
                        last_direction = direction
                    
                    self.bot_core.key_controller.press_and_hold(direction)
                    self.bot_core.key_controller.press_key('shift')
                    move_time = min(0.5, max(0.1, (distance - self.attack_range - 200) / 200))
                    time.sleep(move_time)
                    self.bot_core.key_controller.release_key(direction)
            
            minimap_frame = minimap_frame_getter()
            main_frame = main_frame_getter()
            
            if minimap_frame is None or main_frame is None:
                continue
            
            if self.bot_core and hasattr(self.bot_core, 'detector'):
                pressed_keys = self.bot_core.key_controller.get_pressed_keys()
                movement_direction = None
                if 'left' in pressed_keys:
                    movement_direction = 'left'
                elif 'right' in pressed_keys:
                    movement_direction = 'right'
                
                results = self.bot_core.detector.detect(main_frame, movement_direction)
            else:
                logging.error("❌ detector를 찾을 수 없음")
                return False
        
        logging.warning(f"⚠️ {max_attempts}번 시도 후 클래스 1 몬스터 처치 실패")
        return False
    
    def reset(self):
        self.class_1_detected = False
        self.class_1_alert_played = False
        self._stop_class_1_alert()
        self.class_1_priority_mode = False
        self.class_1_priority_start_time = None
        self.was_paused = False
        self.is_processing_class1 = False
        self.last_hunt_complete_time = 0
        
        current_time = time.time()
        if current_time - self.class1_ignore_time < self.CLASS1_IGNORE_DURATION:
            remaining = self.CLASS1_IGNORE_DURATION - (current_time - self.class1_ignore_time)
            logging.info(f"🔄 클래스1 몬스터 핸들러 초기화 (무시 시간 유지: {remaining:.0f}초 남음)")
        else:
            logging.info("🔄 클래스1 몬스터 핸들러 초기화")