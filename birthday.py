# birthday.py - 생일
import datetime
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands, tasks

# 한국 시간대 설정 (KST)
KST = datetime.timezone(datetime.timedelta(hours=9))

class BirthdayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = "birthday_data.db"
        self._init_db()
        self.birthday_check_loop.start() # 생일 확인 루프 시작

    def _init_db(self):
        """데이터베이스 및 테이블 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_birthdays (
                    guild_id INTEGER,
                    user_id INTEGER,
                    year INTEGER,
                    month INTEGER,
                    day INTEGER,
                    is_public INTEGER,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_channels (
                    guild_id INTEGER PRIMARY KEY,
                    channel_id INTEGER
                )
            """)
            conn.commit()

    def cog_unload(self):
        self.birthday_check_loop.cancel()

    @app_commands.command(name="생일채널", description="[관리자 전용] 생일 축하 쓰레드를 생성할 채널을 지정합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def set_birthday_channel(self, interaction: discord.Interaction):
        from database_manager import DatabaseManager
        if not DatabaseManager().get_user(str(interaction.user.id)):
            if not interaction.response.is_done():
                await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ 일반 텍스트 채널에서만 설정할 수 있습니다.", ephemeral=True)
            return

        guild_id = interaction.guild_id
        channel_id = interaction.channel_id

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO guild_channels (guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?",
                (guild_id, channel_id, channel_id)
            )
            conn.commit()

        await interaction.followup.send(f"✅ 앞으로 생일 축하 쓰레드는 이곳(<#{channel_id}>)에 생성됩니다!", ephemeral=True)

    @app_commands.command(name="생일등록", description="자신의 생일을 등록합니다. (한국 시간 기준)")
    @app_commands.describe(
        년도="태어난 연도 (예: 2000)",
        월="생일 월 (1 ~ 12)",
        일="생일 일 (1 ~ 31)",
        공개유무="True: n번째 생일 공개 | False: 나이 미공개 (축하 문구만 표시)"
    )
    async def register_birthday(
        self,
        interaction: discord.Interaction,
        년도: int,
        월: int,
        일: int,
        공개유무: bool
    ):
        from database_manager import DatabaseManager
        if not DatabaseManager().get_user(str(interaction.user.id)):
            if not interaction.response.is_done():
                await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)

        # 날짜 유효성 검사
        try:
            datetime.date(년도, 월, 일)
        except ValueError:
            await interaction.followup.send("❌ 올바르지 않은 날짜입니다. 다시 확인해 주세요.", ephemeral=True)
            return

        guild_id = interaction.guild_id
        user_id = interaction.user_id
        is_public = 1 if 공개유무 else 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO user_birthdays (guild_id, user_id, year, month, day, is_public) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET year=?, month=?, day=?, is_public=?",
                (guild_id, user_id, 년도, 월, 일, is_public, 년도, 월, 일, is_public)
            )
            conn.commit()

        await interaction.followup.send(f"🎂 생일이 성공적으로 등록되었습니다!\n📅 **{년도}년 {월}월 {일}일** (공개 여부: {'공개' if 공개유무 else '비공개'})", ephemeral=True)

    @tasks.loop(time=datetime.time(hour=0, minute=0, second=0, tzinfo=KST))
    async def birthday_check_loop(self):
        """매일 자정(한국 시간)에 오늘 생일인 사람을 확인하고 쓰레드를 생성하는 루프"""
        # 🚨 [수정] 자동 시스템 루프이므로 interaction 체크 구문을 완전히 제거했습니다.
        now = datetime.datetime.now(KST)
        current_year = now.year
        current_month = now.month
        current_day = now.day

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT guild_id, user_id, year, is_public FROM user_birthdays WHERE month = ? AND day = ?",
                (current_month, current_day)
            )
            birthdays = cursor.fetchall()
            
            if not birthdays:
                return

            for guild_id, user_id, birth_year, is_public in birthdays:
                cursor.execute("SELECT channel_id FROM guild_channels WHERE guild_id = ?", (guild_id,))
                channel_row = cursor.fetchone()
                
                if not channel_row:
                    continue

                channel_id = channel_row[0]
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                    
                channel = guild.get_channel(channel_id)
                if not isinstance(channel, discord.TextChannel):
                    continue

                member = guild.get_member(user_id)
                if not member:
                    try:
                        member = await guild.fetch_member(user_id)
                    except discord.NotFound:
                        continue
                    except discord.HTTPException:
                        continue

                if is_public:
                    ordinal = current_year - birth_year
                    description_text = f"오늘은 {member.mention}님의 **{ordinal}번째** 생일이에요!\n{member.mention}님에게 생일을 축하하는 메시지 하나 남겨주세요."
                else:
                    description_text = f"오늘은 {member.mention}님의 생일이에요!\n{member.mention}님에게 생일을 축하하는 메시지 하나 남겨주세요."

                embed = discord.Embed(
                    title=f"🎂 HAPPY BIRTHDAY! 🎂",
                    description=description_text,
                    color=0xFFC0CB
                )
                embed.set_thumbnail(url=member.display_avatar.url)

                try:
                    msg = await channel.send(content=f"🎉 {member.mention}님의 생일을 축하합니다!", embed=embed)
                    await msg.create_thread(
                        name=f"🎂 {member.display_name}님의 생일 축하방",
                        auto_archive_duration=1440
                    )
                except Exception as e:
                    print(f"[생일 시스템] {guild.name} 서버에서 쓰레드 생성 중 오류 발생: {e}")

    @birthday_check_loop.before_loop
    async def before_birthday_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    if "생일채널" in existing_commands:
        bot.tree.remove_command("생일채널")
    if "생일등록" in existing_commands:
        bot.tree.remove_command("생일등록")
        
    await bot.add_cog(BirthdayCog(bot))
    print("✅ BirthdayCog (생일 모듈) 정상 로드됨!")