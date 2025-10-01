# voice_tracker.py
from __future__ import annotations
import datetime
import discord
import json
import os
import time
import logging
from discord import app_commands, Member
from discord.ext import commands, tasks
from typing import Dict, List, Optional, Set
from collections import defaultdict
from database_manager import get_guild_db_manager
from xp_leaderboard import check_and_send_levelup_notification
from xp_leaderboard import load_xp_settings

from xp_leaderboard import XPLeaderboardCog
from xp_leaderboard import role_reward_manager, ROLE_REWARD_AVAILABLE 

# 로거 설정
logger = logging.getLogger('voice_tracker')

# XP 설정 로드
xp_settings = load_xp_settings()
VOICE_XP_PER_MINUTE = xp_settings.get("voice_xp", 10)

# ✅ 초기화 확인 뷰
class VoiceResetConfirmView(discord.ui.View):
    def __init__(self, cog, guild_id: str, user_id: str = None, target_user: Member = None):
        super().__init__(timeout=30)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id
        self.target_user = target_user

    @discord.ui.button(label="✅ 확인", style=discord.ButtonStyle.danger)
    async def confirm_reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            success = self.cog.reset_voice_data_db(self.guild_id, self.user_id)
            
            if success:
                if self.target_user:
                    await interaction.response.send_message(f"✅ {self.target_user.display_name}님의 음성 기록이 초기화되었습니다.", ephemeral=True)
                else:
                    await interaction.response.send_message("✅ 모든 음성 기록이 초기화되었습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 기록 초기화에 실패했습니다.", ephemeral=True)
            self.stop()
        except Exception as e:
            logger.error(f"초기화 확인 버튼 오류: {e}")
            await interaction.response.send_message("❌ 알 수 없는 오류가 발생했습니다.", ephemeral=True)


# ==================== 메인 COG 클래스 ====================
class VoiceTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.xp_cog = XPLeaderboardCog(bot) # XPLeaderboardCog 인스턴스 생성
        self.active_sessions: Dict[str, Dict] = {}

    async def cog_load(self):
        """Cog이 로드될 때 태스크 시작"""
        self.update_sessions_loop.start()
        self.sync_voice_status_loop.start()

    def cog_unload(self):
        self.update_sessions_loop.cancel()
        self.sync_voice_status_loop.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # 봇은 무시
        if member.bot:
            return

        user_id_str = str(member.id)
        guild_id_str = str(member.guild.id) if member.guild else None
        
        if not guild_id_str:
            return

        was_unmuted = not (before.self_mute or before.deaf or before.self_deaf)
        is_unmuted = not (after.self_mute or after.deaf or after.self_deaf)
        
        # 음성 채널에 들어왔을 때
        if after.channel is not None and before.channel is None:
            if is_unmuted:
                self.active_sessions[user_id_str] = {
                    "guild_id": guild_id_str,
                    "last_active_time": time.time(),
                    "join_time": time.time(),
                    "channel_name": after.channel.name,
                    "is_speaking": True
                }
                logger.info(f"🎤 {member.name} (ID: {user_id_str})가 {after.channel.name} 채널에 입장. XP 세션 시작.")
            else:
                # 음소거 상태로 입장한 경우
                self.active_sessions[user_id_str] = {
                    "guild_id": guild_id_str,
                    "last_active_time": time.time(),
                    "join_time": time.time(),
                    "channel_name": after.channel.name,
                    "is_speaking": False
                }
                logger.info(f"🔇 {member.name} (ID: {user_id_str})가 음소거 상태로 {after.channel.name} 채널에 입장. XP 미지급.")

        # 채널을 이동했을 때
        elif before.channel is not None and after.channel is not None and before.channel != after.channel:
            if user_id_str in self.active_sessions:
                self.active_sessions[user_id_str]["channel_name"] = after.channel.name
                # 마이크 상태가 켜져 있으면 XP 세션 계속 진행
                if is_unmuted:
                    self.active_sessions[user_id_str]["is_speaking"] = True
                    self.active_sessions[user_id_str]["last_active_time"] = time.time()
                    logger.info(f"🔄 {member.name} (ID: {user_id_str})가 채널 이동 후 마이크 켬. XP 세션 계속 진행.")
                else:
                    self.active_sessions[user_id_str]["is_speaking"] = False
                    logger.info(f"🔄🔇 {member.name} (ID: {user_id_str})가 채널 이동 후 마이크 끔. XP 지급 중지.")
            else:
                # 이동했는데 세션이 없던 경우, 새로 생성
                if is_unmuted:
                    self.active_sessions[user_id_str] = {
                        "guild_id": guild_id_str,
                        "last_active_time": time.time(),
                        "join_time": time.time(),
                        "channel_name": after.channel.name,
                        "is_speaking": True
                    }
                    logger.info(f"🎤 {member.name} (ID: {user_id_str})가 채널 이동 후 마이크를 켜고 새로운 세션 시작.")
        
        # 동일 채널 내에서 마이크 상태만 변경되었을 때
        elif before.channel is not None and after.channel is not None and before.channel == after.channel:
            # 마이크가 켜졌을 때
            if is_unmuted and not was_unmuted:
                if user_id_str in self.active_sessions:
                    self.active_sessions[user_id_str]["is_speaking"] = True
                    self.active_sessions[user_id_str]["last_active_time"] = time.time()
                    logger.info(f"🎤 {member.name} (ID: {user_id_str})의 마이크가 켜졌습니다. XP 세션 재개.")
                else:
                    # 세션이 없던 경우 새로 생성 (봇 재시작 등)
                    self.active_sessions[user_id_str] = {
                        "guild_id": guild_id_str,
                        "last_active_time": time.time(),
                        "join_time": time.time(),
                        "channel_name": after.channel.name,
                        "is_speaking": True
                    }
                    logger.info(f"🎤 {member.name} (ID: {user_id_str})가 채널에 있었지만 세션이 없어 새로 시작합니다.")
            # 마이크가 꺼졌을 때
            elif not is_unmuted and was_unmuted:
                if user_id_str in self.active_sessions:
                    self.active_sessions[user_id_str]["is_speaking"] = False
                    logger.info(f"🔇 {member.name} (ID: {user_id_str})의 마이크가 꺼졌습니다. XP 지급 중지.")
        
        # 채널을 나갔을 때
        elif before.channel is not None and after.channel is None:
            if user_id_str in self.active_sessions:
                del self.active_sessions[user_id_str]
                logger.info(f"🚪 {member.name} (ID: {user_id_str})가 채널을 떠났습니다. XP 세션 종료.")

    @tasks.loop(minutes=1)
    async def update_sessions_loop(self):
        """1분마다 활성 음성 세션을 확인하고 XP를 지급합니다."""
        now = time.time()
        sessions_to_update = list(self.active_sessions.items())
                    
        for user_id, session in sessions_to_update:
            try:
                if "guild_id" in session and session.get("is_speaking", False):
                    guild_id = session["guild_id"]
                    guild = self.bot.get_guild(int(guild_id))
                    member = guild.get_member(int(user_id)) if guild else None
                    if not member:
                        logger.warning(f"❌ 멤버를 찾을 수 없어 XP 지급을 건너뜁니다. user_id={user_id}")
                        continue
                    # 레벨업 확인을 위한 이전 레벨 저장
                    old_level = self.xp_cog.get_user_level(user_id, guild_id)
                    # ✅ XP 지급
                    xp_gained = VOICE_XP_PER_MINUTE
                    success = await self.xp_cog.add_xp(user_id, guild_id, xp_gained)
                    if success:
                        logger.info(f"✅ {member.name}에게 음성 XP {xp_gained} 지급 완료!")
                        
                        # ✅ 레벨업 확인 및 알림
                        new_level = self.xp_cog.get_user_level(user_id, guild_id)
    
                        if new_level > old_level:
                            # 1. 레벨업 알림 전송 
                            await check_and_send_levelup_notification(self.bot, member, guild, old_level, new_level)
                            
                            # 2. 역할 지급 로직 (이 부분이 핵심!)
                            if ROLE_REWARD_AVAILABLE:
                                try:
                                    await role_reward_manager.check_and_assign_level_role(member, new_level, old_level)
                                    logger.info(f"✨ 역할 지급 성공: {member.name}에게 레벨 {new_level} 역할 지급 완료.")
                                except Exception as e:
                                    logger.error(f"❌ 역할 지급 중 오류 발생: {e}", exc_info=True)

                        session["last_active_time"] = now
                        
                    else:
                        logger.warning(f"❌ XP 지급 실패: user_id={user_id}, guild_id={guild_id}")
            
            except Exception as e:
                logger.error(f"❌ 음성 XP 지급 처리 중 오류 발생: {e}", exc_info=True)
                continue
                       
    @tasks.loop(minutes=5)
    async def sync_voice_status_loop(self):
        """5분마다 음성 채널 상태와 내부 데이터를 동기화하는 루프"""
        logger.info("🔄 음성 상태 동기화 루프 실행...")
        try:
            guild_ids_in_sessions = {session['guild_id'] for session in self.active_sessions.values()}
            
            for guild_id in guild_ids_in_sessions:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    continue

                # ✅ 모든 음성 채널의 멤버를 확인 (수정됨)
                members_in_vc = set()
                for voice_channel in guild.voice_channels:
                    for member in voice_channel.members:
                        members_in_vc.add(str(member.id))
                
                # 세션에 있지만 실제 채널에 없는 사용자 제거
                user_ids_to_remove = [
                    user_id for user_id, session in self.active_sessions.items()
                    if session['guild_id'] == guild_id and user_id not in members_in_vc
                ]
                for user_id in user_ids_to_remove:
                    if user_id in self.active_sessions:
                        # 제거되는 사용자 정보 로깅
                        member = guild.get_member(int(user_id))
                        member_name = member.display_name if member else f"ID:{user_id}"
                        logger.info(f"🧹 세션에서 사용자가 제거됨: {member_name} (ID={user_id}) - 실제 음성 채널에 없음")
                        del self.active_sessions[user_id]
                        
        except Exception as e:
            logger.error(f"❌ 동기화 루프 중 오류 발생: {e}")

    @app_commands.command(name="보이스시간", description="통화방에서 보낸 총 시간을 확인합니다.")
    async def voice_time_command(self, interaction: discord.Interaction, 사용자: Optional[Member] = None):
        target_member = 사용자 or interaction.user
        user_id = str(target_member.id)
        guild_id = str(interaction.guild.id)
            
        await interaction.response.defer(ephemeral=False)

        total_seconds = await self.get_user_total_voice_time(guild_id, user_id)
            
        formatted_time = self.format_duration(total_seconds)
            
        embed = discord.Embed(
            title=f"🎧 {target_member.display_name}님의 통화 시간",
            description=f"총 통화 시간: **{formatted_time}**",
            color=discord.Color.dark_orange()
        )
        embed.set_thumbnail(url=target_member.display_avatar.url)
        embed.set_footer(text=f"요청자: {interaction.user.display_name}")
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="보이스랭크", description="사용자의 통화 시간을 공개적으로 확인합니다")
    @app_commands.describe(사용자="확인할 사용자")
    async def voice_rank(self, interaction: discord.Interaction, 사용자: discord.Member):
        """보이스 랭크 확인 명령어 (공개)"""
        await interaction.response.defer()
        user_id = str(사용자.id)
        guild_id = str(interaction.guild.id)
        
        try:
            # 일일, 일주일, 한달, 전체 통계 조회
            daily_stats = self.get_voice_statistics_db(guild_id, user_id, 1)
            weekly_stats = self.get_voice_statistics_db(guild_id, user_id, 7)
            monthly_stats = self.get_voice_statistics_db(guild_id, user_id, 30)
            total_stats = self.get_voice_statistics_db(guild_id, user_id)
            
            if not total_stats:
                embed = discord.Embed(
                    title="📊 보이스 랭크",
                    description=f"🎤 **{사용자.display_name}**님의 통화 기록이 없습니다.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="💡 음성 XP 획득 방법",
                    value="음성 채널에 참여하고 **마이크를 켜고** 대화하면 **1분마다 10 XP**를 자동으로 획득합니다!",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            embed = discord.Embed(
                title="📊 보이스 랭크",
                description=f"🎤 **{사용자.display_name}**님의 통화 시간 통계",
                color=discord.Color.blue()
            )
            
            # 기간별 통계
            embed.add_field(
                name="📅 일일 통계 (24시간)",
                value=f"⏱️ {self.format_duration(daily_stats['period_time']) if daily_stats else '0초'}\n"
                      f"📞 {daily_stats['session_count'] if daily_stats else 0}회 통화",
                inline=True
            )
            
            embed.add_field(
                name="📆 일주일 통계 (7일)",
                value=f"⏱️ {self.format_duration(weekly_stats['period_time']) if weekly_stats else '0초'}\n"
                      f"📞 {weekly_stats['session_count'] if weekly_stats else 0}회 통화",
                inline=True
            )
            
            embed.add_field(
                name="🗓️ 한달 통계 (30일)",
                value=f"⏱️ {self.format_duration(monthly_stats['period_time']) if monthly_stats else '0초'}\n"
                      f"📞 {monthly_stats['session_count'] if monthly_stats else 0}회 통화",
                inline=True
            )
            
            # 전체 통계
            embed.add_field(
                name="🏆 전체 통계",
                value=f"⏱️ 총 시간: **{self.format_duration(total_stats['total_time'])}**\n"
                      f"📞 총 통화: **{total_stats['session_count']}회**\n"
                      f"📈 평균 시간: **{self.format_duration(total_stats['average_session'])}**",
                inline=False
            )
            
            embed.add_field(
                name="💎 XP 정보",
                value="**마이크를 켜고 대화 시 1분마다 10 XP** 자동 지급\n",
                inline=False
            )
            
            embed.set_footer(text=f"확인자: {interaction.user.display_name} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
             
        except Exception as e:
            logger.error(f"보이스랭크 명령어 오류: {e}")
            await interaction.followup.send("❌ 명령어 처리 중 오류가 발생했습니다.")

    @app_commands.command(name="보이스통계", description="기간별 통화 순위를 공개적으로 확인합니다 (상위 10명)")
    @app_commands.describe(기간="통계 기간 선택")
    @app_commands.choices(기간=[
        app_commands.Choice(name="📅 하루 (24시간)", value="1"),
        app_commands.Choice(name="📆 일주일 (7일)", value="7"),
        app_commands.Choice(name="🗓️ 2주일 (14일)", value="14"),
        app_commands.Choice(name="📋 한달 (30일)", value="30")
    ])
    async def voice_statistics(self, interaction: discord.Interaction, 기간: app_commands.Choice[str]):
        """보이스 통계 명령어 (공개, 상위 10명만)"""
        await interaction.response.defer()
        try:
            period_days = int(기간.value)
            guild_id = str(interaction.guild.id)
            top_users = self.get_top_voice_users_db(guild_id, 10)
            
            embed = discord.Embed(
                title="📊 기간별 통화 통계",
                description=f"🏆 **{기간.name}** 통화 순위 (상위 10명)",
                color=discord.Color.gold()
            )
            
            if not top_users:
                embed.add_field(
                    name="ℹ️ 현황", 
                    value=f"최근 {period_days}일간 통화 기록이 있는 사용자가 없습니다.", 
                    inline=False
                )
            else:
                ranking_text = ""
                for i, user in enumerate(top_users, 1):
                    if i <= 3:
                        medals = ["🥇", "🥈", "🥉"]
                        rank_display = medals[i-1]
                    else:
                        rank_display = f"**{i}.**"
                    
                    ranking_text += f"{rank_display} **{user['username']}**\n"
                    ranking_text += f"⏱️ {user['formatted_time']}\n\n"
                
                embed.add_field(name="🏅 순위", value=ranking_text, inline=False)
                
                embed.add_field(
                    name="💡 참고사항",
                    value="• **마이크를 켜고** 대화 시작 시부터 **1분마다 10 XP** 자동 지급\n• 순위는 실시간으로 업데이트됩니다",
                    inline=False
                )
            
            embed.set_footer(text=f"조회자: {interaction.user.display_name} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"보이스통계 명령어 오류: {e}")
            await interaction.followup.send("❌ 명령어 처리 중 오류가 발생했습니다.")

    @app_commands.command(name="보이스초기화", description="[관리자] 통화 시간 데이터를 초기화합니다")
    @app_commands.describe(사용자="초기화할 사용자 (미지정시 전체 초기화)")
    @commands.has_permissions(administrator=True)
    async def reset_voice_data_cmd(self, interaction: discord.Interaction, 사용자: Optional[discord.Member] = None):
        # The rest of the function remains the same
        try:
            if 사용자:
                embed = discord.Embed(
                    title="⚠️ 개인 데이터 초기화 확인",
                    description=f"**{사용자.display_name}**님의 모든 통화 시간 데이터를 삭제하시겠습니까?\n\n**이 작업은 되돌릴 수 없습니다!**",
                    color=discord.Color.orange()
                )
                view = VoiceResetConfirmView(self, str(사용자.id), 사용자)
            else:
                embed = discord.Embed(
                    title="⚠️ 전체 데이터 초기화 확인",
                    description="**모든 사용자**의 통화 시간 데이터를 삭제하시겠습니까?\n\n**이 작업은 되돌릴 수 없습니다!**",
                    color=discord.Color.red()
                )
                view = VoiceResetConfirmView(self)
            embed.set_footer(text="30초 내에 선택해주세요.")
                
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                
        except Exception as e:
            logger.error(f"보이스초기화 명령어 오류: {e}")
            await interaction.response.send_message("❌ 명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="보이스현황", description="현재 음성 채널 활동 현황을 확인합니다.")
    async def voice_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
            
        try:
            current_users = []
            for user_id, session in self.active_sessions.items():
                if session.get("is_speaking", False):
                    guild = self.bot.get_guild(int(session["guild_id"]))
                    member = guild.get_member(int(user_id)) if guild else None
                    if member:
                        # 총 활동 시간 계산
                        duration = time.time() - session["join_time"]
                        current_users.append({
                            "username": member.display_name,
                            "channel_name": session["channel_name"],
                            "duration": duration
                        })
            
            embed = discord.Embed(
                title="🎧 음성 채널 활동 현황",
                color=discord.Color.blue()
            )
                
            if not current_users:
                embed.description = "현재 마이크를 켜고 대화 중인 사용자가 없습니다."
                embed.add_field(
                    name="⏰ XP 정보",
                    value="**마이크를 켜고 대화 시** **1분마다 10 XP**를 자동으로 획득합니다!",
                    inline=False
                )
            else:
                embed.description = f"**{len(current_users)}명**이 현재 **마이크를 켜고** 대화 중입니다."
                    
                status_text = ""
                for i, user in enumerate(current_users, 1):
                    status_text += f"**{i}. {user['username']}**\n"
                    status_text += f"📢 채널: {user['channel_name']}\n"
                    status_text += f"⏱️ 시간: {self.format_duration(user['duration'])}\n\n"
                    
                if len(status_text) > 1024:
                    status_text = status_text[:1000] + "...\n*(일부 생략)*"
                    
                embed.add_field(name="📋 대화 중인 사용자 (마이크 ON)", value=status_text, inline=False)
                embed.add_field(
                    name="⏰ XP 정보",
                    value="**마이크를 켜고 대화 시 1분마다 10 XP** 자동 지급",
                    inline=False
                )
                
            embed.set_footer(text=f"확인자: {interaction.user.display_name} | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            await interaction.followup.send(embed=embed)
                
        except Exception as e:
            logger.error(f"음성현황 명령어 처리 중 오류 발생: {e}")
            await interaction.followup.send("❌ 명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

    def format_duration(self, seconds: int) -> str:
        """초를 'HH시간 MM분' 형식으로 변환"""
        minutes, seconds = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
            
        parts = []
        if hours > 0:
            parts.append(f"{hours}시간")
        if minutes > 0:
            parts.append(f"{minutes}분")
                
        return " ".join(parts) if parts else "1분 미만"

    # ✅ 음성 기록 초기화 기능
    def reset_voice_data_db(self, guild_id: str, user_id: str = None) -> bool:
        """
        데이터베이스의 음성 기록을 초기화합니다.
        user_id가 None이면 모든 기록 초기화.
        """
        db = get_guild_db_manager(guild_id)
        try:
            if user_id:
                query = "DELETE FROM voice_time WHERE user_id = ?"
                db.execute_query(query, (user_id,))
                logger.info(f"✅ 사용자 {user_id}의 음성 기록 초기화 완료.")
            else:
                query = "DELETE FROM voice_time"
                db.execute_query(query)
                logger.info("✅ 모든 음성 기록 초기화 완료.")
            return True
        except Exception as e:
            logger.error(f"음성 기록 초기화 실패: {e}")
            return False

    # 데이터베이스 관련 메서드들 추가
    async def get_user_total_voice_time(self, guild_id: str, user_id: str) -> int:
        """사용자의 총 음성 시간을 반환합니다."""
        db = get_guild_db_manager(guild_id)
        try:
            query = "SELECT total_time FROM voice_time WHERE user_id = ?"
            result = db.execute_query(query, (user_id,), 'one')
            return result['total_time'] if result and result['total_time'] else 0
        except Exception as e:
            logger.error(f"음성 시간 조회 실패: {e}")
            return 0

    def get_voice_statistics_db(self, guild_id: str, user_id: str, days: int = None) -> dict:
        """사용자의 음성 통계를 반환합니다."""
        db = get_guild_db_manager(guild_id)
        try:
            if days:
                query = """
                SELECT 
                    SUM(duration_minutes) as period_time,
                    COUNT(*) as session_count
                FROM voice_time_log 
                WHERE user_id = ? AND join_time >= datetime('now', '-{} days')
                """.format(days)
                result = db.execute_query(query, (user_id,), 'one')
                if result and result['period_time']:
                    return {
                        'period_time': result['period_time'] * 60, # 분을 초로 변환
                        'session_count': result['session_count']
                    }
            else:
                query = """
                SELECT 
                    total_time as total_time,
                    (SELECT COUNT(*) FROM voice_time_log WHERE user_id = ?) as session_count,
                    (SELECT AVG(duration_minutes) FROM voice_time_log WHERE user_id = ?) as average_session
                FROM voice_time 
                WHERE user_id = ?
                """
                result = db.execute_query(query, (user_id, user_id, user_id), 'one')
                if result and result['total_time']:
                    return {
                        'total_time': result['total_time'] * 60, # 분을 초로 변환
                        'session_count': result['session_count'],
                        'average_session': (result['average_session'] or 0) * 60 # 분을 초로 변환
                    }
            return None
        except Exception as e:
            logger.error(f"음성 통계 조회 실패: {e}")
            return None

    def get_top_voice_users_db(self, guild_id: str, limit: int = 10) -> List[dict]:
        """상위 음성 사용자 목록을 반환합니다."""
        db = get_guild_db_manager(guild_id)
        try:
            query = """
            SELECT 
                user_id,
                total_time
            FROM voice_time 
            ORDER BY total_time DESC 
            LIMIT ?
            """
            results = db.execute_query(query, (limit,), 'all')
            
            top_users = []
            if not results:
                return top_users

            for result in results:
                user_id = result['user_id']
                total_time = result['total_time'] * 60 # 분을 초로 변환
                
                user = self.bot.get_user(int(user_id))
                username = user.display_name if user else f"Unknown User ({user_id})"
                
                top_users.append({
                    'user_id': user_id,
                    'username': username,
                    'total_time': total_time,
                    'formatted_time': self.format_duration(total_time)
                })
            
            return top_users
        except Exception as e:
            logger.error(f"상위 사용자 조회 실패: {e}")
            return []

async def setup(bot):
    await bot.add_cog(VoiceTracker(bot))