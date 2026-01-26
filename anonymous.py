# anonymous.py - 익명 시스템
import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from database_manager import DatabaseManager

logger = logging.getLogger("anonymous_system")

# 개발자 디스코드 ID
DEVELOPER_ID = 533493429489893390

class Anonymous(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        return DatabaseManager(f"database/{guild_id}.db")

# 대나무 숲 관련 View - 발신자 확인
class AnonymousTrackModal(discord.ui.Modal, title='대나무숲 발신자 확인'):
    msg_num = discord.ui.TextInput(label='확인할 번호', placeholder='예: 10.10 ~ 999.999', required=True, min_length=5, max_length=7)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        query = "SELECT user_id, user_name, content FROM anonymous_messages WHERE msg_id = ?"
        result = self.db.execute_query(query, (self.msg_num.value,), 'one')
        if result:
            embed = discord.Embed(title="🔍 익명 기록 추적 완료", color=discord.Color.red())
            embed.add_field(name="작성자", value=f"{result['user_name']} (<@{result['user_id']}>)", inline=False)
            embed.add_field(name="내용", value=result['content'], inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"❓ `{self.msg_num.value}` 번호를 찾을 수 없습니다.", ephemeral=True)

# 대나무 숲 관련 View - 관리자 인증
class AnonymousAuthModal(discord.ui.Modal, title='관리자 인증'):
    pw_input = discord.ui.TextInput(label='관리자 비밀번호', placeholder='비밀번호를 입력하세요.', required=True)
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
    async def on_submit(self, interaction: discord.Interaction):
        if self.pw_input.value == "18697418":
            view = discord.ui.View()
            btn = discord.ui.Button(label="메시지 번호 입력", style=discord.ButtonStyle.primary)
            btn.callback = lambda i: i.response.send_modal(AnonymousTrackModal(self.db))
            view.add_item(btn)
            await interaction.response.send_message("✅ 인증 성공!", view=view, ephemeral=True)
        else:
            await interaction.response.send_message("❎ 비밀번호가 틀렸습니다.", ephemeral=True)

# 대나무 숲 관련 View - 기록 조회
class AnonymousAdminView(discord.ui.View):
    def __init__(self, db_manager):
        super().__init__(timeout=None)
        self.db = db_manager
    @discord.ui.button(label='기록 조회하기', style=discord.ButtonStyle.danger)
    async def track_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnonymousAuthModal(self.db))

# 메인 Cog. 명령어
class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="익명", description="익명으로 메시지를 보냅니다.")
    @app_commands.describe(대화="익명으로 보낼 내용을 입력하세요")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'anonymous' 권한이 있는지 체크 (channel_config.py의 value="anonymous"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "anonymous", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 익명 메시지 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )

        # 3. 익명 메시지 로직 실행
        db = self.get_db(interaction.guild.id)
        
        # 고유 ID 생성 (중복 방지)
        msg_id = ""
        attempts = 0
        while attempts < 10:
            msg_id = f"{random.randint(10, 999)}.{random.randint(10, 999)}"
            if not db.execute_query("SELECT 1 FROM anonymous_messages WHERE msg_id = ?", (msg_id,), 'one'):
                break
            attempts += 1

        try:
            # DB 저장 및 전송
            db.execute_query(
                "INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)", 
                (msg_id, str(interaction.user.id), str(interaction.user), 대화)
            )
            
            # 유저에게는 비밀 메시지로 성공 알림
            await interaction.response.send_message(f"✅ 익명 메시지를 보냈습니다. (번호: {msg_id})", ephemeral=True)
            
            # 채널에는 익명 임베드 전송
            embed = discord.Embed(description=대화, color=discord.Color.blue())
            embed.set_author(name=f"익명 유저 [{msg_id}]")
            await interaction.channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Anonymous Send Error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 메시지 전송 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="대나무숲", description="관리자 메뉴: 최근 익명 메시지를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.checks.has_permissions(administrator=True)
    async def anonymous_admin(self, interaction: discord.Interaction):
        db = self.get_db(interaction.guild.id)
        # 최근 10개 메시지 조회
        logs = db.execute_query("SELECT msg_id, user_name, content FROM anonymous_messages ORDER BY timestamp DESC LIMIT 10", (), 'all')
        
        if not logs:
            return await interaction.response.send_message("기록된 익명 메시지가 없습니다.", ephemeral=True)
            
        embed = discord.Embed(title="🌲 대나무숲 관리자 로그", color=discord.Color.dark_green())
        for log in logs:
            embed.add_field(name=f"ID: {log[0]} ({log[1]})", value=log[2][:100], inline=False)
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Anonymous(bot))