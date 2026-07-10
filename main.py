# main.py - 메인 시스템
from __future__ import annotations
import os
import sys
import signal
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import traceback
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands, tasks

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))
# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 설정 클래스
class Config:
    """봇 설정 관리 클래스"""
    # Discord 설정
    DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    # 환경 설정
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'production')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # 디렉토리 설정
    LOGS_DIR: Path = PROJECT_ROOT / 'logs'
    DATA_DIR: Path = PROJECT_ROOT / 'data'
    BACKUP_DIR: Path = PROJECT_ROOT / 'backups'
    TEMP_DIR: Path = PROJECT_ROOT / 'temp'
    
    # 길드 설정 (서버 제한 기능 - 허용된 서버만)
    MAIN_GUILD_IDS_STR: str = os.getenv('MAIN_GUILD_IDS', '')
    MAIN_GUILD_IDS: List[int] = [int(gid.strip()) for gid in MAIN_GUILD_IDS_STR.split(',') if gid.strip()]
    
    # 서버 제한 설정 추가
    ENABLE_GUILD_RESTRICTION: bool = os.getenv('ENABLE_GUILD_RESTRICTION', 'True').lower() in ('true', '1', 'yes')
    AUTO_LEAVE_UNAUTHORIZED: bool = os.getenv('AUTO_LEAVE_UNAUTHORIZED', 'True').lower() in ('true', '1', 'yes')
    
    # 성능 설정
    MAX_MESSAGES_PER_GUILD: int = 1000
    MAX_MEMBERS_PER_GUILD: int = 10000
    COMMAND_TIMEOUT: int = 30

    # 새로운 시스템 설정
    ENABLE_EXIT_LOGGER: bool = os.getenv('ENABLE_EXIT_LOGGER', 'True').lower() in ('true', '1', 'yes')
    ENABLE_ENHANCED_UPDATES: bool = os.getenv('ENABLE_ENHANCED_UPDATES', 'False').lower() in ('true', '1', 'yes')
    
    @classmethod
    def validate(cls) -> bool:
        """설정 유효성 검사"""
        if not cls.DISCORD_TOKEN:
            print("❌ DISCORD_TOKEN이 설정되지 않았습니다.")
            print("💡 .env 파일에 DISCORD_TOKEN=your_token_here 형태로 추가해주세요.")
            return False
        
        # 필요한 디렉토리 생성
        for directory in [cls.LOGS_DIR, cls.DATA_DIR, cls.BACKUP_DIR, cls.TEMP_DIR]:
            directory.mkdir(exist_ok=True)

        # 길드 설정 확인
        if cls.MAIN_GUILD_IDS:
            print(f"🏠 설정된 허용 서버: {len(cls.MAIN_GUILD_IDS)}개")
            for i, guild_id in enumerate(cls.MAIN_GUILD_IDS, 1):
                print(f"   서버 {i}: {guild_id}")
        else:
            print("⚠️ 허용 서버가 설정되지 않았습니다. 모든 서버에서 동작합니다.")
        
        # ✅ 서버 제한 설정 확인
        if cls.ENABLE_GUILD_RESTRICTION:
            print(f"🔒 서버 제한 기능: 활성화")
            print(f"🚪 무허가 서버 자동 퇴장: {'활성화' if cls.AUTO_LEAVE_UNAUTHORIZED else '비활성화'}")
        else:
            print(f"🔒 서버 제한 기능: 비활성화")
        return True

# 로깅 시스템 설정
def setup_logging() -> logging.Logger:
    """개선된 로깅 시스템 설정"""
    # 로그 레벨 설정
    log_level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
 
    # 로그 포맷터
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )    
    
    # 파일 핸들러 (중복 선언을 제거하고 깔끔하게 하나로 통일)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        Config.LOGS_DIR / 'bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # 콘솔 핸들러    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # UTF-8 인코딩 설정 (이모지 지원)
    try:
        console_handler.stream.reconfigure(encoding='utf-8')
    except AttributeError:
        pass  # 일부 환경에서 미지원

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    logging.getLogger('discord').setLevel(logging.WARNING)
    return logging.getLogger('main')

# 확장 모듈 존재 여부 체크
def check_extension_exists(extension_name: str) -> bool:
    """확장 모듈이 존재하는지 확인"""
    try:
        file_path = PROJECT_ROOT / f"{extension_name.replace('.', '/')}.py" if '.' in extension_name else PROJECT_ROOT / f"{extension_name}.py"
        return file_path.exists()
    except Exception: return False

def check_extension_has_setup(extension_name: str) -> bool:
    """확장 모듈에 setup 함수가 있는지 확인"""
    try:
        file_path = PROJECT_ROOT / f"{extension_name.replace('.', '/')}.py" if '.' in extension_name else PROJECT_ROOT / f"{extension_name}.py"
        if not file_path.exists(): return False
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return 'async def setup(' in content or 'def setup(' in content
    except Exception: return False

# 사용 가능한 확장 모듈 검색
def get_available_extensions() -> Dict[str, List[str]]:
    """사용 가능한 확장 모듈들을 카테고리별로 자동 검증 및 분류"""
    
    # 1. 카테고리별 코그(Cog) 파일 명단 정의
    categories = {
        "핵심 시스템": [
            'database_manager',          #  [시스템]  데이터베이스 관리 매니저
            'point_manager',             # [서버관리] 포인트 관리
            'exchange_system',           #  [편의성]  경험치, 머니 교환
            'xp_leaderboard',            # [서버관리] 경험치 관리
            'leaderboard_system',        # [서버관리] 통합 리더보드
            'attendance_master',         #  [편의성]  서버 출석
            'voice_tracker',             #  [시스템]  음성 추적
            'improved_post_delete',      # [서버관리] 글 삭제
            'help_command',              #  [시스템]  도움말
            'update_system',             # [서버관리] 공지 업로드
            'improved_user_management',  # [서버관리] 사용자 관리
            'warning',                   # [서버관리] 경고제도
        ],
        "게임 시스템": [
            'lottery_system',            #   [게임]   로또
            'horse_racing',              #   [게임]   경마
            'enhancement_system',        #   [게임]   강화
            'slot_machine',              #   [게임]   슬롯머신
            'blackjack',                 #   [게임]   블랙잭
            'dice_game',                 #   [게임]   주사위
            #'yabawi_game',              #   [게임]   야바위 게임 (임시중단)
            #'rock_paper_scissors',      #   [게임]   가위바위보 (임시중단)   
            'odd_even_game',             #   [게임]   홀짝
            'fishing',                   #   [게임]   낚시
        ],
        "관리 도구": [
            'tax_system',                # [서버관리] 세금
            'role_reward_system',        # [서버관리] 레벨별 역할 지급
            'welcome_system',            # [서버관리] 환영인사
            'anonymous',                 #  [편의성]  익명 채팅
            'sticky_memo',               # [서버관리] 접착 메모
            'room_manager',              #  [편의성]  대화방 설정
        ],
        "유틸리티": [
            'channel_config',            # [서버관리] 명령어 채널 지정
            'common_utils',              #  [시스템]  공통 유틸리티
            'statistics_system',         #   [게임]   통계
            'error_handler',             #  [시스템]  에러 처리
            'birthday',                  #  [편의성]  생일
        ],
        "새로운 시스템": []
    }
    
    # 2. .env 환경설정 값에 따른 선택적 로드 모듈 분기 추가
    if Config.ENABLE_EXIT_LOGGER:
        categories["새로운 시스템"].append('member_exit_logger')  # 퇴장인사
    if Config.ENABLE_ENHANCED_UPDATES:
        categories["새로운 시스템"].append('update_system_enhanced')
        
    # 3. 최종 반환용 딕셔너리 및 파일 실물 유효성 검증 루프
    valid_extensions = {key: [] for key in categories.keys()}
    
    for category_name, extension_list in categories.items():
        for extension in extension_list:
            # 파일이 존재하고 내부의 setup 함수 규격이 온전한 경우에만 봇에 로드하도록 필터링
            if check_extension_exists(extension) and check_extension_has_setup(extension):
                valid_extensions[category_name].append(extension)
                
    return valid_extensions

class EnhancedBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
        self.is_synced = False 
        self.startup_time: Optional[datetime] = None
        self.logger = logging.getLogger('enhanced_bot')
        self.update_system_available = False
        self.exit_logger_available = False
        self.command_usage: Dict[str, int] = {}
        self.error_count: int = 0
        self.backup_system = None

        super().__init__(
            command_prefix="IGNORE_PREFIX",
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
            # 시작할 때 보여줄 초기 상태
            activity=discord.CustomActivity(name="시스템 부팅 중... 🕒"),
            status=discord.Status.online
        )

    @tasks.loop(minutes=30)
    async def update_daily_status(self):
        """오늘 날짜와 시간대별 인삿말을 상태 메시지에 표시"""
        KST = timezone(timedelta(hours=9))
        now = datetime.now(KST)
        date_str = now.strftime("%m/%d")
        hour = now.hour
        
        if 5 <= hour < 9: greeting = "“행운으로 시작하는 하루”"
        elif 9 <= hour < 12: greeting = "“오전 오픈”"
        elif 12 <= hour < 13: greeting = "“여유로운 점심 시간”"
        elif 13 <= hour < 18: greeting = "“오후 시장 준비”"
        elif 18 <= hour < 20: greeting = "“저녁 암시장 오픈”"
        elif 20 <= hour < 23: greeting = "“암거래 시작”"
        else: greeting = "“새벽 밀수 중”"

        await self.change_presence(activity=discord.CustomActivity(name=f"📅{date_str} | {greeting} | (v1.12.1)"), status=discord.Status.online)

    @update_daily_status.before_loop
    async def before_daily_status(self):
        await self.wait_until_ready()

    async def on_guild_join(self, guild: discord.Guild):
        """새로운 서버 참여 시 허가 여부 확인"""
        self.logger.info(f"📥 새로운 서버 참여: {guild.name} (ID: {guild.id})")
        
        # 서버 제한 기능이 비활성화되어 있으면 그냥 진행
        if not Config.ENABLE_GUILD_RESTRICTION:
            self.logger.info(f"✅ 서버 제한 기능 비활성화됨 - {guild.name}에서 계속 활동")
            return
        
        # 허용된 서버 목록 확인
        if guild.id not in Config.MAIN_GUILD_IDS:
            self.logger.warning(f"❌ 무허가 서버 참여 감지: {guild.name} (ID: {guild.id})")
            
            # 서버 소유자나 관리자에게 알림 전송 시도
            try:
                if guild.system_channel:
                    embed = discord.Embed(
                        title="❌ 허가되지 않은 서버",
                        description=f"안녕하세요! **보석상**은 현재 특정 서버에서만 운영되고 있습니다.",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="📝 안내사항",
                        value="• 이 봇은 사설 서버 전용입니다\n• 무허가 사용은 허용되지 않습니다\n• 문의사항은 봇 개발자에게 연락해주세요",
                        inline=False
                    )
                    embed.add_field(
                        name="⏰ 자동 퇴장",
                        value="10초 후 자동으로 서버에서 나가겠습니다.",
                        inline=False
                    )
                    embed.set_footer(text="보석상 v1.12.1 - 서버 제한 시스템")
                    
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                self.logger.error(f"❌ 무허가 서버 알림 전송 실패 ({guild.name}): {e}")
            
            # 자동 퇴장 기능이 활성화되어 있으면 퇴장
            if Config.AUTO_LEAVE_UNAUTHORIZED:
                await asyncio.sleep(10)  # 10초 대기 후 퇴장
                try:
                    await guild.leave()
                    self.logger.info(f"🚪 무허가 서버 자동 퇴장 완수: {guild.name}")
                except Exception as e: self.logger.error(f"자동 퇴장 실패: {e}")

    async def on_guild_remove(self, guild: discord.Guild):
        self.logger.info(f"👋 서버 퇴장: {guild.name} (ID: {guild.id})")
        try:
            app_info = await self.application_info()
            owner = app_info.owner
            if owner:
                embed = discord.Embed(
                    title="ℹ️ 봇이 서버에서 나갔습니다.",
                    description=f"**서버명**: {guild.name}\n"
                                f"**서버 ID**: `{guild.id}`",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(KST)
                )
                await owner.send(embed=embed)
        except Exception as e:
            self.logger.error(f"❌ 봇 소유자에게 알림 전송 실패: {e}")
    
    async def load_extensions(self):
        """사용 가능한 확장 모듈 로드"""
        available_extensions = get_available_extensions()
        priority_order = ["핵심 시스템", "새로운 시스템", "게임 시스템", "관리 도구", "유틸리티"]
        
        # 💡 누락되었던 카운터 초기값 선언 (NameError 방지)
        total_loaded = 0
        total_failed = 0
        
        for category in priority_order:
            extensions = available_extensions.get(category, [])
            if not extensions:
                continue
                
            self.logger.info(f"🔍 {category} 로딩 중...")
            
            for extension in extensions:
                try:
                    await self.load_extension(extension)
                    self.logger.info(f"  ✅ {extension}")
                    total_loaded += 1
                    
                    if extension == 'update_system':
                        self.update_system_available = True
                        self.logger.info("  🔄 실시간 업데이트 시스템 활성화")
                    elif extension == 'member_exit_logger':
                        self.exit_logger_available = True
                        self.logger.info("  👋 퇴장 로그 시스템 활성화")
                        
                except Exception as e:
                    self.logger.error(f"  ❌ {extension}: {e}")
                    total_failed += 1
        
        self.logger.info(f"📊 확장 모듈 로딩 완료: ✅{total_loaded}개 성공, ❌{total_failed}개 실패")
        if total_failed > 0:
            self.logger.warning(f"⚠️ 일부 기능이 제한될 수 있습니다.")
    
    async def setup_hook(self):
        self.startup_time = datetime.now(KST)
        if not self.update_daily_status.is_running():
            self.update_daily_status.start()

        await self.load_extensions()

        # ⚠️ 전역 삭제
        # self.tree.clear_commands(guild=None) 
        # await self.tree.sync() 
        
    async def on_ready(self):
        """봇 준비 완료 시 실행"""
        self.logger.info(f"✅ {self.user} (으)로 로그인 성공!")
        self.logger.info(f"🏠 현재 {len(self.guilds)}개의 서버에 연결됨.")
        
        print("=" * 50)
        print(f"🎉 보석상(v1.12.1) 시스템 가동 성공 (60초 후 백그라운드 명령어 동기화 예정)")
        print(f"✨ {self.user} | {len(self.guilds)}개 서버")
        print("=" * 50)
        
        # 💡 [교정] setup_hook에서 연사되던 무거운 동기화 구문을 온전하게 비동기 스케줄러 테스크로 위임
        if not self.is_synced:
            asyncio.create_task(self.delayed_sync(60))

    async def delayed_sync(self, delay: int):
        """지정된 시간(초) 후에 명령어를 안전 지연 동기화합니다."""
        self.logger.info(f"⏳ 안전 규격에 의거 {delay}초 대기 후 동기화를 수행합니다...")
        await asyncio.sleep(delay)
        
        try:
            if Config.MAIN_GUILD_IDS:
                self.logger.info(f"🔧 설정된 {len(Config.MAIN_GUILD_IDS)}개의 서버에 명령어 동기화 중...")
                for guild_id in Config.MAIN_GUILD_IDS:
                    guild = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                self.logger.info(f"지정된 서버 {len(Config.MAIN_GUILD_IDS)}개 동기화 완료.")
            else:
                self.logger.info("🤔 모든 연결된 서버에 명령어를 동기화 중...")
                synced_count = 0
                for guild in self.guilds:
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                self.logger.info(f"🔄 {synced_count}개의 서버 동기화 완료.")
            
            self.is_synced = True # 한 번 실행 후 플래그 변경
            self.logger.info("✨ 모든 명령어 동기화 프로세스가 완료되었습니다.")
            
        except Exception as e:
            self.logger.error(f"❌ 명령어 동기화 중 오류 발생: {e}")

# 신호 핸들러 설정
def setup_signal_handlers(bot: EnhancedBot):
    """우아한 종료를 위한 신호 핸들러 설정"""
    def signal_handler(signum, frame):
        print(f"\n🛑 외부 강제 강등 신호 수신, 봇 시스템을 우아하게 차단합니다...")
        asyncio.create_task(bot.close())
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# 메인 실행 함수
async def main():
    """메인 실행 함수"""
    
    # 설정 검증
    if not Config.validate(): sys.exit(1)

    # 로깅 설정
    logger = setup_logging()

    # 봇 인스턴스 생성
    bot = EnhancedBot()
    
    # 신호 핸들러 설정
    setup_signal_handlers(bot)
    
    try:
        logger.info("🚀 보석상 v1.12.1 향상된 업데이트 시스템 시작 중...")
        
        # 봇 시작
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
            
    except discord.LoginFailure:
        logger.error("❌ 토큰 인증에 실패했습니다. 환경 변수 스펙을 재확인하세요.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 예상치 못한 크래시: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    # 환경 변수 로드
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ .env 파일 로드 성공")
    except ImportError:
        print("⚠️ python-dotenv 패키지가 설치되지 않았습니다.")
        print("💡 pip install python-dotenv 명령어로 설치하세요.")
    except Exception as e:
        print(f"⚠️ .env 파일 로드 실패: {e}")
    
    # 봇 실행
    asyncio.run(main())