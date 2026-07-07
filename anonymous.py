# anonymous.py - 익명 시스템
import discord
from discord import app_commands
from discord.ext import commands
import random
import logging
from database_manager import DatabaseManager
import random

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
        if self.pw_input.value == "69697474":
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
        return DatabaseManager(f"database/{guild_id}.db")

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
            # 1. 웹훅 찾기 또는 생성
            webhooks = await interaction.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="익명 대나무숲")
            if not webhook:
                webhook = await interaction.channel.create_webhook(name="익명 대나무숲")

            # 2. 아이콘 리스트 설정 (서버 아이콘 포함)
            icon_list = [
                "https://media.discordapp.net/attachments/1468585489060855818/1523584690450071653/A.png?ex=6a4ca451&is=6a4b52d1&hm=b1909c1be5a94511cd89939b521443a0585acd3f3045dde5c001e7eb8d4ed42e&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584710834655312/B.png?ex=6a4ca455&is=6a4b52d5&hm=3221fa1f6ea5a1bc09ff2280881c26daa186f69997631c5bff7f5870197838d0&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584716333125682/C.png?ex=6a4ca457&is=6a4b52d7&hm=1e213662068bdb9e59ca01c425ca03abdd37b101937cc8c66a4749bec2364d40&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584722469392465/D.png?ex=6a4ca458&is=6a4b52d8&hm=a2265309861cda54fd9ee3b19fdba23c40e27666dc24747f141ae44151f7dbd6&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584756804091975/E.png?ex=6a4ca460&is=6a4b52e0&hm=3a35c13eef4b87b6788440a81881250d459277aaad83d4e86d5ff8a93cc36701&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584763649065070/F.png?ex=6a4ca462&is=6a4b52e2&hm=ae023fd2033d1b191ad5e0e6c5ef59d5e66c9a148c04114c3c4685986304dfc3&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523584740244983899/G.png?ex=6a4ca45c&is=6a4b52dc&hm=1d100be6b4ab9850e1cb24b3af45f8181bf45f65348b0174e21f41ab688544d2&=&format=webp&quality=lossless",
                "https://media.discordapp.net/attachments/1468585489060855818/1523585253057499279/H.png?ex=6a4ca4d7&is=6a4b5357&hm=1a50993a3918141544fcb68ced0a03041b99ed6fef0fd4b41961ac216098bfd9&=&format=webp&quality=lossless",
            ]
            
            # 3. 무작위 아이콘 선택
            avatar_url = random.choice(icon_list)

            # 4. 웹훅으로 메시지 전송
            await webhook.send(
                content=대화,
                username=f"익명 유저 [{msg_id}]",
                avatar_url=avatar_url
            )
            
            # 5. DB 저장
            db.execute_query("INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)", 
                             (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            await interaction.response.send_message(f"✅ 전송 완료 (번호: {msg_id})", ephemeral=True)

        except Exception as e:
            logger.error(f"Anonymous Send Error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 메시지 전송 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="대나무숲", description="[관리자 전용] 최근 익명 메시지를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def anonymous_admin(self, interaction: discord.Interaction):
        db = self.get_db(interaction.guild.id)
        
        embed = discord.Embed(
            title="🌲 대나무숲 관리자 시스템", 
            description="익명 메시지의 발신자를 확인하려면 아래 버튼을 눌러 인증해주세요.",
            color=discord.Color.dark_green()
        )
        
        await interaction.response.send_message(embed=embed, view=AnonymousAdminView(db), ephemeral=True)

async def setup(bot):
    await bot.add_cog(AnonymousSystem(bot))