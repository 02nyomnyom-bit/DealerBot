# Channel_Config.py - 채널 지정 파일
import discord
from discord import app_commands
from discord.ext import commands
import logging
from database_manager import DatabaseManager

logger = logging.getLogger("channel_config")

class ChannelConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_db(self, guild_id: int):
        return DatabaseManager(f"database/{guild_id}.db")

    # 공통 선택지 정의
    feature_choices = [
        app_commands.Choice(name="출석체크", value="attendance"),
        app_commands.Choice(name="경험치", value="xp"),
        app_commands.Choice(name="등록", value="point_1"),
        app_commands.Choice(name="포인트", value="point_2"),
        app_commands.Choice(name="리더보드", value="leaderboard"),
        app_commands.Choice(name="교환", value="exchange"),

        app_commands.Choice(name="블랙잭", value="blackjack"),
        app_commands.Choice(name="주사위", value="dice"),
        app_commands.Choice(name="강화", value="enhancement"),
        app_commands.Choice(name="로또", value="lottery"),
        app_commands.Choice(name="홀짝", value="odd_even"),
        app_commands.Choice(name="가위바위보", value="r_p_s"),
        app_commands.Choice(name="슬롯머신", value="slot"),
        app_commands.Choice(name="야바위", value="yabawi"),
        app_commands.Choice(name="익명 시스템", value="anonymous"),

        app_commands.Choice(name="통계", value="statistics"),
        app_commands.Choice(name="보이스", value="voice"),
    ]

    @app_commands.command(name="채널설정", description="특정 기능이 작동할 채널을 관리합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(기능="설정할 기능을 선택하세요", 채널="설정할 채널 (미입력 시 현재 채널)", 상태="True: 활성화, False: 비활성화")
    @app_commands.choices(기능=feature_choices)
    async def configure_channel(
        self, 
        interaction: discord.Interaction, 
        기능: app_commands.Choice[str], 
        채널: discord.TextChannel = None,
        상태: bool = True
    ):
        target_ch = 채널 or interaction.channel
        db = self.get_db(interaction.guild.id)
        
        try:
            if 상태:
                db.execute_query("INSERT OR IGNORE INTO channel_configs (channel_id, feature_type) VALUES (?, ?)", (str(target_ch.id), 기능.value))
                msg = f"✅ {target_ch.mention}에서 이제 **{기능.name}** 기능을 사용할 수 있습니다."
            else:
                db.execute_query("DELETE FROM channel_configs WHERE channel_id = ? AND feature_type = ?", (str(target_ch.id), 기능.value))
                msg = f"❌ {target_ch.mention}에서 더 이상 **{기능.name}** 기능을 사용할 수 없습니다."
            
            await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            logger.error(f"Config Error: {e}")
            await interaction.response.send_message("❌ 설정 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="카테고리설정", description="카테고리 내 모든 채널의 기능을 한 번에 설정합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(카테고리="설정할 카테고리를 선택하세요", 기능="설정할 기능", 상태="True: 전체 활성화, False: 전체 비활성화")
    @app_commands.choices(기능=feature_choices)
    async def configure_category(
        self,
        interaction: discord.Interaction,
        카테고리: discord.CategoryChannel,
        기능: app_commands.Choice[str],
        상태: bool
    ):
        await interaction.response.defer(ephemeral=True)
        db = self.get_db(interaction.guild.id)
        
        count = 0
        for channel in 카테고리.text_channels:
            try:
                if 상태:
                    db.execute_query("INSERT OR IGNORE INTO channel_configs (channel_id, feature_type) VALUES (?, ?)", (str(channel.id), 기능.value))
                else:
                    db.execute_query("DELETE FROM channel_configs WHERE channel_id = ? AND feature_type = ?", (str(channel.id), 기능.value))
                count += 1
            except: continue

        action = "활성화" if 상태 else "비활성화"
        await interaction.followup.send(f"📂 **{카테고리.name}** 카테고리 내 {count}개 채널에 **{기능.name}** 기능을 {action}했습니다.")

    @app_commands.command(name="채널설정확인", description="현재 서버의 모든 채널 기능 설정 목록을 보여줍니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def list_config(self, interaction: discord.Interaction):
        db = self.get_db(interaction.guild.id)
        results = db.execute_query("SELECT channel_id, feature_type FROM channel_configs", (), 'all')

        if not results:
            return await interaction.response.send_message("📢 설정된 채널이 없습니다.", ephemeral=True)

        embed = discord.Embed(title="⚙️ 채널 기능 설정 현황", color=discord.Color.green())
        
        # 데이터를 보기 좋게 가공
        config_map = {}
        for ch_id, f_type in results:
            if f_type not in config_map: config_map[f_type] = []
            config_map[f_type].append(f"<#{ch_id}>")

        for f_type, channels in config_map.items():
            # 기능 이름 매칭 (anonymous -> 익명 시스템 등)
            f_name = next((c.name for c in self.feature_choices if c.value == f_type), f_type)
            embed.add_field(name=f"🔹 {f_name}", value=", ".join(channels), inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def check_permission(self, channel_id: int, feature_type: str, guild_id: int) -> bool:
        db = self.get_db(guild_id)
        # 1. 해당 서버에 이 기능에 대해 등록된 채널이 하나라도 있는지 확인
        total_setup = db.execute_query(
            "SELECT COUNT(*) FROM channel_configs WHERE feature_type = ?", 
            (feature_type,), 'one'
        )[0]
    
        # 2. 등록된 채널이 0개라면 "모든 채널 허용"으로 간주하여 True 반환
        if total_setup == 0:
            return True
        
        # 3. 등록된 채널이 있다면, 현재 채널이 그 중 하나인지 확인
        result = db.execute_query(
            "SELECT 1 FROM channel_configs WHERE channel_id = ? AND feature_type = ?", 
            (str(channel_id), feature_type), 'one'
        )
        return bool(result)

async def setup(bot):
    await bot.add_cog(ChannelConfig(bot))