import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from typing import Optional

logger = logging.getLogger("anonymous_system")

# ================= 설정 구간 =================
ADMIN_PASSWORD = "6974"  # 사용하실 비밀번호로 변경하세요.
# ============================================

# 1. 관리자 확인용 결과 UI (번호 입력 후 데이터 출력)
class AnonymousTrackModal(discord.ui.Modal, title='대나무숲 발신자 확인'):
    msg_num = discord.ui.TextInput(
        label='확인할 번호', 
        placeholder='예: 123.456 (대괄호 제외)', 
        required=True,
        min_length=7,
        max_length=7
    )

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        # DatabaseManager를 통한 조회
        query = "SELECT user_id, user_name, content, timestamp FROM anonymous_messages WHERE msg_id = ?"
        result = self.db.execute_query(query, (self.msg_num.value,), 'one')

        if result:
            embed = discord.Embed(
                title="🔍 익명 기록 추적 완료", 
                description=f"번호 `{self.msg_num.value}`에 대한 조사 결과입니다.",
                color=discord.Color.red()
            )
            embed.add_field(name="작성자", value=f"{result['user_name']} (<@{result['user_id']}>)", inline=False)
            embed.add_field(name="내용", value=result['content'], inline=False)
            embed.add_field(name="작성 시간 (UTC)", value=result['timestamp'], inline=False)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❓ `{self.msg_num.value}` 번호에 해당하는 기록을 찾을 수 없습니다.", 
                ephemeral=True
            )

# 2. 비밀번호 인증용 모달 (추가됨)
class AnonymousAuthModal(discord.ui.Modal, title='관리자 인증'):
    password_input = discord.ui.TextInput(
        label='관리자 비밀번호',
        placeholder='비밀번호를 입력하세요.',
        style=discord.TextStyle.short,
        required=True
    )

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        # 입력한 비밀번호와 설정된 비밀번호 비교
        if self.password_input.value == ADMIN_PASSWORD:
            # 인증 성공 시 다음 단계(번호 입력창) 모달 출력
            await interaction.response.send_modal(AnonymousTrackModal(self.db))
        else:
            # 인증 실패 시 경고 메시지
            await interaction.response.send_message("❌ 비밀번호가 틀렸습니다.", ephemeral=True)

# 3. 메인 Cog 클래스
class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        from database_manager import DatabaseManager
        return DatabaseManager(str(guild_id))

    @app_commands.command(name="익명", description="리더양을 통해 익명 메시지를 보냅니다.")
    @app_commands.describe(대화="전달하고 싶은 내용을 입력하세요.")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        msg_id = f"{random.randint(100, 999)}.{random.randint(100, 999)}"
        db = self.get_db(interaction.guild.id)
        
        try:
            query = "INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)"
            db.execute_query(query, (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            await interaction.response.send_message(f"✅ 익명 메시지가 전송되었습니다. (번호: {msg_id})", ephemeral=True)
            await interaction.channel.send(f"👤 **[{msg_id}]** {대화}")
            
        except Exception as e:
            logger.error(f"익명 메시지 저장 중 오류 발생: {e}")
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)

    @app_commands.command(name="대나무숲", description="[관리자 전용]")
    async def anonymous_track(self, interaction: discord.Interaction):
        # 서버 관리자 권한 체크 (권한이 있어도 비밀번호는 쳐야 함)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 기능은 서버 관리자 권한이 있는 사용자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        db = self.get_db(interaction.guild.id)
        # 먼저 비밀번호 입력 모달을 띄움
        await interaction.response.send_modal(AnonymousAuthModal(db))

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousSystem(bot))