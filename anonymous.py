# anonymous.py
import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from database_manager import DatabaseManager

logger = logging.getLogger("anonymous_system")

# 개발자 디스코드 ID
DEVELOPER_ID = 533493429489893390

# 익명 채널 설정 관련 View
class AnonymousChannelConfigView(discord.ui.View):
    """익명 채널 설정을 위한 버튼 뷰"""
    def __init__(self, db_manager, channel: discord.TextChannel = None):
        super().__init__(timeout=60)
        self.db = db_manager
        self.target_channel = channel

    @discord.ui.button(label="추가 [활성화]", style=discord.ButtonStyle.success)
    async def add_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.target_channel:
            return await interaction.response.send_message("❎ 설정할 채널 정보 없음. 명령어를 다시 실행해주세요.", ephemeral=True)
        
        try:
            self.db.execute_query(
                "INSERT OR REPLACE INTO server_settings (key, value) VALUES (?, ?)", 
                ("anonymous_channel", str(self.target_channel.id))
            )
            await interaction.response.edit_message(content=f"✅ 익명 채널이 {self.target_channel.mention}으로 설정되었습니다.", view=None)
        
        except Exception as e:
            logger.error(f"익명 채널 설정 중 오류: {e}")
            await interaction.response.send_message("❌ 설정 저장 중 오류가 발생했습니다.", ephemeral=True)

    @discord.ui.button(label="해제 [비활성화]", style=discord.ButtonStyle.danger)
    async def clear_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            self.db.execute_query("DELETE FROM server_settings WHERE key = ?", ("anonymous_channel",))
            await interaction.response.edit_message(content="✅ 익명 채널 설정이 비활성화되었습니다.", view=None)
        
        except Exception as e:
            logger.error(f"익명 채널 초기화 중 오류: {e}")
            await interaction.response.send_message("❌ 초기화 중 오류가 발생했습니다.", ephemeral=True)
            
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

    def get_db(self, guild_id: int):
        return DatabaseManager(str(guild_id))
    
    @app_commands.command(name="익명채널설정", description="[관리자 전용] 익명 채널을 추가하거나 설정을 해제합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def set_channel_config(self, interaction: discord.Interaction, 채널: discord.TextChannel = None):
        """버튼을 통해 익명 채널 설정을 관리합니다."""
        db = self.get_db(interaction.guild.id)
        view = AnonymousChannelConfigView(db, 채널)
        
        msg = "수행할 작업을 선택해주세요."
        if 채널:
            msg = f"선택한 채널: {채널.mention}\n익명 채널로 추가하시겠습니까, 아니면 기존 설정을 해제하시겠습니까?"
        
        await interaction.response.send_message(msg, view=view, ephemeral=True)

    @app_commands.command(name="익명", description="익명 메시지를 보냅니다.")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        db = self.get_db(interaction.guild.id)
        
        # 설정된 채널 ID 가져오기
        res = db.execute_query("SELECT value FROM server_settings WHERE key = ?", ("anonymous_channel",), 'one')
        allowed_id = int(res['value']) if res else None

        # 1. 채널 존재 여부 및 예외 처리
        if allowed_id:
            actual_channel = self.bot.get_channel(allowed_id)
            if actual_channel is None:
                # DB에는 있으나 실제 서버에서 삭제된 경우
                db.execute_query("DELETE FROM server_settings WHERE key = ?", ("anonymous_channel",))
                return await interaction.response.send_message("🛑 익명 채널이 삭제되었습니다. 관리자가 다시 설정해야 합니다.", ephemeral=True)

        # 2. 채널 일치 검증
        if interaction.channel_id != allowed_id:
            await interaction.response.send_message("🚫 지정된 채널에서만 사용 가능합니다.", ephemeral=True)
            
            # 개발자에게 제보 전송
            developer = self.bot.get_user(DEVELOPER_ID)
            if developer:
                report_embed = discord.Embed(title="🚨 지정 외 채널 사용 시도", color=discord.Color.orange())
                report_embed.description = f"**서버:** {interaction.guild.name}\n**사용자:** {interaction.user}\n**채널:** {interaction.channel.name}"
                report_embed.add_field(name="내용", value=대화)
                try: await developer.send(embed=report_embed)
                except: pass
            return
        
        # --- 전송 로직 ---
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog: await xp_cog.process_command_xp(interaction)
            
        max_attempts, attempts, msg_id = 100, 0, ""
        while True:
            msg_id = f"{random.randint(10, 999)}.{random.randint(10, 999)}"
            if not db.execute_query("SELECT 1 FROM anonymous_messages WHERE msg_id = ?", (msg_id,), 'one'): break
            attempts += 1
            if attempts >= max_attempts:
                db.execute_query("DELETE FROM anonymous_messages")
                break

        try:
            db.execute_query("INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)", 
                             (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            await interaction.response.send_message(f"✅ 전송 완료 (번호: {msg_id})", ephemeral=True)
            await interaction.channel.send(f"👤 **[{msg_id}]** \n{대화}")
        except Exception as e:
            logger.error(f"Anonymous Send Error: {e}")
            await interaction.response.send_message("❌ 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="대나무숲", description="관리자 메뉴")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def anonymous_admin(self, interaction: discord.Interaction):
        db = self.get_db(interaction.guild.id)
        embed = discord.Embed(title="🌲 대나무숲 관리 센터", description="작업을 선택하세요.", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=AnonymousAdminView(db), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousSystem(bot))