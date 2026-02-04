# member_exit_logger.py - 퇴장 로그 시스템
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands, Member
import datetime
import json
from typing import Optional, Dict, Any, List
from database_manager import DatabaseManager

class MemberExitLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("✅ 통합 멤버 퇴장 로그 시스템 코그 초기화 완료")

    async def get_member_server_time(self, member: Member):
        """멤버의 서버 거주 시간 계산 (비동기 처리)"""
        if not member.joined_at:
            return "알 수 없음"

        now = datetime.datetime.now(datetime.timezone.utc)
        duration = now - member.joined_at

        days = duration.days
        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60
        seconds = duration.seconds % 60

        if days > 0:
            return f"{days}일 {hours}시간"
        elif hours > 0:
            return f"{hours}시간 {minutes}분"
        elif minutes > 0:
            return f"{minutes}분 {seconds}초"
        else:
            return f"{seconds}초"

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        """멤버가 서버를 떠났을 때 로그 기록 및 메시지 전송"""
        
        db = DatabaseManager(str(member.guild.id))
        
        # ✅ 설정이 활성화되어 있는지 확인
        setting = db.execute_query("SELECT * FROM log_settings WHERE guild_id = ?", (str(member.guild.id),), 'one')
        
        # 멤버 정보 수집
        server_time_str = await self.get_member_server_time(member)
        
        # 역할 정보 수집 (v1.0 기능 통합)
        roles_list = []
        if member.roles:
            for role in member.roles:
                if role.name != "@everyone":
                    roles_list.append({
                        "name": role.name,
                        "color": str(role.color)
                    })
        
        user_data = {
            "guild_id": str(member.guild.id),
            "user_id": str(member.id),
            "username": member.name,
            "display_name": member.display_name,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "left_at": datetime.datetime.now().isoformat(),
            "server_time": server_time_str,
            "avatar_url": member.avatar.url if member.avatar else member.default_avatar.url,
            "is_bot": int(member.bot),
            "roles": json.dumps(roles_list) # ✅ 역할 리스트를 JSON 문자열로 저장
        }
        
        # ✅ 데이터베이스에 로그 기록 (봇 포함)
        query = """
            INSERT INTO exit_logs (guild_id, user_id, username, display_name, joined_at, left_at, server_time, avatar_url, is_bot, roles)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        db.execute_query(query, list(user_data.values()))
        print(f"👋 {user_data['display_name']}님 퇴장 로그 기록 완료.")

        # ✅ 설정이 활성화되어 있으면 채널에 메시지 전송
        if setting and setting['enabled']:
            log_channel = self.bot.get_channel(int(setting['channel_id']))
            if log_channel:
                embed = self.create_exit_embed(member, server_time_str, roles_list)
                try:
                    await log_channel.send(embed=embed)
                    print(f"✅ {member.display_name} 퇴장 로그 메시지 전송 완료.")
                except discord.Forbidden:
                    print(f"❌ 퇴장 로그 채널에 메시지를 보낼 권한이 없습니다: {log_channel.id}")

    def create_exit_embed(self, member, server_time, roles_list):
        """퇴장 임베드 메시지 생성 헬퍼 함수 (v1.0 기능 통합)"""
        if member.bot:
            embed = discord.Embed(
                title="🤖 봇이 퇴장했어요",
                description=f"**{member.display_name}**이 서버를 떠났습니다.",
                color=discord.Color.light_grey(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(
                name="🤖 봇 정보",
                value=f"봇 이름: {member.name}\n서버 거주 시간: {server_time}",
                inline=True
            )
        else:
            embed = discord.Embed(
                title="👋 멤버가 퇴장했어요",
                description=f"**{member.display_name}**님이 서버를 떠났습니다.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now()
            )
            embed.add_field(
                name="👤 사용자 정보",
                value=f"사용자명: {member.name}\n닉네임: {member.display_name}\n서버 거주 시간: {server_time}",
                inline=True
            )
            if member.joined_at:
                joined_date = member.joined_at.strftime("%Y년 %m월 %d일")
                embed.add_field(
                    name="📅 가입 정보",
                    value=f"가입일: {joined_date}\n퇴장일: {datetime.datetime.now().strftime('%Y년 %m월 %d일')}",
                    inline=True
                )
            if roles_list:
                roles_text = ", ".join([f"`{role['name']}`" for role in roles_list[:5]])
                if len(roles_list) > 5:
                    roles_text += f" 외 {len(roles_list) - 5}개"
                embed.add_field(
                    name="🎭 보유 역할",
                    value=roles_text,
                    inline=False
                )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"사용자 ID: {member.id} | {member.guild.name}",
            icon_url=member.guild.icon.url if member.guild.icon else None
        )
        return embed
    
    @app_commands.command(name="퇴장로그관리", description="[관리자 전용] 퇴장 로그 시스템 관리")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        작업="수행할 작업 선택",
        채널="로그를 보낼 채널",
        일수="로그 조회 시 필요한 기간"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="⚙️ 설정/변경", value="setup"),
        app_commands.Choice(name="❌ 비활성화", value="disable"),
        app_commands.Choice(name="📊 상태 확인", value="status"),
        app_commands.Choice(name="📋 최근로그 조회", value="view")
    ])
    async def exit_log_admin(self, interaction: discord.Interaction, 작업: str, 채널: Optional[discord.TextChannel] = None, 일수: int = 7):
        if 작업 == "setup":
            if not 채널:
                return await interaction.response.send_message("❌ 설정을 위해 채널을 선택해주세요.", ephemeral=True)
            permissions = 채널.permissions_for(interaction.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                return await interaction.response.send_message(
                    f"❌ {채널.mention} 채널에 메시지를 보낼 권한이 없습니다.",
                    ephemeral=True
                )
            db = DatabaseManager(str(interaction.guild.id))
            query = "INSERT OR REPLACE INTO log_settings (guild_id, channel_id, enabled) VALUES (?, ?, ?)"
            db.execute_query(query, (str(interaction.guild.id), str(채널.id), 1))
        
            embed = discord.Embed(title="✅ 퇴장 로그 활성화", color=discord.Color.green())
            embed.add_field(name="📍 설정 채널", value=채널.mention, inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif 작업 == "disable":
            db = DatabaseManager(str(interaction.guild.id))
            db.execute_query("UPDATE log_settings SET enabled = 0 WHERE guild_id = ?", (str(interaction.guild.id),))
        
            await interaction.response.send_message("🔴 퇴장 로그 시스템이 비활성화되었습니다.", ephemeral=True)
        
        elif 작업 == "status":
            db = DatabaseManager(str(interaction.guild.id))
            setting = db.execute_query("SELECT * FROM log_settings WHERE guild_id = ?", (str(interaction.guild.id),), 'one')
        
            embed = discord.Embed(title="📊 퇴장 로그 시스템 상태", color=discord.Color.blue())
            if setting and setting['enabled']:
                channel = self.bot.get_channel(int(setting['channel_id']))
                embed.add_field(name="상태", value="🟢 활성", inline=True)
                embed.add_field(name="채널", value=channel.mention if channel else "⚠️ 채널 찾을 수 없음", inline=True)
            else:
                embed.add_field(name="상태", value="🔴 비활성", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif 작업 == "view":
            await interaction.response.defer(ephemeral=True)

            if 일수 <= 0:
                return await interaction.followup.send("일수는 1 이상으로 설정해주세요.", ephemeral=True)
            
            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=일수)).isoformat()
        
            db = DatabaseManager(str(interaction.guild.id))
            # ✅ 데이터베이스에서 최근 로그 조회
            query = """
                SELECT * FROM exit_logs
                WHERE guild_id = ? AND left_at >= ?
                ORDER BY left_at DESC
            """
            recent_logs = db.execute_query(query, (str(interaction.guild.id), cutoff_date), 'all')
        
            embed = discord.Embed(
                title=f"📋 {interaction.guild.name} 서버 퇴장 로그",
                description=f"최근 {일수}일 동안의 퇴장 기록입니다.",
                color=discord.Color.brand_red()
            )
        
            if recent_logs:
                log_text = ""
                for i, log in enumerate(recent_logs[:10]):  # 최대 10개만 표시
                    left_time = datetime.datetime.fromisoformat(log["left_at"])
                    time_str = left_time.strftime("%Y-%m-%d %H:%M")
                
                    user_type = "🤖" if log["is_bot"] else "👤"
                    log_text += f"{user_type} **{log['display_name']}** - {time_str}\n"
                    log_text += f"　└ 거주 시간: {log['server_time']}\n"
            
                if len(recent_logs) > 10:
                    log_text += f"\n... 외 {len(recent_logs) - 10}명"
            
                embed.add_field(
                    name="👋 퇴장한 멤버들",
                    value=log_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="ℹ️ 안내",
                    value="최근 퇴장한 멤버가 없습니다.",
                    inline=False
                )
        
            embed.set_footer(text=f"조회 기간: {일수}일 | 요청자: {interaction.user.display_name}")
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberExitLogger(bot))
    print("✅ 통합 멤버 퇴장 로그 시스템 로드 완료")