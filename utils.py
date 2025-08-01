import cv2
import numpy as np
import logging
import os
from datetime import datetime

def setup_logging(log_level=logging.INFO):
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def load_image(path):
    if not os.path.exists(path):
        logging.warning(f"이미지 파일을 찾을 수 없습니다: {path}")
        return None
    
    image = cv2.imread(path)
    if image is None:
        logging.warning(f"이미지 로드 실패: {path}")
    
    return image

def match_template(image, template, threshold=0.8):
    if image is None or template is None:
        return False, None
    
    try:
        result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            return True, max_loc
        else:
            return False, None
    except Exception as e:
        logging.error(f"템플릿 매칭 오류: {e}")
        return False, None

def color_in_range(image, lower, upper):
    if image is None:
        return None
    
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
    return mask

def find_contours(mask, min_area=0, max_area=float('inf')):
    if mask is None:
        return []
    
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    filtered_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            filtered_contours.append(contour)
    
    return filtered_contours

def get_contour_center(contour):
    M = cv2.moments(contour)
    if M["m00"] > 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        return (cx, cy)
    return None

def scale_coordinates(x, y, scale_factor):
    return int(x * scale_factor), int(y * scale_factor)

def point_in_box(point, box):
    x, y = point
    x1, y1, x2, y2 = box
    return x1 <= x <= x2 and y1 <= y <= y2

def calculate_distance(point1, point2):
    x1, y1 = point1
    x2, y2 = point2
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

def save_screenshot(image, prefix="screenshot"):
    if image is None:
        return
    
    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(screenshot_dir, f"{prefix}_{timestamp}.png")
    
    cv2.imwrite(filename, image)
    logging.info(f"스크린샷 저장: {filename}")