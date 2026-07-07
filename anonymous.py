# anonymous.py - [편의성] 익명 채팅
import discord
from discord import app_commands
from discord.ext import commands
import random
import logging

logger = logging.getLogger("anonymous_system")

# ==================== 대나무 숲 관련 관리자 View 시스템 ====================

# 1. [개별 추적] 최종 발신자 확인 모달 창 (기존 동일)
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

# 2. [인증 성공 후 후속 제어] 개별 추적 입력창 유도 다리 뷰
class AnonymousTrackLinkView(discord.ui.View):
    def __init__(self, db_manager):
        super().__init__(timeout=60)
        self.db = db_manager

    @discord.ui.button(label='📌 번호 입력창 열기', style=discord.ButtonStyle.success, emoji="🔎")
    async def open_track_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AnonymousTrackModal(self.db))

# 3. 🎯 [신규] 1달 명단 조회를 위한 비밀번호 입력 모달
class AnonymousListAuthModal(discord.ui.Modal, title='1달 기록 조회 인증'):
    pw_input = discord.ui.TextInput(label='관리자 비밀번호', placeholder='비밀번호를 입력하세요.', required=True)

    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager

    async def on_submit(self, interaction: discord.Interaction):
        # 관리자 패스워드 확인
        if self.pw_input.value != "69697474":
            return await interaction.response.send_message(" Lincoln ❎ 비밀번호가 틀렸습니다.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)

        # SQLite 내장 시계로 최근 1달 데이터 필터링
        query = """
            SELECT msg_id, user_name, user_id, content, timestamp 
            FROM anonymous_messages 
            WHERE timestamp >= datetime('now', '-30 days')
            ORDER BY timestamp DESC
        """
        records = self.db.execute_query(query, (), 'all')
        
        embed = discord.Embed(
            title="🌲 대나무숲 최근 1달간 원본 로그 현황", 
            description="최근 30일 동안 유저들이 전송한 실시간 익명 메시지 명단입니다.",
            color=discord.Color.green()
        )
        
        if records:
            count = 0
            for row in records:
                if count >= 10:
                    embed.add_field(
                        name="➕ 그 외 추가 기록 존재", 
                        value=f"최근 1달간 쌓인 메시지가 총 **{len(records)}개** 있습니다. 이 외의 과거 기록은 개별 번호 조회를 이용하세요.", 
                        inline=False
                    )
                    break
                
                summary = f"👤 **작성자**: {row['user_name']} (<@{row['user_id']}>)\n💬 **내용**: {row['content'][:60]}\n📅 **일시**: {row['timestamp']}"
                embed.add_field(name=f"📌 익명 번호: {row['msg_id']}", value=summary, inline=False)
                count += 1
        else:
            embed.description = "🌲 최근 30일 동안 전송된 익명 메시지가 전혀 없습니다."

        # 명단과 함께 개별 추적도 연동할 수 있도록 버튼도 동봉하여 출력
        await interaction.followup.send(embed=embed, view=AnonymousAdminView(self.db), ephemeral=True)

# 4. [개별 추적] 관리자 패스워드 인증 모달 창
class AnonymousAuthModal(discord.ui.Modal, title='개별 번호 추적 인증'):
    pw_input = discord.ui.TextInput(label='관리자 비밀번호', placeholder='비밀번호를 입력하세요.', required=True)
    
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        
    async def on_submit(self, interaction: discord.Interaction):
        if self.pw_input.value == "69697474":
            await interaction.response.send_message(
                "🔓 **관리자 인증에 성공했습니다.**\n아래 버튼을 눌러 추적할 익명 번호를 입력해 주세요.", 
                view=AnonymousTrackLinkView(self.db), 
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Lincoln ❎ 비밀번호가 틀렸습니다.", ephemeral=True)

# 5. 🎯 [통합 컨트롤 뷰] 최초 명령어 및 하단 패널에 배치될 메뉴
class AnonymousAdminView(discord.ui.View):
    def __init__(self, db_manager):
        super().__init__(timeout=None)
        self.db = db_manager
        
    @discord.ui.button(label='📋 최근 1달 명단 열람하기', style=discord.ButtonStyle.primary, emoji="📂")
    async def view_monthly_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        """1달간의 원본 내역을 비번을 입력하고 열람합니다."""
        await interaction.response.send_modal(AnonymousListAuthModal(self.db))

    @discord.ui.button(label='🔍 번호로 개별 추적하기', style=discord.ButtonStyle.danger, emoji="🚨")
    async def track_record(self, interaction: discord.Interaction, button: discord.ui.Button):
        """특정 번호의 주인을 추적합니다."""
        await interaction.response.send_modal(AnonymousAuthModal(self.db))

# ==================== 메인 통합 Cog 시스템 ====================
class AnonymousSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        """프로젝트 표준 규격에 맞춘 안전한 길드 컨텍스트 DB 매니저 획득"""
        db_cog = self.bot.get_cog("DatabaseManager")
        return db_cog.get_manager(guild_id) if db_cog else None

    @app_commands.command(name="익명", description="익명으로 메시지를 보냅니다.")
    @app_commands.describe(대화="익명으로 보낼 내용을 입력하세요")
    async def anonymous_send(self, interaction: discord.Interaction, 대화: str):
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True
    
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "anonymous", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 익명 메시지 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )

        db = self.get_db(interaction.guild.id)
        if not db:
            return await interaction.response.send_message("❌ 데이터베이스 시스템을 로드할 수 없습니다.", ephemeral=True)
        
        msg_id = ""
        attempts = 0
        while attempts < 10:
            msg_id = f"{random.randint(10, 999)}.{random.randint(10, 999)}"
            if not db.execute_query("SELECT 1 FROM anonymous_messages WHERE msg_id = ?", (msg_id,), 'one'):
                break
            attempts += 1

        try:
            webhooks = await interaction.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="익명 대나무숲")
            if not webhook:
                webhook = await interaction.channel.create_webhook(name="익명 대나무숲")

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
            
            if interaction.guild.icon:
                icon_list.append(interaction.guild.icon.url)

            avatar_url = random.choice(icon_list)

            await webhook.send(
                content=대화,
                username=f"익명 유저 [{msg_id}]",
                avatar_url=avatar_url
            )
            
            db.execute_query("INSERT INTO anonymous_messages (msg_id, user_id, user_name, content) VALUES (?, ?, ?, ?)", 
                             (msg_id, str(interaction.user.id), str(interaction.user), 대화))
            
            await interaction.response.send_message(f"✅ 전송 완료 (번호: {msg_id})", ephemeral=True)

        except Exception as e:
            logger.error(f"Anonymous Send Error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 메시지 전송 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="대나무숲", description="[관리자 전용] 대나무숲 데이터 통합 관리 허브를 호출합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def anonymous_admin(self, interaction: discord.Interaction):
        """🎯 명단을 가리고 비밀번호 모달을 띄우는 버튼형 대시보드 출력"""
        db = self.get_db(interaction.guild.id)
        if not db:
            return await interaction.response.send_message("❌ 데이터베이스 연동에 실패했습니다.", ephemeral=True)
        
        embed = discord.Embed(
            title="🌲 대나무숲 격리제어 대시보드",
            description="⚠️ **보안 경고**\n본 메뉴는 관리자 전용 데이터 관리 허브입니다.\n아래의 버튼을 클릭한 후 비밀번호 인증을 통과해야 1달간의 명단 열람이 가능합니다.",
            color=discord.Color.dark_gray()
        )
        # 데이터를 노출시키지 않고 버튼 뷰만 전송
        await interaction.response.send_message(embed=embed, view=AnonymousAdminView(db), ephemeral=True)

async def setup(bot):
    await bot.add_cog(AnonymousSystem(bot))