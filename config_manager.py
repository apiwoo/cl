import json
import os
import glob

class ConfigManager:
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), "MapleRidingBot", "configs")
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.default_keys = {
            'attack': 'a'
        }
        
        self.default_attack_range = {
            'width': 200,
            'height': 50
        }
    
    def setup_config(self):
        config_files = glob.glob(os.path.join(self.config_dir, "*_config.json"))
        
        if config_files:
            print("\n📁 기존 설정 발견")
            for i, file in enumerate(config_files, 1):
                char_name = os.path.basename(file).replace('_config.json', '')
                print(f"{i}) {char_name}")
            
            use_existing = input("\n기존 설정을 사용하시겠습니까? (y/n, 기본 y): ").strip().lower()
            if use_existing == '' or use_existing == 'y':
                if len(config_files) == 1:
                    return self.load_config(config_files[0])
                else:
                    choice = input(f"선택 (1-{len(config_files)}): ").strip()
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(config_files):
                            return self.load_config(config_files[idx])
                    except:
                        pass
        
        return self.create_new_config()
    
    def create_new_config(self):
        print("\n🆕 새 설정 생성")
        
        print("\n⌨️ 입력 방식 선택")
        print("1) 일반 모드 (PyAutoGUI)")
        print("2) 보안 모드 (Windows API)")
        input_method_choice = input("선택 (기본 1): ").strip()
        if input_method_choice == '2':
            input_method = 'windows_api'
        else:
            input_method = 'pyautogui'
        
        char_data = self.load_characters()
        print("\n🎮 사용 가능한 캐릭터:")
        for i, char_info in enumerate(char_data["characters"], 1):
            print(f"{i}) {char_info['id']} - {char_info['display_name']}")
        
        char_choice = input("\n캐릭터 선택: ").strip()
        try:
            char_idx = int(char_choice) - 1
            if 0 <= char_idx < len(char_data["characters"]):
                selected_char = char_data["characters"][char_idx]
            else:
                selected_char = char_data["characters"][0]
        except:
            selected_char = char_data["characters"][0]
        
        char_name = input("설정 이름 (식별용): ").strip()
        if not char_name:
            char_name = selected_char["id"]
        
        maps_data = self.load_maps()
        print("\n📍 사용 가능한 맵:")
        for i, map_info in enumerate(maps_data["maps"], 1):
            print(f"{i}) {map_info['id']} - {map_info.get('display_name', map_info['name'])}")
        
        map_order = input("\n맵 순서 입력 (예: 1,2,3,4): ").strip()
        if not map_order:
            map_order = "1"
        
        try:
            map_sequence = [int(x.strip()) for x in map_order.split(',')]
        except:
            map_sequence = [1]
        
        print("\n⌨️ 키 설정 (Enter로 기본값 사용)")
        
        attack_keys = {}
        print("\n🎯 공격키 설정")
        key = input(f"공격키 (기본 {self.default_keys['attack']}): ").strip()
        if not key:
            key = self.default_keys['attack']
        
        delay = input("공격키 후딜레이 (ms, 기본 1000): ").strip()
        if not delay or not delay.isdigit():
            delay = 1000
        else:
            delay = int(delay)
        
        attack_keys["attack"] = {"key": key, "delay": delay}
        
        print("\n🎯 사냥 설정")
        hunting_direction = input("사냥 방향 (1: 진행방향만, 2: 전체범위, 기본 1): ").strip()
        if hunting_direction == '2':
            hunting_direction = "full_range"
        else:
            hunting_direction = "movement_only"
        
        look_at_monster = input("몬스터를 바라보고 스킬 시전? (y/n, 기본 y): ").strip().lower()
        look_at_monster = look_at_monster != 'n'
        
        attack_hold_mode = input("공격키를 누른 채로 유지? (y/n, 기본 y): ").strip().lower()
        attack_hold_mode = attack_hold_mode != 'n'
        
        use_teleport = input("텔레포트 사용? (y/n, 기본 n): ").strip().lower()
        use_teleport = use_teleport == 'y'
        
        monster_confidence = input("몬스터 탐지 신뢰도 (0.0~1.0, 기본 0.25): ").strip()
        try:
            monster_confidence = float(monster_confidence)
            if monster_confidence < 0.0 or monster_confidence > 1.0:
                monster_confidence = 0.25
        except:
            monster_confidence = 0.25
        
        print("\n🎯 공격범위 설정")
        attack_width = input(f"공격범위 너비 (기본 {self.default_attack_range['width']}): ").strip()
        if attack_width and attack_width.isdigit():
            attack_width = int(attack_width)
        else:
            attack_width = self.default_attack_range['width']
        
        attack_height = input(f"공격범위 높이 (기본 {self.default_attack_range['height']}): ").strip()
        if attack_height and attack_height.isdigit():
            attack_height = int(attack_height)
        else:
            attack_height = self.default_attack_range['height']
        
        buffs_data = self.load_buffs()
        print("\n💊 사용 가능한 버프:")
        for i, buff_info in enumerate(buffs_data["buffs"], 1):
            print(f"{i}) {buff_info['id']} - {buff_info['display_name']}")
        
        buff_choice = input("\n버프 선택: ").strip()
        try:
            buff_idx = int(buff_choice) - 1
            if 0 <= buff_idx < len(buffs_data["buffs"]):
                buff_config_path = buffs_data["buffs"][buff_idx]["config_path"]
            else:
                buff_config_path = buffs_data["buffs"][0]["config_path"]
        except:
            buff_config_path = buffs_data["buffs"][0]["config_path"]
        
        config = {
            "char_name": char_name,
            "input_method": input_method,
            "character_info": {
                "id": selected_char["id"],
                "display_name": selected_char["display_name"],
                "model_path": selected_char["model_path"],
                "alert_audio": selected_char["alert_audio"]
            },
            "map_sequence": map_sequence,
            "attack_keys": attack_keys,
            "hunting_config": {
                "hunting_direction": hunting_direction,
                "look_at_monster": look_at_monster,
                "attack_hold_mode": attack_hold_mode,
                "monster_confidence": monster_confidence,
                "use_teleport": use_teleport
            },
            "attack_range": {
                "width": attack_width,
                "height": attack_height
            },
            "buff_config_path": buff_config_path
        }
        
        self.save_config(config)
        return config
    
    def load_characters(self):
        char_file = os.path.join("configs", "char.json")
        with open(char_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load_maps(self):
        maps_file = os.path.join("configs", "maps.json")
        with open(maps_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def load_buffs(self):
        buffs_file = os.path.join("configs", "buffs.json")
        with open(buffs_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def save_config(self, config):
        config_file = os.path.join(self.config_dir, f"{config['char_name']}_config.json")
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 설정 저장: {config_file}")
    
    def load_config(self, config_file):
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        if 'input_method' not in config:
            config['input_method'] = 'pyautogui'
        print(f"\n✅ 설정 로드: {config['char_name']}")
        return config