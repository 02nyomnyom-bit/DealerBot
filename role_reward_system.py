# role_reward_system.py - [서버관리] 레벨별 역할 지급
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional, Tuple
import json
import os
from common_utils import log_admin_action, now_str

# 데이터 파일 경로
DATA_DIR = "data"
ROLE_REWARDS_FILE = os.path.join(DATA_DIR, "role_rewards.json")                             # 레벨별 역할 보상 정보 저장 파일
ROLE_NOTIFICATION_CHANNELS_FILE = os.path.join(DATA_DIR, "role_notification_channels.json") # 역할 지급 알림을 보낼 채널 설정 저장 파일
EXCLUDE_ROLES_FILE = os.path.join(DATA_DIR, "exclude_roles.json")

# 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)

# --- [데이터 관리 함수들] ---
def load_json_file(file_path, default_value):
    if not os.path.exists(file_path):
        return default_value
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"파일 로드 오류 ({file_path}): {e}")
        return default_value
    
def save_json_file(file_path, data):
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"파일 저장 오류 ({file_path}): {e}")
        return False

# 역할 알림 채널 관리 함수들
def load_role_notification_channels():
    """레벨 역할 지급 안내 채널 설정 로드"""
    if not os.path.exists(ROLE_NOTIFICATION_CHANNELS_FILE):
        return {}
    try:
        with open(ROLE_NOTIFICATION_CHANNELS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"역할 알림 채널 설정 로드 오류: {e}")
        return {}

def save_role_notification_channels(channels_data):
    """레벨 역할 지급 안내 채널 설정 저장"""
    try:
        with open(ROLE_NOTIFICATION_CHANNELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(channels_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"역할 알림 채널 설정 저장 오류: {e}")
        return False
    
# --- [데이터 관리 클래스] ---
class RoleRewardManager:
    def __init__(self):
        self.role_rewards: Dict[str, Dict[int, str]] = {}
        self.role_notification_channels = load_json_file(ROLE_NOTIFICATION_CHANNELS_FILE, {})
        self.exclude_roles = load_json_file(EXCLUDE_ROLES_FILE, {})
        self.load_data()
    
    def load_data(self):
        """역할 보상 데이터 로드"""
        data = load_json_file(ROLE_REWARDS_FILE, {})
        for guild_id, rewards in data.items():
            self.role_rewards[guild_id] = {int(level): role_id for level, role_id in rewards.items()}
    
    def save_data(self):
        """역할 보상 데이터 저장"""
        save_data = {gid: {str(lvl): rid for lvl, rid in rwds.items()} for gid, rwds in self.role_rewards.items()}
        return save_json_file(ROLE_REWARDS_FILE, save_data)

    # --- 제외 역할 관련 로직 [신버전 이식] ---
    def add_exclude_role(self, guild_id: str, role_id: str) -> bool:
        if guild_id not in self.exclude_roles: 
            self.exclude_roles[guild_id] = []
        if role_id not in self.exclude_roles[guild_id]:
            self.exclude_roles[guild_id].append(role_id)
            return save_json_file(EXCLUDE_ROLES_FILE, self.exclude_roles)
        return False

    def remove_exclude_role(self, guild_id: str, role_id: str) -> bool:
        if guild_id in self.exclude_roles and role_id in self.exclude_roles[guild_id]:
            self.exclude_roles[guild_id].remove(role_id)
            return save_json_file(EXCLUDE_ROLES_FILE, self.exclude_roles)
        return False

    # --- 기존 보상 관리 로직 ---
    def set_role_reward(self, guild_id: str, level: int, role_id: str) -> bool:
        if guild_id not in self.role_rewards: self.role_rewards[guild_id] = {}
        self.role_rewards[guild_id][level] = role_id
        return self.save_data()

    def remove_role_reward(self, guild_id: str, level: int) -> bool:
        if guild_id in self.role_rewards and level in self.role_rewards[guild_id]:
            del self.role_rewards[guild_id][level]
            if not self.role_rewards[guild_id]: del self.role_rewards[guild_id]
            return self.save_data()
        return False

    def clear_all_rewards(self, guild_id: str) -> bool:
        if guild_id in self.role_rewards:
            del self.role_rewards[guild_id]
            return self.save_data()
        return True

    async def check_and_assign_level_role(self, member: discord.Member, new_level: int, old_level: int = 0):
        guild_id = str(member.guild.id)
        
        # [신규] 제외 역할 보유 확인 로직
        exclude_list = self.exclude_roles.get(guild_id, [])
        if any(str(role.id) in exclude_list for role in member.roles):
            return

        guild_rewards = self.role_rewards.get(guild_id, {})
        if not guild_rewards or not member.guild.me.guild_permissions.manage_roles:
            return

        try:
            earned_levels = sorted([level for level in guild_rewards.keys() if level <= new_level])
            highest_earned_level = max(earned_levels) if earned_levels else None
            target_role_id = guild_rewards.get(highest_earned_level) if highest_earned_level else None

            roles_to_remove, roles_to_add = [], []

            for level, role_id_str in guild_rewards.items():
                role = member.guild.get_role(int(role_id_str))
                if not role or role.position >= member.guild.me.top_role.position: continue

                is_target = str(role.id) == target_role_id
                if is_target and role not in member.roles: roles_to_add.append((level, role))
                elif not is_target and role in member.roles: roles_to_remove.append((level, role))
            
            for _, role in roles_to_remove: await member.remove_roles(role)
            for _, role in roles_to_add: await member.add_roles(role)
            
            if roles_to_add:
                await self.send_notification(member, roles_to_add, new_level)
        except Exception as e: print(f"역할 부여 오류: {e}")

    def get_guild_rewards(self, guild_id: str) -> Dict[int, str]:
        """특정 서버의 보상 목록 반환"""
        return self.role_rewards.get(guild_id, {})

    def set_notification_channel(self, guild_id: str, channel_id: str) -> bool:
        """알림 채널 설정 저장"""
        self.role_notification_channels[guild_id] = channel_id
        return save_json_file(ROLE_NOTIFICATION_CHANNELS_FILE, self.role_notification_channels)

    async def send_notification(self, member, roles_to_add, new_level):
        guild_id = str(member.guild.id)
        embed = discord.Embed(title="🎉 새로운 역할 획득!", color=discord.Color.gold())
        role_text = "\n".join([f"🏆 Lv.{lvl} - **{r.name}**" for lvl, r in roles_to_add])
        embed.add_field(name="획득한 역할", value=role_text, inline=False)
        embed.add_field(name="현재 레벨", value=f"**Lv.{new_level}**", inline=True)
        
        channel_id = self.role_notification_channels.get(guild_id)
        channel = member.guild.get_channel(int(channel_id)) if channel_id else None
        
        if not channel:
            for c in member.guild.text_channels:
                if c.name in ['일반', 'general', '채팅']: channel = c; break
        
        if channel: await channel.send(embed=embed)

# 전역 인스턴스
role_reward_manager = RoleRewardManager()

class RoleRewardCog(commands.Cog):
    """레벨별 역할 보상 시스템 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.role_manager = role_reward_manager
    
    async def check_and_assign_roles(self, member: discord.Member, new_level: int, old_level: int = 0):
        """레벨업 시 역할 확인 및 부여 - Cog 내부용 메서드"""
        await self.role_manager.check_and_assign_level_role(member, new_level, old_level)
    
    # ==================== 관리자 명령어 통합 (최종본) ====================

    @app_commands.command(name="역할관리", description="[관리자 전용] 레벨 보상 역할 및 시스템 관리")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        작업="수행할 작업을 선택하세요",
        레벨="역할을 부여할 레벨 (설정 시 필요)",
        역할="대상 역할 (설정/제외 등록 시 필요)",
        채널="알림을 보낼 채널 (알림채널설정 시 필요)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="⚙️ 레벨 역할 설정", value="set_reward"),
        app_commands.Choice(name="❌ 레벨 역할 삭제", value="delete_reward"),
        app_commands.Choice(name="📋 전체 목록 확인", value="list_all"),
        app_commands.Choice(name="🚫 제외 역할 등록", value="exclude_add"),
        app_commands.Choice(name="✅ 제외 역할 해제", value="exclude_remove"),
        app_commands.Choice(name="🔔 알림 채널 설정", value="set_notify")
    ])
    
    async def role_admin_integrated(
        self, 
        interaction: discord.Interaction, 
        작업: str, 
        레벨: Optional[int] = None, 
        역할: Optional[discord.Role] = None,
        채널: Optional[discord.TextChannel] = None
    ):
        guild_id = str(interaction.guild.id)

        # 전체 목록 확인 (오류 수정됨)
        if 작업 == "list_all":
            rewards = self.role_manager.get_guild_rewards(guild_id) # 이제 정의된 메서드 호출
            excludes = self.role_manager.exclude_roles.get(guild_id, [])
            
            embed = discord.Embed(title=f"📊 {interaction.guild.name} 설정 현황", color=discord.Color.blue())
            
            # 보상 목록 구성
            reward_text = "\n".join([f"Lv.{lv}: <@&{r_id}>" for lv, r_id in sorted(rewards.items())]) if rewards else "설정된 보상 없음"
            embed.add_field(name="🏆 레벨별 보상", value=reward_text, inline=False)
            
            # 제외 목록 구성
            exclude_text = ", ".join([f"<@&{r_id}>" for r_id in excludes]) if excludes else "없음"
            embed.add_field(name="🚫 보상 제외 역할", value=exclude_text, inline=False)
            
            return await interaction.response.send_message(embed=embed)
        
        # 레벨 역할 설정 (add_role_reward -> set_role_reward로 수정)
        elif 작업 == "set_reward":
            if 레벨 is None or 역할 is None:
                return await interaction.response.send_message("❌ 레벨과 역할을 입력하세요.", ephemeral=True)
            self.role_manager.set_role_reward(guild_id, 레벨, str(역할.id))
            await interaction.response.send_message(f"✅ Lv.{레벨} 보상: {역할.mention}")

        # 레벨 역할 삭제 (delete_reward)
        elif 작업 == "delete_reward":
            if 레벨 is None:
                return await interaction.response.send_message("❌ 삭제할 레벨을 입력해주세요.", ephemeral=True)
            if self.role_manager.remove_role_reward(guild_id, 레벨):
                await interaction.response.send_message(f"✅ 레벨 **{레벨}** 보상 설정을 삭제했습니다.")
            else:
                await interaction.response.send_message(f"❌ 레벨 **{레벨}**에 설정된 보상이 없습니다.", ephemeral=True)

        # 전체 목록 확인 (list_all)
        elif 작업 == "list_all":
            rewards = self.role_manager.get_guild_rewards(guild_id)
            excludes = self.role_manager.exclude_roles.get(guild_id, [])
            
            embed = discord.Embed(title=f"📊 {interaction.guild.name} 역할 보상 설정 현황", color=discord.Color.blue())
            
            # 보상 목록
            reward_text = "\n".join([f"Lv.{lv}: <@&{r_id}>" for lv, r_id in sorted(rewards.items())]) if rewards else "설정된 보상 없음"
            embed.add_field(name="🏆 레벨별 보상", value=reward_text, inline=False)
            
            # 제외 목록
            exclude_text = ", ".join([f"<@&{r_id}>" for r_id in excludes]) if excludes else "없음"
            embed.add_field(name="🚫 보상 제외 역할", value=exclude_text, inline=False)
            
            await interaction.response.send_message(embed=embed)

        # 제외 역할 등록 (exclude_add)
        elif 작업 == "exclude_add":
            if 역할 is None: return await interaction.response.send_message("❌ 역할을 선택해주세요.", ephemeral=True)
            if self.role_manager.add_exclude_role(guild_id, str(역할.id)):
                await interaction.response.send_message(f"🚫 {역할.mention} 보유자는 이제 보상에서 제외됩니다.")
            else:
                await interaction.response.send_message("❌ 이미 등록된 역할입니다.", ephemeral=True)

        # 제외 역할 해제 (Brilliance)
        elif 작업 == "exclude_remove":
            if 역할 is None: return await interaction.response.send_message("❌ 역할 선택 필수.", ephemeral=True)
            if self.role_manager.remove_exclude_role(guild_id, str(역할.id)):
                await interaction.response.send_message(f"✅ {역할.mention} 제외 해제 완료.")
            else:
                await interaction.response.send_message("❌ 목록에 없는 역할입니다.", ephemeral=True)

        # 7. 알림 채널 설정 (set_notify)
        elif 작업 == "set_notify":
            if 채널 is None:
                return await interaction.response.send_message("❌ 채널을 선택해주세요.", ephemeral=True)
            self.role_manager.set_notification_channel(guild_id, str(채널.id))
            await interaction.response.send_message(f"🔔 역할 지급 알림 채널이 {채널.mention}으로 설정되었습니다.")
            
async def setup(bot):
    await bot.add_cog(RoleRewardCog(bot))