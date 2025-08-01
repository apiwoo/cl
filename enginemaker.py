import os
from pathlib import Path
from ultralytics import YOLO

def find_pt_files_without_engine():
    pt_files = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.pt'):
                pt_path = os.path.join(root, file)
                engine_path = pt_path.replace('.pt', '.engine')
                if not os.path.exists(engine_path):
                    pt_files.append(pt_path)
    return pt_files

def display_files(files):
    print("\n.engine 파일이 없는 .pt 파일 목록:")
    for i, file in enumerate(files, 1):
        print(f"{i}. {file}")

def get_user_selection(max_num):
    selection = input(f"\n변환할 파일 번호를 입력하세요 (예: 1,2,3,4,6,7): ")
    try:
        numbers = [int(x.strip()) for x in selection.split(',')]
        valid_numbers = [n for n in numbers if 1 <= n <= max_num]
        return valid_numbers
    except:
        return []

def convert_to_engine(pt_files, selected_indices):
    for idx in selected_indices:
        pt_file = pt_files[idx - 1]
        print(f"\n변환 중: {pt_file}")
        
        try:
            model = YOLO(pt_file)
            model.export(
                format='engine',
                device=0,
                half=True,
                imgsz=640
            )
            print(f"완료: {pt_file} -> {pt_file.replace('.pt', '.engine')}")
        except Exception as e:
            print(f"오류 발생: {pt_file}")
            print(f"에러: {e}")

def main():
    pt_files = find_pt_files_without_engine()
    
    if not pt_files:
        print("변환할 .pt 파일이 없습니다.")
        return
    
    display_files(pt_files)
    selected = get_user_selection(len(pt_files))
    
    if not selected:
        print("선택된 파일이 없습니다.")
        return
    
    print(f"\n선택된 파일: {selected}")
    confirm = input("변환을 시작하시겠습니까? (y/n): ")
    
    if confirm.lower() == 'y':
        convert_to_engine(pt_files, selected)
        print("\n모든 변환 작업이 완료되었습니다.")
    else:
        print("취소되었습니다.")

if __name__ == "__main__":
    main()