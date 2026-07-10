# birthday.py - [편의성] 생일
import datetime
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands, tasks

KST = datetime.timezone(datetime.timedelta(hours=9))

# 🌌 별자리 및 💎 탄생석 데이터 매핑 리스트
ZODIAC_LIST = ["Capricorn♑", "Aquarius♒", "Pisces♓", "Aries♈", "Taurus♉", "Gemini♊", "Cancer♋", "Leo♌", "Virgo♍", "Libra♎", "Scorpio♏", "Sagittarius♐"]
STONE_LIST = ["Garnet🔴", "Amethyst🟣", "Aquamarine🔹", "Diamond💎", "Emerald🟢", "Pearl⚪", "Ruby🔻", "Peridot💚", "Sapphire🔷", "Opal💖", "Topaz🔸", "Turquoise💠"]

def get_zodiac_and_stone(month: int, day: int):
    """월과 일을 기반으로 별자리(날짜 구간 기준)와 탄생석(순수 월 기준) 이름을 반환합니다."""
    # 1. 탄생석 판정: 철저하게 태어난 '월' 기준으로만 결정 (12월생 = 터키석, 1월생 = 가넷)
    stone = STONE_LIST[month - 1]

    # 2. 별자리 판정: 기존 날짜 구간 구조 유지
    if (month == 12 and day >= 25) or (month == 1 and day <= 19): zodiac = "Capricorn♑"
    elif (month == 1 and day >= 20) or (month == 2 and day <= 18): zodiac = "Aquarius♒"
    elif (month == 2 and day >= 19) or (month == 3 and day <= 20): zodiac = "Pisces♓"
    elif (month == 3 and day >= 21) or (month == 4 and day <= 19): zodiac = "Aries♈"
    elif (month == 4 and day >= 20) or (month == 5 and day <= 20): zodiac = "Taurus♉"
    elif (month == 5 and day >= 21) or (month == 6 and day <= 21): zodiac = "Gemini♊"
    elif (month == 6 and day >= 22) or (month == 7 and day <= 22): zodiac = "Cancer♋"
    elif (month == 7 and day >= 23) or (month == 8 and day <= 22): zodiac = "Leo♌"
    elif (month == 8 and day >= 23) or (month == 9 and day <= 23): zodiac = "Virgo♍"
    elif (month == 9 and day >= 24) or (month == 10 and day <= 22): zodiac = "Libra♎"
    elif (month == 10 and day >= 23) or (month == 11 and day <= 22): zodiac = "Scorpio♏"
    else: zodiac = "Sagittarius♐"

    return zodiac, stone

class BirthdayCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._init_global_tables()
        self.birthday_check_loop.start()

    def _init_global_tables(self):
        """봇이 켜질 때 각 길드 데이터베이스에 생일 관련 테이블 인프라가 확보되도록 사전 선언"""
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

    async def _assign_birthday_roles(self, member: discord.Member, month: int, day: int):
        """유저의 생일에 맞는 별자리 및 탄생석 역할을 지급하고 기존 역할을 회수합니다."""
        guild = member.guild
        target_zodiac, target_stone = get_zodiac_and_stone(month, day)

        # 🛠️ 깔끔한 버전(시나리오 A)에 맞춘 기존 역할 회수 로직 (오류 수정 완료)
        roles_to_remove = []
        for role in member.roles:
            # 역할 이름이 별자리/탄생석 목록에 포함되어 있으면서, 이번에 새로 받을 역할이 아니라면 회수
            if role.name in ZODIAC_LIST and role.name != target_zodiac:
                roles_to_remove.append(role)
            if role.name in STONE_LIST and role.name != target_stone:
                roles_to_remove.append(role)
        
        if roles_to_remove:
            try:
                await member.remove_roles(*roles_to_remove)
            except discord.Forbidden:
                print(f"[생일 시스템] {guild.name} 서버에서 역할을 제거할 권한이 없습니다.")

        # 2. 새 역할 지급 (없으면 중복 없이 단 하나만 동적 생성)
        roles_to_add = []
        for role_name in [target_zodiac, target_stone]:
            role = discord.utils.get(guild.roles, name=role_name)
            
            if not role:
                try:
                    role = await guild.create_role(
                        name=role_name, 
                        mentionable=True, 
                        reason="생일 시스템 동적 생성"
                    )
                except discord.Forbidden:
                    print(f"[생일 시스템] {guild.name} 서버에서 역할을 생성할 권한이 없습니다.")
                    continue

            if role and role not in member.roles:
                roles_to_add.append(role)

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add)
            except discord.Forbidden:
                print(f"[생일 시스템] {guild.name} 서버에서 역할을 지급할 권한이 없습니다.")

    @app_commands.command(name="생일채널", description="[관리자 전용] 생일 축하 쓰레드를 생성할 채널을 지정합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def set_birthday_channel(self, interaction: discord.Interaction):
        db = self.get_db(interaction.guild_id)
        # 매니저 자체의 내장 가입 검증 기능 활용으로 안전성 향상
        if not db or not db.get_user(str(interaction.user.id)):
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
        if not db or not db.get_user(str(interaction.user.id)):
            return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)

        try:
            datetime.date(년도, 월, 일)
        except ValueError:
            await interaction.followup.send("❌ 올바르지 않은 날짜입니다. 다시 확인해 주세요.", ephemeral=True)
            return

        user_id = str(interaction.user.id) 
        is_public = 1 if 공개유무 else 0

        exists = db.execute_query("SELECT 1 FROM user_birthdays WHERE user_id = ?", (user_id,), 'one')
        action_type = "변경" if exists else "등록"

        # 🛠️ 오타 수정: 년度 ➡️ 년도
        db.execute_query(
            "INSERT OR REPLACE INTO user_birthdays (user_id, year, month, day, is_public) VALUES (?, ?, ?, ?, ?)",
            (user_id, 년도, 월, 일, is_public)
        )

        # 생일 등록 완료 후 별자리 및 탄생석 역할 즉시 지급
        zodiac_name, stone_name = get_zodiac_and_stone(월, 일)
        if isinstance(interaction.user, discord.Member):
            await self._assign_birthday_roles(interaction.user, 월, 일)

        await interaction.followup.send(
            f"🎂 생일이 성공적으로 **{action_type}**되었습니다!\n"
            f"📅 **{년도}년 {월}월 {일}일** (공개 여부: {'공개' if 공개유무 else '비공개'})\n"
            f"✨ 부여된 역할: `{zodiac_name}`, `{stone_name}`", 
            ephemeral=True
        )

    @tasks.loop(time=datetime.time(hour=0, minute=0, second=0, tzinfo=KST))
    async def birthday_check_loop(self):
        """매일 자정(한국 시간)에 오늘 생일인 사람을 확인하고 단체 멘션과 함께 쓰레드를 생성하는 루프"""
        now = datetime.datetime.now(KST)
        current_year = now.year
        current_month = now.month
        current_day = now.day

        for guild in self.bot.guilds:
            db = self.get_db(guild.id) 
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
    print("✅ BirthdayCog (생일 및 역할 연동 모듈) 통합 가동 준비 완료!")