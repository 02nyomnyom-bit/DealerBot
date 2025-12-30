import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from typing import Optional

logger = logging.getLogger("anonymous_system")

# 1. 관리자 확인용 UI (비밀번호 필드 제거됨)
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
            # result는 sqlite3.Row 객체이므로 딕셔너리처럼 접근 가능
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

# 2. 메인 Cog 클래스
class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        """해당 길드의 DatabaseManager 인스턴스를 반환"""
        # main.py에서 각 길드별 DB를 관리하므로 동일한 방식으로 가져옵니다.
        from database_manager import DatabaseManager
        return DatabaseManager(str(guild_id))

    @app_commands.command(name="익명", description="리더양을 통해 익명 메시지를 보냅니다.")
    @app_commands.describe(대화="전달하고 싶은 내용을 입력하세요.")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        # 랜덤 메시지 ID 생성 [000.000]
        msg_id = f"{random.randint(100, 999)}.{random.randint(100, 999)}"
        db = self.get_db(interaction.guild.id)
        
        try:
            # DB 저장 (테이블은 database_manager.py에서 자동 생성됨)
            query = "INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)"
            db.execute_query(query, (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            # 사용자에게 전송 성공 알림 (본인에게만 보임)
            await interaction.response.send_message(f"✅ 익명 메시지가 전송되었습니다. (번호: {msg_id})", ephemeral=True)
            
            # 채널에 익명으로 전송
            await interaction.channel.send(f"👤 **[{msg_id}]** {대화}")
            
        except Exception as e:
            logger.error(f"익명 메시지 저장 중 오류 발생: {e}")
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)

    @app_commands.command(name="대나무숲", description="[관리자 전용]")
    async def anonymous_track(self, interaction: discord.Interaction):
        # ✅ 보안: 서버 관리자 권한이 있는지 체크 (비밀번호 대체)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 기능은 서버 관리자 권한이 있는 사용자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        db = self.get_db(interaction.guild.id)
        # 모달창 띄우기 (비밀번호 입력칸 없음)
        await interaction.response.send_modal(AnonymousTrackModal(db))

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousSystem(bot))