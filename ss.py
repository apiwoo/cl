import cv2
import numpy as np
import mss
import time
import pygetwindow as gw

def capture_screenshots():
    windows = gw.getWindowsWithTitle('Mapleland')
    if not windows:
        print("❌ Mapleland 창을 찾을 수 없습니다")
        return
        
    game_window = windows[0]
    print(f"✅ 게임 창 찾음: {game_window.title}")
    
    regions = [
        {"name": "region1", "x1": 20, "y1": 170, "x2": 285, "y2": 274}
    ]

    with mss.mss() as sct:
        monitor = {
            'left': game_window.left,
            'top': game_window.top,
            'width': game_window.width,
            'height': game_window.height
        }
        
        screenshot = sct.grab(monitor)
        img = np.array(screenshot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        timestamp = int(time.time())
        
        for i, region in enumerate(regions, 1):
            x1, y1, x2, y2 = region["x1"], region["y1"], region["x2"], region["y2"]
            
            cropped = img[y1:y2, x1:x2]
            
            filename = f"capture_{i}_{timestamp}.png"
            cv2.imwrite(filename, cropped)
            print(f"✅ {filename} 저장 완료 - 크기: {x2-x1}x{y2-y1}")
        
        full_filename = f"mapleland_capture_{timestamp}.png"
        cv2.imwrite(full_filename, img)
        print(f"✅ {full_filename} 메이플랜드 전체 화면 저장 완료")

if __name__ == "__main__":
    capture_screenshots()