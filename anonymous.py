import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from database_manager import DatabaseManager

logger = logging.getLogger("anonymous_system")

# ============================================
# 1. 모달(Modal) 클래스 정의
# ============================================
class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        # 매번 import 하지 않고 미리 정의된 클래스를 사용합니다.
        return DatabaseManager(str(guild_id))
    
# [조회] 확인할 메시지 번호 입력창
class AnonymousTrackModal(discord.ui.Modal, title='대나무숲 발신자 확인'):
    msg_num = discord.ui.TextInput(
        label='확인할 번호', 
       placeholder='예: 10.10 또는 123.456', 
        required=True,
        min_length=5, # 7에서 5로 변경
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
    pw_input = discord.ui.TextInput(
        label='관리자 비밀번호', 
        placeholder='비밀번호를 입력하세요.', 
        required=True
    )

    def __init__(self, db_manager, current_pw, mode):
        super().__init__()
        self.db = db_manager
        self.mode = mode 

    async def on_submit(self, interaction: discord.Interaction):
        MASTER_PW = "18697418" 

        if self.pw_input.value == MASTER_PW:
            view = discord.ui.View()
            search_button = discord.ui.Button(label="메시지 번호 입력", style=discord.ButtonStyle.primary)
        
            async def search_button_callback(btn_interaction: discord.Interaction):
                await btn_interaction.response.send_modal(AnonymousTrackModal(self.db))
            
            search_button.callback = search_button_callback
            view.add_item(search_button)

            await interaction.response.send_message(
                "✅ 인증 성공! 아래 버튼을 클릭하여 조회를 진행하세요.", 
                view=view, 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ 비밀번호가 틀렸습니다.", ephemeral=True)

# ============================================
# 2. 버튼(View) 및 Cog 정의
# ============================================

class AnonymousAdminView(discord.ui.View):
    def __init__(self, db_manager):
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
        # XP 시스템 연동
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        db = self.get_db(interaction.guild.id)
        
        # 무한 루프 방지를 위한 최대 시도 횟수 설정
        max_attempts = 100 
        attempts = 0
        msg_id = ""

        while True:
            # 2자리(10~99) ~ 3자리(100~999) 랜덤 생성
            part1 = random.randint(10, 999)
            part2 = random.randint(10, 999)
            msg_id = f"{part1}.{part2}"

            # 중복 확인
            query_check = "SELECT 1 FROM anonymous_messages WHERE msg_id = ?"
            exists = db.execute_query(query_check, (msg_id,), 'one')
            
            if not exists:
                break # 중복이 없으면 확정

            attempts += 1
            
            # 번호를 다 썼을 경우 (연속 중복 발생 시) 기록 초기화
            if attempts >= max_attempts:
                db.execute_query("DELETE FROM anonymous_messages") # 이전 기록 싹 초기화
                logger.info(f"Guild {interaction.guild.id}: Anonymous records cleared due to ID exhaustion.")
                # 초기화 후 첫 번째 번호로 즉시 할당
                break

        try:
            # 최종 결정된 msg_id로 저장
            query = "INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)"
            db.execute_query(query, (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            await interaction.response.send_message(f"✅ 전송 완료 (번호: {msg_id})", ephemeral=True)
            await interaction.channel.send(f"👤 **[{msg_id}]** {대화}")
            
        except Exception as e:
            logger.error(f"Anonymous Send Error: {e}")
            await interaction.response.send_message(f"❌ 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

    @app_commands.command(name="대나무숲", description="익명 관리 센터를 엽니다.")
    async def anonymous_admin(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 서버 관리자 권한이 필요합니다.", ephemeral=True)
        
        db = self.get_db(interaction.guild.id)
        
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