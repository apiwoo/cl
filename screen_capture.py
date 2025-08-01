import threading
import queue
import time
import mss
import numpy as np
import pygetwindow as gw
import logging

class ScreenCapture:
    def __init__(self, minimap_info=None):
        self.running = False
        self.thread = None
        self.minimap_queue = queue.Queue(maxsize=5)
        self.main_queue = queue.Queue(maxsize=5)
        self.game_window = None
        self._find_game_window()
        self.update_minimap_info(minimap_info)
    
    def update_minimap_info(self, minimap_info):
        if minimap_info:
            self.minimap_left = minimap_info.get("left", 20)
            self.minimap_top = minimap_info.get("top", 170)
            self.minimap_width = minimap_info.get("width", 350)
            self.minimap_height = minimap_info.get("height", 221)
        else:
            self.minimap_left = 20
            self.minimap_top = 170
            self.minimap_width = 350
            self.minimap_height = 221
    
    def _find_game_window(self):
        wins = gw.getWindowsWithTitle("Mapleland")
        if wins:
            self.game_window = wins[0]
            logging.info(f"✅ 게임 창 찾음: {self.game_window.width}x{self.game_window.height}")
            logging.info(f"  → 위치: ({self.game_window.left}, {self.game_window.top})")
        else:
            logging.error("❌ Mapleland 창을 찾을 수 없습니다")
            self.game_window = None
    
    def start(self):
        if not self.game_window:
            logging.error("❌ 게임 창이 없어서 화면 캡처를 시작할 수 없습니다")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        logging.info("📷 화면 캡처 스레드 시작")
        return True
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            logging.info("📷 화면 캡처 스레드 종료")
    
    def get_minimap(self, timeout=0.1):
        try:
            return self.minimap_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_main_frame(self, timeout=0.1):
        try:
            return self.main_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def _capture_loop(self):
        minimap_region = {
            "left": self.game_window.left + self.minimap_left,
            "top": self.game_window.top + self.minimap_top,
            "width": self.minimap_width,
            "height": self.minimap_height
        }
        
        game_region = {
            "left": self.game_window.left,
            "top": self.game_window.top,
            "width": self.game_window.width,
            "height": self.game_window.height
        }
        
        logging.info(f"📷 캡처 영역 설정 완료")
        logging.info(f"  → 게임 영역: {game_region}")
        logging.info(f"  → 미니맵 영역: {minimap_region}")
        
        frame_count = 0
        
        with mss.mss() as sct:
            while self.running:
                try:
                    minimap_shot = sct.grab(minimap_region)
                    minimap_frame = np.array(minimap_shot)[:, :, :3].copy()
                    
                    main_shot = sct.grab(game_region)
                    main_frame = np.array(main_shot)[:, :, :3].copy()
                    
                    try:
                        self.minimap_queue.put_nowait(minimap_frame)
                    except queue.Full:
                        try:
                            self.minimap_queue.get_nowait()
                            self.minimap_queue.put_nowait(minimap_frame)
                        except:
                            pass
                    
                    try:
                        self.main_queue.put_nowait(main_frame)
                    except queue.Full:
                        try:
                            self.main_queue.get_nowait()
                            self.main_queue.put_nowait(main_frame)
                        except:
                            pass
                    
                    frame_count += 1
                    if frame_count == 1:
                        logging.info("📷 첫 프레임 캡처 성공")
                    
                except Exception as e:
                    logging.error(f"캡처 오류: {e}")
                
                time.sleep(0.016)
        
        logging.info(f"📷 캡처 스레드 종료 (총 {frame_count}개 프레임 캡처)")