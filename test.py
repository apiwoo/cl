import time
import logging
import json
import os
from config_manager import ConfigManager
from screen_capture import ScreenCapture
from yellow_dot_tracker import YellowDotTracker
from scroll_tracker import ScrollTracker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)

def main():
    print("🟡 노란점 위치 테스트")
    print("=" * 50)
    
    config_manager = ConfigManager()
    config = config_manager.setup_config()
    
    if not config:
        print("❌ 설정 실패")
        return
    
    with open(os.path.join("configs", "maps.json"), "r", encoding="utf-8") as f:
        maps_data = json.load(f)
    
    map_sequence = config['map_sequence']
    current_map_idx = map_sequence[0]
    map_info = maps_data["maps"][current_map_idx - 1]
    
    config_file = os.path.join("configs", map_info["config_file"])
    with open(config_file, "r", encoding="utf-8") as f:
        map_config = json.load(f)
    
    minimap_info = map_config.get("minimap", {})
    screen_capture = ScreenCapture(minimap_info)
    
    scroll_tracker = ScrollTracker()
    scroll_tracker.update_map_config(map_config)
    
    yellow_dot_tracker = YellowDotTracker(
        screen_capture,
        map_config,
        scroll_tracker
    )
    
    if not screen_capture.start():
        logging.error("화면 캡처 시작 실패")
        return
    
    yellow_dot_tracker.start()
    
    print(f"맵: {map_config.get('display_name', 'Unknown')}")
    print(f"미니맵 크기: {minimap_info.get('width')}x{minimap_info.get('height')}")
    print(f"640 스케일: {minimap_info.get('scale_to_640', 1.0):.2f}x")
    print("노란점 위치 확인 중... (Ctrl+C로 종료)")
    print("-" * 50)
    
    try:
        while True:
            yellow_pos = yellow_dot_tracker.get_yellow_dot_position()
            
            if yellow_pos:
                x, y = yellow_pos
                if x < 320:
                    position = "왼쪽"
                else:
                    position = "오른쪽"
                print(f"노란점 위치: ({x}, {y}) - 중앙 기준 {position}")
            else:
                print("노란점을 찾을 수 없음")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n테스트 종료")
    finally:
        screen_capture.stop()
        yellow_dot_tracker.stop()

if __name__ == "__main__":
    main()