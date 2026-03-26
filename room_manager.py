import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger("room_manager")

# --- 1. 대화방 삭제용 버튼 뷰 ---
class DeleteConfirmView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__(timeout=30)
        self.channel = channel

    @discord.ui.button(label="정말 삭제할게요", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_name = self.channel.name
        
        await interaction.response.send_message(f"🧹 `{channel_name}` 채널을 삭제합니다...", ephemeral=True)
        await self.channel.delete(reason="사용자 요청")

    @discord.ui.button(label="아니요, 취소할게요", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content=f"❌ `{self.channel.name}` 삭제 작업이 취소되었습니다.", view=None)
        self.stop()


# --- 2. 메인 룸 매니저 클래스 ---
class RoomManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.rename_cooldown = {} # {유저ID: datetime} 1분 쿨타임용

    def get_db(self, guild_id: int):
        db_cog = self.bot.get_cog("DatabaseManager")
        return db_cog.get_manager(guild_id) if db_cog else None

    async def get_or_create_category(self, guild, name):
        category = discord.utils.get(guild.categories, name=name)
        if not category:
            category = await guild.create_category(name)
        return category

    room_group = app_commands.Group(name="방설정", description="대화방 및 음성방 관리 시스템")


    @room_group.command(name="작업", description="방 관련 작업을 수행합니다.")
    @app_commands.describe(
        작업="수행할 작업 선택",
        제목="방 이름 (생성 및 변경 시)",
        임시방제목="음성방 생성기에서 생성될 자동 방의 기본 이름",
        인원수="입장 가능한 최대 인원수 (인원수변경/음성방 생성 시)",
        멤버1="초대할 멤버 1 (대화방 전용)",
        멤버2="초대할 멤버 2 (대화방 전용)",
        멤버3="초대할 멤버 3 (대화방 전용)",
        지정역할="인원수 제한 권한을 줄 역할 (역할지정 전용)"
    )
    @app_commands.choices(작업=[
        app_commands.Choice(name="역할지정", value="role_setup"),
        app_commands.Choice(name="역할해제", value="role_remove"),
        app_commands.Choice(name="음성방생성기", value="voice_gen_setup"),
        app_commands.Choice(name="대화방생성기", value="text_gen_setup"),
        app_commands.Choice(name="방제변경", value="rename_room"),
        app_commands.Choice(name="인원수변경", value="limit_change"),
        app_commands.Choice(name="대화방삭제", value="text_delete")
    ])
    async def room_tasks(
        self, 
        interaction: discord.Interaction, 
        작업: str, 
        제목: Optional[str] = None, 
        임시방제목: Optional[str] = None,
        인원수: Optional[int] = 0, 
        멤버1: Optional[discord.Member] = None,
        멤버2: Optional[discord.Member] = None,
        멤버3: Optional[discord.Member] = None,
        지정역할: Optional[discord.Role] = None
    ):
        db = self.get_db(interaction.guild_id)
        guild = interaction.guild

        # [1] 역할 지정 / 해제
        if 작업 == "role_setup":
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 관리자 전용입니다.", ephemeral=True)
            if not 지정역할:
                return await interaction.response.send_message("❌ 역할을 선택해주세요.", ephemeral=True)
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("room_manager_role", str(지정역할.id)))
            return await interaction.response.send_message(f"✅ {지정역할.mention} 역할에게 인원수 제한 수정 권한을 부여했습니다.")

        elif 작업 == "role_remove":
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 관리자 전용입니다.", ephemeral=True)
            db.execute_query("DELETE FROM settings WHERE key = 'room_manager_role'")
            return await interaction.response.send_message("🗑️ 인원 제한 권한 설정이 해제되었습니다. 이제 관리자만 사용 가능합니다.")

        # 권한 확인 로직 (공통)
        role_data = db.execute_query("SELECT value FROM settings WHERE key = 'room_manager_role'", (), 'one')
        is_allowed = interaction.user.guild_permissions.administrator
        if role_data and not is_allowed:
            is_allowed = discord.utils.get(interaction.user.roles, id=int(role_data['value'])) is not None


        # [2] 음성방 생성기 (관리자 전용)
        if 작업 == "voice_gen_setup":
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message("❌ 관리자만 음성방 생성기를 만들 수 있습니다.", ephemeral=True)
            if not 제목:
                return await interaction.response.send_message("❌ 방명을 입력해주세요.", ephemeral=True)
            
            await interaction.response.defer(ephemeral=True)
            
            category = interaction.channel.category if interaction.channel.category else None
            
            temp_name = 임시방제목 if 임시방제목 else 제목
            topic_memo = f"생성기|기본명:{temp_name}|인원:{인원수}"
            
            channel = await guild.create_voice_channel(name=f"🎙️ {제목}", category=category)
            db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"v_gen_{channel.id}", topic_memo))
            
            await interaction.followup.send(f"✅ 음성방 생성기가 만들어졌습니다: {channel.mention}")


        # [3] 대화방 생성기 (역할권한 및 관리자 가능)
        elif 작업 == "text_gen_setup":
            if not is_allowed:
                return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
            if not 제목:
                return await interaction.response.send_message("❌ 제목을 입력해주세요.", ephemeral=True)
                
            await interaction.response.defer(ephemeral=True)
            category = await self.get_or_create_category(guild, "─── 임시 대화방 ───")
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True),
                interaction.user: discord.PermissionOverwrite(view_channel=True)
            }
            
            invited_members = []
            for m in [멤버1, 멤버2, 멤버3]:
                if m:
                    overwrites[m] = discord.PermissionOverwrite(view_channel=True)
                    invited_members.append(m.mention)

            channel = await guild.create_text_channel(name=f"🔒-{제목}", category=category, overwrites=overwrites)
            welcome_msg = f"✅ `{channel.name}` 생성 완료!"
            if invited_members:
                welcome_msg += f"\n초대된 멤버: {', '.join(invited_members)}"
            await interaction.followup.send(welcome_msg)


        # [4] 방제 변경 (내부 사람들만 가능, 쿨타임 1분)
        elif 작업 == "rename_room":
            if not interaction.user.voice or not interaction.user.voice.channel:
                return await interaction.response.send_message("❌ 음성 채널에 먼저 접속해 주세요.", ephemeral=True)
            if not 제목:
                return await interaction.response.send_message("❌ 변경할 제목을 입력해 주세요.", ephemeral=True)

            current_channel = interaction.user.voice.channel

            # 💡 원본 생성기 채널은 유저가 이름을 함부로 바꿀 수 없도록 잠금
            is_generator = db.execute_query("SELECT value FROM settings WHERE key = ?", (f"v_gen_{current_channel.id}",), 'one')
            if is_generator:
                return await interaction.response.send_message("❌ 음성방 생성기의 이름은 명령어로 변경할 수 없습니다.", ephemeral=True)

            is_temp = db.execute_query("SELECT value FROM settings WHERE key = ?", (f"v_temp_{current_channel.id}",), 'one')
            if not is_temp:
                return await interaction.response.send_message("❌ 이 방은 자동 생성된 임시 음성방이 아닙니다.", ephemeral=True)

            now = datetime.now()
            user_id = interaction.user.id
            if user_id in self.rename_cooldown:
                elapsed = now - self.rename_cooldown[user_id]
                if elapsed < timedelta(minutes=1):
                    remain = 60 - elapsed.seconds
                    return await interaction.response.send_message(f"⏳ 쿨타임 중입니다. {remain}초 뒤에 시도하세요.", ephemeral=True)

            await current_channel.edit(name=제목)
            self.rename_cooldown[user_id] = now
            await interaction.response.send_message(f"✅ 방 제목이 `{제목}`으로 변경되었습니다.")


        # [5] 인원수 변경 (지정 역할 및 관리자 가능)
        elif 작업 == "limit_change":
            if not is_allowed:
                return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
            if not interaction.user.voice or not interaction.user.voice.channel:
                return await interaction.response.send_message("❌ 음성 채널에 먼저 접속해 주세요.", ephemeral=True)

            current_channel = interaction.user.voice.channel

            await current_channel.edit(user_limit=인원수)
            await interaction.response.send_message(f"✅ 인원수가 {인원수}명으로 설정되었습니다.")


        # [6] 대화방 삭제
        elif 작업 == "text_delete":
            if not isinstance(interaction.channel, discord.TextChannel) or "🔒-" not in interaction.channel.name:
                return await interaction.response.send_message("❌ 삭제 가능한 방이 아닙니다.", ephemeral=True)
            view = DeleteConfirmView(interaction.channel)
            await interaction.response.send_message(f"⚠️ **방 삭제 확인**\n현재 방: **`{interaction.channel.name}`**\n정말 삭제하시겠습니까?", view=view, ephemeral=True)


    # ⚙️ 음성방 자동 관리 리스너
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        db = self.get_db(member.guild.id)
        if not db: return

        # 입장 시 자동 순간이동 및 방 복제
        if after.channel is not None:
            gen_data = db.execute_query("SELECT value FROM settings WHERE key = ?", (f"v_gen_{after.channel.id}",), 'one')
            
            if gen_data:
                memo = gen_data['value'].split('|')
                temp_name = memo[1].split(':')[1]
                limit = int(memo[2].split(':')[1])

                generator_category = after.channel.category
                
                new_channel = await member.guild.create_voice_channel(
                    name=temp_name, 
                    category=generator_category, 
                    user_limit=limit,
                    position=after.channel.position + 1
                )
                
                # 임시방 ID를 DB에 기록
                db.execute_query("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (f"v_temp_{new_channel.id}", "true"))
                
                await member.move_to(new_channel)

        # 퇴장 시 자동 방 청소
        if before.channel is not None:
            v_channel = before.channel
            
            # 💡 이모지에 의존하지 않고, DB에 기록된 임시 채널인지 조회
            temp_data = db.execute_query("SELECT value FROM settings WHERE key = ?", (f"v_temp_{v_channel.id}",), 'one')
            
            if temp_data:
                if len([m for m in v_channel.members if not m.bot]) == 0:
                    try:
                        await v_channel.delete()
                        db.execute_query("DELETE FROM settings WHERE key = ?", (f"v_temp_{v_channel.id}",))
                    except discord.NotFound:
                        db.execute_query("DELETE FROM settings WHERE key = ?", (f"v_temp_{v_channel.id}",))
                    except Exception as e:
                        logger.error(f"채널 삭제 중 에러 발생: {e}")


async def setup(bot):
    await bot.add_cog(RoomManager(bot))