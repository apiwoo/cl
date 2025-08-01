import sys
import logging
from config_manager import ConfigManager
from bot_core import BotCore

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    print("🎮 메이플 라이딩 봇 시작")
    print("=" * 50)
    
    try:
        config_manager = ConfigManager()
        config = config_manager.setup_config()
        
        if not config:
            print("❌ 설정 실패")
            sys.exit(1)
        
        bot = BotCore(config)
        bot.run()
        
    except KeyboardInterrupt:
        print("\n⌨️ 사용자 중단")
    except Exception as e:
        logging.error(f"치명적 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n👋 프로그램 종료")

if __name__ == "__main__":
    main()