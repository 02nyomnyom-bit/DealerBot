# main.py
from __future__ import annotations
import os
import sys
import signal
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import traceback
import psutil
from datetime import datetime, timezone
import discord
from discord.ext import commands, tasks
from discord import app_commands, Member

# 프로젝트 루트 디렉토리 설정
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ✅ 설정 클래스 (서버 제한 기능 강화)
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
    
    # ✅ 메인 길드 설정 (서버 제한 기능 - 허용된 서버만)
    MAIN_GUILD_IDS_STR: str = os.getenv('MAIN_GUILD_IDS', '')
    MAIN_GUILD_IDS: List[int] = [int(gid.strip()) for gid in MAIN_GUILD_IDS_STR.split(',') if gid.strip()]
    
    # ✅ 서버 제한 설정 추가
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
        
        # 기존 시스템 설정 확인
        print(f"🔧 퇴장 로그 시스템: {'활성화' if cls.ENABLE_EXIT_LOGGER else '비활성화'}")
        print(f"🔧 강화된 업데이트 시스템: {'활성화' if cls.ENABLE_ENHANCED_UPDATES else '비활성화'}")
        
        return True

# ✅ 로깅 시스템 설정
def setup_logging() -> logging.Logger:
    """개선된 로깅 시스템 설정"""
    
    # 로그 레벨 설정
    log_level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
    
    # 로그 포맷터
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)-15s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 파일 핸들러 (회전 로그)
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
    
    # Discord 라이브러리 로그 레벨 조정
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.WARNING)
    
    return logging.getLogger('main')

# ✅ 확장 모듈 존재 여부 체크 함수
def check_extension_exists(extension_name: str) -> bool:
    """확장 모듈이 존재하는지 확인"""
    try:
        # 점(.)이 포함된 경우 경로로 변환 (예: admin.user_management -> admin/user_management.py)
        if '.' in extension_name:
            file_path = PROJECT_ROOT / f"{extension_name.replace('.', '/')}.py"
        else:
            file_path = PROJECT_ROOT / f"{extension_name}.py"
        
        return file_path.exists()
    except Exception as e:
        # 디버깅을 위해 로그 추가
        logging.getLogger('main').debug(f"확장 모듈 체크 오류 ({extension_name}): {e}")
        return False

def check_extension_has_setup(extension_name: str) -> bool:
    """확장 모듈에 setup 함수가 있는지 확인"""
    try:
        # 점(.)이 포함된 경우 경로로 변환
        if '.' in extension_name:
            file_path = PROJECT_ROOT / f"{extension_name.replace('.', '/')}.py"
        else:
            file_path = PROJECT_ROOT / f"{extension_name}.py"
        
        if not file_path.exists():
            return False
        
        # 파일 내용에서 setup 함수 확인
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return 'async def setup(' in content or 'def setup(' in content
    except Exception:
        return False

# ✅ 사용 가능한 확장 모듈 검색
def get_available_extensions() -> Dict[str, List[str]]:
    """사용 가능한 확장 모듈들을 카테고리별로 반환"""
    
    # 핵심 시스템 (우선 로드)
    core_extensions = [
        'database_manager',          # 데이터베이스 관리
        'point_manager',             # 포인트 시스템
        'exchange_system',           # 교환 시스템
        'xp_leaderboard',            # XP 리더보드
        'leaderboard_system',        # 통합리더보드
        'attendance_master',         # 출석 시스템
        'voice_tracker',             # 음성 추적
        'improved_post_delete',      # 글 삭제
        'help_command',              # 도움말
        'update_system',             # 업데이트 시스템
        'improved_user_management',  # 향상된 사용자 관리
    ]
    
    # 게임 시스템
    game_extensions = [
        'horse_racing',              # 경마 게임
        'enhancement_system',        # 강화 시스템
        'slot_machine',              # 슬롯머신
        'blackjack',                 # 블랙잭
        'dice_game',                 # 주사위 게임
        'yabawi_game',               # 야바위 게임
        "rock_paper_scissors",       # 가위바위보
        'odd_even_game',             # 홀짝 
        'ladder_game',               # 사다리타기
    ]
    
    # 관리 도구
    admin_extensions = [
        'tax_system',                # 세금 시스템
        'role_reward_system',        # 역할 보상 시스템
        'welcome_system',            # 환영 시스템
    ]
    
    # 유틸리티
    utility_extensions = [
        'common_utils',              # 공통 유틸리티
        'database_manager',          # 데이터베이스 관리
        'utility_commands',          # 유틸리티 명령어
        'error_handler',             # 통합 에러 처리 시스템
        'anonymous',  # ✅ 익명 시스템 추가
    ]
    
    # ✨ 새로운 시스템들 (선택적 로드)
    new_extensions = []
    if Config.ENABLE_EXIT_LOGGER:
        new_extensions.append('member_exit_logger')  # 퇴장 로그 시스템
    if Config.ENABLE_ENHANCED_UPDATES:
        new_extensions.append('update_system_enhanced')  # 강화된 업데이트 시스템
    
    # 결과 딕셔너리
    extensions = {
        "핵심 시스템": [],
        "게임 시스템": [],
        "관리 도구": [],
        "유틸리티": [],
        "새로운 시스템": []
    }
    
    # 모든 확장 모듈 체크
    all_extensions = [
        (core_extensions, "핵심 시스템"),
        (game_extensions, "게임 시스템"), 
        (admin_extensions, "관리 도구"),
        (utility_extensions, "유틸리티"),
        (new_extensions, "새로운 시스템")
    ]
    
    for extension_list, category in all_extensions:
        for extension in extension_list:
            if check_extension_exists(extension) and check_extension_has_setup(extension):
                extensions[category].append(extension)
            else:
                # 디버깅 정보 출력 (중요한 시스템만)
                if extension in ['update_system', 'member_exit_logger', 'update_system_enhanced']:
                    print(f"🔍 {extension} 확인: 존재={check_extension_exists(extension)}, setup={check_extension_has_setup(extension)}")
    
    return extensions

# ✅ 향상된 봇 클래스 (서버 제한 기능 추가)
class EnhancedBot(commands.Bot):
    """서버 제한 기능이 추가된 향상된 봇 클래스"""
    
    def __init__(self):
        # 인텐트 설정
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        
        super().__init__(
            command_prefix="IGNORE_PREFIX",
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
            activity=discord.Game(name="딜러양 v7 | /안녕"),
            status=discord.Status.online
        )
        
        # 상태 정보
        self.startup_time: Optional[datetime] = None
        self.logger = logging.getLogger('enhanced_bot')
        
        # 새로운 시스템 상태 추적
        self.update_system_available = False
        self.exit_logger_available = False
        
        # 성능 추적
        self.command_usage: Dict[str, int] = {}
        self.error_count: int = 0
        
        # 백업 시스템
        self.backup_system = None

    def _get_safe_latency(self) -> str:
        """안전한 지연시간 조회"""
        try:
            latency = self.latency
            if latency is None or latency != latency or latency < 0:
                return "알 수 없음"
            if latency == float('inf'):
                return "무한대"
            latency_ms = round(latency * 1000)
            return f"{latency_ms}"
        except Exception:
            return "오류"
    
    # ✅ 서버 제한 이벤트 핸들러 추가
    async def on_guild_join(self, guild: discord.Guild):
        """새로운 서버 참여 시 허가 여부 확인"""
        self.logger.info(f"📥 새로운 서버 참여: {guild.name} (ID: {guild.id})")
        
        # 서버 제한 기능이 비활성화되어 있으면 그냥 진행
        if not Config.ENABLE_GUILD_RESTRICTION:
            self.logger.info(f"✅ 서버 제한 기능 비활성화됨 - {guild.name}에서 계속 활동")
            return
        
        # 허용된 서버 목록 확인
        if guild.id not in Config.MAIN_GUILD_IDS:
            self.logger.warning(f"🚫 무허가 서버 참여 감지: {guild.name} (ID: {guild.id})")
            
            # 서버 소유자나 관리자에게 알림 전송 시도
            try:
                if guild.system_channel:
                    embed = discord.Embed(
                        title="🚫 허가되지 않은 서버",
                        description=f"안녕하세요! **딜러양**은 현재 특정 서버에서만 운영되고 있습니다.",
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
                    embed.set_footer(text="딜러양 v7 - 서버 제한 시스템")
                    
                    await guild.system_channel.send(embed=embed)
            except Exception as e:
                self.logger.error(f"❌ 무허가 서버 알림 전송 실패 ({guild.name}): {e}")
            
            # 자동 퇴장 기능이 활성화되어 있으면 퇴장
            if Config.AUTO_LEAVE_UNAUTHORIZED:
                await asyncio.sleep(10)  # 10초 대기 후 퇴장
                try:
                    await guild.leave()
                    self.logger.info(f"🚪 무허가 서버에서 자동 퇴장: {guild.name}")
                except Exception as e:
                    self.logger.error(f"❌ 서버 퇴장 실패 ({guild.name}): {e}")
            else:
                self.logger.warning(f"⚠️ 자동 퇴장 비활성화 - {guild.name}에서 계속 활동 (수동 퇴장 필요)")
        else:
            self.logger.info(f"✅ 허가된 서버 참여 확인: {guild.name}")
    
    # ✅ 수정된 on_guild_remove 로직
    async def on_guild_remove(self, guild: discord.Guild):
        self.logger.info(f"👋 서버 퇴장: {guild.name} (ID: {guild.id})")
        try:
            # 봇 소유자 정보 가져오기
            app_info = await self.application_info()
            owner = app_info.owner
            if owner:
                embed = discord.Embed(
                    title="ℹ️ 봇이 서버에서 나갔습니다.",
                    description=f"**서버명**: {guild.name}\n"
                                f"**서버 ID**: `{guild.id}`",
                    color=discord.Color.blue(),
                    timestamp=datetime.now(timezone.utc)
                )
            await owner.send(embed=embed)
        except Exception as e:
            self.logger.error(f"❌ 봇 소유자에게 알림 전송 실패: {e}")
    
    # ✅ 서버 제한 상태 확인 명령어 추가
    @app_commands.command(name="서버제한상태", description="현재 서버 제한 설정 상태를 확인합니다 (관리자 전용)")
    async def server_restriction_status(self, interaction: discord.Interaction):
        """서버 제한 설정 상태 확인"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)
        
        embed = discord.Embed(
            title="🔒 서버 제한 설정 상태",
            description="딜러양의 서버 접근 제한 설정 현황입니다.",
            color=discord.Color.blue() if Config.ENABLE_GUILD_RESTRICTION else discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # 현재 서버 상태
        current_guild_allowed = interaction.guild.id in Config.MAIN_GUILD_IDS
        embed.add_field(
            name="🏠 현재 서버 상태",
            value=f"**서버명**: {interaction.guild.name}\n"
                  f"**서버 ID**: {interaction.guild.id}\n"
                  f"**허가 상태**: {'✅ 허가됨' if current_guild_allowed else '❌ 무허가'}",
            inline=False
        )
        
        # 제한 설정 상태
        embed.add_field(
            name="⚙️ 제한 설정",
            value=f"**서버 제한 기능**: {'🔒 활성화' if Config.ENABLE_GUILD_RESTRICTION else '🔓 비활성화'}\n"
                  f"**자동 퇴장**: {'✅ 활성화' if Config.AUTO_LEAVE_UNAUTHORIZED else '❌ 비활성화'}\n"
                  f"**허가된 서버 수**: {len(Config.MAIN_GUILD_IDS)}개",
            inline=True
        )
        
        # 봇 연결 상태
        embed.add_field(
            name="📊 연결 정보",
            value=f"**연결된 서버**: {len(self.guilds)}개\n"
                  f"**총 사용자**: {len(set(self.get_all_members())):,}명\n"
                  f"**지연시간**: {self._get_safe_latency()}ms",
            inline=True
        )
        
        # 허가된 서버 목록
        if Config.MAIN_GUILD_IDS:
            allowed_servers = []
            for guild_id in Config.MAIN_GUILD_IDS:
                guild = self.get_guild(guild_id)
                if guild:
                    allowed_servers.append(f"✅ {guild.name} (`{guild_id}`)")
                else:
                    allowed_servers.append(f"❓ 알 수 없는 서버 (`{guild_id}`)")
            
            embed.add_field(
                name="🏠 허가된 서버 목록",
                value="\n".join(allowed_servers) if allowed_servers else "없음",
                inline=False
            )
        
        # 경고 메시지
        if not current_guild_allowed and Config.ENABLE_GUILD_RESTRICTION:
            embed.add_field(
                name="⚠️ 경고",
                value="현재 서버는 허가되지 않은 서버입니다!\n"
                      "자동 퇴장 기능이 활성화되어 있다면 곧 봇이 나가게 됩니다.",
                inline=False
            )
        
        embed.set_footer(text="딜러양 v7 - 서버 제한 시스템")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="시스템상태", description="봇의 현재 시스템 상태를 확인합니다 (관리자 전용)")
    async def system_status_slash(self, interaction: discord.Interaction):
        """시스템 상태 확인 (슬래시 명령어 버전)"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)
        
        # 시스템 정보 수집
        process = psutil.Process()
        memory_mb = round(process.memory_info().rss / 1024 / 1024, 1)
        cpu_percent = round(process.cpu_percent(), 1)
        uptime = datetime.now(timezone.utc) - self.startup_time if self.startup_time else None
        
        embed = discord.Embed(
            title="🔧 시스템 상태 점검 v6",
            description="딜러양의 현재 상태와 로드된 시스템들입니다.",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # 기본 정보
        embed.add_field(
            name="🤖 봇 정보",
            value=f"• 서버 수: {len(self.guilds)}개\n• 사용자 수: {len(set(self.get_all_members())):,}명\n• 지연시간: {self._get_safe_latency()}ms",
            inline=True
        )
        
        embed.add_field(
            name="💻 시스템 리소스",
            value=f"• 메모리: {memory_mb}MB\n• CPU: {cpu_percent}%\n• 가동시간: {str(uptime).split('.')[0] if uptime else '알 수 없음'}",
            inline=True
        )
        
        # 로드된 확장 모듈
        loaded_extensions = list(self.extensions.keys())
        embed.add_field(
            name="📦 로드된 시스템",
            value=f"총 {len(loaded_extensions)}개 시스템 로드됨",
            inline=True
        )
        
        embed.set_footer(text=f"점검자: {interaction.user.display_name} | 딜러양 v7")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def load_extensions(self):
        """사용 가능한 확장 모듈 로드"""
        self.logger.info("🔧 확장 모듈 로딩 시작...")
        
        available_extensions = get_available_extensions()
        
        # 우선순위 로딩 (핵심 시스템 먼저)
        priority_order = ["핵심 시스템", "새로운 시스템", "게임 시스템", "관리 도구", "유틸리티"]
        
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
                    
                    # 시스템 로드 완료 확인
                    if extension == 'update_system':
                        self.update_system_available = True
                        self.logger.info("  🔄 실시간 업데이트 시스템 활성화")
                    elif extension == 'member_exit_logger':
                        self.exit_logger_available = True
                        self.logger.info("  👋 퇴장 로그 시스템 활성화")
                        
                except Exception as e:
                    self.logger.error(f"  ❌ {extension}: {e}")
                    total_failed += 1
        
        # 로딩 결과 요약
        self.logger.info(f"📊 확장 모듈 로딩 완료: ✅{total_loaded}개 성공, ❌{total_failed}개 실패")
        
        if total_failed > 0:
            self.logger.warning(f"⚠️ 일부 기능이 제한될 수 있습니다.")
    
    async def setup_hook(self):
        """봇 설정 후크"""
        self.startup_time = datetime.now(timezone.utc)
        
        # 💡 개선: 확장 모듈 로딩을 setup_hook에서 한 번만 수행
        await self.load_extensions()

        # 특정 길드에만 슬래시 명령어 동기화 (빠른 반영을 위해)
        if Config.MAIN_GUILD_IDS:
            self.logger.info(f"🔧 설정된 {len(Config.MAIN_GUILD_IDS)}개의 서버에 명령어 동기화를 시도합니다...")
            for guild_id in Config.MAIN_GUILD_IDS:
                try:
                    guild = discord.Object(id=guild_id)
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    self.logger.info(f"  ✅ 서버 ID {guild_id}에 명령어 동기화 완료.")
                except Exception as e:
                    self.logger.error(f"  ❌ 서버 ID {guild_id}에 명령어 동기화 실패: {e}")

        # 백업 시스템 초기화는 BackupCog에서 처리
        pass
            
    async def on_ready(self):
        """봇 준비 완료 시 실행"""
        self.logger.info(f"✅ {self.user} (으)로 로그인 성공!")
        self.logger.info(f"🏠 현재 {len(self.guilds)}개의 서버에 연결됨.")

        # setup_hook에서 특정 길드 동기화를 하지 않은 경우, 여기서 모든 길드에 동기화
        if not Config.MAIN_GUILD_IDS:
            self.logger.info("🤔 특정 길드 설정이 없어, 연결된 모든 서버에 명령어를 동기화합니다...")
            synced_count = 0
            for guild in self.guilds:
                try:
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    synced_count += 1
                except Exception as e:
                    self.logger.error(f"❌ '{guild.name}' 서버에 명령어 동기화 실패: {e}")
            self.logger.info(f"🔄 {synced_count}개의 서버에 명령어 동기화 완료.")
        else:
            self.logger.info("✅ 특정 길드에 대한 명령어 동기화는 setup_hook에서 처리되었습니다.")

        print("=" * 50)
        print("🎉 딜러양 v7 완전히 준비 완료!")
        print(f"✨ {self.user} | {len(self.guilds)}개 서버")
        print("=" * 50)
    
    async def close(self):
        """봇 종료 시 정리 작업"""
        self.logger.info("🛑 봇 종료 프로세스 시작...")
        
        # 종료 알림 (가능한 경우)
        #try:
        #    if self.update_system_available:
        #        from update_system import add_realtime_update
        #        add_realtime_update(
        #            "🛑 딜러양 종료",
        #            "딜러양이 일시적으로 종료되었습니다. 곧 다시 돌아올게요!",
        #            "시스템",
        #            "일반"
        #        )
        #except Exception as e:
        #    self.logger.warning(f"⚠️ 종료 알림 추가 실패: {e}")
        
        # 백업 시스템 중지 (BackupCog에서 처리)
        # if self.backup_system:
        #     try:
        #         self.backup_system.stop_auto_backup()
        #     except Exception as e:
        #         self.logger.warning(f"⚠️ 백업 시스템 종료 실패: {e}")
        
        await super().close()
        self.logger.info("✅ 봇 정상 종료")

# ✅ 신호 핸들러 설정
def setup_signal_handlers(bot: EnhancedBot):
    """우아한 종료를 위한 신호 핸들러 설정"""
    def signal_handler(signum, frame):
        print(f"\n🛑 종료 신호 {signum} 수신, 봇을 안전하게 종료합니다...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

# ✅ 메인 실행 함수
async def main():
    """메인 실행 함수"""
    
    # 설정 검증
    if not Config.validate():
        sys.exit(1)
    
    # 로깅 설정
    logger = setup_logging()
    
    # 사용 가능한 확장 확인
    available_extensions = get_available_extensions()
    total_available = sum(len(exts) for exts in available_extensions.values())
    
    print(f"🔍 사용 가능한 확장 모듈: {total_available}개")
    for category, extensions in available_extensions.items():
        if extensions:  # 빈 카테고리는 건너뛰기
            print(f"   📁 {category}: {', '.join(extensions)}")
    print()
    
    # 활성화된 새로운 시스템 확인
    active_new_systems = []
    all_extensions = sum(available_extensions.values(), [])
    if 'update_system' in all_extensions:
        active_new_systems.append("실시간 업데이트 (/안녕 포함)")
    if 'member_exit_logger' in all_extensions:
        active_new_systems.append("퇴장 로그")
    if 'update_system_enhanced' in all_extensions:
        active_new_systems.append("강화된 업데이트 (v6.0)")
    
    if active_new_systems:
        print(f"✨ v6 활성화된 시스템: {', '.join(active_new_systems)}")
        print()
    
    # 봇 인스턴스 생성
    bot = EnhancedBot()
    
    # 신호 핸들러 설정
    setup_signal_handlers(bot)
    
    try:
        logger.info("🚀 딜러양 v7 서버 제한 + 퇴장 로그 + 향상된 업데이트 시스템 시작 중...")
        
        # 봇 시작
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
            
    except discord.LoginFailure:
        logger.error("❌ Discord 토큰이 유효하지 않습니다.")
        logger.error("💡 DISCORD_TOKEN 환경변수를 확인해주세요.")
        logger.error("💡 .env 파일에 DISCORD_TOKEN=your_token_here 형태로 추가해주세요.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("🛑 사용자에 의한 종료 요청")
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류: {e}")
        logger.error(traceback.format_exc())
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