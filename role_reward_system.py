# role_reward_system.py
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

# 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)

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
    
# --- [데이터 관리 클래스] 역할 보상 로직 처리 ---
class RoleRewardManager:
    """레벨별 역할 보상 관리 클래스"""
    
    def __init__(self):
        self.role_rewards: Dict[str, Dict[int, str]] = {}                    # {서버ID: {레벨: 역할ID}} 구조로 데이터 저장
        self.role_notification_channels = load_role_notification_channels()  # 역할 알림 채널 설정
        self.load_data()
    
    def load_data(self):
        """역할 보상 데이터 로드"""
        try:
            if os.path.exists(ROLE_REWARDS_FILE):
                with open(ROLE_REWARDS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 문자열 키를 int로 변환
                    for guild_id, rewards in data.items():
                        self.role_rewards[guild_id] = {int(level): role_id for level, role_id in rewards.items()}
                print(f"✅ 역할 보상 데이터 로드 완료: {len(self.role_rewards)}개 서버")
            else:
                self.role_rewards = {}
                print("📂 새로운 역할 보상 데이터 파일 생성")
        except Exception as e:
            print(f"❌ 역할 보상 데이터 로드 실패: {e}")
            self.role_rewards = {}
    
    def save_data(self):
        """역할 보상 데이터 저장"""
        try:
            # int 키를 문자열로 변환해서 저장
            save_data = {}
            for guild_id, rewards in self.role_rewards.items():
                save_data[guild_id] = {str(level): role_id for level, role_id in rewards.items()}
            
            with open(ROLE_REWARDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 역할 보상 데이터 저장 실패: {e}")
            return False
    
    def set_role_reward(self, guild_id: str, level: int, role_id: str) -> bool:
        """특정 레벨에 역할 보상 설정"""
        try:
            if guild_id not in self.role_rewards:
                self.role_rewards[guild_id] = {}
            
            self.role_rewards[guild_id][level] = role_id
            return self.save_data()
        except Exception as e:
            print(f"❌ 역할 보상 설정 실패: {e}")
            return False
    
    def remove_role_reward(self, guild_id: str, level: int) -> bool:
        """특정 레벨의 역할 보상 제거"""
        try:
            if guild_id in self.role_rewards and level in self.role_rewards[guild_id]:
                del self.role_rewards[guild_id][level]
                
                # 해당 서버의 보상이 모두 없으면 서버 데이터도 제거
                if not self.role_rewards[guild_id]:
                    del self.role_rewards[guild_id]
                
                return self.save_data()
            return False
        except Exception as e:
            print(f"❌ 역할 보상 제거 실패: {e}")
            return False
    
    def clear_all_rewards(self, guild_id: str) -> bool:
        """특정 서버의 모든 역할 보상 초기화"""
        try:
            if guild_id in self.role_rewards:
                del self.role_rewards[guild_id]
                return self.save_data()
            return True
        except Exception as e:
            print(f"❌ 역할 보상 초기화 실패: {e}")
            return False
    
    def get_role_rewards(self, guild_id: str) -> Dict[int, str]:
        """특정 서버의 역할 보상 목록 반환"""
        return self.role_rewards.get(guild_id, {})
    
    def get_role_for_level(self, guild_id: str, level: int) -> Optional[str]:
        """특정 레벨에 설정된 역할 ID 반환"""
        guild_rewards = self.role_rewards.get(guild_id, {})
        return guild_rewards.get(level)
    
    def get_all_levels_for_user(self, guild_id: str, user_level: int) -> List[int]:
        """사용자 레벨 이하의 모든 보상 레벨 반환 (정렬됨)"""
        guild_rewards = self.role_rewards.get(guild_id, {})
        return sorted([level for level in guild_rewards.keys() if level <= user_level])

    async def check_and_assign_level_role(self, member: discord.Member, new_level: int, old_level: int = 0):
        """레벨업 시 역할 확인 및 부여 - xp_leaderboard.py에서 호출되는 메서드"""
        guild_id = str(member.guild.id)
        guild_rewards = self.get_role_rewards(guild_id)
        
        if not guild_rewards:
            return  # 설정된 역할 보상이 없음
        
        try:
            # 봇 권한 확인
            if not member.guild.me.guild_permissions.manage_roles:
                print(f"⚠️ 역할 관리 권한이 없어서 {member.display_name}에게 역할을 부여할 수 없습니다.")
                return
            
            # 사용자가 달성한 레벨 이하의 모든 보상 레벨
            earned_levels = self.get_all_levels_for_user(guild_id, new_level)
            
            # 획득한 가장 높은 레벨의 역할만 유지
            highest_earned_level = max(earned_levels) if earned_levels else None
            target_role_id = guild_rewards.get(highest_earned_level) if highest_earned_level else None

            roles_to_remove = []
            roles_to_add = []

            for level, role_id_str in guild_rewards.items():
                role = member.guild.get_role(int(role_id_str))
                if not role:
                    continue  # 역할이 존재하지 않음

                # 봇 역할이 대상 역할보다 높은지 확인
                if role.position >= member.guild.me.top_role.position:
                    print(f"⚠️ 봇의 역할이 '{role.name}' 역할보다 낮아서 관리할 수 없습니다.")
                    continue

                has_role = role in member.roles
                # 현재 역할이 사용자가 가져야 할 가장 높은 레벨의 역할인지 확인
                is_target_role = str(role.id) == target_role_id

                if is_target_role and not has_role:
                    roles_to_add.append((level, role))
                elif not is_target_role and has_role:
                    roles_to_remove.append((level, role))
            
            # 역할 제거
            for level, role in roles_to_remove:
                try:
                    await member.remove_roles(role, reason=f"레벨 {new_level}: 더 이상 Lv.{level} 역할 자격 없음")
                    log_admin_action(f"[역할제거] {member.display_name} ({member.id}) Lv.{level} 역할 '{role.name}' 제거")
                except Exception as e:
                    print(f"❌ 역할 제거 실패 ({role.name}): {e}")
            
            # 역할 부여
            for level, role in roles_to_add:
                try:
                    await member.add_roles(role, reason=f"레벨업: Lv.{new_level} 달성으로 Lv.{level} 역할 획득")
                    log_admin_action(f"[역할부여] {member.display_name} ({member.id}) Lv.{level} 역할 '{role.name}' 부여")
                except Exception as e:
                    print(f"❌ 역할 부여 실패 ({role.name}): {e}")
            
            # 새로 부여된 역할이 있으면 알림
            if roles_to_add:
                try:
                    embed = discord.Embed(
                        title="🎉 새로운 역할 획득!",
                        description=f"**{member.display_name}**님이 레벨업으로 새로운 역할을 획득했습니다!",
                        color=discord.Color.gold()
                    )
                    
                    role_text = "\n".join([f"🏆 Lv.{level} - **{role.name}**" for level, role in roles_to_add])
                    embed.add_field(name="획득한 역할", value=role_text, inline=False)
                    embed.add_field(name="현재 레벨", value=f"**Lv.{new_level}**", inline=True)
                    
                    # 레벨 역할 지급 안내 채널에서 알림 전송 (우선순위)
                    notification_sent = False
                    if guild_id in self.role_notification_channels:
                        channel_id = self.role_notification_channels[guild_id]
                        channel = member.guild.get_channel(int(channel_id))
                        if channel:
                            await channel.send(embed=embed)
                            notification_sent = True
                    
                    # 설정된 채널이 없거나 채널을 찾을 수 없으면 일반 채널에서 알림
                    if not notification_sent:
                        for channel in member.guild.text_channels:
                            if channel.name in ['일반', 'general', '채팅']:
                                await channel.send(embed=embed)
                                break
                                
                except Exception as e:
                    print(f"❌ 역할 획득 알림 전송 실패: {e}")
        
        except Exception as e:
            print(f"❌ 역할 부여 처리 중 오류: {e}")

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
    
    @app_commands.command(name="역할설정", description="[관리자 전용] 특정 레벨에 도달시 부여할 역할을 설정합니다.")
    @app_commands.describe(레벨="역할을 부여할 레벨", 역할="부여할 역할")
    async def set_role_reward(self, interaction: discord.Interaction, 레벨: int, 역할: discord.Role):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        # 레벨 유효성 검사
        if 레벨 < 1 or 레벨 > 1000:
            return await interaction.response.send_message(
                "❌ 레벨은 1~1000 사이의 값이어야 합니다.", 
                ephemeral=True
            )
        
        # 봇 권한 확인
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❌ 봇에게 **역할 관리** 권한이 없습니다. 서버 설정에서 권한을 부여해주세요.", 
                ephemeral=True
            )
        
        # 봇 역할이 설정하려는 역할보다 높은지 확인
        if 역할.position >= interaction.guild.me.top_role.position:
            return await interaction.response.send_message(
                f"❌ 봇의 역할이 **{역할.name}** 역할보다 낮아서 부여할 수 없습니다.\n"
                f"봇의 역할을 더 높은 위치로 이동해주세요.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        
        # 역할 보상 설정
        if self.role_manager.set_role_reward(guild_id, 레벨, str(역할.id)):
            embed = discord.Embed(
                title="✅ 역할 보상 설정 완료",
                description=f"**Lv.{레벨}**에 도달한 사용자에게 **{역할.name}** 역할을 자동으로 부여합니다.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="📋 설정 내용",
                value=f"**레벨**: Lv.{레벨}\n**역할**: {역할.mention}\n**조건**: 레벨업으로 Lv.{레벨} 달성 시",
                inline=False
            )
            
            embed.add_field(
                name="🎯 보상 설정",
                value=f"Lv.{레벨} → **{역할.name}**",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="• 앞으로 이 레벨에 도달하는 사용자에게 자동으로 역할이 부여됩니다.\n"
                      "• 더 높은 레벨의 역할을 획득하면 낮은 레벨 역할은 자동으로 제거됩니다.\n"
                      "• `/역할목록`으로 설정된 모든 역할을 확인할 수 있습니다.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[역할보상설정] {interaction.user.display_name} ({interaction.user.id}) Lv.{레벨} → {역할.name} ({역할.id})")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ 역할 보상 설정에 실패했습니다. 다시 시도해주세요.", 
                ephemeral=True
            )
    
    @app_commands.command(name="역할목록", description="[관리자 전용] 설정된 레벨별 역할 보상 목록을 확인합니다.")
    async def list_role_rewards(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        guild_rewards = self.role_manager.get_role_rewards(guild_id)
        
        if not guild_rewards:
            embed = discord.Embed(
                title="📋 역할 보상 목록",
                description="아직 설정된 레벨별 역할 보상이 없습니다.\n`/역할설정`으로 새로운 보상을 추가해보세요!",
                color=discord.Color.blue()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        embed = discord.Embed(
            title="📋 레벨별 역할 보상 목록",
            description=f"현재 **{len(guild_rewards)}개**의 역할 보상이 설정되어 있습니다.",
            color=discord.Color.blue()
        )
        
        # 레벨 순으로 정렬
        sorted_rewards = sorted(guild_rewards.items())
        
        reward_text = ""
        valid_count = 0
        invalid_count = 0
        
        for level, role_id in sorted_rewards:
            role = interaction.guild.get_role(int(role_id))
            if role:
                reward_text += f"**Lv.{level}** → {role.mention} ({role.name})\n"
                valid_count += 1
            else:
                reward_text += f"**Lv.{level}** → ❌ *삭제된 역할* (ID: {role_id})\n"
                invalid_count += 1
        
        embed.add_field(
            name="🎯 설정된 보상",
            value=reward_text or "설정된 보상이 없습니다.",
            inline=False
        )
        
        # 통계 정보
        stats_text = f"✅ 유효한 보상: **{valid_count}개**"
        if invalid_count > 0:
            stats_text += f"\n❌ 무효한 보상: **{invalid_count}개**"
        
        embed.add_field(
            name="📊 통계",
            value=stats_text,
            inline=True
        )
        
        embed.add_field(
            name="🛠️ 관리 명령어",
            value="`/역할설정` - 새 보상 추가\n`/역할삭제` - 특정 보상 제거\n`/역할초기화` - 모든 보상 삭제",
            inline=True
        )
        
        embed.set_footer(text=f"관리자: {interaction.user.display_name} | {now_str()}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="역할삭제", description="[관리자 전용] 특정 레벨의 역할 보상을 삭제합니다.")
    @app_commands.describe(레벨="삭제할 역할 보상의 레벨")
    async def remove_role_reward(self, interaction: discord.Interaction, 레벨: int):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        # 레벨 유효성 검사
        if 레벨 < 1 or 레벨 > 1000:
            return await interaction.response.send_message(
                "❌ 레벨은 1~1000 사이의 값이어야 합니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        
        # 기존 설정 확인
        existing_role_id = self.role_manager.get_role_for_level(guild_id, 레벨)
        if not existing_role_id:
            return await interaction.response.send_message(
                f"❌ **Lv.{레벨}**에 설정된 역할 보상이 없습니다.", 
                ephemeral=True
            )
        
        # 역할 정보 가져오기
        role = interaction.guild.get_role(int(existing_role_id))
        role_name = role.name if role else f"삭제된 역할 (ID: {existing_role_id})"
        
        # 역할 보상 제거
        if self.role_manager.remove_role_reward(guild_id, 레벨):
            embed = discord.Embed(
                title="✅ 역할 보상 삭제 완료",
                description=f"**Lv.{레벨}**에 설정된 역할 보상이 삭제되었습니다.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="🗑️ 삭제된 보상",
                value=f"**레벨**: Lv.{레벨}\n**역할**: {role_name}",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="• 이미 부여된 역할은 자동으로 제거되지 않습니다.\n"
                      "• 필요시 수동으로 역할을 제거해주세요.\n"
                      "• `/역할목록`으로 남은 보상을 확인할 수 있습니다.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[역할보상삭제] {interaction.user.display_name} ({interaction.user.id}) Lv.{레벨} 보상 삭제: {role_name}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                "❌ 역할 보상 삭제에 실패했습니다. 다시 시도해주세요.", 
                ephemeral=True
            )
    
    @app_commands.command(name="역할초기화", description="[관리자 전용] 모든 레벨별 역할 보상을 삭제합니다.")
    async def clear_role_rewards(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        guild_rewards = self.role_manager.get_role_rewards(guild_id)
        
        if not guild_rewards:
            embed = discord.Embed(
                title="ℹ️ 초기화할 데이터 없음",
                description="설정된 역할 보상이 없어서 초기화할 것이 없습니다.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 확인 메시지 표시
        embed = discord.Embed(
            title="⚠️ 역할 보상 전체 초기화",
            description=f"정말로 **{len(guild_rewards)}개**의 모든 역할 보상을 삭제하시겠습니까?",
            color=discord.Color.red()
        )
        
        # 현재 설정된 보상들 표시
        reward_list = []
        for level in sorted(guild_rewards.keys()):
            role_id = guild_rewards[level]
            role = interaction.guild.get_role(int(role_id))
            role_name = role.name if role else f"삭제된 역할 (ID: {role_id})"
            reward_list.append(f"Lv.{level} → {role_name}")
        
        embed.add_field(
            name="🗑️ 삭제될 보상들",
            value="\n".join(reward_list[:10]) + ("\n..." if len(reward_list) > 10 else ""),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 주의사항",
            value="• 이 작업은 되돌릴 수 없습니다.\n"
                  "• 이미 부여된 역할은 자동으로 제거되지 않습니다.\n"
                  "• 60초 안에 확인해주세요.",
            inline=False
        )
        
        # 확인/취소 버튼 추가
        view = ClearConfirmView(self.role_manager, guild_id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="역할알림채널설정", description="[관리자 전용] 레벨 역할 지급 안내 채널을 설정합니다.")
    @app_commands.describe(채널="레벨 역할 지급 안내를 보낼 채널")
    async def setup_role_notification_channel(self, interaction: discord.Interaction, 채널: discord.TextChannel = None):
        """레벨 역할 지급 안내 채널 설정"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        if 채널:
            # 채널 설정
            self.role_manager.role_notification_channels[guild_id] = str(채널.id)
            if save_role_notification_channels(self.role_manager.role_notification_channels):
                embed = discord.Embed(
                    title="✅ 레벨 역할 지급 안내 채널 설정 완료",
                    description=f"레벨 역할이 지급되는 레벨에 달성하여 레벨 역할이 지급되는 경우, 레벨 역할이 지급되었다는 알림이 {채널.mention}에서 전송됩니다.",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 설정 내용",
                    value=f"**채널**: {채널.mention}\n**기능**: 레벨 역할 지급 알림",
                    inline=False
                )
                embed.add_field(
                    name="ℹ️ 안내",
                    value="• 사용자가 레벨업으로 새로운 역할을 획득할 때마다 이 채널에서 알림이 전송됩니다.\n"
                          "• 역할이 설정되지 않은 레벨의 레벨업에는 알림이 전송되지 않습니다.\n"
                          "• `/역할목록`으로 현재 설정된 역할들을 확인할 수 있습니다.",
                    inline=False
                )
                embed.set_footer(text=f"설정자: {interaction.user.display_name}")
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ 설정 저장에 실패했습니다.", ephemeral=True)
        else:
            # 현재 설정 확인
            if guild_id in self.role_manager.role_notification_channels:
                channel_id = self.role_manager.role_notification_channels[guild_id]
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    embed = discord.Embed(
                        title="📋 현재 레벨 역할 지급 안내 채널 설정",
                        description=f"현재 {channel.mention}으로 설정되어 있습니다.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="🔧 변경 방법",
                        value="`/역할알림채널설정 채널:[새채널]` - 새 채널로 변경\n"
                              "`/역할알림채널해제` - 설정 해제",
                        inline=False
                    )
                else:
                    embed = discord.Embed(
                        title="⚠️ 설정된 채널을 찾을 수 없음",
                        description="설정된 채널이 삭제되었거나 봇이 접근할 수 없습니다.\n새로운 채널을 설정해주세요.",
                        color=discord.Color.orange()
                    )
            else:
                embed = discord.Embed(
                    title="📋 레벨 역할 지급 안내 채널 미설정",
                    description="아직 레벨 역할 지급 안내 채널이 설정되지 않았습니다.",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="🔧 설정 방법",
                    value="`/역할알림채널설정 채널:[채널명]` - 채널 설정",
                    inline=False
                )
                embed.add_field(
                    name="ℹ️ 기본 동작",
                    value="채널이 설정되지 않은 경우, 역할 획득 알림은 '일반', 'general', '채팅' 채널에서 전송됩니다.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="역할알림채널해제", description="[관리자 전용] 레벨 역할 지급 안내 채널 설정을 해제합니다.")
    async def remove_role_notification_channel(self, interaction: discord.Interaction):
        """레벨 역할 지급 안내 채널 설정 해제"""
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        if guild_id in self.role_manager.role_notification_channels:
            # 기존 설정된 채널 정보
            channel_id = self.role_manager.role_notification_channels[guild_id]
            channel = self.bot.get_channel(int(channel_id))
            channel_name = channel.mention if channel else f"삭제된 채널 (ID: {channel_id})"
            
            # 설정 제거
            del self.role_manager.role_notification_channels[guild_id]
            if save_role_notification_channels(self.role_manager.role_notification_channels):
                embed = discord.Embed(
                    title="✅ 레벨 역할 지급 안내 채널 설정 해제 완료",
                    description=f"**{channel_name}**에 설정된 레벨 역할 지급 안내 기능이 해제되었습니다.",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="📋 변경 내용",
                    value="• 이제 역할 획득 알림이 설정된 전용 채널에서 전송되지 않습니다.\n"
                          "• 대신 '일반', 'general', '채팅' 채널에서 알림이 전송됩니다.",
                    inline=False
                )
                embed.add_field(
                    name="🔧 다시 설정하기",
                    value="`/역할알림채널설정 채널:[채널명]`",
                    inline=False
                )
                embed.set_footer(text=f"해제자: {interaction.user.display_name}")
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ 설정 해제에 실패했습니다.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="ℹ️ 해제할 설정이 없음",
                description="현재 설정된 레벨 역할 지급 안내 채널이 없습니다.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="🔧 설정 방법",
                value="`/역할알림채널설정 채널:[채널명]`",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class ClearConfirmView(discord.ui.View):
    """역할 보상 초기화 확인 View"""
    
    def __init__(self, role_manager: RoleRewardManager, guild_id: str, admin_id: int):
        super().__init__(timeout=60)
        self.role_manager = role_manager
        self.guild_id = guild_id
        self.admin_id = admin_id
    
    @discord.ui.button(label="✅ 확인", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 권한 재확인
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message(
                "❌ 본인만 이 작업을 확인할 수 있습니다.", 
                ephemeral=True
            )
        
        # 전체 초기화 실행
        guild_rewards = self.role_manager.get_role_rewards(self.guild_id)
        reward_count = len(guild_rewards)
        
        if self.role_manager.clear_all_rewards(self.guild_id):
            embed = discord.Embed(
                title="✅ 역할 보상 전체 초기화 완료",
                description=f"**{reward_count}개**의 모든 역할 보상이 삭제되었습니다.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="📋 초기화 결과",
                value="• 모든 레벨별 역할 보상이 제거되었습니다.\n"
                      "• 이미 부여된 역할은 유지됩니다.\n"
                      "• 새로운 보상은 `/역할설정`으로 추가할 수 있습니다.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[역할보상전체초기화] {interaction.user.display_name} ({interaction.user.id}) {reward_count}개 보상 삭제")
            
        else:
            embed = discord.Embed(
                title="❌ 초기화 실패",
                description="역할 보상 초기화 중 오류가 발생했습니다.",
                color=discord.Color.red()
            )
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 권한 재확인
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message(
                "❌ 본인만 이 작업을 취소할 수 있습니다.", 
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="⏹️ 초기화 취소됨",
            description="역할 보상 전체 초기화가 취소되었습니다.\n기존 설정이 그대로 유지됩니다.",
            color=discord.Color.blue()
        )
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """60초 타임아웃 시 버튼 비활성화"""
        for item in self.children:
            item.disabled = True
        
        # 메시지가 아직 유효한 경우에만 수정 시도
        try:
            embed = discord.Embed(
                title="⏰ 시간 만료",
                description="확인 시간이 만료되었습니다. 다시 시도해주세요.",
                color=discord.Color.orange()
            )
            # 원본 메시지 수정 (interaction이 없으므로 직접 수정 불가능)
        except:
            pass

async def setup(bot):
    await bot.add_cog(RoleRewardCog(bot))