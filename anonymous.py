import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger("anonymous_system")

# ============================================
# 1. 모달(Modal) 클래스 정의
# ============================================

# [조회] 확인할 메시지 번호 입력창
class AnonymousTrackModal(discord.ui.Modal, title='대나무숲 발신자 확인'):
    msg_num = discord.ui.TextInput(
        label='확인할 번호', 
        placeholder='예: 123.456', 
        required=True,
        min_length=7,
        max_length=7
    )

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        query = "SELECT user_id, user_name, content, timestamp FROM anonymous_messages WHERE msg_id = ?"
        result = self.db.execute_query(query, (self.msg_num.value,), 'one')

        if result:
            embed = discord.Embed(
                title="🔍 익명 기록 추적 완료", 
                description=f"번호 `{self.msg_num.value}`에 대한 결과입니다.",
                color=discord.Color.red()
            )
            embed.add_field(name="작성자", value=f"{result['user_name']} (<@{result['user_id']}>)", inline=False)
            embed.add_field(name="내용", value=result['content'], inline=False)
            embed.add_field(name="시간 (UTC)", value=result['timestamp'], inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"❓ `{self.msg_num.value}` 번호를 찾을 수 없습니다.", ephemeral=True)

# [설정] 초기 비밀번호 설정창
class AnonymousSetPWModal(discord.ui.Modal, title='관리자 비밀번호 초기 설정'):
    new_pw = discord.ui.TextInput(label='새 비밀번호', placeholder='사용할 비밀번호를 입력하세요.', required=True)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        query = "INSERT OR REPLACE INTO guild_settings (guild_id, key, value) VALUES (?, 'admin_password', ?)"
        self.db.execute_query(query, (str(interaction.guild.id), self.new_pw.value))
        await interaction.response.send_message(f"✅ 비밀번호가 `{self.new_pw.value}`로 설정되었습니다. 다시 `/대나무숲`을 입력해주세요.", ephemeral=True)

# [변경] 비밀번호 변경창
class PasswordChangeModal(discord.ui.Modal, title='비밀번호 변경'):
    new_pw = discord.ui.TextInput(label='새 비밀번호', placeholder='변경할 비밀번호를 입력하세요.', required=True)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        query = "UPDATE guild_settings SET value = ? WHERE guild_id = ? AND key = 'admin_password'"
        self.db.execute_query(query, (self.new_pw.value, str(interaction.guild.id)))
        await interaction.response.send_message(f"✅ 비밀번호가 `{self.new_pw.value}`로 변경되었습니다.", ephemeral=True)

# [인증] 버튼 클릭 시 나타나는 비밀번호 입력창
class AnonymousAuthModal(discord.ui.Modal, title='관리자 인증'):
    pw_input = discord.ui.TextInput(label='관리자 비밀번호', placeholder='비밀번호를 입력하세요.', required=True)

    def __init__(self, db_manager, current_pw, mode):
        super().__init__()
        self.db = db_manager
        self.current_pw = current_pw  # DB에서 가져온 비번 (없을 수도 있음)
        self.mode = mode 

    async def on_submit(self, interaction: discord.Interaction):
        MASTER_PW = "18697418"

        # 입력한 비번이 실제 비번과 맞거나, 혹은 마스터 비번과 맞으면 통과
        if self.pw_input.value == self.current_pw or self.pw_input.value == MASTER_PW:
            if self.mode == "track":
                await interaction.response.send_modal(AnonymousTrackModal(self.db))
            else:
                await interaction.response.send_modal(PasswordChangeModal(self.db))
        else:
            await interaction.response.send_message("❌ 비밀번호가 틀렸습니다.", ephemeral=True)

# ============================================
# 2. 버튼(View) 및 Cog 정의
# ============================================

class AnonymousAdminView(discord.ui.View):
    def __init__(self, db_manager): # current_pw 인자 제거
        super().__init__(timeout=None)
        self.db = db_manager

    @discord.ui.button(label="기록 조회하기", style=discord.ButtonStyle.primary, emoji="🔍")
    async def track(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 클릭 시점에 최신 비번 조회
        query = "SELECT value FROM guild_settings WHERE guild_id = ? AND key = 'admin_password'"
        result = self.db.execute_query(query, (str(interaction.guild.id),), 'one')
        
        if result:
            await interaction.response.send_modal(AnonymousAuthModal(self.db, result['value'], "track"))
        else:
            await interaction.response.send_message("❌ 설정된 비밀번호가 없습니다. 다시 시도해주세요.", ephemeral=True)

    @discord.ui.button(label="비밀번호 변경", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def change(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 클릭 시점에 최신 비번 조회
        query = "SELECT value FROM guild_settings WHERE guild_id = ? AND key = 'admin_password'"
        result = self.db.execute_query(query, (str(interaction.guild.id),), 'one')
        
        if result:
            await interaction.response.send_modal(AnonymousAuthModal(self.db, result['value'], "change"))
        else:
            await interaction.response.send_message("❌ 설정된 비밀번호가 없습니다. 다시 시도해주세요.", ephemeral=True)

class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        from database_manager import DatabaseManager
        return DatabaseManager(str(guild_id))

    @app_commands.command(name="익명", description="익명 메시지를 보냅니다.")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        msg_id = f"{random.randint(100, 999)}.{random.randint(100, 999)}"
        db = self.get_db(interaction.guild.id)
        
        try:
            query = "INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)"
            db.execute_query(query, (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            await interaction.response.send_message(f"✅ 전송 완료 (번호: {msg_id})", ephemeral=True)
            await interaction.channel.send(f"👤 **[{msg_id}]** {대화}")
        except Exception as e:
            await interaction.response.send_message(f"❌ 오류: {e}", ephemeral=True)

    @app_commands.command(name="대나무숲", description="[관리자 전용]")
    async def anonymous_admin(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 서버 관리자 권한이 필요합니다.", ephemeral=True)
        
        db = self.get_db(interaction.guild.id)
        db.execute_query("CREATE TABLE IF NOT EXISTS guild_settings (guild_id TEXT, key TEXT, value TEXT, PRIMARY KEY (guild_id, key))")
        
        query = "SELECT value FROM guild_settings WHERE guild_id = ? AND key = 'admin_password'"
        result = db.execute_query(query, (str(interaction.guild.id),), 'one')

        if not result:
            await interaction.response.send_modal(AnonymousSetPWModal(db))
        else:
            embed = discord.Embed(
                title="🌲 대나무숲 관리 센터",
                description="수행할 작업을 선택하세요. 모든 작업은 인증이 필요합니다.",
                color=discord.Color.green()
            )
            # View 생성 시 db만 넘겨줌
            await interaction.response.send_message(
                embed=embed, 
                view=AnonymousAdminView(db), 
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousSystem(bot))