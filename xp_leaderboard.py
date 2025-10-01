# xp_leaderboard.py
from __future__ import annotations
import discord
from discord import app_commands, Interaction, Member
from discord.ext import commands, tasks
from database_manager import get_guild_db_manager
import math
import json
import os
import time
import random
from datetime import datetime
from typing import Dict, Set, Optional, Literal, Union
from collections import defaultdict

# 역할 보상 시스템 import 시도
try:
    from role_reward_system import role_reward_manager
    ROLE_REWARD_AVAILABLE = True
except ImportError:
    ROLE_REWARD_AVAILABLE = False
    print("⚠️ 역할 보상 시스템을 사용할 수 없습니다.")

# 설정 파일 경로
DATA_DIR = "data"
LEVELUP_CHANNELS_FILE = os.path.join(DATA_DIR, "levelup_channels.json")
XP_SETTINGS_FILE = os.path.join(DATA_DIR, "xp_settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ✅ 레벨업 채널 관리 함수를 클래스 밖으로 이동
def load_levelup_channels():
    """레벨업 알림 채널 설정 로드"""
    if not os.path.exists(LEVELUP_CHANNELS_FILE):
        return {}
    try:
        with open(LEVELUP_CHANNELS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"레벨업 채널 설정 로드 오류: {e}")
        return {}
    
def get_levelup_channel_id(guild_id: str) -> Optional[int]:
    """길드 ID로 레벨업 채널 ID 조회"""
    data = load_levelup_channels()
    return data.get(guild_id)

# ✅ 사용자 등록 확인 함수를 클래스 밖으로 이동
def is_user_registered(user_id: str, guild_id: str) -> bool:
    """사용자 등록 여부 확인"""
    try:
        db = get_guild_db_manager(guild_id)
        user = db.get_user(str(user_id))
        return user is not None
    except Exception as e:
        print(f"등록 확인 오류: {e}")
        return False

def save_levelup_channels(channels_data):
    """레벨업 알림 채널 설정 저장"""
    try:
        with open(LEVELUP_CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(channels_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"레벨업 채널 설정 저장 오류: {e}")
        return False
    
# XP 포맷팅 함수
def format_xp(xp):
    return f"{xp:,}"

# XP 설정 관리
def load_xp_settings():
    """XP 설정 파일을 로드합니다."""
    if not os.path.exists(XP_SETTINGS_FILE):
        print("⚠️ xp_settings.json 파일이 없습니다. 기본 설정으로 대체합니다.")
        return {
            "chat_cooldown": 30, # 채팅 XP 쿨다운 (초)
            "voice_xp_per_minute": 10, # 음성 채널 분당 XP
            "chat_xp": 5,           # 채팅 XP
            "attendance_xp": 100,   # 출석체크 XP
        }
    try:
        with open(XP_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            return settings
    except Exception as e:
        print(f"❌ xp_settings.json 로드 중 오류 발생: {e}")
        return {}

def save_xp_settings(settings):
    """XP 설정 저장"""
    try:
        with open(XP_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"XP 설정 저장 오류: {e}")
        return False

# 관리자 액션 로그 함수
def log_admin_action(action_msg):
    """관리자 작업 로그 기록"""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {action_msg}"
        print(f"📝 ADMIN: {log_msg}")
        
        # 로그 파일 저장 (선택사항)
        os.makedirs("logs", exist_ok=True)
        with open("logs/admin_actions.log", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

# ✅ 레벨업 알림 함수 - 수정된 버전
async def check_and_send_levelup_notification(bot, member, guild, old_level, new_level):
    """
    레벨업 알림을 보냅니다.
    """
    
    # 레벨업이 여러 단계로 발생한 경우를 처리합니다.
    if new_level <= old_level:
        print("ℹ️ 레벨업이 발생하지 않았으므로 알림을 보내지 않습니다.")
        return
        
    for level in range(old_level + 1, new_level + 1):
        # 레벨업 알림을 보낼 채널을 가져옵니다.
        channel_id = get_levelup_channel_id(str(guild.id))
        if not channel_id:
            print(f"⚠️ 레벨업 알림 채널이 설정되지 않았습니다.")
            continue # 다음 레벨로 계속 진행

        channel = bot.get_channel(int(channel_id))
        if not channel or not channel.permissions_for(guild.me).send_messages:
            print(f"❌ 설정된 레벨업 채널({channel_id})이 없거나 권한이 부족합니다.")
            continue # 다음 레벨로 계속 진행
        
        # 임베드를 생성하고 전송합니다.
        embed = discord.Embed(
            title="🎉 레벨업!",
            description=f"{member.mention}님이 **Lv.{level}**로 레벨업했습니다!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🎊", value="축하합니다!", inline=True)
        
        try:
            await channel.send(embed=embed)
            print(f"✅ 레벨업 알림 전송 성공: {member.display_name} (Lv.{old_level} → Lv.{new_level})")
        except Exception as e:
            print(f"❌ 레벨업 알림 전송 실패: {e}")

# ==================== 메인 COG 클래스 ====================

class XPLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.synced = False
        self.message_cooldowns: Dict[str, float] = {}
        self.last_chat_xp_time: Dict[str, float] = {}
        self.xp_settings = load_xp_settings()
        self.levelup_channels = load_levelup_channels()

    # ✅ XP 계산 함수는 기존과 동일
    def get_xp_for_next_level(self, user_id: str, guild_id: str) -> int:
        """다음 레벨까지 필요한 XP를 계산합니다."""
        # ⚠️ 수정된 부분: 현재 XP를 다시 가져오고, 레벨 계산 로직을 명확히 합니다.
        user_xp = self.get_user_xp(user_id, guild_id)
        current_level = self.calculate_level_from_xp(user_xp)

        xp_required_for_next_level = self.calculate_xp_for_level(current_level + 1)
    
        return xp_required_for_next_level - user_xp

    @app_commands.command(name="레벨", description="자신 또는 다른 사용자의 레벨 및 XP를 확인합니다.")
    @app_commands.describe(사용자="레벨을 확인할 사용자 (선택 사항)")
    async def level(self, interaction: discord.Interaction, 사용자: Optional[discord.Member] = None):
        """레벨 조회 명령어"""
        await interaction.response.defer()
        target = 사용자 if 사용자 else interaction.user
        user_id = str(target.id)
        guild_id = str(interaction.guild.id)
        
        # 🔒 등록 확인
        if not is_user_registered(user_id):
            embed = discord.Embed(
                title="❌ 등록되지 않은 사용자",
                description="아직 봇에 등록되지 않았습니다. 활동을 시작하면 자동으로 등록됩니다!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            # ✅ get_user_level_info 함수를 사용하여 모든 정보를 한 번에 가져옴
            user_xp_info = self.get_user_level_info(user_id, guild_id)
            current_level = user_xp_info['level']
            total_xp = user_xp_info['total_xp']
            xp_in_current_level = user_xp_info['current_xp']
            xp_needed_for_level_up = user_xp_info['next_level_xp']
            progress_percentage = user_xp_info['progress'] * 100
            
            # ✅ 순위 계산
            db = get_guild_db_manager(guild_id)
            rank_result = db.execute_query('''
                SELECT COUNT(*) + 1 as rank
                FROM user_xp 
                WHERE guild_id = ? AND xp > ? 
            ''', (guild_id, total_xp), 'one')
            
            user_rank = rank_result['rank'] if rank_result else 0

            progress_bar = self.create_progress_bar(progress_percentage)
            
            embed = discord.Embed(
                title=f"📊 {target.display_name}님의 레벨 정보",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="📈 현재 레벨", value=f"**Lv.{current_level}**", inline=True)
            embed.add_field(name="⭐ 누적 XP", value=f"**{format_xp(total_xp)}**", inline=True)
            embed.add_field(name="🎯 다음 레벨까지", value=f"**{format_xp(xp_needed_for_level_up - xp_in_current_level)}** XP", inline=False)
            embed.add_field(name="📊 진행도", value=f"`{progress_bar}` {progress_percentage:.1f}%", inline=False)
            
            # 순위에 따른 이모지 추가
            if user_rank == 1:
                embed.add_field(name="🥇", value="길드의 1등! 축하합니다!", inline=False)
            elif user_rank <= 10:
                embed.add_field(name="🏆", value="상위 10위 안에 있습니다!", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ 레벨 조회 중 오류 발생: {e}")
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"레벨 조회 중 오류가 발생했습니다: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    # 수정된 xp_leaderboard.py 파일

    @app_commands.command(name="레벨업채널설정", description="레벨업 알림이 전송될 채널을 설정합니다.")
    async def set_levelup_channel(self, interaction: Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
    
        guild_id = str(interaction.guild_id)
    
        # ⚠️ 수정된 부분: 응답할 embed를 미리 정의합니다.
        embed = None
    
        # 채널 설정 or 해제 로직
        if channel:
            channels_data = load_levelup_channels()
            channels_data[guild_id] = str(channel.id)
            if save_levelup_channels(channels_data):
                self.levelup_channels = channels_data
                embed = discord.Embed(
                    title="✅ 레벨업 채널 설정 완료",
                    description=f"레벨업 알림이 {channel.mention}에서 전송됩니다.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ 설정 저장 실패",
                    description="채널 설정을 저장하는 중 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
        else:
            channels_data = load_levelup_channels()
            if guild_id in channels_data:
                del channels_data[guild_id]
                self.levelup_channels = channels_data
                if save_levelup_channels(channels_data):
                    embed = discord.Embed(
                        title="✅ 레벨업 채널 설정 해제",
                        description="레벨업 알림 채널 설정이 해제되었습니다.\n기본 채널에서 알림이 전송됩니다.",
                        color=discord.Color.orange()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 설정 해제 실패",
                        description="채널 설정 해제 중 오류가 발생했습니다.",
                        color=discord.Color.red()
                    )
            else:
                embed = discord.Embed(
                    title="ℹ️ 설정된 채널 없음",
                    description="현재 설정된 레벨업 알림 채널이 없습니다.",
                    color=discord.Color.blue()
                )
    
        # ⚠️ 수정된 부분: 모든 로직이 끝난 후 한 번만 응답을 보냅니다.
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # channel이 None이고 기존에 설정된 채널도 없을 때
            await interaction.response.send_message("⚠️ 채널 설정 실패: 유효한 채널이 지정되지 않았습니다.", ephemeral=True)

    def create_progress_bar(self, percentage):
        """진행도를 시각적인 막대로 변환합니다."""
        # Ensure the percentage is capped at 100 to prevent oversized bars
        # This also correctly handles negative or invalid percentages
        percentage = max(0, min(100, percentage))
    
        # Calculate filled and empty blocks for a fixed-length bar (e.g., 20 blocks)
        bar_length = 20
        filled_blocks = int(percentage / (100 / bar_length))
        empty_blocks = bar_length - filled_blocks
    
        # Return the formatted string
        return "⬛" * filled_blocks + "⬜" * empty_blocks
    
    def cog_unload(self):
        """Cog 언로드시 태스크 정리"""
        pass
    
    # ===== 레벨 계산 함수들 =====
    
    def calculate_xp_for_level(self, level: int) -> int:
        """특정 레벨에 도달하는데 필요한 총 XP를 계산합니다. (10 * 레벨)² - 2"""
        if level <= 0:
            return 0
        return (10 * level) ** 2 - 2

    def calculate_level_from_xp(self, xp: int) -> int:
        """현재 XP를 기반으로 레벨을 계산합니다."""
        if xp < 98:  # 레벨 1에 필요한 최소 XP는 98입니다.
            return 0
        # 수식 역산: level = sqrt((xp + 2) / 100)
        level = math.floor(math.sqrt((xp + 2) / 100))
        return int(level)
    
    # ===== 사용자 관리 함수들 (등록 확인 제거) =====
    
    def get_user_xp(self, user_id: str, guild_id: str) -> int:
        """사용자 XP 조회"""
        db = get_guild_db_manager(guild_id)
        result = db.execute_query('''
            SELECT xp FROM user_xp WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id), 'one')
        return result['xp'] if result else 0
    
    def get_user_level(self, user_id: str, guild_id: str) -> int:
        """사용자 레벨 조회"""
        db = get_guild_db_manager(guild_id)
        result = db.execute_query('''
            SELECT level FROM user_xp WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id), 'one')
        return result['level'] if result else 1
    
    def get_user_level_info(self, user_id: str, guild_id: str) -> Dict[str, Union[int, float]]:
        """사용자의 레벨, XP, 다음 레벨 정보 등을 반환합니다."""
    
        db = get_guild_db_manager(guild_id)
        user_data = db.execute_query(
            "SELECT xp, level FROM user_xp WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
            'one'
        )

        if not user_data:
            # XP 기록이 없는 경우 기본값 반환
            return {
                'level': 0,
                'current_xp': 0,
                'total_xp': 0,
                'next_level_xp': self.calculate_xp_for_level(1),
                'progress': 0.0
            }

        # ⚠️ 수정된 부분: sqlite3.Row 객체는 'get' 메서드가 없으므로 대괄호를 사용합니다.
        current_xp = user_data['xp']
        current_level = user_data['level']

        # 현재 레벨의 시작 XP와 다음 레벨의 시작 XP를 정확히 계산합니다.
        xp_for_current_level = self.calculate_xp_for_level(current_level)
        xp_for_next_level = self.calculate_xp_for_level(current_level + 1)

        # 진행도 계산 시, 현재 레벨에서 얻은 XP를 기준으로 계산합니다.
        xp_in_current_level = current_xp - xp_for_current_level
        xp_needed_for_level_up = xp_for_next_level - xp_for_current_level

        # 0으로 나누는 오류 방지
        progress = xp_in_current_level / xp_needed_for_level_up if xp_needed_for_level_up > 0 else 0.0

        return {
            'level': current_level,
            'current_xp': xp_in_current_level, # 현재 레벨에서의 XP
            'total_xp': current_xp,
            'next_level_xp': xp_needed_for_level_up, # 다음 레벨까지 필요한 총 XP
            'progress': progress
        }
    
    def update_user_level(self, user_id: str, guild_id: str):
        """사용자 레벨 업데이트"""
        current_xp = self.get_user_xp(user_id, guild_id)
        new_level = self.calculate_level_from_xp(current_xp)
        
        db = get_guild_db_manager(guild_id)
        db.execute_query('''
            UPDATE user_xp SET level = ? WHERE user_id = ? AND guild_id = ?
        ''', (new_level, user_id, guild_id))
    
    async def add_xp(self, user_id: str, guild_id: str, xp_amount: int):
        """사용자에게 XP 추가 (등록된 사용자만)"""
        # 🔒 등록 확인 추가
        if not is_user_registered(user_id, guild_id):
            return False
            
        # XP 레코드가 없으면 생성
        db = get_guild_db_manager(guild_id)
        db.execute_query('''
            INSERT OR IGNORE INTO user_xp (user_id, guild_id, xp, level)
            VALUES (?, ?, 0, 1)
        ''', (user_id, guild_id))
        
        # XP 추가
        db.execute_query('''
            UPDATE user_xp 
            SET xp = xp + ?, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND guild_id = ?
        ''', (xp_amount, user_id, guild_id))

        self.update_user_level(user_id, guild_id)

        # ✅ XP 지급 성공 시 터미널에 로그 출력
        new_xp = self.get_user_xp(user_id, guild_id)
        guild = self.bot.get_guild(int(guild_id))
        member = guild.get_member(int(user_id)) if guild else None

        if member:
           print(f"✅ XP 지급 로그: {member.display_name} ({member.id})에게 {xp_amount}XP 추가 완료. 현재 XP: {new_xp}")
        else:
           print(f"✅ XP 지급 로그: 사용자 ID({user_id})에게 {xp_amount}XP 추가 완료. 현재 XP: {new_xp}")
        
        return True
    
    # ===== 슬래시 명령어들 =====
    @app_commands.command(name="레벨순위", description="XP 리더보드를 확인합니다")
    @app_commands.describe(페이지="확인할 페이지 (기본값: 1)")
    async def level_leaderboard(self, interaction: Interaction, 페이지: int = 1):
        """레벨 순위 (XP 리더보드)"""
        await self._show_xp_leaderboard(interaction, 페이지)
    
# xp_leaderboard.py
from __future__ import annotations
import discord
from discord import app_commands, Interaction, Member
from discord.ext import commands, tasks
from database_manager import get_guild_db_manager
import math
import json
import os
import time
import random
from datetime import datetime
from typing import Dict, Set, Optional, Literal, Union
from collections import defaultdict

# 역할 보상 시스템 import 시도
try:
    from role_reward_system import role_reward_manager
    ROLE_REWARD_AVAILABLE = True
except ImportError:
    ROLE_REWARD_AVAILABLE = False
    print("⚠️ 역할 보상 시스템을 사용할 수 없습니다.")

# 설정 파일 경로
DATA_DIR = "data"
LEVELUP_CHANNELS_FILE = os.path.join(DATA_DIR, "levelup_channels.json")
XP_SETTINGS_FILE = os.path.join(DATA_DIR, "xp_settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ✅ 레벨업 채널 관리 함수를 클래스 밖으로 이동
def load_levelup_channels():
    """레벨업 알림 채널 설정 로드"""
    if not os.path.exists(LEVELUP_CHANNELS_FILE):
        return {}
    try:
        with open(LEVELUP_CHANNELS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"레벨업 채널 설정 로드 오류: {e}")
        return {}
    
def get_levelup_channel_id(guild_id: str) -> Optional[int]:
    """길드 ID로 레벨업 채널 ID 조회"""
    data = load_levelup_channels()
    return data.get(guild_id)

# ✅ 사용자 등록 확인 함수를 클래스 밖으로 이동
def is_user_registered(user_id: str, guild_id: str) -> bool:
    """사용자 등록 여부 확인"""
    try:
        db = get_guild_db_manager(guild_id)
        user = db.get_user(str(user_id))
        return user is not None
    except Exception as e:
        print(f"등록 확인 오류: {e}")
        return False

def save_levelup_channels(channels_data):
    """레벨업 알림 채널 설정 저장"""
    try:
        with open(LEVELUP_CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(channels_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"레벨업 채널 설정 저장 오류: {e}")
        return False
    
# XP 포맷팅 함수
def format_xp(xp):
    return f"{xp:,}"

# XP 설정 관리
def load_xp_settings():
    """XP 설정 파일을 로드합니다."""
    if not os.path.exists(XP_SETTINGS_FILE):
        print("⚠️ xp_settings.json 파일이 없습니다. 기본 설정으로 대체합니다.")
        return {
            "chat_cooldown": 30, # 채팅 XP 쿨다운 (초)
            "voice_xp_per_minute": 10, # 음성 채널 분당 XP
            "chat_xp": 5,           # 채팅 XP
            "attendance_xp": 100,   # 출석체크 XP
        }
    try:
        with open(XP_SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            return settings
    except Exception as e:
        print(f"❌ xp_settings.json 로드 중 오류 발생: {e}")
        return {}

def save_xp_settings(settings):
    """XP 설정 저장"""
    try:
        with open(XP_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"XP 설정 저장 오류: {e}")
        return False

# 관리자 액션 로그 함수
def log_admin_action(action_msg):
    """관리자 작업 로그 기록"""
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] {action_msg}"
        print(f"📝 ADMIN: {log_msg}")
        
        # 로그 파일 저장 (선택사항)
        os.makedirs("logs", exist_ok=True)
        with open("logs/admin_actions.log", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except Exception as e:
        print(f"로그 기록 실패: {e}")

# ✅ 레벨업 알림 함수 - 수정된 버전
async def check_and_send_levelup_notification(bot, member, guild, old_level, new_level):
    """
    레벨업 알림을 보냅니다.
    """
    
    # 레벨업이 여러 단계로 발생한 경우를 처리합니다.
    if new_level <= old_level:
        print("ℹ️ 레벨업이 발생하지 않았으므로 알림을 보내지 않습니다.")
        return
        
    for level in range(old_level + 1, new_level + 1):
        # 레벨업 알림을 보낼 채널을 가져옵니다.
        channel_id = get_levelup_channel_id(str(guild.id))
        if not channel_id:
            print(f"⚠️ 레벨업 알림 채널이 설정되지 않았습니다.")
            continue # 다음 레벨로 계속 진행

        channel = bot.get_channel(int(channel_id))
        if not channel or not channel.permissions_for(guild.me).send_messages:
            print(f"❌ 설정된 레벨업 채널({channel_id})이 없거나 권한이 부족합니다.")
            continue # 다음 레벨로 계속 진행
        
        # 임베드를 생성하고 전송합니다.
        embed = discord.Embed(
            title="🎉 레벨업!",
            description=f"{member.mention}님이 **Lv.{level}**로 레벨업했습니다!",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🎊", value="축하합니다!", inline=True)
        
        try:
            await channel.send(embed=embed)
            print(f"✅ 레벨업 알림 전송 성공: {member.display_name} (Lv.{old_level} → Lv.{new_level})")
        except Exception as e:
            print(f"❌ 레벨업 알림 전송 실패: {e}")

# ==================== 메인 COG 클래스 ====================

class XPLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.synced = False
        self.message_cooldowns: Dict[str, float] = {}
        self.last_chat_xp_time: Dict[str, float] = {}
        self.xp_settings = load_xp_settings()
        self.levelup_channels = load_levelup_channels()

    # ✅ XP 계산 함수는 기존과 동일
    def get_xp_for_next_level(self, user_id: str, guild_id: str) -> int:
        """다음 레벨까지 필요한 XP를 계산합니다."""
        # ⚠️ 수정된 부분: 현재 XP를 다시 가져오고, 레벨 계산 로직을 명확히 합니다.
        user_xp = self.get_user_xp(user_id, guild_id)
        current_level = self.calculate_level_from_xp(user_xp)

        xp_required_for_next_level = self.calculate_xp_for_level(current_level + 1)
    
        return xp_required_for_next_level - user_xp

    @app_commands.command(name="레벨", description="자신 또는 다른 사용자의 레벨 및 XP를 확인합니다.")
    @app_commands.describe(사용자="레벨을 확인할 사용자 (선택 사항)")
    async def level(self, interaction: discord.Interaction, 사용자: Optional[discord.Member] = None):
        """레벨 조회 명령어"""
        await interaction.response.defer()
        target = 사용자 if 사용자 else interaction.user
        user_id = str(target.id)
        guild_id = str(interaction.guild.id)
        
        # 🔒 등록 확인
        if not is_user_registered(user_id):
            embed = discord.Embed(
                title="❌ 등록되지 않은 사용자",
                description="아직 봇에 등록되지 않았습니다. 활동을 시작하면 자동으로 등록됩니다!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            # ✅ get_user_level_info 함수를 사용하여 모든 정보를 한 번에 가져옴
            user_xp_info = self.get_user_level_info(user_id, guild_id)
            current_level = user_xp_info['level']
            total_xp = user_xp_info['total_xp']
            xp_in_current_level = user_xp_info['current_xp']
            xp_needed_for_level_up = user_xp_info['next_level_xp']
            progress_percentage = user_xp_info['progress'] * 100
            
            # ✅ 순위 계산
            db = get_guild_db_manager(guild_id)
            rank_result = db.execute_query('''
                SELECT COUNT(*) + 1 as rank
                FROM user_xp 
                WHERE guild_id = ? AND xp > ? 
            ''', (guild_id, total_xp), 'one')
            
            user_rank = rank_result['rank'] if rank_result else 0

            progress_bar = self.create_progress_bar(progress_percentage)
            
            embed = discord.Embed(
                title=f"📊 {target.display_name}님의 레벨 정보",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="📈 현재 레벨", value=f"**Lv.{current_level}**", inline=True)
            embed.add_field(name="⭐ 누적 XP", value=f"**{format_xp(total_xp)}**", inline=True)
            embed.add_field(name="🎯 다음 레벨까지", value=f"**{format_xp(xp_needed_for_level_up - xp_in_current_level)}** XP", inline=False)
            embed.add_field(name="📊 진행도", value=f"`{progress_bar}` {progress_percentage:.1f}%", inline=False)
            
            # 순위에 따른 이모지 추가
            if user_rank == 1:
                embed.add_field(name="🥇", value="길드의 1등! 축하합니다!", inline=False)
            elif user_rank <= 10:
                embed.add_field(name="🏆", value="상위 10위 안에 있습니다!", inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ 레벨 조회 중 오류 발생: {e}")
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"레벨 조회 중 오류가 발생했습니다: {e}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

    # 수정된 xp_leaderboard.py 파일

    @app_commands.command(name="레벨업채널설정", description="레벨업 알림이 전송될 채널을 설정합니다.")
    async def set_levelup_channel(self, interaction: Interaction, channel: discord.TextChannel):
        if interaction.guild is None:
            await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다.", ephemeral=True)
            return
    
        guild_id = str(interaction.guild_id)
    
        # ⚠️ 수정된 부분: 응답할 embed를 미리 정의합니다.
        embed = None
    
        # 채널 설정 or 해제 로직
        if channel:
            channels_data = load_levelup_channels()
            channels_data[guild_id] = str(channel.id)
            if save_levelup_channels(channels_data):
                self.levelup_channels = channels_data
                embed = discord.Embed(
                    title="✅ 레벨업 채널 설정 완료",
                    description=f"레벨업 알림이 {channel.mention}에서 전송됩니다.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ 설정 저장 실패",
                    description="채널 설정을 저장하는 중 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
        else:
            channels_data = load_levelup_channels()
            if guild_id in channels_data:
                del channels_data[guild_id]
                self.levelup_channels = channels_data
                if save_levelup_channels(channels_data):
                    embed = discord.Embed(
                        title="✅ 레벨업 채널 설정 해제",
                        description="레벨업 알림 채널 설정이 해제되었습니다.\n기본 채널에서 알림이 전송됩니다.",
                        color=discord.Color.orange()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 설정 해제 실패",
                        description="채널 설정 해제 중 오류가 발생했습니다.",
                        color=discord.Color.red()
                    )
            else:
                embed = discord.Embed(
                    title="ℹ️ 설정된 채널 없음",
                    description="현재 설정된 레벨업 알림 채널이 없습니다.",
                    color=discord.Color.blue()
                )
    
        # ⚠️ 수정된 부분: 모든 로직이 끝난 후 한 번만 응답을 보냅니다.
        if embed:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            # channel이 None이고 기존에 설정된 채널도 없을 때
            await interaction.response.send_message("⚠️ 채널 설정 실패: 유효한 채널이 지정되지 않았습니다.", ephemeral=True)

    def create_progress_bar(self, percentage):
        """진행도를 시각적인 막대로 변환합니다."""
        # Ensure the percentage is capped at 100 to prevent oversized bars
        # This also correctly handles negative or invalid percentages
        percentage = max(0, min(100, percentage))
    
        # Calculate filled and empty blocks for a fixed-length bar (e.g., 20 blocks)
        bar_length = 20
        filled_blocks = int(percentage / (100 / bar_length))
        empty_blocks = bar_length - filled_blocks
    
        # Return the formatted string
        return "⬛" * filled_blocks + "⬜" * empty_blocks
    
    def cog_unload(self):
        """Cog 언로드시 태스크 정리"""
        pass
    
    # ===== 레벨 계산 함수들 =====
    
    def calculate_xp_for_level(self, level: int) -> int:
        """특정 레벨에 도달하는데 필요한 총 XP를 계산합니다. (10 * 레벨)² - 2"""
        if level <= 0:
            return 0
        return (10 * level) ** 2 - 2

    def calculate_level_from_xp(self, xp: int) -> int:
        """현재 XP를 기반으로 레벨을 계산합니다."""
        if xp < 98:  # 레벨 1에 필요한 최소 XP는 98입니다.
            return 0
        # 수식 역산: level = sqrt((xp + 2) / 100)
        level = math.floor(math.sqrt((xp + 2) / 100))
        return int(level)
    
    # ===== 사용자 관리 함수들 (등록 확인 제거) =====
    
    def get_user_xp(self, user_id: str, guild_id: str) -> int:
        """사용자 XP 조회"""
        db = get_guild_db_manager(guild_id)
        result = db.execute_query('''
            SELECT xp FROM user_xp WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id), 'one')
        return result['xp'] if result else 0
    
    def get_user_level(self, user_id: str, guild_id: str) -> int:
        """사용자 레벨 조회"""
        db = get_guild_db_manager(guild_id)
        result = db.execute_query('''
            SELECT level FROM user_xp WHERE user_id = ? AND guild_id = ?
        ''', (user_id, guild_id), 'one')
        return result['level'] if result else 1
    
    def get_user_level_info(self, user_id: str, guild_id: str) -> Dict[str, Union[int, float]]:
        """사용자의 레벨, XP, 다음 레벨 정보 등을 반환합니다."""
    
        db = get_guild_db_manager(guild_id)
        user_data = db.execute_query(
            "SELECT xp, level FROM user_xp WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
            'one'
        )

        if not user_data:
            # XP 기록이 없는 경우 기본값 반환
            return {
                'level': 0,
                'current_xp': 0,
                'total_xp': 0,
                'next_level_xp': self.calculate_xp_for_level(1),
                'progress': 0.0
            }

        # ⚠️ 수정된 부분: sqlite3.Row 객체는 'get' 메서드가 없으므로 대괄호를 사용합니다.
        current_xp = user_data['xp']
        current_level = user_data['level']

        # 현재 레벨의 시작 XP와 다음 레벨의 시작 XP를 정확히 계산합니다.
        xp_for_current_level = self.calculate_xp_for_level(current_level)
        xp_for_next_level = self.calculate_xp_for_level(current_level + 1)

        # 진행도 계산 시, 현재 레벨에서 얻은 XP를 기준으로 계산합니다.
        xp_in_current_level = current_xp - xp_for_current_level
        xp_needed_for_level_up = xp_for_next_level - xp_for_current_level

        # 0으로 나누는 오류 방지
        progress = xp_in_current_level / xp_needed_for_level_up if xp_needed_for_level_up > 0 else 0.0

        return {
            'level': current_level,
            'current_xp': xp_in_current_level, # 현재 레벨에서의 XP
            'total_xp': current_xp,
            'next_level_xp': xp_needed_for_level_up, # 다음 레벨까지 필요한 총 XP
            'progress': progress
        }
    
    def update_user_level(self, user_id: str, guild_id: str):
        """사용자 레벨 업데이트"""
        current_xp = self.get_user_xp(user_id, guild_id)
        new_level = self.calculate_level_from_xp(current_xp)
        
        db = get_guild_db_manager(guild_id)
        db.execute_query('''
            UPDATE user_xp SET level = ? WHERE user_id = ? AND guild_id = ?
        ''', (new_level, user_id, guild_id))
    
    async def add_xp(self, user_id: str, guild_id: str, xp_amount: int):
        """사용자에게 XP 추가 (등록된 사용자만)"""
        # 🔒 등록 확인 추가
        if not is_user_registered(user_id, guild_id):
            return False
            
        # XP 레코드가 없으면 생성
        db = get_guild_db_manager(guild_id)
        db.execute_query('''
            INSERT OR IGNORE INTO user_xp (user_id, guild_id, xp, level)
            VALUES (?, ?, 0, 1)
        ''', (user_id, guild_id))
        
        # XP 추가
        db.execute_query('''
            UPDATE user_xp 
            SET xp = xp + ?, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ? AND guild_id = ?
        ''', (xp_amount, user_id, guild_id))

        self.update_user_level(user_id, guild_id)

        # ✅ XP 지급 성공 시 터미널에 로그 출력
        new_xp = self.get_user_xp(user_id, guild_id)
        guild = self.bot.get_guild(int(guild_id))
        member = guild.get_member(int(user_id)) if guild else None

        if member:
           print(f"✅ XP 지급 로그: {member.display_name} ({member.id})에게 {xp_amount}XP 추가 완료. 현재 XP: {new_xp}")
        else:
           print(f"✅ XP 지급 로그: 사용자 ID({user_id})에게 {xp_amount}XP 추가 완료. 현재 XP: {new_xp}")
        
        return True
    
    # ===== 슬래시 명령어들 =====
    @app_commands.command(name="레벨순위", description="XP 리더보드를 확인합니다")
    @app_commands.describe(페이지="확인할 페이지 (기본값: 1)")
    async def level_leaderboard(self, interaction: Interaction, 페이지: int = 1):
        """레벨 순위 (XP 리더보드)"""
        await self._show_xp_leaderboard(interaction, 페이지)
    
    async def _show_xp_leaderboard(self, interaction: Interaction, 페이지: int = 1):
        """XP 리더보드 표시 (공통 함수)"""
        guild_id = str(interaction.guild.id)
        
        # 페이지 검증
        if 페이지 < 1:
            페이지 = 1
        
        offset = (페이지 - 1) * 10
        
        try:
            # 🔒 등록된 사용자만 표시하도록 JOIN 추가
            db = get_guild_db_manager(guild_id)
            leaderboard_data = db.execute_query('''
                SELECT u.user_id, u.username, u.display_name, x.xp, x.level
                FROM user_xp x
                JOIN users u ON x.user_id = u.user_id
                WHERE x.guild_id = ? AND x.xp > 0
                ORDER BY x.xp DESC
                LIMIT 10 OFFSET ?
            ''', (guild_id, offset), 'all')
            
            if not leaderboard_data:
                embed = discord.Embed(
                    title="📊 XP 리더보드",
                    description="아직 등록된 사용자의 XP 기록이 없습니다.\n`/등록` 명령어로 먼저 등록해주세요!",
                    color=discord.Color.blue()
                )
                return await interaction.response.send_message(embed=embed)
            
            # 전체 사용자 수 계산 (등록된 사용자만)
            total_users_result = db.execute_query('''
                SELECT COUNT(*) as count 
                FROM user_xp x
                JOIN users u ON x.user_id = u.user_id
                WHERE x.guild_id = ? AND x.xp > 0
            ''', (guild_id,), 'one')
            total_users = total_users_result['count']
            total_pages = math.ceil(total_users / 10)
            
            embed = discord.Embed(
                title="📊 XP 리더보드 (등록된 사용자)",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for i, user_data in enumerate(leaderboard_data):
                rank = offset + i + 1
                user_id = user_data['user_id']
                display_name = user_data['display_name'] or user_data['username']
                xp = user_data['xp']
                level = user_data['level']
                
                # 순위 이모지
                rank_emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}위"
                
                leaderboard_text += f"{rank_emoji} **{display_name}**\n"
                leaderboard_text += f"   💰 Lv.{level} ({format_xp(xp)} XP)\n\n"
            
            embed.description = leaderboard_text
            embed.set_footer(text=f"페이지 {페이지}/{total_pages} • 총 {total_users}명 (등록된 사용자만)")
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 리더보드 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True)
    
    # ===== 관리자 명령어들 =====
    @app_commands.command(name="경험치관리", description="XP 및 레벨 관리 (관리자 전용)")
    @app_commands.describe(
        작업="수행할 작업",
        대상자="대상 사용자 (일부 작업에만 필요)",
        수량="XP나 레벨 수량 (일부 작업에만 필요)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="XP 지급", value="give_xp"),
        app_commands.Choice(name="XP 차감", value="remove_xp"),
        app_commands.Choice(name="XP 설정", value="set_xp"),
        app_commands.Choice(name="레벨 설정", value="set_level"),
        app_commands.Choice(name="사용자 초기화", value="reset_user"),
        app_commands.Choice(name="서버 통계", value="stats"),
        app_commands.Choice(name="설정 보기", value="view_settings"),
        app_commands.Choice(name="채팅XP설정", value="set_chat_xp"),
        app_commands.Choice(name="음성XP설정", value="set_voice_xp"),
        app_commands.Choice(name="출석XP설정", value="set_attendance_xp"),
        app_commands.Choice(name="채팅쿨다운설정", value="set_chat_cooldown")
    ])
    async def xp_management(self, interaction: Interaction, 작업: str, 대상자: Member = None, 수량: int = None):
        """XP 관리 명령어"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        try:
            # 통계 보기
            if 작업 == "stats":
                db = get_guild_db_manager(guild_id)
                stats = db.execute_query('''
                    SELECT 
                        COUNT(*) as total_users,
                        SUM(xp) as total_xp,
                        AVG(xp) as avg_xp,
                        MAX(xp) as max_xp,
                        AVG(level) as avg_level,
                        MAX(level) as max_level
                    FROM user_xp x
                    JOIN users u ON x.user_id = u.user_id
                    WHERE x.guild_id = ? AND x.xp > 0
                ''', (guild_id,), 'one')
                
                if not stats or stats['total_users'] == 0:
                    return await interaction.response.send_message("❌ 아직 등록된 사용자의 XP 데이터가 없습니다.", ephemeral=True)
                
                embed = discord.Embed(
                    title="📊 서버 XP 통계 (등록된 사용자)",
                    color=discord.Color.blue()
                )
                embed.add_field(name="👥 총 사용자", value=f"{stats['total_users']:,}명", inline=True)
                embed.add_field(name="⭐ 총 XP", value=f"{int(stats['total_xp']):,}", inline=True)
                embed.add_field(name="📈 평균 XP", value=f"{int(stats['avg_xp']):,}", inline=True)
                embed.add_field(name="🏆 최고 XP", value=f"{int(stats['max_xp']):,}", inline=True)
                embed.add_field(name="📊 평균 레벨", value=f"Lv.{stats['avg_level']:.1f}", inline=True)
                embed.add_field(name="🥇 최고 레벨", value=f"Lv.{stats['max_level']}", inline=True)
                
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # 설정 보기
            elif 작업 == "view_settings":
                embed = discord.Embed(
                    title="⚙️ 현재 XP 설정",
                    color=discord.Color.green()
                )
                embed.add_field(name="💬 채팅 XP", value=f"{self.xp_settings['chat_xp']} XP", inline=True)
                embed.add_field(name="🎤 음성방 XP", value=f"{self.xp_settings.get('voice_xp', 0)} XP/분", inline=True)
                embed.add_field(name="📅 출석체크 XP", value=f"{self.xp_settings.get('attendance_xp', 0)} XP", inline=True)
                embed.add_field(name="⏰ 채팅 쿨타임", value=f"{self.xp_settings['chat_cooldown']}초", inline=True)
                embed.add_field(name="🔒 등록 요구", value="✅ 활성화됨", inline=True)
                
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # XP 설정 변경
            elif 작업 in ["set_chat_xp", "set_voice_xp", "set_attendance_xp", "set_chat_cooldown"]:
                if 수량 is None:
                    return await interaction.response.send_message("❌ 설정값을 입력해주세요.", ephemeral=True)
                
                if 수량 < 0:
                    return await interaction.response.send_message("❌ 설정값은 0 이상이어야 합니다.", ephemeral=True)
                
                setting_key = {
                    "set_chat_xp": "chat_xp",
                    "set_voice_xp": "voice_xp",
                    "set_attendance_xp": "attendance_xp",
                    "set_chat_cooldown": "chat_cooldown"
                }[작업]
                
                setting_name = {
                    "set_chat_xp": "채팅 XP",
                    "set_voice_xp": "음성방 XP",
                    "set_attendance_xp": "출석체크 XP",
                    "set_chat_cooldown": "채팅 쿨타임"
                }[작업]
                
                setting_unit = {
                    "set_chat_xp": "XP",
                    "set_voice_xp": "XP",
                    "set_attendance_xp": "XP",
                    "set_chat_cooldown": "초"
                }[작업]
                
                if self.update_xp_setting(setting_key, 수량):
                    embed = discord.Embed(
                        title="✅ XP 설정 변경 완료",
                        description=f"**{setting_name}**을(를) **{수량}{setting_unit}**로 설정했습니다.",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📝 적용 안내",
                        value="설정 변경사항은 즉시 적용됩니다.",
                        inline=False
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("❌ 설정 저장에 실패했습니다.", ephemeral=True)
                return
            
            # 대상자와 수량이 필요한 작업들
            if not 대상자:
                return await interaction.response.send_message("❌ 대상자를 지정해주세요.", ephemeral=True)
            
            # 🔒 대상자 등록 확인
            user_id = str(대상자.id)
            if not is_user_registered(user_id, guild_id):
                return await interaction.response.send_message(
                    f"❌ **{대상자.display_name}**님이 등록되지 않았습니다.\n"
                    f"먼저 `/등록` 명령어로 등록해주세요.",
                    ephemeral=True
                )
            
            if 작업 != "reset_user" and not 수량:
                return await interaction.response.send_message("❌ 수량을 입력해주세요.", ephemeral=True)
            
            # XP 레코드 생성 (필요시)
            db = get_guild_db_manager(guild_id)
            db.execute_query('''
                INSERT OR IGNORE INTO user_xp (user_id, guild_id, xp, level)
                VALUES (?, ?, 0, 1)
            ''', (user_id, guild_id))
            
            # 🔥 핵심 수정 부분: 레벨 변경 추적을 위한 변수들
            old_level = self.get_user_level(user_id, guild_id)
            role_update_needed = False
            
            if 작업 == "give_xp":
                success = await self.add_xp(user_id, guild_id, 수량) # ✅ [수정] await 추가
                if not success:
                    return await interaction.response.send_message("❌ XP 지급에 실패했습니다.", ephemeral=True)
                    
                new_level = self.get_user_level(user_id, guild_id)
                new_xp = self.get_user_xp(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 지급 완료",
                    description=f"{대상자.mention}님에게 {format_xp(수량)} XP를 지급했습니다.\n"
                                f"현재 XP: **{format_xp(new_xp)}**\n"
                                f"현재 레벨: **{new_level}**",
                    color=discord.Color.green()
                )
                
                if new_level > old_level:
                    embed.add_field(name="레벨업!", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    # ✅ 레벨업 알림 호출 - 올바른 매개변수 전달
                    await check_and_send_levelup_notification(self.bot, 대상자, interaction.guild, old_level, new_level)
                
            elif 작업 == "remove_xp":
                current_xp = self.get_user_xp(user_id, guild_id)
                new_xp = max(0, current_xp - 수량)
                
                db = get_guild_db_manager(guild_id)
                db.execute_query('''
                    UPDATE user_xp SET xp = ? WHERE user_id = ? AND guild_id = ?
                ''', (new_xp, user_id, guild_id))
                self.update_user_level(user_id, guild_id)
                
                new_level = self.get_user_level(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 차감 완료",
                    description=f"{대상자.mention}님의 XP를 {format_xp(수량)} 차감했습니다.",
                    color=discord.Color.orange()
                )
                
                if new_level < old_level:
                    embed.add_field(name="레벨 다운", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    
            elif 작업 == "set_xp":
                db = get_guild_db_manager(guild_id)
                db.execute_query('''
                    UPDATE user_xp SET xp = ? WHERE user_id = ? AND guild_id = ?
                ''', (수량, user_id, guild_id))
                self.update_user_level(user_id, guild_id)
                
                new_level = self.get_user_level(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 설정 완료",
                    description=f"{대상자.mention}님의 XP를 {format_xp(수량)}로 설정했습니다.",
                    color=discord.Color.blue()
                )
                
                if new_level != old_level:
                    embed.add_field(name="레벨 변경", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    
            elif 작업 == "set_level":
                required_xp = self.calculate_xp_for_level(수량)
                db = get_guild_db_manager(guild_id)
                db.execute_query('''
                    UPDATE user_xp SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?
                ''', (required_xp, 수량, user_id, guild_id))
                
                new_level = 수량
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ 레벨 설정 완료",
                    description=f"{대상자.mention}님의 레벨을 Lv.{수량}로 설정했습니다.",
                    color=discord.Color.purple()
                )
                
                embed.add_field(name="레벨 변경", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                
            elif 작업 == "reset_user":
                db = get_guild_db_manager(guild_id)
                db.execute_query('''
                    UPDATE user_xp SET xp = 0, level = 1 WHERE user_id = ? AND guild_id = ?
                ''', (user_id, guild_id))
                
                new_level = 1
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ 사용자 초기화 완료",
                    description=f"{대상자.mention}님의 XP와 레벨이 초기화되었습니다.",
                    color=discord.Color.red()
                )
                
                embed.add_field(name="초기화 결과", value="Lv.1 (0 XP)", inline=False)
            
            # 🔥 핵심 수정 부분: 역할 자동 조정 실행
            if role_update_needed and ROLE_REWARD_AVAILABLE:
                try:
                    await role_reward_manager.check_and_assign_level_role(대상자, new_level, old_level)
                    embed.add_field(
                        name="🎭 역할 자동 조정",
                        value="레벨 변경에 따른 역할이 자동으로 조정되었습니다.",
                        inline=False
                    )
                except Exception as role_error:
                    print(f"❌ 역할 자동 조정 실패: {role_error}")
                    embed.add_field(
                        name="⚠️ 역할 조정 알림",
                        value="역할 자동 조정 중 오류가 발생했습니다.",
                        inline=False
                    )
            
            # 관리자 작업 로그 기록
            log_admin_action(f"[경험치관리] {interaction.user.display_name} ({interaction.user.id}) - {작업}: {대상자.display_name} ({대상자.id})")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 경험치 관리 중 오류: {str(e)}", ephemeral=True)
    
    def update_xp_setting(self, setting_key: str, value: int) -> bool:
        """XP 설정 업데이트"""
        try:
            self.xp_settings[setting_key] = value
            return save_xp_settings(self.xp_settings)
        except Exception as e:
            print(f"XP 설정 업데이트 실패: {e}")
            return False

    @app_commands.command(name="경험치데이터확인", description="등록되지 않은 사용자의 경험치 데이터를 확인합니다 (관리자 전용)")
    @app_commands.describe(
        작업="수행할 작업",
        확인="정말로 실행하시겠습니까? (삭제 작업시 필수)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="📊 불일치 데이터 확인만", value="check_only"),
        app_commands.Choice(name="🧹 등록되지 않은 사용자 XP 삭제", value="cleanup_unregistered"),
    ])
    @app_commands.choices(확인=[
        app_commands.Choice(name="✅ 네, 실행합니다", value="confirmed"),
        app_commands.Choice(name="❌ 아니오", value="cancelled")
    ])
    async def check_xp_data_integrity(self, interaction: Interaction, 작업: str, 확인: str = "cancelled"):
        """경험치 데이터 무결성 확인 및 정리"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        await interaction.response.defer(ephemeral=True)
        
        try:
            if 작업 == "check_only":
                # 📊 불일치 데이터 확인만
                
                # 1. user_xp에는 있지만 users에는 없는 사용자들 찾기
                unregistered_xp_users = self.db.execute_query('''
                    SELECT ux.user_id, ux.guild_id, ux.xp, ux.level, ux.updated_at
                    FROM user_xp ux
                    LEFT JOIN users u ON ux.user_id = u.user_id
                    WHERE ux.guild_id = ? AND u.user_id IS NULL AND ux.xp > 0
                    ORDER BY ux.xp DESC
                ''', (guild_id,), 'all')
                
                # 2. users에는 있지만 user_xp에는 없는 사용자들 찾기
                registered_no_xp = self.db.execute_query('''
                    SELECT u.user_id, u.username, u.display_name, u.registered_at
                    FROM users u
                    LEFT JOIN user_xp ux ON u.user_id = ux.user_id AND ux.guild_id = ?
                    WHERE ux.user_id IS NULL
                    ORDER BY u.registered_at DESC
                ''', (guild_id,), 'all')
                
                # 3. 정상 등록된 사용자 수
                properly_registered = self.db.execute_query('''
                    SELECT COUNT(*) as count
                    FROM users u
                    INNER JOIN user_xp ux ON u.user_id = ux.user_id
                    WHERE ux.guild_id = ?
                ''', (guild_id,), 'one')
                
                embed = discord.Embed(
                    title="📊 경험치 데이터 무결성 확인 결과",
                    color=discord.Color.blue()
                )
                
                # 결과 요약
                embed.add_field(
                    name="📈 정상 등록된 사용자",
                    value=f"**{properly_registered['count']}명**\n(등록 + XP 데이터 모두 있음)",
                    inline=True
                )
                
                embed.add_field(
                    name="⚠️ 등록되지 않았지만 XP 있음",
                    value=f"**{len(unregistered_xp_users)}명**\n(정리 대상)",
                    inline=True
                )
                
                embed.add_field(
                    name="📋 등록되었지만 XP 없음",
                    value=f"**{len(registered_no_xp)}명**\n(정상 - 아직 활동 안함)",
                    inline=True
                )
                
                # 상세 내역
                if unregistered_xp_users:
                    unregistered_text = ""
                    total_unregistered_xp = 0
                    for i, user in enumerate(unregistered_xp_users[:10]):  # 최대 10명까지만 표시
                        unregistered_text += f"• `{user['user_id']}` - Lv.{user['level']} ({format_xp(user['xp'])})\n"
                        total_unregistered_xp += user['xp']
                    
                    if len(unregistered_xp_users) > 10:
                        unregistered_text += f"... 그리고 {len(unregistered_xp_users) - 10}명 더"
                    
                    embed.add_field(
                        name="🔍 등록되지 않은 XP 사용자 목록",
                        value=unregistered_text or "없음",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="📊 등록되지 않은 사용자들의 총 XP",
                        value=f"{format_xp(total_unregistered_xp)}",
                        inline=True
                    )
                
                if len(unregistered_xp_users) > 0:
                    embed.add_field(
                        name="🧹 정리 방법",
                        value="`/경험치데이터확인 작업:🧹등록되지_않은_사용자_XP_삭제 확인:✅네_실행합니다`\n"
                              "위 명령어로 등록되지 않은 사용자들의 XP를 삭제할 수 있습니다.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="✅ 데이터 상태",
                        value="모든 XP 데이터가 올바르게 등록된 사용자들에게만 있습니다!",
                        inline=False
                    )
            
            elif 작업 == "cleanup_unregistered":
                # 🧹 등록되지 않은 사용자 XP 삭제
                
                if 확인 != "confirmed":
                    return await interaction.followup.send(
                        "❌ 삭제 작업을 실행하려면 '확인: ✅ 네, 실행합니다'를 선택해야 합니다.",
                        ephemeral=True
                    )
                
                # 삭제 전 현황 확인
                unregistered_xp_users = self.db.execute_query('''
                    SELECT ux.user_id, ux.guild_id, ux.xp, ux.level
                    FROM user_xp ux
                    LEFT JOIN users u ON ux.user_id = u.user_id AND ux.guild_id = u.guild_id
                    WHERE ux.guild_id = ? AND u.user_id IS NULL
                ''', (guild_id,), 'all')
                
                if not unregistered_xp_users:
                    embed = discord.Embed(
                        title="ℹ️ 정리할 데이터 없음",
                        description="등록되지 않은 사용자의 XP 데이터가 없습니다.\n모든 XP가 등록된 사용자들에게만 있습니다!",
                        color=discord.Color.green()
                    )
                else:
                    # 삭제 실행
                    total_deleted_xp = sum(user['xp'] for user in unregistered_xp_users)
                    
                    deleted_count = self.db.execute_query('''
                        DELETE FROM user_xp 
                        WHERE guild_id = ? AND user_id IN (
                            SELECT ux.user_id 
                            FROM user_xp ux
                            LEFT JOIN users u ON ux.user_id = u.user_id AND ux.guild_id = u.guild_id
                            WHERE ux.guild_id = ? AND u.user_id IS NULL
                        )
                    ''', (guild_id, guild_id), 'count')
                    
                    embed = discord.Embed(
                        title="🧹 XP 데이터 정리 완료",
                        description=f"등록되지 않은 사용자들의 XP 데이터가 정리되었습니다.",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="📊 정리 결과",
                        value=f"• **삭제된 사용자**: {len(unregistered_xp_users)}명\n"
                              f"• **삭제된 레코드**: {deleted_count}개\n"
                              f"• **삭제된 총 XP**: {format_xp(total_deleted_xp)}",
                        inline=False
                    )
                    
                    # 상위 삭제 대상들 표시
                    if len(unregistered_xp_users) > 0:
                        deleted_list = ""
                        for user in sorted(unregistered_xp_users, key=lambda x: x['xp'], reverse=True)[:5]:
                            deleted_list += f"• `{user['user_id']}` - Lv.{user['level']} ({format_xp(user['xp'])})\n"
                        
                        embed.add_field(
                            name="🗑️ 삭제된 주요 XP 데이터",
                            value=deleted_list,
                            inline=False
                        )
                    
                    # 관리자 로그
                    log_admin_action(f"[XP데이터정리] {interaction.user.display_name} - {len(unregistered_xp_users)}명의 등록되지 않은 XP 삭제")
            
            elif 작업 == "full_stats":
                # 📋 전체 XP 통계
                
                # 전체 통계 수집
                stats = self.db.execute_query('''
                    SELECT 
                        (SELECT COUNT(*) FROM users WHERE guild_id = ?) as total_registered,
                        (SELECT COUNT(*) FROM user_xp WHERE guild_id = ?) as total_xp_records,
                        (SELECT COUNT(*) FROM user_xp ux 
                        INNER JOIN users u ON ux.user_id = u.user_id
                        WHERE ux.guild_id = ?) as properly_linked,
                        (SELECT COALESCE(SUM(xp), 0) FROM user_xp WHERE guild_id = ?) as total_xp,
                        (SELECT COALESCE(AVG(xp), 0) FROM user_xp WHERE guild_id = ? AND xp > 0) as avg_xp,
                        (SELECT COALESCE(MAX(level), 0) FROM user_xp WHERE guild_id = ?) as max_level
                ''', (guild_id, guild_id, guild_id, guild_id, guild_id, guild_id), 'one')
                
                embed.add_field(
                    name="👥 사용자 현황",
                    value=f"• **등록된 사용자**: {stats['total_registered']}명\n"
                          f"• **XP 레코드 수**: {stats['total_xp_records']}개\n"
                          f"• **정상 연결**: {stats['properly_linked']}명",
                    inline=True
                )
                
                embed.add_field(
                    name="⭐ XP 통계",
                    value=f"• **총 XP**: {format_xp(stats['total_xp'])}\n"
                          f"• **평균 XP**: {format_xp(int(stats['avg_xp']))}\n"
                          f"• **최고 레벨**: Lv.{stats['max_level']}",
                    inline=True
                )
                
                # 데이터 무결성 상태
                integrity_status = "✅ 정상" if stats['total_xp_records'] == stats['properly_linked'] else "⚠️ 불일치 발견"
                embed.add_field(
                    name="🔍 데이터 무결성",
                    value=integrity_status,
                    inline=True
                )
                
                if stats['total_xp_records'] != stats['properly_linked']:
                    unregistered_count = stats['total_xp_records'] - stats['properly_linked']
                    embed.add_field(
                        name="⚠️ 발견된 문제",
                        value=f"**{unregistered_count}개**의 등록되지 않은 XP 레코드가 있습니다.\n"
                              f"`/경험치데이터확인 작업:📊불일치_데이터_확인만`으로 상세 확인하세요.",
                        inline=False
                    )
            
            embed.set_footer(text=f"실행자: {interaction.user.display_name} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 데이터 확인 중 오류: {str(e)}", ephemeral=True)

    # ===== 이벤트 핸들러 (등록 확인 추가) =====
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """메시지 이벤트로 채팅 XP 지급 (등록된 사용자만)"""
        # 봇이 보낸 메시지나 DM, 명령어는 무시
        if message.author.bot or message.guild is None or (self.bot.command_prefix and message.content.startswith(self.bot.command_prefix)):
            return
        # 길드(서버)에서 온 메시지가 아니면 무시
        if message.guild is None:
            return
        # 너무 짧은 메시지는 무시
        if len(message.content) < 5:
            return
    
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        # 🔒 등록 확인 - 등록되지 않은 사용자는 XP를 받지 않음
        if not is_user_registered(user_id, guild_id):
            return
        
        # 쿨다운 확인
        current_time = time.time()
        last_xp_time = self.last_chat_xp_time.get(user_id, 0)
        
        if current_time - last_xp_time < self.xp_settings["chat_cooldown"]:
            return
        
        # ✅ 1. 레벨업 확인을 위한 이전 레벨 저장 (XP 지급 전에 실행되어야 함)
        old_level = self.get_user_level(user_id, guild_id)
        
        # 2. XP 지급
        xp_gained = self.xp_settings["chat_xp"]
        success = await self.add_xp(user_id, guild_id, xp_gained)
        
        if not success:
            return  # XP 지급 실패 시, 여기서 함수를 종료합니다.
        
        # 3. 쿨다운 업데이트
        self.last_chat_xp_time[user_id] = current_time
        
        # ✅ 4. 레벨업 확인: XP 지급 성공 시에만 new_level을 계산합니다.
        new_level = self.get_user_level(user_id, guild_id)
        
        # 5. 레벨업 처리 (라인 1048)
        if new_level > old_level:
            member = message.author
            
            # 5-1. 레벨업 알림 전송
            await check_and_send_levelup_notification(self.bot, member, message.guild, old_level, new_level)
            
            # 5-2. ✅ 역할 지급 로직
            if ROLE_REWARD_AVAILABLE:
                try:
                    await role_reward_manager.check_and_assign_level_role(member, new_level, old_level)
                    print(f"✨ 채팅 레벨업 역할 지급 성공: {member.display_name} (Lv.{old_level} → Lv.{new_level})")
                except Exception as e:
                    print(f"❌ 채팅 레벨업 역할 지급 오류: {e}")
            
# ✅ setup 함수 (확장 로드용)
async def setup(bot: commands.Bot):
    await bot.add_cog(XPLeaderboardCog(bot))
    print("✅ XP 리더보드 Cog 로드 완료")
    
    # ===== 관리자 명령어들 =====
    @app_commands.command(name="경험치관리", description="XP 및 레벨 관리 (관리자 전용)")
    @app_commands.describe(
        작업="수행할 작업",
        대상자="대상 사용자 (일부 작업에만 필요)",
        수량="XP나 레벨 수량 (일부 작업에만 필요)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="XP 지급", value="give_xp"),
        app_commands.Choice(name="XP 차감", value="remove_xp"),
        app_commands.Choice(name="XP 설정", value="set_xp"),
        app_commands.Choice(name="레벨 설정", value="set_level"),
        app_commands.Choice(name="사용자 초기화", value="reset_user"),
        app_commands.Choice(name="서버 통계", value="stats"),
        app_commands.Choice(name="설정 보기", value="view_settings"),
        app_commands.Choice(name="채팅XP설정", value="set_chat_xp"),
        app_commands.Choice(name="음성XP설정", value="set_voice_xp"),
        app_commands.Choice(name="출석XP설정", value="set_attendance_xp"),
        app_commands.Choice(name="채팅쿨다운설정", value="set_chat_cooldown")
    ])
    async def xp_management(self, interaction: Interaction, 작업: str, 대상자: Member = None, 수량: int = None):
        """XP 관리 명령어"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        try:
            # 통계 보기
            if 작업 == "stats":
                stats = self.db.execute_query('''
                    SELECT 
                        COUNT(*) as total_users,
                        SUM(xp) as total_xp,
                        AVG(xp) as avg_xp,
                        MAX(xp) as max_xp,
                        AVG(level) as avg_level,
                        MAX(level) as max_level
                    FROM user_xp x
                    JOIN users u ON x.user_id = u.user_id
                    WHERE x.guild_id = ? AND x.xp > 0
                ''', (guild_id,), 'one')
                
                if not stats or stats['total_users'] == 0:
                    return await interaction.response.send_message("❌ 아직 등록된 사용자의 XP 데이터가 없습니다.", ephemeral=True)
                
                embed = discord.Embed(
                    title="📊 서버 XP 통계 (등록된 사용자)",
                    color=discord.Color.blue()
                )
                embed.add_field(name="👥 총 사용자", value=f"{stats['total_users']:,}명", inline=True)
                embed.add_field(name="⭐ 총 XP", value=f"{int(stats['total_xp']):,}", inline=True)
                embed.add_field(name="📈 평균 XP", value=f"{int(stats['avg_xp']):,}", inline=True)
                embed.add_field(name="🏆 최고 XP", value=f"{int(stats['max_xp']):,}", inline=True)
                embed.add_field(name="📊 평균 레벨", value=f"Lv.{stats['avg_level']:.1f}", inline=True)
                embed.add_field(name="🥇 최고 레벨", value=f"Lv.{stats['max_level']}", inline=True)
                
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # 설정 보기
            elif 작업 == "view_settings":
                embed = discord.Embed(
                    title="⚙️ 현재 XP 설정",
                    color=discord.Color.green()
                )
                embed.add_field(name="💬 채팅 XP", value=f"{self.xp_settings['chat_xp']} XP", inline=True)
                embed.add_field(name="🎤 음성방 XP", value=f"{self.xp_settings.get('voice_xp', 0)} XP/분", inline=True)
                embed.add_field(name="📅 출석체크 XP", value=f"{self.xp_settings.get('attendance_xp', 0)} XP", inline=True)
                embed.add_field(name="⏰ 채팅 쿨타임", value=f"{self.xp_settings['chat_cooldown']}초", inline=True)
                embed.add_field(name="🔒 등록 요구", value="✅ 활성화됨", inline=True)
                
                return await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # XP 설정 변경
            elif 작업 in ["set_chat_xp", "set_voice_xp", "set_attendance_xp", "set_chat_cooldown"]:
                if 수량 is None:
                    return await interaction.response.send_message("❌ 설정값을 입력해주세요.", ephemeral=True)
                
                if 수량 < 0:
                    return await interaction.response.send_message("❌ 설정값은 0 이상이어야 합니다.", ephemeral=True)
                
                setting_key = {
                    "set_chat_xp": "chat_xp",
                    "set_voice_xp": "voice_xp",
                    "set_attendance_xp": "attendance_xp",
                    "set_chat_cooldown": "chat_cooldown"
                }[작업]
                
                setting_name = {
                    "set_chat_xp": "채팅 XP",
                    "set_voice_xp": "음성방 XP",
                    "set_attendance_xp": "출석체크 XP",
                    "set_chat_cooldown": "채팅 쿨타임"
                }[작업]
                
                setting_unit = {
                    "set_chat_xp": "XP",
                    "set_voice_xp": "XP",
                    "set_attendance_xp": "XP",
                    "set_chat_cooldown": "초"
                }[작업]
                
                if self.update_xp_setting(setting_key, 수량):
                    embed = discord.Embed(
                        title="✅ XP 설정 변경 완료",
                        description=f"**{setting_name}**을(를) **{수량}{setting_unit}**로 설정했습니다.",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="📝 적용 안내",
                        value="설정 변경사항은 즉시 적용됩니다.",
                        inline=False
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("❌ 설정 저장에 실패했습니다.", ephemeral=True)
                return
            
            # 대상자와 수량이 필요한 작업들
            if not 대상자:
                return await interaction.response.send_message("❌ 대상자를 지정해주세요.", ephemeral=True)
            
            # 🔒 대상자 등록 확인
            user_id = str(대상자.id)
            if not is_user_registered(user_id):
                return await interaction.response.send_message(
                    f"❌ **{대상자.display_name}**님이 등록되지 않았습니다.\n"
                    f"먼저 `/등록` 명령어로 등록해주세요.",
                    ephemeral=True
                )
            
            if 작업 != "reset_user" and not 수량:
                return await interaction.response.send_message("❌ 수량을 입력해주세요.", ephemeral=True)
            
            # XP 레코드 생성 (필요시)
            self.db.execute_query('''
                INSERT OR IGNORE INTO user_xp (user_id, guild_id, xp, level)
                VALUES (?, ?, 0, 1)
            ''', (user_id, guild_id))
            
            # 🔥 핵심 수정 부분: 레벨 변경 추적을 위한 변수들
            old_level = self.get_user_level(user_id, guild_id)
            role_update_needed = False
            
            if 작업 == "give_xp":
                success = await self.add_xp(user_id, guild_id, 수량) # ✅ [수정] await 추가
                if not success:
                    return await interaction.response.send_message("❌ XP 지급에 실패했습니다.", ephemeral=True)
                    
                new_level = self.get_user_level(user_id, guild_id)
                new_xp = self.get_user_xp(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 지급 완료",
                    description=f"{대상자.mention}님에게 {format_xp(수량)} XP를 지급했습니다.\n"
                                f"현재 XP: **{format_xp(new_xp)}**\n"
                                f"현재 레벨: **{new_level}**",
                    color=discord.Color.green()
                )
                
                if new_level > old_level:
                    embed.add_field(name="레벨업!", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    # ✅ 레벨업 알림 호출 - 올바른 매개변수 전달
                    await check_and_send_levelup_notification(self.bot, 대상자, interaction.guild, old_level, new_level)
                
            elif 작업 == "remove_xp":
                current_xp = self.get_user_xp(user_id, guild_id)
                new_xp = max(0, current_xp - 수량)
                
                self.db.execute_query('''
                    UPDATE user_xp SET xp = ? WHERE user_id = ? AND guild_id = ?
                ''', (new_xp, user_id, guild_id))
                self.update_user_level(user_id, guild_id)
                
                new_level = self.get_user_level(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 차감 완료",
                    description=f"{대상자.mention}님의 XP를 {format_xp(수량)} 차감했습니다.",
                    color=discord.Color.orange()
                )
                
                if new_level < old_level:
                    embed.add_field(name="레벨 다운", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    
            elif 작업 == "set_xp":
                self.db.execute_query('''
                    UPDATE user_xp SET xp = ? WHERE user_id = ? AND guild_id = ?
                ''', (수량, user_id, guild_id))
                self.update_user_level(user_id, guild_id)
                
                new_level = self.get_user_level(user_id, guild_id)
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ XP 설정 완료",
                    description=f"{대상자.mention}님의 XP를 {format_xp(수량)}로 설정했습니다.",
                    color=discord.Color.blue()
                )
                
                if new_level != old_level:
                    embed.add_field(name="레벨 변경", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                    
            elif 작업 == "set_level":
                required_xp = self.calculate_xp_for_level(수량)
                self.db.execute_query('''
                    UPDATE user_xp SET xp = ?, level = ? WHERE user_id = ? AND guild_id = ?
                ''', (required_xp, 수량, user_id, guild_id))
                
                new_level = 수량
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ 레벨 설정 완료",
                    description=f"{대상자.mention}님의 레벨을 Lv.{수량}로 설정했습니다.",
                    color=discord.Color.purple()
                )
                
                embed.add_field(name="레벨 변경", value=f"Lv.{old_level} → Lv.{new_level}", inline=False)
                
            elif 작업 == "reset_user":
                self.db.execute_query('''
                    UPDATE user_xp SET xp = 0, level = 1 WHERE user_id = ? AND guild_id = ?
                ''', (user_id, guild_id))
                
                new_level = 1
                role_update_needed = True  # 역할 업데이트 필요
                
                embed = discord.Embed(
                    title="✅ 사용자 초기화 완료",
                    description=f"{대상자.mention}님의 XP와 레벨이 초기화되었습니다.",
                    color=discord.Color.red()
                )
                
                embed.add_field(name="초기화 결과", value="Lv.1 (0 XP)", inline=False)
            
            # 🔥 핵심 수정 부분: 역할 자동 조정 실행
            if role_update_needed and ROLE_REWARD_AVAILABLE:
                try:
                    await role_reward_manager.check_and_assign_level_role(대상자, new_level, old_level)
                    embed.add_field(
                        name="🎭 역할 자동 조정",
                        value="레벨 변경에 따른 역할이 자동으로 조정되었습니다.",
                        inline=False
                    )
                except Exception as role_error:
                    print(f"❌ 역할 자동 조정 실패: {role_error}")
                    embed.add_field(
                        name="⚠️ 역할 조정 알림",
                        value="역할 자동 조정 중 오류가 발생했습니다.",
                        inline=False
                    )
            
            # 관리자 작업 로그 기록
            log_admin_action(f"[경험치관리] {interaction.user.display_name} ({interaction.user.id}) - {작업}: {대상자.display_name} ({대상자.id})")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 경험치 관리 중 오류: {str(e)}", ephemeral=True)
    
    def update_xp_setting(self, setting_key: str, value: int) -> bool:
        """XP 설정 업데이트"""
        try:
            self.xp_settings[setting_key] = value
            return save_xp_settings(self.xp_settings)
        except Exception as e:
            print(f"XP 설정 업데이트 실패: {e}")
            return False

    @app_commands.command(name="경험치데이터확인", description="등록되지 않은 사용자의 경험치 데이터를 확인합니다 (관리자 전용)")
    @app_commands.describe(
        작업="수행할 작업",
        확인="정말로 실행하시겠습니까? (삭제 작업시 필수)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="📊 불일치 데이터 확인만", value="check_only"),
        app_commands.Choice(name="🧹 등록되지 않은 사용자 XP 삭제", value="cleanup_unregistered"),
    ])
    @app_commands.choices(확인=[
        app_commands.Choice(name="✅ 네, 실행합니다", value="confirmed"),
        app_commands.Choice(name="❌ 아니오", value="cancelled")
    ])
    async def check_xp_data_integrity(self, interaction: Interaction, 작업: str, 확인: str = "cancelled"):
        """경험치 데이터 무결성 확인 및 정리"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        await interaction.response.defer(ephemeral=True)
        
        try:
            if 작업 == "check_only":
                # 📊 불일치 데이터 확인만
                
                # 1. user_xp에는 있지만 users에는 없는 사용자들 찾기
                unregistered_xp_users = self.db.execute_query('''
                    SELECT ux.user_id, ux.guild_id, ux.xp, ux.level, ux.updated_at
                    FROM user_xp ux
                    LEFT JOIN users u ON ux.user_id = u.user_id
                    WHERE ux.guild_id = ? AND u.user_id IS NULL AND ux.xp > 0
                    ORDER BY ux.xp DESC
                ''', (guild_id,), 'all')
                
                # 2. users에는 있지만 user_xp에는 없는 사용자들 찾기
                registered_no_xp = self.db.execute_query('''
                    SELECT u.user_id, u.username, u.display_name, u.registered_at
                    FROM users u
                    LEFT JOIN user_xp ux ON u.user_id = ux.user_id AND ux.guild_id = ?
                    WHERE ux.user_id IS NULL
                    ORDER BY u.registered_at DESC
                ''', (guild_id,), 'all')
                
                # 3. 정상 등록된 사용자 수
                properly_registered = self.db.execute_query('''
                    SELECT COUNT(*) as count
                    FROM users u
                    INNER JOIN user_xp ux ON u.user_id = ux.user_id
                    WHERE ux.guild_id = ?
                ''', (guild_id,), 'one')
                
                embed = discord.Embed(
                    title="📊 경험치 데이터 무결성 확인 결과",
                    color=discord.Color.blue()
                )
                
                # 결과 요약
                embed.add_field(
                    name="📈 정상 등록된 사용자",
                    value=f"**{properly_registered['count']}명**\n(등록 + XP 데이터 모두 있음)",
                    inline=True
                )
                
                embed.add_field(
                    name="⚠️ 등록되지 않았지만 XP 있음",
                    value=f"**{len(unregistered_xp_users)}명**\n(정리 대상)",
                    inline=True
                )
                
                embed.add_field(
                    name="📋 등록되었지만 XP 없음",
                    value=f"**{len(registered_no_xp)}명**\n(정상 - 아직 활동 안함)",
                    inline=True
                )
                
                # 상세 내역
                if unregistered_xp_users:
                    unregistered_text = ""
                    total_unregistered_xp = 0
                    for i, user in enumerate(unregistered_xp_users[:10]):  # 최대 10명까지만 표시
                        unregistered_text += f"• `{user['user_id']}` - Lv.{user['level']} ({format_xp(user['xp'])})\n"
                        total_unregistered_xp += user['xp']
                    
                    if len(unregistered_xp_users) > 10:
                        unregistered_text += f"... 그리고 {len(unregistered_xp_users) - 10}명 더"
                    
                    embed.add_field(
                        name="🔍 등록되지 않은 XP 사용자 목록",
                        value=unregistered_text or "없음",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="📊 등록되지 않은 사용자들의 총 XP",
                        value=f"{format_xp(total_unregistered_xp)}",
                        inline=True
                    )
                
                if len(unregistered_xp_users) > 0:
                    embed.add_field(
                        name="🧹 정리 방법",
                        value="`/경험치데이터확인 작업:🧹등록되지_않은_사용자_XP_삭제 확인:✅네_실행합니다`\n"
                              "위 명령어로 등록되지 않은 사용자들의 XP를 삭제할 수 있습니다.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="✅ 데이터 상태",
                        value="모든 XP 데이터가 올바르게 등록된 사용자들에게만 있습니다!",
                        inline=False
                    )
            
            elif 작업 == "cleanup_unregistered":
                # 🧹 등록되지 않은 사용자 XP 삭제
                
                if 확인 != "confirmed":
                    return await interaction.followup.send(
                        "❌ 삭제 작업을 실행하려면 '확인: ✅ 네, 실행합니다'를 선택해야 합니다.",
                        ephemeral=True
                    )
                
                # 삭제 전 현황 확인
                unregistered_xp_users = self.db.execute_query('''
                    SELECT ux.user_id, ux.guild_id, ux.xp, ux.level
                    FROM user_xp ux
                    LEFT JOIN users u ON ux.user_id = u.user_id AND ux.guild_id = u.guild_id
                    WHERE ux.guild_id = ? AND u.user_id IS NULL
                ''', (guild_id,), 'all')
                
                if not unregistered_xp_users:
                    embed = discord.Embed(
                        title="ℹ️ 정리할 데이터 없음",
                        description="등록되지 않은 사용자의 XP 데이터가 없습니다.\n모든 XP가 등록된 사용자들에게만 있습니다!",
                        color=discord.Color.green()
                    )
                else:
                    # 삭제 실행
                    total_deleted_xp = sum(user['xp'] for user in unregistered_xp_users)
                    
                    deleted_count = self.db.execute_query('''
                        DELETE FROM user_xp 
                        WHERE guild_id = ? AND user_id IN (
                            SELECT ux.user_id 
                            FROM user_xp ux
                            LEFT JOIN users u ON ux.user_id = u.user_id AND ux.guild_id = u.guild_id
                            WHERE ux.guild_id = ? AND u.user_id IS NULL
                        )
                    ''', (guild_id, guild_id), 'count')
                    
                    embed = discord.Embed(
                        title="🧹 XP 데이터 정리 완료",
                        description=f"등록되지 않은 사용자들의 XP 데이터가 정리되었습니다.",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="📊 정리 결과",
                        value=f"• **삭제된 사용자**: {len(unregistered_xp_users)}명\n"
                              f"• **삭제된 레코드**: {deleted_count}개\n"
                              f"• **삭제된 총 XP**: {format_xp(total_deleted_xp)}",
                        inline=False
                    )
                    
                    # 상위 삭제 대상들 표시
                    if len(unregistered_xp_users) > 0:
                        deleted_list = ""
                        for user in sorted(unregistered_xp_users, key=lambda x: x['xp'], reverse=True)[:5]:
                            deleted_list += f"• `{user['user_id']}` - Lv.{user['level']} ({format_xp(user['xp'])})\n"
                        
                        embed.add_field(
                            name="🗑️ 삭제된 주요 XP 데이터",
                            value=deleted_list,
                            inline=False
                        )
                    
                    # 관리자 로그
                    log_admin_action(f"[XP데이터정리] {interaction.user.display_name} - {len(unregistered_xp_users)}명의 등록되지 않은 XP 삭제")
            
            elif 작업 == "full_stats":
                # 📋 전체 XP 통계
                
                # 전체 통계 수집
                stats = self.db.execute_query('''
                    SELECT 
                        (SELECT COUNT(*) FROM users WHERE guild_id = ?) as total_registered,
                        (SELECT COUNT(*) FROM user_xp WHERE guild_id = ?) as total_xp_records,
                        (SELECT COUNT(*) FROM user_xp ux 
                        INNER JOIN users u ON ux.user_id = u.user_id
                        WHERE ux.guild_id = ?) as properly_linked,
                        (SELECT COALESCE(SUM(xp), 0) FROM user_xp WHERE guild_id = ?) as total_xp,
                        (SELECT COALESCE(AVG(xp), 0) FROM user_xp WHERE guild_id = ? AND xp > 0) as avg_xp,
                        (SELECT COALESCE(MAX(level), 0) FROM user_xp WHERE guild_id = ?) as max_level
                ''', (guild_id, guild_id, guild_id, guild_id, guild_id, guild_id), 'one')
                
                embed.add_field(
                    name="👥 사용자 현황",
                    value=f"• **등록된 사용자**: {stats['total_registered']}명\n"
                          f"• **XP 레코드 수**: {stats['total_xp_records']}개\n"
                          f"• **정상 연결**: {stats['properly_linked']}명",
                    inline=True
                )
                
                embed.add_field(
                    name="⭐ XP 통계",
                    value=f"• **총 XP**: {format_xp(stats['total_xp'])}\n"
                          f"• **평균 XP**: {format_xp(int(stats['avg_xp']))}\n"
                          f"• **최고 레벨**: Lv.{stats['max_level']}",
                    inline=True
                )
                
                # 데이터 무결성 상태
                integrity_status = "✅ 정상" if stats['total_xp_records'] == stats['properly_linked'] else "⚠️ 불일치 발견"
                embed.add_field(
                    name="🔍 데이터 무결성",
                    value=integrity_status,
                    inline=True
                )
                
                if stats['total_xp_records'] != stats['properly_linked']:
                    unregistered_count = stats['total_xp_records'] - stats['properly_linked']
                    embed.add_field(
                        name="⚠️ 발견된 문제",
                        value=f"**{unregistered_count}개**의 등록되지 않은 XP 레코드가 있습니다.\n"
                              f"`/경험치데이터확인 작업:📊불일치_데이터_확인만`으로 상세 확인하세요.",
                        inline=False
                    )
            
            embed.set_footer(text=f"실행자: {interaction.user.display_name} | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 데이터 확인 중 오류: {str(e)}", ephemeral=True)

    # ===== 이벤트 핸들러 (등록 확인 추가) =====
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """메시지 이벤트로 채팅 XP 지급 (등록된 사용자만)"""
        # 봇이 보낸 메시지나 DM, 명령어는 무시
        if message.author.bot or message.guild is None or (self.bot.command_prefix and message.content.startswith(self.bot.command_prefix)):
            return
        # 길드(서버)에서 온 메시지가 아니면 무시
        if message.guild is None:
            return
        # 너무 짧은 메시지는 무시
        if len(message.content) < 5:
            return
    
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        # 🔒 등록 확인 - 등록되지 않은 사용자는 XP를 받지 않음
        if not is_user_registered(user_id):
            return
        
        # 쿨다운 확인
        current_time = time.time()
        last_xp_time = self.last_chat_xp_time.get(user_id, 0)
        
        if current_time - last_xp_time < self.xp_settings["chat_cooldown"]:
            return
        
        # ✅ 1. 레벨업 확인을 위한 이전 레벨 저장 (XP 지급 전에 실행되어야 함)
        old_level = self.get_user_level(user_id, guild_id)
        
        # 2. XP 지급
        xp_gained = self.xp_settings["chat_xp"]
        success = await self.add_xp(user_id, guild_id, xp_gained)
        
        if not success:
            return  # XP 지급 실패 시, 여기서 함수를 종료합니다.
        
        # 3. 쿨다운 업데이트
        self.last_chat_xp_time[user_id] = current_time
        
        # ✅ 4. 레벨업 확인: XP 지급 성공 시에만 new_level을 계산합니다.
        new_level = self.get_user_level(user_id, guild_id)
        
        # 5. 레벨업 처리 (라인 1048)
        if new_level > old_level:
            member = message.author
            
            # 5-1. 레벨업 알림 전송
            await check_and_send_levelup_notification(self.bot, member, message.guild, old_level, new_level)
            
            # 5-2. ✅ 역할 지급 로직
            if ROLE_REWARD_AVAILABLE:
                try:
                    await role_reward_manager.check_and_assign_level_role(member, new_level, old_level)
                    print(f"✨ 채팅 레벨업 역할 지급 성공: {member.display_name} (Lv.{old_level} → Lv.{new_level})")
                except Exception as e:
                    print(f"❌ 채팅 레벨업 역할 지급 오류: {e}")
            
# ✅ setup 함수 (확장 로드용)
async def setup(bot: commands.Bot):
    await bot.add_cog(XPLeaderboardCog(bot))
    print("✅ XP 리더보드 Cog 로드 완료")