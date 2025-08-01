import cv2
import numpy as np
import json
import os
import sys
import time

minimap_640 = None
roi_start = None
roi_end = None
drawing = False
zones = []
zone_count = 0
zone_actions = {}
zone_cooldowns = {}
no_hunt_boxes = []
no_teleport_boxes = []
current_mode = "zone"
selected_action_zone = None
start_point = None
roi_x1, roi_y1, roi_x2, roi_y2 = 20, 170, 370, 391
loaded_config = None
map_id = None
display_name = None
monster_model_name = None
scale_to_640 = 1.0
minimap_file_path = "mm.png"
scroll_enabled = False
scroll_tracking_files = []
forced_movement_config = {
    "enabled": False,
    "trigger_zones": [],
    "target_zone": 1,
    "repeat_actions": [],
    "repeat_interval": 1000
}

def load_map_list():
    maps_file = os.path.join("configs", "maps.json")
    if not os.path.exists(maps_file):
        return {"maps": []}
    
    try:
        with open(maps_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"maps": []}

def load_existing_config():
    global zones, zone_count, zone_actions, zone_cooldowns, no_hunt_boxes, no_teleport_boxes
    global loaded_config, map_id, display_name, scale_to_640
    global minimap_file_path, roi_x1, roi_y1, roi_x2, roi_y2
    global scroll_enabled, scroll_tracking_files, forced_movement_config
    global monster_model_name
    
    maps_data = load_map_list()
    
    if not maps_data.get("maps"):
        print("❌ 등록된 맵이 없습니다.")
        return False
    
    print("\n📁 기존 맵 목록:")
    print("-" * 50)
    for i, map_info in enumerate(maps_data["maps"], 1):
        print(f"{i}) {map_info['id']} - {map_info['name']}")
    
    while True:
        try:
            choice = input(f"\n선택 (1-{len(maps_data['maps'])}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(maps_data["maps"]):
                selected_map = maps_data["maps"][idx]
                break
            print("❌ 잘못된 선택")
        except:
            print("❌ 숫자를 입력하세요")
    
    config_file = os.path.join("configs", selected_map["config_file"])
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            loaded_config = json.load(f)
        
        map_id = loaded_config.get("id", "")
        display_name = loaded_config.get("display_name", map_id)
        monster_model_name = loaded_config.get("monstermodelname", selected_map.get("monstermodelname", selected_map.get("name", display_name)))
        
        minimap_info = loaded_config.get("minimap", {})
        roi_x1 = minimap_info.get("left", 20)
        roi_y1 = minimap_info.get("top", 170)
        roi_x2 = roi_x1 + minimap_info.get("width", 350)
        roi_y2 = roi_y1 + minimap_info.get("height", 221)
        scale_to_640 = minimap_info.get("scale_to_640", 640.0 / 350)
        minimap_file_path = minimap_info.get("file_path", "mm.png")
        
        scroll_enabled = loaded_config.get("scroll_enabled", False)
        
        if "scroll_tracking_files" in loaded_config:
            scroll_tracking_files = loaded_config.get("scroll_tracking_files", [])
        elif "scroll_tracking_file" in loaded_config:
            tracking_file = loaded_config.get("scroll_tracking_file", "")
            scroll_tracking_files = [tracking_file] if tracking_file else []
        else:
            scroll_tracking_files = []
        
        forced_movement_config.update(loaded_config.get("forced_movement_config", {
            "enabled": False,
            "trigger_zones": [],
            "target_zone": 1,
            "repeat_actions": [],
            "repeat_interval": 1000
        }))
        
        zones = []
        for zone in loaded_config.get("zones", []):
            zone_copy = zone.copy()
            
            if "bbox_640" in zone_copy:
                zones.append(zone_copy)
            else:
                bbox = zone_copy.get("bbox", [])
                if len(bbox) == 4:
                    x1, y1, x2, y2 = bbox
                    rel_x1 = int((x1 - roi_x1) * scale_to_640)
                    rel_y1 = int((y1 - roi_y1) * scale_to_640)
                    rel_x2 = int((x2 - roi_x1) * scale_to_640)
                    rel_y2 = int((y2 - roi_y1) * scale_to_640)
                    zone_copy["bbox_640"] = [rel_x1, rel_y1, rel_x2, rel_y2]
                    zones.append(zone_copy)
        
        zone_count = max([z["id"] for z in zones]) if zones else 0
        
        zone_actions = {}
        for key, value in loaded_config.get("zone_actions", {}).items():
            zone_actions[int(key)] = value
        
        no_hunt_boxes = loaded_config.get("no_hunt_boxes", loaded_config.get("no_heal_boxes", []))
        no_teleport_boxes = loaded_config.get("no_teleport_boxes", [])
        
        zone_cooldowns = {}
        for key, value in loaded_config.get("zone_cooldowns", {}).items():
            zone_cooldowns[int(key)] = value
        
        print(f"\n✅ 맵 설정 로드 완료: {display_name}")
        print(f"   몬스터 모델명: {monster_model_name}")
        print(f"   미니맵 파일: {minimap_file_path}")
        print(f"   미니맵 좌표: ({roi_x1}, {roi_y1}) ~ ({roi_x2}, {roi_y2})")
        print(f"   스크롤 여부: {'활성화' if scroll_enabled else '비활성화'}")
        if scroll_enabled and scroll_tracking_files:
            for i, file in enumerate(scroll_tracking_files):
                print(f"   스크롤 추적 파일 {i+1}: {file}")
        print(f"   Zone 개수: {len(zones)}")
        print(f"   액션 설정된 Zone: {list(zone_actions.keys())}")
        if no_hunt_boxes:
            print(f"   사냥불가 박스: {len(no_hunt_boxes)}개")
        if no_teleport_boxes:
            print(f"   텔레포트금지 박스: {len(no_teleport_boxes)}개")
        if zone_cooldowns:
            print(f"   쿨다운 설정된 Zone: {list(zone_cooldowns.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ 파일 로드 실패: {e}")
        return False

def cb_zone(event, x, y, flags, param):
    global zones, zone_count, selected_action_zone, start_point, current_img, no_hunt_boxes, no_teleport_boxes
    
    ox = x
    oy = y
    
    if current_mode == "zone":
        if event == cv2.EVENT_LBUTTONDOWN:
            start_point = (ox, oy)
        elif event == cv2.EVENT_MOUSEMOVE and start_point:
            temp = current_img.copy()
            cv2.rectangle(temp, start_point, (x, y), (0, 255, 0), 1)
            cv2.imshow("Zone Editor", temp)
        elif event == cv2.EVENT_LBUTTONUP and start_point:
            ox1, oy1 = start_point
            ox2, oy2 = ox, oy
            
            x1, y1 = min(ox1, ox2), min(oy1, oy2)
            x2, y2 = max(ox1, ox2), max(oy1, oy2)
            
            if abs(x2 - x1) > 3 and abs(y2 - y1) > 3:
                zone_count += 1
                
                zones.append({
                    "id": zone_count,
                    "name": f"Zone {zone_count}",
                    "bbox_640": [x1, y1, x2, y2]
                })
                print(f"✅ Zone {zone_count} 생성됨: 640기준[{x1}, {y1}, {x2}, {y2}]")
                redraw()
            start_point = None
    
    elif current_mode == "nohunt":
        if event == cv2.EVENT_LBUTTONDOWN:
            start_point = (ox, oy)
        elif event == cv2.EVENT_MOUSEMOVE and start_point:
            temp = current_img.copy()
            cv2.rectangle(temp, start_point, (x, y), (0, 0, 255), 1)
            cv2.imshow("Zone Editor", temp)
        elif event == cv2.EVENT_LBUTTONUP and start_point:
            ox1, oy1 = start_point
            ox2, oy2 = ox, oy
            
            x1, y1 = min(ox1, ox2), min(oy1, oy2)
            x2, y2 = max(ox1, ox2), max(oy1, oy2)
            
            if abs(x2 - x1) > 3 and abs(y2 - y1) > 3:
                no_hunt_boxes.append([x1, y1, x2, y2])
                print(f"✅ 사냥불가 박스 생성됨: 640기준[{x1}, {y1}, {x2}, {y2}]")
                redraw()
            start_point = None
    
    elif current_mode == "noteleport":
        if event == cv2.EVENT_LBUTTONDOWN:
            start_point = (ox, oy)
        elif event == cv2.EVENT_MOUSEMOVE and start_point:
            temp = current_img.copy()
            cv2.rectangle(temp, start_point, (x, y), (255, 0, 0), 1)
            cv2.imshow("Zone Editor", temp)
        elif event == cv2.EVENT_LBUTTONUP and start_point:
            ox1, oy1 = start_point
            ox2, oy2 = ox, oy
            
            x1, y1 = min(ox1, ox2), min(oy1, oy2)
            x2, y2 = max(ox1, ox2), max(oy1, oy2)
            
            if abs(x2 - x1) > 3 and abs(y2 - y1) > 3:
                no_teleport_boxes.append([x1, y1, x2, y2])
                print(f"✅ 텔레포트금지 박스 생성됨: 640기준[{x1}, {y1}, {x2}, {y2}]")
                redraw()
            start_point = None
    
    elif current_mode == "action":
        if event == cv2.EVENT_LBUTTONDOWN:
            for zone in zones:
                x1, y1, x2, y2 = zone["bbox_640"]
                if x1 <= ox <= x2 and y1 <= oy <= y2:
                    selected_action_zone = zone["id"]
                    print(f"\n🎯 Zone {selected_action_zone} 선택됨")
                    show_existing_actions(selected_action_zone)
                    define_zone_action(selected_action_zone)
                    redraw()
                    break
    
    elif current_mode == "delete":
        if event == cv2.EVENT_LBUTTONDOWN:
            deleted = False
            
            for i, zone in enumerate(zones):
                x1, y1, x2, y2 = zone["bbox_640"]
                if x1 <= ox <= x2 and y1 <= oy <= y2:
                    removed = zones.pop(i)
                    zone_id = removed["id"]
                    if zone_id in zone_actions:
                        del zone_actions[zone_id]
                    if zone_id in zone_cooldowns:
                        del zone_cooldowns[zone_id]
                    print(f"🗑️ Zone {zone_id} 삭제됨")
                    deleted = True
                    redraw()
                    break
            
            if not deleted:
                for i, box in enumerate(no_hunt_boxes):
                    x1, y1, x2, y2 = box
                    if x1 <= ox <= x2 and y1 <= oy <= y2:
                        no_hunt_boxes.pop(i)
                        print(f"🗑️ 사냥불가 박스 삭제됨")
                        redraw()
                        deleted = True
                        break
            
            if not deleted:
                for i, box in enumerate(no_teleport_boxes):
                    x1, y1, x2, y2 = box
                    if x1 <= ox <= x2 and y1 <= oy <= y2:
                        no_teleport_boxes.pop(i)
                        print(f"🗑️ 텔레포트금지 박스 삭제됨")
                        redraw()
                        deleted = True
                        break

def show_existing_actions(zone_id):
    if zone_id in zone_actions:
        print(f"\n📋 Zone {zone_id} 기존 액션:")
        for i, action in enumerate(zone_actions[zone_id], 1):
            if action['action'] == 'sleep':
                action_str = f"{i}. SLEEP - {action.get('delay', 0)}ms"
            else:
                action_str = f"{i}. {action['key']} - {action['action']}"
                if action.get('delay', 0) > 0:
                    action_str += f" ({action['delay']}ms)"
            print(f"   {action_str}")
        print("(수정하려면 새로 정의하세요)")

def redraw():
    global minimap_640, zones, current_img, zone_cooldowns, no_hunt_boxes, no_teleport_boxes, forced_movement_config
    
    if minimap_640 is None:
        return
    
    display = minimap_640.copy()
    
    for box in no_hunt_boxes:
        x1, y1, x2, y2 = box
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 0, 255), 1)
        cv2.putText(display, "NO HUNT", (x1 + 5, y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)
    
    for box in no_teleport_boxes:
        x1, y1, x2, y2 = box
        cv2.rectangle(display, (x1, y1), (x2, y2), (255, 0, 0), 1)
        cv2.putText(display, "NO TP", (x1 + 5, y1 + 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 1)
    
    for zone in zones:
        x1, y1, x2, y2 = zone["bbox_640"]
        
        color = (0, 255, 0)
        thickness = 1
        if zone["id"] in zone_actions:
            color = (255, 255, 0)
            thickness = 1
        if zone["id"] == selected_action_zone:
            color = (0, 255, 255)
            thickness = 1
        if zone["id"] in forced_movement_config.get("trigger_zones", []):
            color = (255, 0, 255)
            thickness = 2
        if zone["id"] == forced_movement_config.get("target_zone"):
            color = (0, 128, 255)
            thickness = 2
        
        cv2.rectangle(display, (x1, y1), (x2, y2), color, thickness)
        
        label = str(zone["id"])
        if zone["id"] in zone_cooldowns:
            label += f"⏱{zone_cooldowns[zone['id']]}s"
        if zone["id"] in forced_movement_config.get("trigger_zones", []):
            label += "⚡"
        if zone["id"] == forced_movement_config.get("target_zone"):
            label += "🎯"
        
        text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        text_x = x1 + 5
        text_y = y1 + text_size[1] + 5
        
        cv2.rectangle(display, (text_x - 2, text_y - text_size[1] - 2), 
                     (text_x + text_size[0] + 2, text_y + 2), (0, 0, 0), -1)
        cv2.putText(display, label, (text_x, text_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    current_img = display
    cv2.imshow("Zone Editor", current_img)

def define_zone_action(zone_id):
    print(f"\n🎮 Zone {zone_id} 액션 정의")
    print("-" * 50)
    
    actions = []
    
    keys = {
        '1': 'LEFT',
        '2': 'RIGHT', 
        '3': 'UP',
        '4': 'DOWN',
        '5': 'ALT',
        '6': 'SHIFT',
        '7': 'SLEEP',
        '8': 'z'
    }
    
    action_types = {
        '1': 'up',
        '2': 'down',
        '3': 'tap'
    }
    
    while True:
        print("\n키 선택:")
        print("1) ← LEFT")
        print("2) → RIGHT")
        print("3) ↑ UP")
        print("4) ↓ DOWN")
        print("5) ALT (점프)")
        print("6) SHIFT (텔레포트)")
        print("7) SLEEP (대기)")
        print("8) z 키")
        print("9) 특정키 (탭)")
        print("0) 액션 정의 완료")
        
        key_choice = input("선택: ").strip()
        
        if key_choice == '0':
            break
        
        if key_choice == '9':
            custom_key = input("탭할 키를 입력하세요 (예: a, b, c, d, x, space, enter 등): ").strip()
            if not custom_key:
                print("❌ 키가 입력되지 않았습니다")
                continue
            
            action = {
                "key": custom_key,
                "action": "tap",
                "delay": 50
            }
            actions.append(action)
            print(f"✅ 추가됨: {custom_key} - tap (50ms)")
            continue
        
        if key_choice not in keys:
            print("❌ 잘못된 선택")
            continue
        
        selected_key = keys[key_choice]
        
        if selected_key == 'SLEEP':
            sleep_time = input("대기 시간 (ms, 기본 1000): ").strip()
            if sleep_time:
                try:
                    delay = int(sleep_time)
                except:
                    delay = 1000
            else:
                delay = 1000
            
            action = {
                "key": "SLEEP",
                "action": "sleep",
                "delay": delay
            }
            actions.append(action)
            print(f"✅ 추가됨: SLEEP - {delay}ms")
            continue
        
        print(f"\n{selected_key} 키 액션:")
        print("1) 떼기 (up)")
        print("2) 누르기 (down)")
        print("3) 눌렀다떼기 (tap)")
        
        action_choice = input("선택: ").strip()
        
        if action_choice not in action_types:
            print("❌ 잘못된 선택")
            continue
        
        selected_action = action_types[action_choice]
        
        delay = 0
        if selected_action == 'tap':
            delay_input = input("tap 지속시간 (ms, 기본 50): ").strip()
            if delay_input:
                try:
                    delay = int(delay_input)
                except:
                    delay = 50
            else:
                delay = 50
        
        action = {
            "key": selected_key,
            "action": selected_action
        }
        if delay > 0:
            action["delay"] = delay
        
        actions.append(action)
        print(f"✅ 추가됨: {selected_key} - {selected_action}" + (f" ({delay}ms)" if delay > 0 else ""))
    
    if actions:
        zone_actions[zone_id] = actions
        print(f"\n✅ Zone {zone_id} 액션 저장 완료")
        print("저장된 액션:")
        for i, action in enumerate(actions, 1):
            if action['action'] == 'sleep':
                print(f"  {i}. SLEEP - {action.get('delay', 0)}ms")
            else:
                print(f"  {i}. {action['key']} - {action['action']}" + 
                      (f" ({action.get('delay', 0)}ms)" if action.get('delay', 0) > 0 else ""))

def define_cooldowns():
    global zone_cooldowns
    
    print("\n⏱️ 쿨다운 설정")
    print("쿨다운을 설정할 존 번호를 입력하세요 (쉼표로 구분)")
    print("예: 1,3,4")
    print("(설정하지 않은 존은 기본 1초 쿨다운)")
    
    zone_input = input("존 번호: ").strip()
    if not zone_input:
        return
    
    try:
        zone_ids = [int(x.strip()) for x in zone_input.split(',')]
    except:
        print("❌ 잘못된 입력")
        return
    
    for zone_id in zone_ids:
        if zone_id not in [z["id"] for z in zones]:
            print(f"❌ Zone {zone_id}는 존재하지 않습니다")
            continue
        
        cooldown_input = input(f"Zone {zone_id} 쿨다운 시간 (초 단위, 기본 1.0): ").strip()
        if cooldown_input:
            try:
                cooldown = float(cooldown_input)
                if cooldown >= 0:
                    zone_cooldowns[zone_id] = cooldown
                    print(f"✅ Zone {zone_id} 쿨다운: {cooldown}초")
                else:
                    print("❌ 0 이상의 값을 입력하세요")
            except:
                print("❌ 잘못된 숫자")
        else:
            zone_cooldowns[zone_id] = 1.0
    
    redraw()

def define_forced_movement():
    global forced_movement_config
    
    print("\n⚡ 강제 이동 모드 설정")
    print("-" * 50)
    print("특정 존 진입 시 모든 행동을 멈추고 목표 존까지 지정된 액션만 반복합니다.")
    
    enable_input = input("\n강제 이동 모드를 활성화하시겠습니까? (y/n, 기본 n): ").strip().lower()
    if enable_input != 'y':
        forced_movement_config["enabled"] = False
        print("✅ 강제 이동 모드 비활성화")
        redraw()
        return
    
    forced_movement_config["enabled"] = True
    
    print("\n🎯 트리거 존 설정 (강제 이동을 시작할 존)")
    trigger_input = input("트리거 존 번호 (쉼표로 구분, 예: 5,7): ").strip()
    if trigger_input:
        try:
            trigger_zones = [int(x.strip()) for x in trigger_input.split(',')]
            valid_triggers = []
            for zone_id in trigger_zones:
                if zone_id in [z["id"] for z in zones]:
                    valid_triggers.append(zone_id)
                else:
                    print(f"❌ Zone {zone_id}는 존재하지 않습니다")
            forced_movement_config["trigger_zones"] = valid_triggers
            print(f"✅ 트리거 존: {valid_triggers}")
        except:
            print("❌ 잘못된 입력")
            return
    
    print("\n🏁 목표 존 설정 (도달할 존)")
    target_input = input("목표 존 번호 (기본 1): ").strip()
    if target_input:
        try:
            target_zone = int(target_input)
            if target_zone in [z["id"] for z in zones]:
                forced_movement_config["target_zone"] = target_zone
                print(f"✅ 목표 존: {target_zone}")
            else:
                print(f"❌ Zone {target_zone}는 존재하지 않습니다")
                return
        except:
            print("❌ 잘못된 입력")
            return
    
    print("\n🔄 반복 액션 정의")
    print("강제 이동 중 반복할 액션을 정의합니다.")
    repeat_actions = []
    
    keys = {
        '1': 'LEFT',
        '2': 'RIGHT', 
        '3': 'UP',
        '4': 'DOWN',
        '5': 'ALT',
        '6': 'SHIFT',
        '7': 'SLEEP',
        '8': 'z'
    }
    
    action_types = {
        '1': 'up',
        '2': 'down',
        '3': 'tap'
    }
    
    while True:
        print("\n반복 액션 추가:")
        print("1) ← LEFT")
        print("2) → RIGHT")
        print("3) ↑ UP")
        print("4) ↓ DOWN")
        print("5) ALT (점프)")
        print("6) SHIFT (텔레포트)")
        print("7) SLEEP (대기)")
        print("8) z 키")
        print("9) 특정키")
        print("0) 액션 정의 완료")
        
        key_choice = input("선택: ").strip()
        
        if key_choice == '0':
            break
        
        if key_choice == '9':
            custom_key = input("키 입력 (예: space, x, a, b, c, d): ").strip()
            if not custom_key:
                print("❌ 키가 입력되지 않았습니다")
                continue
            
            action = {
                "key": custom_key,
                "action": "tap",
                "delay": 50
            }
            repeat_actions.append(action)
            print(f"✅ 추가됨: {custom_key} - tap (50ms)")
            continue
        
        if key_choice not in keys:
            print("❌ 잘못된 선택")
            continue
        
        selected_key = keys[key_choice]
        
        if selected_key == 'SLEEP':
            sleep_time = input("대기 시간 (ms, 기본 1000): ").strip()
            if sleep_time:
                try:
                    delay = int(sleep_time)
                except:
                    delay = 1000
            else:
                delay = 1000
            
            action = {
                "key": "SLEEP",
                "action": "sleep",
                "delay": delay
            }
            repeat_actions.append(action)
            print(f"✅ 추가됨: SLEEP - {delay}ms")
            continue
        
        print(f"\n{selected_key} 키 액션:")
        print("1) 떼기 (up)")
        print("2) 누르기 (down)")
        print("3) 눌렀다떼기 (tap)")
        
        action_choice = input("선택: ").strip()
        
        if action_choice not in action_types:
            print("❌ 잘못된 선택")
            continue
        
        selected_action = action_types[action_choice]
        
        delay = 0
        if selected_action == 'tap':
            delay_input = input("tap 지속시간 (ms, 기본 50): ").strip()
            if delay_input:
                try:
                    delay = int(delay_input)
                except:
                    delay = 50
            else:
                delay = 50
        
        action = {
            "key": selected_key,
            "action": selected_action
        }
        if delay > 0:
            action["delay"] = delay
        
        repeat_actions.append(action)
        print(f"✅ 추가됨: {selected_key} - {selected_action}" + (f" ({delay}ms)" if delay > 0 else ""))
    
    if repeat_actions:
        forced_movement_config["repeat_actions"] = repeat_actions
        print(f"\n✅ 반복 액션 {len(repeat_actions)}개 설정됨")
        print("저장된 액션:")
        for i, action in enumerate(repeat_actions, 1):
            if action['action'] == 'sleep':
                print(f"  {i}. SLEEP - {action.get('delay', 0)}ms")
            else:
                print(f"  {i}. {action['key']} - {action['action']}" + 
                      (f" ({action.get('delay', 0)}ms)" if action.get('delay', 0) > 0 else ""))
    
    interval_input = input("\n반복 주기 (ms, 기본 1000): ").strip()
    if interval_input:
        try:
            interval = int(interval_input)
            forced_movement_config["repeat_interval"] = interval
            print(f"✅ 반복 주기: {interval}ms")
        except:
            print("❌ 잘못된 입력, 기본값 사용")
    
    print("\n✅ 강제 이동 모드 설정 완료!")
    print(f"트리거 존: {forced_movement_config['trigger_zones']}")
    print(f"목표 존: {forced_movement_config['target_zone']}")
    print(f"반복 액션: {len(forced_movement_config['repeat_actions'])}개")
    print(f"반복 주기: {forced_movement_config['repeat_interval']}ms")
    redraw()

def renumber_zones():
    global zones, zone_actions, zone_count, zone_cooldowns
    
    if not zones:
        print("❌ Zone이 없습니다")
        return
    
    old_zone_actions = zone_actions.copy()
    old_cooldowns = zone_cooldowns.copy()
    
    zone_actions = {}
    zone_cooldowns = {}
    
    zones.sort(key=lambda z: (z["bbox_640"][1], z["bbox_640"][0]))
    
    id_mapping = {}
    for i, zone in enumerate(zones, 1):
        old_id = zone["id"]
        zone["id"] = i
        zone["name"] = f"Zone {i}"
        id_mapping[old_id] = i
        
        if old_id in old_zone_actions:
            zone_actions[i] = old_zone_actions[old_id]
        
        if old_id in old_cooldowns:
            zone_cooldowns[i] = old_cooldowns[old_id]
    
    zone_count = len(zones)
    print(f"✅ Zone 번호 재정렬 완료 (총 {zone_count}개)")
    redraw()

def save_config():
    global map_id, display_name, scale_to_640, minimap_file_path
    global scroll_enabled, scroll_tracking_files, forced_movement_config
    global monster_model_name
    
    zone_actions_str = {str(k): v for k, v in zone_actions.items()}
    zone_cooldowns_str = {str(k): v for k, v in zone_cooldowns.items()}
    
    minimap_width = roi_x2 - roi_x1
    minimap_height = roi_y2 - roi_y1
    
    config = {
        "id": map_id,
        "display_name": display_name,
        "monstermodelname": monster_model_name,
        "minimap": {
            "file_path": minimap_file_path,
            "left": roi_x1,
            "top": roi_y1,
            "width": minimap_width,
            "height": minimap_height,
            "scale_to_640": scale_to_640
        },
        "scroll_enabled": scroll_enabled,
        "scroll_tracking_files": scroll_tracking_files,
        "forced_movement_config": forced_movement_config,
        "zones": zones,
        "zone_actions": zone_actions_str,
        "zone_cooldowns": zone_cooldowns_str,
        "no_hunt_boxes": no_hunt_boxes,
        "no_teleport_boxes": no_teleport_boxes,
        "resolution": {
            "width": 1920,
            "height": 1080
        }
    }
    
    config_dir = "configs"
    os.makedirs(config_dir, exist_ok=True)
    
    is_new_map = loaded_config is None
    
    if not is_new_map:
        print(f"\n💾 저장 옵션:")
        print("1) 기존 파일 덮어쓰기")
        print("2) 새 이름으로 저장")
        
        choice = input("선택 (기본 1): ").strip() or "1"
        
        if choice == "2":
            new_map_id = input("새 맵 ID: ").strip()
            if not new_map_id:
                print("❌ 맵 ID가 입력되지 않았습니다.")
                return
            
            new_display_name = input("새 맵 이름: ").strip()
            if not new_display_name:
                new_display_name = new_map_id
            
            new_monster_model_name = input("새 몬스터 모델명 (예: 중국): ").strip()
            if not new_monster_model_name:
                new_monster_model_name = new_display_name
            
            config["id"] = new_map_id
            config["display_name"] = new_display_name
            config["monstermodelname"] = new_monster_model_name
            map_id = new_map_id
            display_name = new_display_name
            monster_model_name = new_monster_model_name
    
    config_file = os.path.join(config_dir, f"{map_id}.json")
    
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 설정 저장 완료: {config_file}")
    
    update_maps_json(map_id, display_name, monster_model_name)

def update_maps_json(map_id, display_name, monster_model_name):
    try:
        maps_file = os.path.join(os.path.dirname(__file__), "configs", "maps.json")
        
        if os.path.exists(maps_file):
            with open(maps_file, "r", encoding="utf-8") as f:
                maps_data = json.load(f)
        else:
            maps_data = {"maps": []}
        
        new_map_entry = {
            "id": map_id,
            "name": display_name,
            "monstermodelname": monster_model_name,
            "config_file": f"{map_id}.json"
        }
        
        existing_map = next((m for m in maps_data["maps"] if m["id"] == map_id), None)
        if existing_map:
            existing_map.update(new_map_entry)
            print(f"✅ maps.json에서 맵 '{map_id}' 정보가 업데이트되었습니다.")
        else:
            maps_data["maps"].append(new_map_entry)
            print(f"✅ maps.json에 새 맵 '{map_id}'이 추가되었습니다.")
        
        with open(maps_file, "w", encoding="utf-8") as f:
            json.dump(maps_data, f, ensure_ascii=False, indent=2)
        
        return True
        
    except Exception as e:
        print(f"❌ maps.json 업데이트 실패: {e}")
        return False

def print_help():
    print("\n🎮 조작법:")
    print("=" * 50)
    print("🖱️  마우스:")
    print("   좌클릭 드래그: Zone/박스 생성")
    print("   좌클릭: Zone 선택 (action 모드) / Zone/박스 삭제 (delete 모드)")
    print()
    print("⌨️  키보드:")
    print("   [z] Zone 생성 모드")
    print("   [j] 사냥불가 박스 생성 모드")
    print("   [t] 텔레포트금지 박스 생성 모드")
    print("   [a] Action 지정 모드")
    print("   [o] 쿨다운 설정")
    print("   [f] 강제 이동 모드 설정 ⚡")
    print("   [d] 삭제 모드")
    print("   [n] Zone 번호 재정렬")
    print("   [c] 모든 Zone 삭제")
    print("   [u] 마지막 Zone 삭제 (Undo)")
    print("   [h] 도움말")
    print("   [s] 현재 설정 보기")
    print("   [q] 완료 및 저장")
    print("=" * 50)

print("\n🗺️ Map Layout Tool (MLT)")
print("=" * 50)

print("\n📝 작업 선택:")
print("1) 새로 작성")
print("2) 기존 파일 수정")

while True:
    choice = input("선택 (1-2): ").strip()
    if choice in ['1', '2']:
        break
    print("❌ 1 또는 2를 입력하세요")

if choice == '2':
    if not load_existing_config():
        print("❌ 기존 파일 로드 실패. 종료합니다.")
        sys.exit(1)
else:
    print("\n🎮 새 맵 설정")
    map_id = input("맵 ID (예: china): ").strip()
    if not map_id:
        print("❌ 맵 ID가 입력되지 않았습니다.")
        sys.exit(1)
    
    display_name = input("맵 이름 (예: 중국): ").strip()
    if not display_name:
        display_name = map_id
    
    monster_model_name = input("몬스터 모델명 (예: 중국): ").strip()
    if not monster_model_name:
        monster_model_name = display_name
    
    minimap_file_path = input("\n미니맵 파일 경로 (기본 mm.png): ").strip()
    if not minimap_file_path:
        minimap_file_path = "mm.png"
    
    print("\n미니맵 게임 내 좌표 입력")
    left_input = input("  Left (기본 20): ").strip()
    roi_x1 = int(left_input) if left_input else 20
    
    top_input = input("  Top (기본 170): ").strip()
    roi_y1 = int(top_input) if top_input else 170
    
    right_input = input("  Right (기본 370): ").strip()
    roi_x2 = int(right_input) if right_input else 370
    
    bottom_input = input("  Bottom (기본 391): ").strip()
    roi_y2 = int(bottom_input) if bottom_input else 391
    
    scroll_input = input("\n스크롤 맵입니까? (y/n, 기본 n): ").strip().lower()
    scroll_enabled = scroll_input == 'y'
    
    if scroll_enabled:
        print("\n📜 스크롤 추적 파일 설정 (최대 2개)")
        file1 = input("스크롤 추적 파일 1: ").strip()
        file2 = input("스크롤 추적 파일 2 (선택사항, Enter로 스킵): ").strip()
        
        scroll_tracking_files = []
        if file1:
            scroll_tracking_files.append(file1)
        if file2:
            scroll_tracking_files.append(file2)
    else:
        scroll_tracking_files = []

if not os.path.exists(minimap_file_path):
    print(f"❌ {minimap_file_path} 파일이 없습니다.")
    sys.exit(1)

minimap = cv2.imread(minimap_file_path)
if minimap is None:
    print(f"❌ {minimap_file_path} 파일을 읽을 수 없습니다.")
    sys.exit(1)

print(f"✅ 미니맵 로드 완료")
print(f"   파일: {minimap_file_path}")
print(f"   크기: {minimap.shape[1]} x {minimap.shape[0]}")
print(f"   게임 내 위치: ({roi_x1}, {roi_y1}) ~ ({roi_x2}, {roi_y2})")

minimap_h, minimap_w = minimap.shape[:2]
scale_to_640 = 640.0 / minimap_w
scaled_h = int(minimap_h * scale_to_640)
minimap_640 = cv2.resize(minimap, (640, scaled_h), interpolation=cv2.INTER_LINEAR)

print(f"\n📐 640 기준 확대 비율: {scale_to_640:.2f}배")
print(f"   640 기준 크기: 640 x {scaled_h}")

cv2.namedWindow("Zone Editor", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Zone Editor", 960, int(960 * scaled_h / 640))
cv2.setMouseCallback("Zone Editor", cb_zone)

current_img = minimap_640.copy()
redraw()

print_help()

if choice == '1':
    print("\n🟢 Zone 생성 모드 시작! (드래그로 사각형 그리기)")
else:
    print("\n🎯 맵 수정 모드 시작!")

while True:
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('z'):
        current_mode = "zone"
        selected_action_zone = None
        print("\n🟢 Zone 생성 모드")
        redraw()
    
    elif key == ord('j'):
        current_mode = "nohunt"
        print("\n🚫 사냥불가 박스 생성 모드")
        redraw()
    
    elif key == ord('t'):
        current_mode = "noteleport"
        print("\n🚷 텔레포트금지 박스 생성 모드")
        redraw()
    
    elif key == ord('a'):
        if not zones:
            print("❌ 먼저 Zone을 생성하세요")
            continue
        current_mode = "action"
        print("\n🎯 Action 지정 모드 - Zone을 클릭하세요")
        redraw()
    
    elif key == ord('o'):
        if not zones:
            print("❌ 먼저 Zone을 생성하세요")
            continue
        define_cooldowns()
    
    elif key == ord('f'):
        if not zones:
            print("❌ 먼저 Zone을 생성하세요")
            continue
        define_forced_movement()
    
    elif key == ord('d'):
        current_mode = "delete"
        print("\n🗑️ 삭제 모드 - 클릭하여 삭제")
        redraw()
    
    elif key == ord('n'):
        renumber_zones()
    
    elif key == ord('c'):
        zones = []
        zone_count = 0
        zone_actions = {}
        zone_cooldowns = {}
        forced_movement_config = {
            "enabled": False,
            "trigger_zones": [],
            "target_zone": 1,
            "repeat_actions": [],
            "repeat_interval": 500
        }
        print("\n🗑️ 모든 Zone 삭제됨")
        redraw()
    
    elif key == ord('u'):
        if zones:
            removed_zone = zones.pop()
            zone_id = removed_zone["id"]
            if zone_id in zone_actions:
                del zone_actions[zone_id]
            if zone_id in zone_cooldowns:
                del zone_cooldowns[zone_id]
            if zone_id in forced_movement_config.get("trigger_zones", []):
                forced_movement_config["trigger_zones"].remove(zone_id)
            if zone_id == forced_movement_config.get("target_zone"):
                forced_movement_config["target_zone"] = 1
            zone_count = len(zones) if zones else 0
            print(f"\n↩️ Zone {zone_id} 삭제됨")
            redraw()
    
    elif key == ord('s'):
        print("\n📋 현재 설정:")
        print(f"맵: {map_id} ({display_name})")
        print(f"몬스터 모델명: {monster_model_name}")
        print(f"미니맵 파일: {minimap_file_path}")
        print(f"미니맵: ({roi_x1}, {roi_y1}) ~ ({roi_x2}, {roi_y2})")
        print(f"스크롤 여부: {'활성화' if scroll_enabled else '비활성화'}")
        if scroll_enabled and scroll_tracking_files:
            for i, file in enumerate(scroll_tracking_files):
                print(f"스크롤 추적 파일 {i+1}: {file}")
        print(f"640 확대 비율: {scale_to_640:.2f}")
        print(f"Zone 개수: {len(zones)}")
        for zone in zones:
            bbox = zone["bbox_640"]
            print(f"  Zone {zone['id']}: 640기준[{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]")
        if zone_actions:
            print("액션 설정된 Zone:", list(zone_actions.keys()))
        if no_hunt_boxes:
            print(f"사냥불가 박스: {len(no_hunt_boxes)}개")
            for i, box in enumerate(no_hunt_boxes, 1):
                print(f"  박스 {i}: 640기준[{box[0]}, {box[1]}, {box[2]}, {box[3]}]")
        if no_teleport_boxes:
            print(f"텔레포트금지 박스: {len(no_teleport_boxes)}개")
            for i, box in enumerate(no_teleport_boxes, 1):
                print(f"  박스 {i}: 640기준[{box[0]}, {box[1]}, {box[2]}, {box[3]}]")
        if zone_cooldowns:
            print("쿨다운 설정:", zone_cooldowns)
        if forced_movement_config.get("enabled"):
            print("\n⚡ 강제 이동 모드:")
            print(f"  트리거 존: {forced_movement_config.get('trigger_zones', [])}")
            print(f"  목표 존: {forced_movement_config.get('target_zone', 1)}")
            print(f"  반복 액션: {len(forced_movement_config.get('repeat_actions', []))}개")
            print(f"  반복 주기: {forced_movement_config.get('repeat_interval', 1000)}ms")
    
    elif key == ord('h'):
        print_help()
    
    elif key == ord('q'):
        if not zones:
            print("❌ 최소 1개 이상의 Zone이 필요합니다")
            continue
        
        save_config()
        break

cv2.destroyAllWindows()
print("\n✅ 맵 설정 완료!")