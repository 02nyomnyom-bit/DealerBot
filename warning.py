# warning.py - [서버관리] 경고제도
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
from typing import Literal, Optional

class ApprovalView(discord.ui.View):
    def __init__(self, action_type, user, target, reason, cog):
        super().__init__(timeout=300)
        self.action_type = action_type
        self.user = user
        self.target = target
        self.reason = reason
        self.cog = cog

    @discord.ui.button(label="승인", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자만 승인할 수 있습니다.", ephemeral=True)
        
        await interaction.response.edit_message(content="✅ 승인되었습니다.", view=None)
        if self.action_type == "warn":
            await self.cog._apply_warn(self.target, self.reason, self.user)
        else:
            await self.cog._apply_caution(self.target, self.reason, self.user)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자만 거절할 수 있습니다.", ephemeral=True)
        await interaction.response.edit_message(content="❌ 거절되었습니다.", view=None)

class WarningSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warn_data = {} 
        self.caution_data = {} 
        self.pre_ban_list = set() # 사전 차단할 유저 ID 목록
        self.manager_role_id = None 
        self.approval_channel_id = None
        self.TOTAL_ADMIN_ID = 533493429489893390

    async def _notify_total_admin(self, action_type, target, reason, admin, amount=None):
        """총 관리자에게 관리 활동 알림을 보냅니다."""
        # 본인이 수행한 활동은 알림을 보내지 않음
        if admin.id == self.TOTAL_ADMIN_ID:
            return

        try:
            total_admin = self.bot.get_user(self.TOTAL_ADMIN_ID)
            if not total_admin:
                total_admin = await self.bot.fetch_user(self.TOTAL_ADMIN_ID)
            
            if not total_admin:
                return

            action_names = {
                "warn": "경고 부여",
                "caution": "주의 부여",
                "warn_reduce": "경고 삭감",
                "caution_reduce": "주의 삭감"
            }
            action_name = action_names.get(action_type, "알 수 없는 활동")
            
            embed = discord.Embed(
                title=f"🚨 [관리자 알림] {action_name} 보고",
                description=f"관리 권한을 가진 이용자에 의해 {action_name}가 수행되었습니다.",
                color=discord.Color.orange() if "reduce" not in action_type else discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.add_field(name="담당 관리진", value=f"{admin.mention} ({admin.display_name})", inline=True)
            embed.add_field(name="대상 이용자", value=f"{target.mention} ({target.display_name})", inline=True)
            
            if amount:
                embed.add_field(name="삭감 횟수", value=f"{amount}회", inline=True)
            
            embed.add_field(name="내용/사유", value=reason, inline=False)
            
            await total_admin.send(embed=embed)
        except Exception as e:
            print(f"총 관리자 알림 전송 실패: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.id in self.pre_ban_list:
            try:
                await member.ban(reason="사전 차단 목록에 등록된 유저")
            except:
                pass

    warning_config = app_commands.Group(name="경고설정", description="경고 시스템 환경 설정을 관리합니다.")

    @warning_config.command(name="사전차단", description="특정 유저 ID를 사전 차단 목록에 추가/제거합니다. (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def manage_pre_ban(self, interaction: discord.Interaction, 유저id: str, 상태: Literal["추가", "제거"]):
        uid = int(유저id)
        if 상태 == "추가":
            self.pre_ban_list.add(uid)
            await interaction.response.send_message(f"✅ {유저id} 유저가 사전 차단 목록에 추가되었습니다.", ephemeral=True)
        else:
            self.pre_ban_list.discard(uid)
            await interaction.response.send_message(f"✅ {유저id} 유저가 사전 차단 목록에서 제거되었습니다.", ephemeral=True)

    @warning_config.command(name="채널", description="경고/주의 승인 요청을 받을 채널을 설정합니다. (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_approval_channel(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        self.approval_channel_id = 채널.id
        await interaction.response.send_message(f"✅ 경고 승인 채널이 {채널.mention}로 설정되었습니다.", ephemeral=True)

    @warning_config.command(name="역할", description="경고 관련 명령어를 사용할 수 있는 관리 역할을 설정합니다. (관리자 전용)")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_manager_role(self, interaction: discord.Interaction, 역할: discord.Role):
        self.manager_role_id = 역할.id
        await interaction.response.send_message(f"✅ 경고 관리 역할이 {역할.mention}로 설정되었습니다.", ephemeral=True)

    @app_commands.command(name="경고", description="이용자에게 경고를 부여합니다.")
    @app_commands.describe(이용자="경고를 줄 멤버", 메시지="경고 사유")
    async def warn(self, interaction: discord.Interaction, 이용자: discord.Member, 메시지: str):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = self.manager_role_id and any(r.id == self.manager_role_id for r in interaction.user.roles)
        
        if not (is_admin or has_role):
            return await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

        if is_admin:
            await self._apply_warn(이용자, 메시지, interaction.user)
            await interaction.response.send_message("✅ 경고가 즉시 부여되었습니다.", ephemeral=True)
        else:
            await self._request_approval("warn", interaction, 이용자, 메시지)

    async def _apply_warn(self, 이용자, 메시지, admin):
        uid = str(이용자.id)
        if uid not in self.warn_data: self.warn_data[uid] = []
        warn_entry = {"reason": 메시지, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "admin": admin.display_name}
        self.warn_data[uid].append(warn_entry)
        
        warn_count = len(self.warn_data[uid])
        
        # 관리자에게 보내는 알림
        admin_embed = discord.Embed(title="⚠️ 이용자 경고 부여", description=f"{이용자.mention}님에게 경고가 부여되었습니다.", color=discord.Color.red())
        admin_embed.add_field(name="사유", value=메시지, inline=False)
        admin_embed.add_field(name="누적 경고 횟수", value=f"총 **{warn_count}**회", inline=True)
        admin_embed.add_field(name="담당 관리진", value=admin.display_name, inline=True)
        await admin.send(embed=admin_embed)
        
        # 총 관리자에게 알림 보고
        await self._notify_total_admin("warn", 이용자, 메시지, admin)

        # 이용자에게 보내는 알림 (임베드)
        user_embed = discord.Embed(
            title="⚠️ 경고 부여 알림",
            description="서버 관리진으로부터 경고를 받았습니다.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        user_embed.add_field(name="사유", value=메시지, inline=False)
        user_embed.add_field(name="누적 경고 횟수", value=f"총 **{warn_count}**회", inline=True)
        user_embed.set_footer(text="반복적인 경고 누적 시 서버 이용이 제한될 수 있습니다.")
        
        try: await 이용자.send(embed=user_embed)
        except: pass

        if warn_count >= 3:
            try:
                await 이용자.ban(reason="경고 3회 누적")
                await admin.send(f"❌ {이용자.mention}님이 경고 3회 누적으로 차단되었습니다.")
            except:
                pass

    @app_commands.command(name="경고삭감", description="이용자의 경고를 삭감합니다.")
    @app_commands.describe(이용자="경고를 삭감할 멤버", 횟수="삭감할 횟수 (기본 1회)", 사유="삭감 사유")
    async def reduce_warn(self, interaction: discord.Interaction, 이용자: discord.Member, 횟수: int = 1, 사유: str = "관리자 판단에 의한 삭감"):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = self.manager_role_id and any(r.id == self.manager_role_id for r in interaction.user.roles)
        
        if not (is_admin or has_role):
            return await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

        uid = str(이용자.id)
        if uid not in self.warn_data or not self.warn_data[uid]:
            return await interaction.response.send_message(f"❌ {이용자.mention}님은 삭감할 경고가 없습니다.", ephemeral=True)

        current_count = len(self.warn_data[uid])
        reduce_amount = min(횟수, current_count)
        
        for _ in range(reduce_amount):
            self.warn_data[uid].pop()
            
        new_count = len(self.warn_data[uid])
        
        # 관리자에게 결과 알림
        embed = discord.Embed(title="✅ 경고 삭감 완료", description=f"{이용자.mention}님의 경고가 삭감되었습니다.", color=discord.Color.green())
        embed.add_field(name="삭감 횟수", value=f"{reduce_amount}회", inline=True)
        embed.add_field(name="현재 남은 경고", value=f"총 **{new_count}**회", inline=True)
        embed.add_field(name="사유", value=사유, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 총 관리자에게 보고
        await self._notify_total_admin("warn_reduce", 이용자, 사유, interaction.user, amount=reduce_amount)
        
        # 이용자에게 알림 (임베드)
        user_embed = discord.Embed(
            title="✨ 경고 삭감 알림",
            description="서버 관리진에 의해 경고가 삭감되었습니다.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        user_embed.add_field(name="삭감 횟수", value=f"{reduce_amount}회", inline=True)
        user_embed.add_field(name="현재 누적 경고", value=f"총 **{new_count}**회", inline=True)
        user_embed.add_field(name="사유", value=사유, inline=False)
        
        try: await 이용자.send(embed=user_embed)
        except: pass

    async def _request_approval(self, action_type, interaction, target, reason):
        if not self.approval_channel_id:
            return await interaction.response.send_message("❌ 승인 채널이 설정되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
        
        channel = self.bot.get_channel(self.approval_channel_id)
        if not channel:
            return await interaction.response.send_message("❌ 승인 채널을 찾을 수 없습니다.", ephemeral=True)

        embed = discord.Embed(title="🔔 경고/주의 승인 요청", description=f"관리자 승인이 필요합니다.", color=discord.Color.blue())
        embed.add_field(name="요청자", value=interaction.user.mention)
        embed.add_field(name="대상", value=target.mention)
        embed.add_field(name="사유", value=reason)
        view = ApprovalView(action_type, interaction.user, target, reason, self)
        await interaction.response.send_message("✅ 관리자의 승인을 기다리는 중입니다.", ephemeral=True)
        await channel.send(embed=embed, view=view)

    @app_commands.command(name="주의", description="이용자에게 주의를 줍니다.")
    @app_commands.describe(이용자="주의를 줄 멤버", 메시지="주의 사유")
    async def caution(self, interaction: discord.Interaction, 이용자: discord.Member, 메시지: str):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = self.manager_role_id and any(r.id == self.manager_role_id for r in interaction.user.roles)
        if not (is_admin or has_role):
            return await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

        if is_admin:
            await self._apply_caution(이용자, 메시지, interaction.user)
            await interaction.response.send_message("✅ 주의가 즉시 부여되었습니다.", ephemeral=True)
        else:
            await self._request_approval("caution", interaction, 이용자, 메시지)

    async def _apply_caution(self, 이용자, 메시지, admin):
        uid = str(이용자.id)
        self.caution_data[uid] = self.caution_data.get(uid, 0) + 1
        count = self.caution_data[uid]
        
        # 관리자에게 보내는 알림
        admin_embed = discord.Embed(title="🟡 이용자 주의 안내", description=f"{이용자.mention}님, 원활한 서버 이용을 위해 주의 부탁드립니다.", color=discord.Color.yellow())
        admin_embed.add_field(name="내용", value=메시지, inline=False)
        admin_embed.add_field(name="누적 주의 횟수", value=f"{count}회", inline=True)
        admin_embed.add_field(name="담당 관리진", value=admin.display_name, inline=True)
        await admin.send(embed=admin_embed)
        
        # 총 관리자에게 알림 보고
        await self._notify_total_admin("caution", 이용자, 메시지, admin)

        # 이용자에게 보내는 알림 (임베드)
        user_embed = discord.Embed(
            title="🟡 주의 안내",
            description="서버 관리진으로부터 주의를 받았습니다.",
            color=discord.Color.yellow(),
            timestamp=datetime.now()
        )
        user_embed.add_field(name="사유", value=메시지, inline=False)
        user_embed.add_field(name="누적 주의 횟수", value=f"총 **{count}**회", inline=True)
        user_embed.set_footer(text="주의 3회 누적 시 경고 1회로 전환됩니다.")

        try: await 이용자.send(embed=user_embed)
        except: pass

        if count >= 3:
            self.caution_data[uid] = 0
            await self._apply_warn(이용자, "주의 3회 누적에 의한 자동 경고", admin)

    @app_commands.command(name="주의삭감", description="이용자의 주의를 삭감합니다.")
    @app_commands.describe(이용자="주의를 삭감할 멤버", 횟수="삭감할 횟수 (기본 1회)", 사유="삭감 사유")
    async def reduce_caution(self, interaction: discord.Interaction, 이용자: discord.Member, 횟수: int = 1, 사유: str = "관리자 판단에 의한 삭감"):
        is_admin = interaction.user.guild_permissions.administrator
        has_role = self.manager_role_id and any(r.id == self.manager_role_id for r in interaction.user.roles)
        
        if not (is_admin or has_role):
            return await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

        uid = str(이용자.id)
        if uid not in self.caution_data or self.caution_data[uid] <= 0:
            return await interaction.response.send_message(f"❌ {이용자.mention}님은 삭감할 주의가 없습니다.", ephemeral=True)

        current_count = self.caution_data[uid]
        reduce_amount = min(횟수, current_count)
        self.caution_data[uid] -= reduce_amount
        
        new_count = self.caution_data[uid]
        
        # 관리자에게 결과 알림
        embed = discord.Embed(title="✅ 주의 삭감 완료", description=f"{이용자.mention}님의 주의가 삭감되었습니다.", color=discord.Color.green())
        embed.add_field(name="삭감 횟수", value=f"{reduce_amount}회", inline=True)
        embed.add_field(name="현재 남은 주의", value=f"총 **{new_count}**회", inline=True)
        embed.add_field(name="사유", value=사유, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 총 관리자에게 보고
        await self._notify_total_admin("caution_reduce", 이용자, 사유, interaction.user, amount=reduce_amount)
        
        # 이용자에게 알림 (임베드)
        user_embed = discord.Embed(
            title="✨ 주의 삭감 알림",
            description="서버 관리진에 의해 주의가 삭감되었습니다.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        user_embed.add_field(name="삭감 횟수", value=f"{reduce_amount}회", inline=True)
        user_embed.add_field(name="현재 누적 주의", value=f"총 **{new_count}**회", inline=True)
        user_embed.add_field(name="사유", value=사유, inline=False)
        
        try: await 이용자.send(embed=user_embed)
        except: pass

    @warn.error
    @caution.error
    @reduce_warn.error
    @reduce_caution.error
    async def admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 이 명령어를 사용할 권한이 없습니다.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WarningSystem(bot))
