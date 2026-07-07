# birthday.py - [편의성] 생일
import datetime
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands, tasks

KST = datetime.timezone(datetime.timedelta(hours=9))

class BirthdayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._init_global_tables()
        self.birthday_check_loop.start()

    def _init_global_tables(self):
        """봇이 켜질 때 각 길드 데이터베이스에 생일 관련 테이블 인프라가 확보되도록 사전 선언"""
        # 이 작업은 가동 시 모든 길드 DB 관리자를 거쳐 안전하게 등록됩니다.
        db_cog = self.bot.get_cog("DatabaseManager")
        if db_cog:
            for guild in self.bot.guilds:
                db = db_cog.get_manager(guild.id)
                if db:
                    db.create_table(
                        "user_birthdays",
                        """
                        user_id TEXT NOT NULL,
                        year INTEGER,
                        month INTEGER,
                        day INTEGER,
                        is_public INTEGER,
                        PRIMARY KEY (user_id)
                        """
                    )
                    db.create_table(
                        "birthday_config",
                        """
                        key TEXT PRIMARY KEY,
                        value TEXT
                        """
                    )

    def get_db(self, guild_id: int):
        """프로젝트 표준 규격에 맞춘 안전한 길드 컨텍스트 DB 매니저 획득 + 실시간 인프라 보장"""
        db_cog = self.bot.get_cog("DatabaseManager")
        if not db_cog:
            return None
            
        db = db_cog.get_manager(guild_id)
        if db:
            # 💡 명령어가 실행되는 순간, 테이블이 유실되어 있다면 즉시 실시간 복구/생성합니다.
            db.create_table(
                "user_birthdays",
                """
                user_id TEXT NOT NULL,
                year INTEGER,
                month INTEGER,
                day INTEGER,
                is_public INTEGER,
                PRIMARY KEY (user_id)
                """
            )
            db.create_table(
                "birthday_config",
                """
                key TEXT PRIMARY KEY,
                value TEXT
                """
            )
        return db

    def cog_unload(self):
        self.birthday_check_loop.cancel()

    @app_commands.command(name="생일채널", description="[관리자 전용] 생일 축하 쓰레드를 생성할 채널을 지정합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def set_birthday_channel(self, interaction: discord.Interaction):
        # 1. 가입 검증 방식 표준화 구문으로 전면 교체
        db = self.get_db(interaction.guild_id)
        if not db or not db.execute_query("SELECT * FROM users WHERE user_id = ?", (str(interaction.user.id),), 'one'):
            return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ 일반 텍스트 채널에서만 설정할 수 있습니다.", ephemeral=True)
            return

        channel_id = str(interaction.channel_id)
        db.execute_query(
            "INSERT OR REPLACE INTO birthday_config (key, value) VALUES ('target_channel', ?)",
            (channel_id,)
        )

        await interaction.followup.send(f"✅ 앞으로 생일 축하 쓰레드는 이곳(<#{channel_id}>)에 생성됩니다!", ephemeral=True)

    @app_commands.command(name="생일등록", description="자신의 생일을 등록하거나 변경합니다. (한국 시간 기준)")
    @app_commands.describe(
        년도="태어난 연도 (예: 2000)",
        월="생일 월 (1 ~ 12)",
        일="생일 일 (1 ~ 31)",
        공개유무="True: n번째 생일 공개 | False: 나이 미공개"
    )
    async def register_birthday(
        self,
        interaction: discord.Interaction,
        년도: int,
        월: int,
        일: int,
        공개유무: bool
    ):
        db = self.get_db(interaction.guild_id)
        if not db or not db.execute_query("SELECT * FROM users WHERE user_id = ?", (str(interaction.user.id),), 'one'):
            return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)

        try:
            datetime.date(년도, 월, 일)
        except ValueError:
            await interaction.followup.send("❌ 올바르지 않은 날짜입니다. 다시 확인해 주세요.", ephemeral=True)
            return

        user_id = str(interaction.user.id) 
        is_public = 1 if 공개유무 else 0

        # [기능 개선] 기존에 이미 생일을 등록한 유저인지 선제 검사하여 가독성 확보
        exists = db.execute_query("SELECT 1 FROM user_birthdays WHERE user_id = ?", (user_id,), 'one')
        action_type = "변경" if exists else "등록"

        db.execute_query(
            "INSERT OR REPLACE INTO user_birthdays (user_id, year, month, day, is_public) VALUES (?, ?, ?, ?, ?)",
            (user_id, 년도, 월, 일, is_public)
        )

        await interaction.followup.send(
            f"🎂 생일이 성공적으로 **{action_type}**되었습니다!\n📅 **{년도}년 {월}월 {일}일** (공개 여부: {'공개' if 공개유무 else '비공개'})", 
            ephemeral=True
        )

    @tasks.loop(time=datetime.time(hour=0, minute=0, second=0, tzinfo=KST))
    async def birthday_check_loop(self):
        """매일 자정(한국 시간)에 오늘 생일인 사람을 확인하고 단체 멘션과 함께 쓰레드를 생성하는 루프"""
        now = datetime.datetime.now(KST)
        current_year = now.year
        current_month = now.month
        current_day = now.day

        db_cog = self.bot.get_cog("DatabaseManager")
        if not db_cog:
            return

        for guild in self.bot.guilds:
            db = db_cog.get_manager(guild.id)
            if not db:
                continue

            birthdays = db.execute_query(
                "SELECT user_id, year, is_public FROM user_birthdays WHERE month = ? AND day = ?",
                (current_month, current_day), 'all'
            )
            
            if not birthdays:
                continue

            channel_row = db.execute_query("SELECT value FROM birthday_config WHERE key = 'target_channel'", (), 'one')
            if not channel_row:
                continue

            channel_id = int(channel_row['value'])
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue

            for row in birthdays:
                user_id = int(row['user_id'])
                birth_year = row['year']
                is_public = row['is_public']

                member = guild.get_member(user_id)
                if not member:
                    try: member = await guild.fetch_member(user_id)
                    except: continue

                if is_public:
                    ordinal = current_year - birth_year
                    description_text = f"오늘은 {member.mention}님의 **{ordinal}번째** 생일이에요!\n{member.mention}님에게 생일을 축하하는 메시지 하나 남겨주세요."
                else:
                    description_text = f"오늘은 {member.mention}님의 생일이에요!\n{member.mention}님에게 생일을 축하하는 메시지 하나 남겨주세요."

                embed = discord.Embed(title="🎂 HAPPY BIRTHDAY! 🎂", description=description_text, color=0xFFC0CB)
                embed.set_thumbnail(url=member.display_avatar.url)

                try:
                    # 💡 [수정] 서버 전체 인원을 태그하고 싶다면 @everyone 을 문구 앞에 넣어줍니다.
                    # 만약 서버에 무리가 간다면 @here 나 특정 역할 ID(<@&역할ID>)로 교체하셔도 됩니다.
                    mention_prefix = "@here" 
                    
                    msg = await channel.send(
                        content=f"🎉 {mention_prefix}! 오늘 생일인 소중한 멤버가 있어요! {member.mention}님의 생일을 축하합니다!", 
                        embed=embed
                    )
                    await msg.create_thread(name=f"🎂 {member.display_name}님의 생일 축하방", auto_archive_duration=1440)
                except Exception as e:
                    print(f"[생일 시스템] {guild.name} 서버 쓰레드 생성 오류: {e}")

    @birthday_check_loop.before_loop
    async def before_birthday_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    if "생일채널" in existing_commands: bot.tree.remove_command("생일채널")
    if "생일등록" in existing_commands: bot.tree.remove_command("생일등록")
        
    await bot.add_cog(BirthdayCog(bot))
    print("✅ BirthdayCog (생일 모듈) 통합 가동 준비 완료!")