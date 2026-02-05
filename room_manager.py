import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
import asyncio

logger = logging.getLogger("room_manager")

# --- 1. 삭제 확인을 위한 버튼 뷰 클래스 ---
class DeleteConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, cog: commands.Cog):
        super().__init__(timeout=30)
        self.channel = channel
        self.cog = cog # 카테고리 정리를 위해 Cog 참조

    @discord.ui.button(label="정말 삭제할게요", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        category = self.channel.category
        channel_name = self.channel.name
        
        await interaction.response.send_message(f"🧹 `{channel_name}` 채널을 삭제합니다...", ephemeral=True)
        await self.channel.delete(reason="사용자 요청")
        
        # 채널 삭제 후 잠시 기다렸다가 카테고리가 비었는지 확인
        await asyncio.sleep(1)
        if category:
            await self.cog.cleanup_category(category)

    @discord.ui.button(label="아니요, 취소할게요", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    async def get_or_create_category(self, guild, name):
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name)
        return category

    async def cleanup_category(self, category: discord.CategoryChannel):
        """카테고리에 채널이 없으면 카테고리를 삭제합니다."""
        # 최신 상태의 채널 목록을 확인하기 위해 fetch_category 사용 권장되나 기본적으로 리스트 체크
        if len(category.channels) == 0:
            try:
                await category.delete(reason="빈 카테고리 자동 정리")
                logger.info(f"📁 빈 카테고리 삭제 완료: {category.name}")
            except Exception as e:
                logger.error(f"❌ 카테고리 삭제 실패: {e}")

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

        # [1] 역할지정
        if 작업 == "role_setup":
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 관리자만 설정 가능합니다.", ephemeral=True)
            if not 지정역할:
                return await interaction.response.send_message("❌ 역할을 선택해주세요.", ephemeral=True)
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("room_manager_role", str(지정역할.id)))
            return await interaction.response.send_message(f"✅ {지정역할.mention} 역할에게 권한을 부여했습니다.")

        # [권한 체크]
        role_data = db.execute_query("SELECT value FROM settings WHERE key = 'room_manager_role'", (), 'one')
        allowed = interaction.user.guild_permissions.administrator
        if role_data and not allowed:
            allowed = discord.utils.get(interaction.user.roles, id=int(role_data['value'])) is not None
        
        if not allowed:
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)

        # [2] 대화방 생성
        if 작업 == "text_setup":
            if not 제목: return await interaction.response.send_message("❌ 제목을 입력해주세요.", ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            category = await self.get_or_create_category(guild, "─── 임시 대화방 ───")
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True)
            }
            if 멤버: overwrites[멤버] = discord.PermissionOverwrite(view_channel=True)
            channel = await guild.create_text_channel(name=f"🔒-{제목}", category=category, overwrites=overwrites)
            await interaction.followup.send(f"✅ 대화방 생성: {channel.mention}")

        # [3] 음성방 생성
        elif 작업 == "voice_setup":
            if not 제목: return await interaction.response.send_message("❌ 제목을 입력해주세요.", ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            category = await self.get_or_create_category(guild, "─── 임시 음성방 ───")
            channel = await guild.create_voice_channel(name=f"🎙️ {제목}", category=category, user_limit=인원수)
            await interaction.followup.send(f"✅ 음성방 생성: {channel.mention}")

        # [4] 대화방 삭제
        elif 작업 == "text_delete":
            if not isinstance(interaction.channel, discord.TextChannel) or "🔒-" not in interaction.channel.name:
                return await interaction.response.send_message("❌ 이곳은 삭제 가능한 비밀방이 아닙니다.", ephemeral=True)
            
            view = DeleteConfirmView(interaction.channel, self)
            await interaction.response.send_message(
                f"⚠️ **방 삭제 확인**\n현재 방: **`{interaction.channel.name}`**\n정말 삭제하시겠습니까?",
                view=view, ephemeral=True
            )

    # [5] 음성방 자동 삭제 리스너
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel and before.channel.category and before.channel.category.name == "─── 임시 음성방 ───":
            # 봇 제외 실제 유저가 없으면 삭제
            if len([m for m in before.channel.members if not m.bot]) == 0:
                category = before.channel.category
                await before.channel.delete(reason="인원 없음")
                await asyncio.sleep(1)
                await self.cleanup_category(category)

async def setup(bot):
    await bot.add_cog(RoomManager(bot))