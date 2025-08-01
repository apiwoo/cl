import cv2
import numpy as np
import mss
import pygetwindow as gw
import time
import sys
import os
from config_manager import ConfigManager
from detector_engine import DetectorEngine
from screen_capture import ScreenCapture
from yellow_dot_tracker import YellowDotTracker
from scroll_tracker import ScrollTracker

def main():
    print("🎮 몬스터 탐지 테스트 프로그램")
    print("=" * 50)
    
    windows = gw.getWindowsWithTitle("Mapleland")
    if not windows:
        print("❌ Mapleland 창을 찾을 수 없습니다.")
        sys.exit(1)
    
    window = windows[0]
    print(f"✅ 게임 창 찾음: {window.title}")
    
    if window.width != 1920 or window.height != 1080:
        print("⚠️ 게임 창을 1920x1080으로 조정합니다...")
        try:
            window.resizeTo(1920, 1080)
            time.sleep(0.5)
            print("✅ 게임 창 크기 조정 완료")
        except Exception as e:
            print(f"⚠️ 창 크기 조정 실패: {e}")
    
    try:
        window.activate()
        time.sleep(0.3)
        print("✅ 게임 창 활성화 완료")
    except Exception as e:
        print(f"⚠️ 게임 창 활성화 실패: {e}")
    
    config_manager = ConfigManager()
    config = config_manager.setup_config()
    
    if not config:
        print("❌ 설정 실패")
        sys.exit(1)
    
    maps_data = config_manager.load_maps()
    map_sequence = config['map_sequence']
    current_map_idx = map_sequence[0]
    map_info = maps_data["maps"][current_map_idx - 1]
    
    import json
    config_file = os.path.join("configs", map_info["config_file"])
    with open(config_file, "r", encoding="utf-8") as f:
        map_config = json.load(f)
    
    minimap_info = map_config.get("minimap", {})
    screen_capture = ScreenCapture(minimap_info)
    
    attack_range = config.get('attack_range', {'width': 200, 'height': 50})
    hunting_config = config.get('hunting_config', {})
    detector_engine = DetectorEngine(attack_range, hunting_config)
    
    character_model_path = config.get('character_info', {}).get('model_path')
    monster_model_path = f"maple_models/{map_info.get('monstermodelname', 'default')}/model/{map_info.get('monstermodelname', 'default')}_best.engine"
    
    if not detector_engine.initialize(character_model_path, monster_model_path):
        print("❌ 탐지 엔진 초기화 실패")
        sys.exit(1)
    
    scroll_tracker = ScrollTracker()
    scroll_tracker.update_map_config(map_config)
    
    yellow_dot_tracker = YellowDotTracker(screen_capture, map_config, scroll_tracker)
    
    if not screen_capture.start():
        print("❌ 화면 캡처 시작 실패")
        sys.exit(1)
    
    yellow_dot_tracker.start()
    
    cv2.namedWindow("Monster Detection Debug", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Monster Detection Debug", 1280, 720)
    
    print("\n🚀 실시간 탐지 시작... (q: 종료)")
    print(f"📁 캐릭터 모델: {character_model_path}")
    print(f"📁 몬스터 모델: {monster_model_path}")
    print(f"🎯 공격 범위: {attack_range['width']}x{attack_range['height']}")
    print(f"🗺️ 맵: {map_info.get('name', 'Unknown')}")
    
    frame_count = 0
    last_status_time = time.time()
    
    while True:
        try:
            frame_count += 1
            
            main_frame = screen_capture.get_main_frame()
            minimap_frame = screen_capture.get_minimap()
            
            if main_frame is None:
                continue
            
            display_frame = main_frame.copy()
            
            movement_direction = None
            detection = detector_engine.detect(main_frame, movement_direction)
            
            if detection:
                if detection["character_pos"]:
                    char_x, char_y = detection["character_pos"]
                    cv2.circle(display_frame, (char_x, char_y), 10, (0, 255, 0), -1)
                    cv2.putText(display_frame, f"Character (Class: {detection.get('character_class', 'N/A')})", 
                               (char_x - 50, char_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    attack_width = attack_range['width']
                    attack_height = attack_range['height']
                    
                    attack_left = char_x - attack_width
                    attack_right = char_x + attack_width
                    attack_top = char_y - attack_height
                    attack_bottom = char_y + attack_height
                    
                    cv2.rectangle(display_frame, (attack_left, attack_top), 
                                 (attack_right, attack_bottom), (255, 255, 0), 2)
                    cv2.putText(display_frame, "Attack Range", 
                               (attack_left + 5, attack_top - 5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
                    
                    if detection.get("monsters_info"):
                        for i, monster in enumerate(detection["monsters_info"]):
                            bbox = monster["bbox"]
                            x1, y1, x2, y2 = [int(coord) for coord in bbox]
                            
                            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                            
                            center_x, center_y = monster["center"]
                            cv2.circle(display_frame, (center_x, center_y), 3, (0, 0, 255), -1)
                            
                            conf = monster.get("confidence", 0)
                            label = f"M{i+1} ({monster['direction']}) D:{monster['distance']:.0f} C:{conf:.3f}"
                            cv2.putText(display_frame, label, (x1, y1 - 5), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
                            
                            cv2.line(display_frame, (char_x, char_y), (center_x, center_y), 
                                    (255, 0, 255), 1)
            
            current_zone = yellow_dot_tracker.get_current_zone()
            yellow_pos = yellow_dot_tracker.get_yellow_dot_position()
            
            info_texts = [
                f"Frame: {frame_count}",
                f"Character: {'O' if detection and detection['character_pos'] else 'X'}",
                f"Monsters in range: {'O' if detection and detection['monsters_in_range'] else 'X'}",
                f"Monster count: {len(detection.get('monsters_info', [])) if detection else 0}",
                f"Current Zone: {current_zone if current_zone else 'None'}",
                f"Yellow Dot: {yellow_pos if yellow_pos else 'Not found'}"
            ]
            
            for i, text in enumerate(info_texts):
                color = (255, 255, 255)
                if "Monsters in range: O" in text:
                    color = (0, 0, 255)
                cv2.putText(display_frame, text, (10, 30 + i * 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            no_hunt_zones = map_config.get('no_hunt_boxes', [])
            if yellow_pos and no_hunt_zones:
                x, y = yellow_pos
                is_no_hunt = False
                for box in no_hunt_zones:
                    if len(box) == 4:
                        x1, y1, x2, y2 = box
                        if x1 <= x <= x2 and y1 <= y <= y2:
                            is_no_hunt = True
                            break
                
                cv2.putText(display_frame, f"No Hunt Zone: {'O' if is_no_hunt else 'X'}", 
                           (10, 30 + len(info_texts) * 25), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                           (0, 0, 255) if is_no_hunt else (0, 255, 0), 2)
            
            current_time = time.time()
            if current_time - last_status_time > 2.0:
                if detection and detection['monsters_in_range']:
                    print(f"\n⚠️ 몬스터 감지!")
                    print(f"   몬스터 수: {len(detection.get('monsters_info', []))}")
                    for i, monster in enumerate(detection.get('monsters_info', [])):
                        conf = monster.get('confidence', 0)
                        print(f"   몬스터 {i+1}: {monster['direction']} 방향, 거리 {monster['distance']:.0f}, 신뢰도 {conf:.3f}")
                last_status_time = current_time
            
            cv2.imshow("Monster Detection Debug", display_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        except Exception as e:
            print(f"❌ 오류: {e}")
            import traceback
            traceback.print_exc()
            break
    
    cv2.destroyAllWindows()
    screen_capture.stop()
    yellow_dot_tracker.stop()
    print("\n✅ 프로그램 종료")

if __name__ == "__main__":
    main()