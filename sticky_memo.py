# sticky_memo.py - [서버관리] 접착 메모
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict

class StickyMemoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_tasks: Dict[int, asyncio.Task] = {}
        self._init_global_tables()

    def _init_global_tables(self):
        """통합 DB에 접착 메모 영구 보관을 위한 테이블 구조 사전 생성"""
        db_cog = self.bot.get_cog("DatabaseManager")
        if db_cog:
            for guild in self.bot.guilds:
                db = db_cog.get_manager(guild.id)
                if db:
                    db.create_table(
                        "sticky_memos",
                        """
                        channel_id TEXT NOT NULL,
                        title TEXT,
                        content TEXT,
                        use_embed INTEGER,
                        last_msg_id TEXT,
                        PRIMARY KEY (channel_id)
                        """
                    )

    def get_db(self, guild_id: int):
        """서버 격리 DB를 획득하는 동시에, 과거 파편 스키마가 있다면 실시간으로 무결성을 교정합니다."""
        db_cog = self.bot.get_cog("DatabaseManager")
        if not db_cog:
            return None
            
        db = db_cog.get_manager(guild_id)
        if db:
            # 💡 [스키마 검증] 만약 기존 테이블에 아직도 'message_id'라는 구버전 찌꺼기가 남아있다면
            info = db.execute_query("PRAGMA table_info(sticky_memos)", (), 'all')
            has_old_column = any(row['name'] == 'message_id' for row in info) if info else False
            
            # 구버전 파편이 발견되면 테이블을 완전히 새로 구조 조정(Drop & Create)합니다.
            if has_old_column:
                db.execute_query("DROP TABLE IF EXISTS sticky_memos")
            
            # 프로젝트 안전 규격 표준 5대 컬럼으로 실시간 보장 빌드
            db.create_table(
                "sticky_memos",
                """
                channel_id TEXT NOT NULL,
                title TEXT,
                content TEXT,
                use_embed INTEGER,
                last_msg_id TEXT,
                PRIMARY KEY (channel_id)
                """
            )
        return db

    async def send_sticky_memo(self, channel: discord.TextChannel, title: str, content: str, use_embed: bool) -> discord.Message:
        """메모 모양에 맞춰 메시지를 전송하는 내부 함수"""
        formatted_content = content.replace("\\n", "\n")
        if use_embed:
            embed = discord.Embed(title=title, description=formatted_content, color=0xFFFF00)
            return await channel.send(embed=embed)
        else:
            return await channel.send(f"**{title}**\n{formatted_content}")

    @app_commands.command(name="접착메모", description="[관리자 전용] 이 채팅방 하단에 고정될 고유한 메모를 생성/삭제합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        임베드모양="True: 노란색 박스 모양 | False: 일반 텍스트 모양",
        제목="메모의 제목을 입력하세요",
        내용="메모 내용 입력 ('삭제' 입력 시 이 채널의 메모가 제거되며 \\n으로 줄바꿈 가능)"
    )
    async def sticky_memo(self, interaction: discord.Interaction, 임베드모양: bool, 제목: str, 내용: str):
        # 1. 통합 DB 기준 회원 명단 가입 여부 검증
        db = self.get_db(interaction.guild_id)
        if not db or not db.execute_query("SELECT * FROM users WHERE user_id = ?", (str(interaction.user.id),), 'one'):
            return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        channel_id_str = str(interaction.channel_id)

        # 2. 이 채널에서 돌고 있던 기존 타이머(디바운스)가 있다면 즉시 취소
        if interaction.channel_id in self.active_tasks:
            self.active_tasks[interaction.channel_id].cancel()

        # 3. [삭제 모드] 데이터베이스에서 지우고 기존 메시지 파괴
        if 내용.strip() == "삭제":
            record = db.execute_query("SELECT last_msg_id FROM sticky_memos WHERE channel_id = ?", (channel_id_str,), 'one')
            if record and record['last_msg_id']:
                try:
                    old_msg = await interaction.channel.fetch_message(int(record['last_msg_id']))
                    await old_msg.delete()
                except: pass
            
            db.execute_query("DELETE FROM sticky_memos WHERE channel_id = ?", (channel_id_str,))
            return await interaction.followup.send("🗑️ 이 채널의 접착 메모가 데이터베이스에서 영구 삭제되었습니다.", ephemeral=True)

        # 4. [새로 등록] 기존에 떠 있던 이전 메모 메시지 청소
        record = db.execute_query("SELECT last_msg_id FROM sticky_memos WHERE channel_id = ?", (channel_id_str,), 'one')
        if record and record['last_msg_id']:
            try:
                old_msg = await interaction.channel.fetch_message(int(record['last_msg_id']))
                await old_msg.delete()
            except: pass

        # 5. 새 메모 전송 및 해당 채널 전용 데이터로 영구 바인딩
        try:
            msg = await self.send_sticky_memo(interaction.channel, 제목, 내용, 임베드모양)
            db.execute_query(
                "INSERT OR REPLACE INTO sticky_memos (channel_id, title, content, use_embed, last_msg_id) VALUES (?, ?, ?, ?, ?)",
                (channel_id_str, 제목, 내용, 1 if 임베드모양 else 0, str(msg.id))
            )
            await interaction.followup.send("✅ 이 채널 전용 접착 메모가 활성화되었습니다!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ 봇에게 이 채널에 메시지를 전송하거나 삭제할 권한이 없습니다.", ephemeral=True)

    async def delayed_renew(self, channel: discord.TextChannel, delay: float):
        """6초 동안 추가 채팅이 없을 때(잠잠해졌을 때) 호출되는 디바운스 핵심 핵심 함수"""
        try:
            await asyncio.sleep(delay)
            db = self.get_db(channel.guild.id)
            if not db: return

            channel_id_str = str(channel.id)
            # 데이터베이스에서 '현재 채널'에 매핑된 메모만 정확하게 쿼리
            memo = db.execute_query("SELECT * FROM sticky_memos WHERE channel_id = ?", (channel_id_str,), 'one')
            if not memo: return

            # 1. 기존 메모 메시지 안전하게 선 삭제
            if memo['last_msg_id']:
                try:
                    old_msg = await channel.fetch_message(int(memo['last_msg_id']))
                    await old_msg.delete()
                except: pass

            # 2. 채널 최하단에 완전히 새 메시지로 전송
            new_msg = await self.send_sticky_memo(channel, memo['title'], memo['content'], bool(memo['use_embed']))
            
            # 3. 새로 보낸 메시지 ID를 DB에 업데이트 (다음 삭제를 위해)
            db.execute_query("UPDATE sticky_memos SET last_msg_id = ? WHERE channel_id = ?", (str(new_msg.id), channel_id_str))
            
        except asyncio.CancelledError: pass
        finally:
            self.active_tasks.pop(channel.id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # 봇이 쓴 글이거나 서버가 아닌 DM인 경우 무시
        if message.author.bot or not message.guild:
            return

        db = self.get_db(message.guild.id)
        if not db: return

        # 현재 대화가 올라온 '그 채널'에 등록된 접착 메모가 있는지 확인
        if db.execute_query("SELECT 1 FROM sticky_memos WHERE channel_id = ?", (str(message.channel.id),), 'one'):
            # 유저가 계속 말을 이어 나가는 중이라면 이전 타이머를 파괴 (디바운스 초기화)
            if message.channel.id in self.active_tasks:
                self.active_tasks[message.channel.id].cancel()

            # 유저의 마지막 채팅 시점부터 딱 6초간 타이머 가동 (6초 뒤 조용해지면 이사 시작)
            task = asyncio.create_task(self.delayed_renew(message.channel, 6.0))
            self.active_tasks[message.channel.id] = task

async def setup(bot: commands.Bot):
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    if "접착메모" in existing_commands: bot.tree.remove_command("접착메모")
        
    await bot.add_cog(StickyMemoCog(bot))
    print("✅ StickyMemoCog (안전 디바운스 삭제/전송 버전) 로드 완료!")