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
                "https://media.discordapp.net/attachments/1370786196183318729/1465364594175377459/28419D34-9489-4B90-B9BF-5D2584552409.png?ex=6978d6a0&is=69778520&hm=c7b60691eb012210bd20279508fe42a8d236b7c1858dad2b0d0b1013537fe843&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465364565414904004/D2B54449-3500-4F9F-A410-2D0EB0EFD631.png?ex=6978d699&is=69778519&hm=2e6a43c331758c54de2d3ffe5e579cb78c0aa52f92567f37d6bb0163617ac070&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465365091133165569/954527BE-DFCD-4EB3-B301-21CD1782DB3E.png?ex=6978d716&is=69778596&hm=5114579a285909f1c4b0f460fc329c19ee9d8c77e353793a53b60898e3d38487&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465365422730903665/90C86F91-FEA0-4F9B-8D1E-40AC93388BE6.png?ex=6978d765&is=697785e5&hm=b6eacd1e6a50947e440cb6fd0f7a493b84fabe80cd198ba1deb27719a8516469&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465365405173551195/BCA8FFC0-3F2E-465F-903B-24F78998C7D7.png?ex=6978d761&is=697785e1&hm=7f676d7d584406eb6990704443e4bed82431a55c60a0aca4d79aa921fb706343&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465366449639002213/IMG_4026.png?ex=6978d85a&is=697786da&hm=c9c132ebfe77f74f3d699d6532015c8b56ea5fd2286d256d2439dd65b20cdeae&=&format=webp&quality=lossless&width=960&height=960",
                "https://media.discordapp.net/attachments/1370786196183318729/1465366552692920516/IMG_4027.png?ex=6978d873&is=697786f3&hm=5d367bf12415f8ab8c4da486643c3dda50cc99f7fb055b3b6b9cdec63d155a09&=&format=webp&quality=lossless&width=960&height=960",
            ]
            
            # 서버 아이콘이 있다면 리스트에 추가
            if interaction.guild.icon:
                icon_list.append(interaction.guild.icon.url)

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
    @app_commands.checks.has_permissions(administrator=True)
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