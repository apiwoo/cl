import time
from pynput import keyboard
import threading
from collections import defaultdict
from datetime import datetime

class KeyMonitor:
    def __init__(self):
        self.key_press_count = 0
        self.key_release_count = 0
        self.total_actions = 0
        self.start_time = time.time()
        self.running = True
        self.key_press_details = defaultdict(int)
        self.key_release_details = defaultdict(int)
        self.pressed_keys = set()
        self.lock = threading.Lock()
        self.max_simultaneous = 0
        self.key_events = []
        
    def on_press(self, key):
        timestamp = time.time()
        
        if key == keyboard.Key.esc:
            self.running = False
            return False
            
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key).replace('Key.', '')
            
        with self.lock:
            if key_name not in self.pressed_keys:
                self.pressed_keys.add(key_name)
                self.key_press_count += 1
                self.total_actions += 1
                self.key_press_details[key_name] += 1
                
                current_pressed = len(self.pressed_keys)
                if current_pressed > self.max_simultaneous:
                    self.max_simultaneous = current_pressed
                
                self.key_events.append({
                    'time': timestamp,
                    'type': 'press',
                    'key': key_name,
                    'simultaneous': current_pressed
                })
                
                if len(self.key_events) > 100:
                    self.key_events.pop(0)
        
    def on_release(self, key):
        timestamp = time.time()
        
        try:
            key_name = key.char
        except AttributeError:
            key_name = str(key).replace('Key.', '')
            
        with self.lock:
            if key_name in self.pressed_keys:
                self.pressed_keys.discard(key_name)
                self.key_release_count += 1
                self.total_actions += 1
                self.key_release_details[key_name] += 1
                
                self.key_events.append({
                    'time': timestamp,
                    'type': 'release',
                    'key': key_name,
                    'simultaneous': len(self.pressed_keys)
                })
                
                if len(self.key_events) > 100:
                    self.key_events.pop(0)
        
    def print_stats(self):
        while self.running:
            current_time = time.time()
            elapsed_seconds = current_time - self.start_time
            
            if elapsed_seconds > 0:
                elapsed_minutes = elapsed_seconds / 60
                per_second = self.total_actions / elapsed_seconds
                per_minute = per_second * 60
                per_hour = per_minute * 60
                
                tap_count = min(self.key_press_count, self.key_release_count)
                
                print("\033[2J\033[H")
                print("=== 키입력 모니터 (ESC로 종료) ===")
                print(f"\n경과 시간: {elapsed_minutes:.1f}분 ({elapsed_seconds:.0f}초)")
                print(f"\n총 액션수: {self.total_actions}회 (DOWN: {self.key_press_count}, UP: {self.key_release_count})")
                print(f"TAP 횟수 (DOWN+UP): 약 {tap_count}회")
                print(f"최대 동시 입력: {self.max_simultaneous}개")
                print(f"\n시간당: {per_hour:.0f}회")
                print(f"분당: {per_minute:.1f}회")
                print(f"초당: {per_second:.2f}회")
                
                print(f"\n=== 현재 누르고 있는 키 ({len(self.pressed_keys)}개) ===")
                if self.pressed_keys:
                    print(", ".join(sorted(self.pressed_keys)))
                else:
                    print("없음")
                
                print("\n=== 주요 키 입력 횟수 (Press) ===")
                sorted_keys = sorted(self.key_press_details.items(), key=lambda x: x[1], reverse=True)[:10]
                for key_name, count in sorted_keys:
                    print(f"{key_name}: {count}회")
                
                print("\n=== 최근 이벤트 (최대 3개 동시입력) ===")
                recent_multi = [e for e in self.key_events[-20:] if e['simultaneous'] >= 3]
                for event in recent_multi[-5:]:
                    time_str = datetime.fromtimestamp(event['time']).strftime('%H:%M:%S.%f')[:-3]
                    print(f"{time_str} - {event['type']} {event['key']} (동시: {event['simultaneous']}개)")
                    
                print("\n※ 3개 이상 동시입력이 안되면 키보드 하드웨어 제한일 수 있습니다.")
                    
            time.sleep(0.05)
            
    def start(self):
        stats_thread = threading.Thread(target=self.print_stats, daemon=True)
        stats_thread.start()
        
        print("키입력 모니터링 시작...")
        print("ESC를 누르면 종료됩니다.")
        print("\n※ 일부 키보드는 하드웨어적으로 3개 이상 동시입력을 지원하지 않습니다.")
        print("※ 게이밍 키보드나 N-Key Rollover를 지원하는 키보드를 사용하면 개선됩니다.")
        time.sleep(2)
        
        with keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        ) as listener:
            listener.join()
            
        print(f"\n\n최종 통계:")
        elapsed_seconds = time.time() - self.start_time
        elapsed_minutes = elapsed_seconds / 60
        per_minute = (self.total_actions / elapsed_seconds) * 60 if elapsed_seconds > 0 else 0
        
        print(f"총 시간: {elapsed_minutes:.1f}분")
        print(f"총 액션수: {self.total_actions}회")
        print(f"키 DOWN: {self.key_press_count}회")
        print(f"키 UP: {self.key_release_count}회")
        print(f"분당 평균: {per_minute:.1f}회")
        print(f"최대 동시 입력: {self.max_simultaneous}개")

if __name__ == "__main__":
    monitor = KeyMonitor()
    monitor.start()