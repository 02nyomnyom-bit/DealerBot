# room_manager.py 대화방생성
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging

logger = logging.getLogger("room_manager")

# --- 1. 삭제 확인을 위한 버튼 뷰 클래스 ---
class DeleteConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=30)
        self.channel = channel

    @discord.ui.button(label="정말 삭제할게요", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 삭제 버튼 클릭 시 처리
        await interaction.response.send_message(f"🧹 `{self.channel.name}` 채널을 삭제합니다...", ephemeral=True)
        await self.channel.delete(reason="사용자 요청에 의한 상담방 삭제")

    @discord.ui.button(label="아니요, 취소할게요", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 취소 버튼 클릭 시 처리
        await interaction.response.edit_message(content=f"❌ `{self.channel.name}` 삭제 작업이 취소되었습니다.", view=None)
        self.stop()

# --- 2. 메인 RoomManager 클래스 ---
class RoomManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        db_cog = self.bot.get_cog("DatabaseManager")
        if db_cog:
            return db_cog.get_manager(guild_id)
        return None

    room_group = app_commands.Group(name="방설정", description="대화방 및 음성방 관리 시스템")

    @room_group.command(name="작업", description="방 관련 작업을 수행합니다.")
    @app_commands.describe(
        작업="수행할 작업 선택",
        제목="대화방/음성방 이름",
        인원수="입장 가능한 최대 인원수 (음성방 전용)",
        멤버="초대할 멤버 (대화방 전용)",
        지정역할="방 생성 권한을 줄 역할 (역할지정 전용)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="역할지정", value="role_setup"),
        app_commands.Choice(name="대화방생성", value="text_setup"),
        app_commands.Choice(name="음성방생성", value="voice_setup"),
        app_commands.Choice(name="대화방삭제", value="text_delete")
    ])
    async def room_tasks(
        self, 
        interaction: discord.Interaction, 
        작업: str, 
        제목: Optional[str] = None, 
        인원수: Optional[int] = 0, 
        멤버: Optional[discord.Member] = None,
        지정역할: Optional[discord.Role] = None
    ):
        db = self.get_db(interaction.guild_id)
        guild = interaction.guild

        # 1. 역할지정 작업 (관리자 전용)
        if 작업 == "role_setup":
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 관리자만 권한 역할을 지정할 수 있습니다.", ephemeral=True)
            if not 지정역할:
                return await interaction.response.send_message("❌ 지정할 역할을 선택해주세요.", ephemeral=True)
            
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("room_manager_role", str(지정역할.id)))
            return await interaction.response.send_message(f"✅ 앞으로 {지정역할.mention} 역할을 가진 분들만 방 관리가 가능합니다.")

        # 2. 권한 확인 (역할 체크)
        role_data = db.execute_query("SELECT value FROM settings WHERE key = 'room_manager_role'", (), 'one')
        if not role_data:
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 아직 권한 역할이 지정되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
        else:
            allowed_role_id = int(role_data['value'])
            if discord.utils.get(interaction.user.roles, id=allowed_role_id) is None and not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 이 기능을 사용할 권한이 없습니다.", ephemeral=True)

        # 3. 대화방 생성
        if 작업 == "text_setup":
            if not 제목:
                return await interaction.response.send_message("❌ 생성할 방의 제목을 입력해주세요.", ephemeral=True)
            
            await interaction.response.defer(ephemeral=True)
            category = await self.get_or_create_category(guild, "─── 임시 대화방 ───")
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True),
                interaction.user: discord.PermissionOverwrite(view_channel=True)
            }
            if 멤버: overwrites[멤버] = discord.PermissionOverwrite(view_channel=True)

            channel = await guild.create_text_channel(
                name=f"🔒-{제목}", 
                category=category, 
                overwrites=overwrites, 
                topic=f"생성자:{interaction.user.id}"
            )
            await interaction.followup.send(f"✅ `{channel.name}` 대화방이 생성되었습니다: {channel.mention}")

        # 4. 음성방 생성
        elif 작업 == "voice_setup":
            if not 제목:
                return await interaction.response.send_message("❌ 생성할 방의 제목을 입력해주세요.", ephemeral=True)
            
            await interaction.response.defer(ephemeral=True)
            category = await self.get_or_create_category(guild, "─── 임시 음성방 ───")
            channel = await guild.create_voice_channel(name=f"🎙️ {제목}", category=category, user_limit=인원수)
            await interaction.followup.send(f"✅ 음성방이 생성되었습니다: {channel.mention}")

        # 5. 대화방 삭제 (확인 버튼 단계)
        elif 작업 == "text_delete":
            if not isinstance(interaction.channel, discord.TextChannel) or "🔒-" not in interaction.channel.name:
                return await interaction.response.send_message(
                    "❌ 이곳은 삭제 가능한 비밀 상담방이 아닙니다.", ephemeral=True
                )
            
            view = DeleteConfirmView(interaction.channel)
            await interaction.response.send_message(
                f"⚠️ **채널 삭제 경고**\n현재 계신 **` {interaction.channel.name} `** 방을 정말로 삭제하시겠습니까?\n모든 기록이 즉시 사라집니다.",
                view=view,
                ephemeral=True
            )

    async def get_or_create_category(self, guild, name):
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name)
        return category

async def setup(bot):
    await bot.add_cog(RoomManager(bot))