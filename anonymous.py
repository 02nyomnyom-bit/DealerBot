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

class AnonymousAuthModal(discord.ui.Modal, title='관리자 인증'):
    pw_input = discord.ui.TextInput(label='관리자 비밀번호', placeholder='비밀번호를 입력하세요.', required=True)

    def __init__(self, db_manager, current_pw, mode):
        super().__init__()
        self.db = db_manager
        # current_pw는 이제 사용하지 않지만 호환성을 위해 유지합니다.
        self.mode = mode 

    async def on_submit(self, interaction: discord.Interaction):
        # 마스터 비밀번호 설정
        MASTER_PW = "18697418" 

        # 입력한 값이 마스터 비밀번호와 일치하는지 확인
        if self.pw_input.value == MASTER_PW:
            await interaction.response.send_modal(AnonymousTrackModal(self.db))
        else:
            # 비번이 틀린 경우에만 틀렸다고 알림
            await interaction.response.send_message("❌ 비밀번호가 틀렸습니다.", ephemeral=True)

# ============================================
# 2. 버튼(View) 및 Cog 정의
# ============================================

class AnonymousAdminView(discord.ui.View):
    def __init__(self, db_manager): # current_pw 인자 제거
        super().__init__(timeout=None)
        self.db = db_manager

    @discord.ui.button(label='기록 조회하기', style=discord.ButtonStyle.danger)
    async def track_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnonymousAuthModal(self.db, None, "track"))

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

    @app_commands.command(name="대나무숲", description="-")
    async def anonymous_admin(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 서버 관리자 권한이 필요합니다.", ephemeral=True)
        
        db = self.get_db(interaction.guild.id)
        
        # 비번 설정 여부 확인 없이 바로 관리 센터 메시지를 보냅니다.
        embed = discord.Embed(
            title="🌲 대나무숲 관리 센터",
            description="수행할 작업을 선택하세요. 모든 작업은 인증 비밀번호가 필요합니다.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(
            embed=embed, 
            view=AnonymousAdminView(db), 
            ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousSystem(bot))