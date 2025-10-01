from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os
import asyncio
from typing import Optional, Dict, Any
import logging
# Removed direct imports of PointManager and DatabaseManager classes as they are guild-specific
# and will be retrieved per interaction.

# ✅ 로깅 설정
def setup_logging():
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger("exchange_system")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler = logging.FileHandler(os.path.join(log_dir, 'exchange.log'), encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# 안전한 의존성 import
# Changed to import get_guild_db_manager
def safe_import_database():
    try:
        from database_manager import get_guild_db_manager
        return get_guild_db_manager, True
    except ImportError as e:
        logger.warning(f"⚠️ database_manager 임포트 실패: {e}")
        return None, False

def safe_import_point_manager():
    try:
        from point_manager import get_point, add_point, set_point, is_registered
        return get_point, add_point, set_point, is_registered, True
    except ImportError as e:
        logger.warning(f"⚠️ point_manager 임포트 실패: {e}")
        return None, None, None, None, False

# 의존성 로드
get_guild_db_manager_func, DATABASE_AVAILABLE = safe_import_database()
get_point, add_point, set_point, is_registered, POINT_MANAGER_AVAILABLE = safe_import_point_manager()

# 설정 파일 관리
DATA_DIR = "data"
EXCHANGE_SETTINGS_FILE = os.path.join(DATA_DIR, "exchange_settings.json")
EXCHANGE_HISTORY_FILE = os.path.join(DATA_DIR, "exchange_history.json")

os.makedirs(DATA_DIR, exist_ok=True)

class ExchangeSystem:
    def __init__(self):
        self.exchange_history = {}
        self.settings_file = "data/exchange_settings.json"
        self.settings = self.load_settings()
        self.cooldowns = {}

    def load_settings(self) -> Dict[str, Any]:
        """설정 파일 로드 및 기본값 설정"""
        default_settings = {
            "현금_to_XP_비율": 1.0,
            "XP_to_현금_비율": 1.0,
            "현금_수수료율": 0,
            "XP_수수료율": 0,
            "일일_제한": 5,
            "쿨다운_분": 1
        }
        
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            logger.info("✅ 설정 파일이 존재하지 않아 기본 설정으로 생성했습니다.")
            return default_settings

        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            # 이전 버전 호환성
            if "현금_수수료율" not in settings:
                settings["현금_수수료율"] = 0
            if "XP_수수료율" not in settings:
                settings["XP_수수료율"] = 0
            return {**default_settings, **settings}
        except Exception as e:
            logger.error(f"❌ 설정 파일 로드 중 오류 발생: {e}")
            logger.warning("⚠️ 기본 설정으로 복원합니다.")
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            return default_settings

    def save_settings(self, settings_data: Dict[str, Any]):
        """설정 파일 저장"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=4)
        except Exception as e:
            logger.error(f"❌ 설정 파일 저장 중 오류 발생: {e}")

    def load_history(self) -> Dict[str, Any]:
        """교환 기록 로드"""
        if not os.path.exists(EXCHANGE_HISTORY_FILE):
            self.save_history({})
            logger.info("✅ 교환 기록 파일이 없어 새로 생성했습니다.")
            return {}
        try:
            with open(EXCHANGE_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ 교환 기록 로드 오류: {e}")
            return {}

    def save_history(self, history: Dict[str, Any]):
        """교환 기록 저장"""
        try:
            with open(EXCHANGE_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            logger.error(f"❌ 교환 기록 저장 오류: {e}")

    def get_user_daily_exchanges(self, user_id: str) -> int:
        """오늘 교환 횟수 계산"""
        today_str = datetime.datetime.now().date().isoformat()
        return sum(1 for entry in self.exchange_history.get(user_id, []) if entry['date'].startswith(today_str))

    def check_cooldown(self, user_id: str) -> bool:
        """쿨다운 체크"""
        if user_id in self.cooldowns:
            last_use = self.cooldowns[user_id]
            cooldown_period = datetime.timedelta(minutes=self.settings['쿨다운_분'])
            if datetime.datetime.now() < last_use + cooldown_period:
                return False
        return True

    def update_cooldown(self, user_id: str):
        """쿨다운 업데이트"""
        self.cooldowns[user_id] = datetime.datetime.now()

    def record_exchange(self, user_id: str, exchange_type: str, amount: int, result: int):
        """교환 기록 저장"""
        if user_id not in self.exchange_history:
            self.exchange_history[user_id] = []
        
        self.exchange_history[user_id].append({
            "date": datetime.datetime.now().isoformat(),
            "type": exchange_type,
            "amount": amount,
            "result": result
        })
        self.save_history(self.exchange_history)

class ExchangeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.exchange_system = ExchangeSystem()
        logger.info("✅ 통합 교환 시스템 v6 로드 완료")
        
        # These checks are now done per interaction as managers are guild-specific
        # if not DATABASE_AVAILABLE:
        #     logger.error("❌ database_manager가 없어 교환 시스템이 정상 작동하지 않습니다.")
        # if not POINT_MANAGER_AVAILABLE:
        #     logger.error("❌ point_manager가 없어 교환 시스템이 정상 작동하지 않습니다.")

    # XP를 현금으로 교환
    @app_commands.command(name="현금교환", description="XP를 현금으로 교환합니다. 수수료가 부과됩니다.")
    @app_commands.describe(xp_amount="교환할 XP")
    async def exchange_xp_to_cash(self, interaction: discord.Interaction, xp_amount: int):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        
        if not await is_registered(self.bot, interaction.guild_id, user_id):
            return await interaction.followup.send("❌ 먼저 `/등록` 명령어로 플레이어 등록을 해주세요!")
            
        if not DATABASE_AVAILABLE or not POINT_MANAGER_AVAILABLE:
            return await interaction.followup.send("❌ 시스템 오류: 데이터베이스 또는 포인트 관리 시스템을 불러올 수 없습니다. 관리자에게 문의해주세요.")
        
        if xp_amount <= 0:
            return await interaction.followup.send("❌ 교환할 XP는 0보다 커야 합니다.")
        
        if self.exchange_system.get_user_daily_exchanges(user_id) >= self.exchange_system.settings['일일_제한']:
            return await interaction.followup.send("❌ 일일 교환 횟수 제한에 도달했습니다.")
            
        if not self.exchange_system.check_cooldown(user_id):
            return await interaction.followup.send(f"❌ 쿨다운 중입니다. {self.exchange_system.settings['쿨다운_분']}분 후에 다시 시도해주세요.")

        db = get_guild_db_manager_func(str(interaction.guild.id))
        user_xp_data = db.get_user_xp(user_id)
        current_xp = user_xp_data.get('xp', 0)
        
        if current_xp < xp_amount:
            return await interaction.followup.send(f"❌ 보유 XP가 부족합니다. 현재 XP: {db.format_xp(current_xp)}")
            
        # XP 차감 및 현금 지급
        try:
            cash_gained = int(xp_amount * self.exchange_system.settings['XP_to_현금_비율'])
            
            db.add_user_xp(user_id, -xp_amount)
            new_cash = await add_point(self.bot, interaction.guild.id, user_id, cash_gained)

            self.exchange_system.record_exchange(user_id, "xp_to_cash", xp_amount, cash_gained)
            self.exchange_system.update_cooldown(user_id)
            
            embed = discord.Embed(
                title="✨ XP를 현금으로 교환 완료",
                description=f"{db.format_xp(xp_amount)}를 교환하여 **{db.format_money(cash_gained)}**을(를) 획득했습니다!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💰 남은 현금",
                value=f"**{db.format_money(new_cash)}**",
                inline=True
            )
            embed.add_field(
                name="📊 남은 XP",
                value=f"**{db.format_xp(db.get_user_xp(user_id)['xp'])}**",
                inline=True
            )
            embed.set_footer(text=f"현재 교환 비율: 1 XP = {self.exchange_system.settings['XP_to_현금_비율']:.2f}원 | 일일 {self.exchange_system.get_user_daily_exchanges(user_id)}회 사용")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ XP to 현금 교환 중 오류 발생: {e}")
            await interaction.followup.send("❌ 교환 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.")

    # 현금을 XP로 교환
    @app_commands.command(name="경험치교환", description="현금을 XP로 교환합니다. 수수료가 부과됩니다.")
    @app_commands.describe(cash_amount="교환할 현금")
    async def exchange_cash_to_xp(self, interaction: discord.Interaction, cash_amount: int):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        
        if not await is_registered(self.bot, interaction.guild_id, user_id):
            return await interaction.followup.send("❌ 먼저 `/등록` 명령어로 플레이어 등록을 해주세요!")
            
        if not DATABASE_AVAILABLE or not POINT_MANAGER_AVAILABLE:
            return await interaction.followup.send("❌ 시스템 오류: 데이터베이스 또는 포인트 관리 시스템을 불러올 수 없습니다. 관리자에게 문의해주세요.")
        
        if cash_amount <= 0:
            return await interaction.followup.send("❌ 교환할 현금은 0보다 커야 합니다.")
            
        if self.exchange_system.get_user_daily_exchanges(user_id) >= self.exchange_system.settings['일일_제한']:
            return await interaction.followup.send("❌ 일일 교환 횟수 제한에 도달했습니다.")
            
        if not self.exchange_system.check_cooldown(user_id):
            return await interaction.followup.send(f"❌ 쿨다운 중입니다. {self.exchange_system.settings['쿨다운_분']}분 후에 다시 시도해주세요.")

        current_cash = await get_point(self.bot, interaction.guild_id, user_id)
        db = get_guild_db_manager_func(str(interaction.guild.id))
        if current_cash < cash_amount:
            return await interaction.followup.send(f"❌ 보유 현금이 부족합니다. 현재 현금: {db.format_money(current_cash)}")
            
        # 현금 차감 및 XP 지급
        try:
            xp_gained = int(cash_amount * self.exchange_system.settings['현금_to_XP_비율'])
            
            new_cash = await add_point(self.bot, interaction.guild_id, user_id, -cash_amount)
            db.add_user_xp(user_id, xp_gained)
            
            self.exchange_system.record_exchange(user_id, "cash_to_xp", cash_amount, xp_gained)
            self.exchange_system.update_cooldown(user_id)
            
            embed = discord.Embed(
                title="💰 현금을 XP로 교환 완료",
                description=f"{db.format_money(cash_amount)}를 교환하여 **{db.format_xp(xp_gained)}**을(를) 획득했습니다!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="💰 남은 현금",
                value=f"**{db.format_money(new_cash)}**",
                inline=True
            )
            embed.add_field(
                name="📊 남은 XP",
                value=f"**{db.format_xp(db.get_user_xp(user_id)['xp'])}**",
                inline=True
            )
            embed.set_footer(text=f"현재 교환 비율: 1원 = {self.exchange_system.settings['현금_to_XP_비율']:.2f} XP | 일일 {self.exchange_system.get_user_daily_exchanges(user_id)}회 사용")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ 현금 to XP 교환 중 오류 발생: {e}")
            await interaction.followup.send("❌ 교환 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.")

    @app_commands.command(name="교환설정", description="교환 시스템 설정을 변경합니다. (관리자 전용)")
    @app_commands.describe(
        현금수수료="현금 교환시 차감할 수수료율 (%)",
        경험치수수료="XP 교환시 차감할 수수료율 (%)",
        횟수="하루 최대 교환 횟수",
        쿨다운="교환 쿨다운 시간 (분)"
    )
    @app_commands.default_permissions(administrator=True)
    async def exchange_settings(
        self,
        interaction: discord.Interaction,
        현금수수료: Optional[float] = None,
        경험치수수료: Optional[float] = None,
        횟수: Optional[int] = None,
        쿨다운: Optional[int] = None
    ):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send("❌ 이 명령어는 서버 관리자만 사용할 수 있습니다.")
            
        updated_settings = self.exchange_system.settings.copy()
        
        # 현금 수수료율 처리 (현금 -> XP)
        if 현금수수료 is not None:
            if not 0 <= 현금수수료 <= 100:
                return await interaction.followup.send("❌ 현금 수수료율은 0%에서 100% 사이의 값이어야 합니다.")
            updated_settings["현금_수수료율"] = 현금수수료
            updated_settings["현금_to_XP_비율"] = 1.0 - (현금수수료 / 100)

        # XP 수수료율 처리 (XP -> 현금)
        if 경험치수수료 is not None:
            if not 0 <= 경험치수수료 <= 100:
                return await interaction.followup.send("❌ 경험치 수수료율은 0%에서 100% 사이의 값이어야 합니다.")
            updated_settings["XP_수수료율"] = 경험치수수료
            updated_settings["XP_to_현금_비율"] = 1.0 - (경험치수수료 / 100)

        if 횟수 is not None:
            updated_settings["일일_제한"] = 횟수
        if 쿨다운 is not None:
            updated_settings["쿨다운_분"] = 쿨다운
            
        self.exchange_system.save_settings(updated_settings)
        self.exchange_system.settings = updated_settings
        
        embed = discord.Embed(
            title="⚙️ 교환 설정 업데이트 완료",
            description="교환 시스템 설정이 성공적으로 변경되었습니다.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="현재 설정",
            value=(
                f"**현금→XP 수수료**: {self.exchange_system.settings['현금_수수료율']:.1f}%\n"
                f"**XP→현금 수수료**: {self.exchange_system.settings['XP_수수료율']:.1f}%\n"
                f"**일일 제한**: {self.exchange_system.settings['일일_제한']}회\n"
                f"**쿨다운**: {self.exchange_system.settings['쿨다운_분']}분"
            ),
            inline=False
        )
        
        logger.info(f"✅ {interaction.user.display_name}님이 교환 설정을 변경했습니다.")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="교환현황", description="XP/현금 교환 시스템의 현재 상태를 확인합니다.")
    
    async def exchange_status(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        
        # 시스템 설정
        embed = discord.Embed(
            title="🔄 XP/현금 교환 시스템 현황",
            description="현재 교환 시스템의 설정 및 나의 교환 현황입니다.",
            color=discord.Color.dark_green()
        )
        embed.add_field(
            name="⚙️ 시스템 설정",
            value=f"**현금→XP 수수료**: {self.exchange_system.settings['현금_수수료율']:.1f}%\n"
                  f"**XP→현금 수수료**: {self.exchange_system.settings['XP_수수료율']:.1f}%\n"
                  f"**일일 제한**: {self.exchange_system.settings['일일_제한']}회\n"
                  f"**쿨다운**: {self.exchange_system.settings['쿨다운_분']}분",
            inline=True
        )
        
        # 내 교환 현황
        daily_count = self.exchange_system.get_user_daily_exchanges(user_id)
        user_history = self.exchange_system.exchange_history.get(user_id, [])
        total_exchanges = len(user_history)
        
        embed.add_field(
            name="📈 내 교환 현황",
            value=f"**오늘 교환**: {daily_count}/{self.exchange_system.settings['일일_제한']}회\n"
                  f"**총 교환 횟수**: {total_exchanges}회\n"
                  f"**남은 횟수**: {max(0, self.exchange_system.settings['일일_제한'] - daily_count)}회",
            inline=False
        )
        
        # 최근 교환 기록 (최대 3개)
        if user_history:
            recent_exchanges = sorted(user_history, key=lambda x: x['date'], reverse=True)[:3]
            history_text = ""
            for exchange in recent_exchanges:
                date = datetime.datetime.fromisoformat(exchange['date']).strftime('%m/%d %H:%M')
                type_emoji = "💰→✨" if exchange['type'] == "cash_to_xp" else "✨→💰"
                history_text += f"{type_emoji} {exchange['amount']:,} → {exchange['result']:,} ({date})\n"
            
            embed.add_field(
                name="⏳ 최근 교환 기록",
                value=history_text,
                inline=False
            )
        else:
            embed.add_field(
                name="⏳ 최근 교환 기록",
                value="아직 교환 기록이 없습니다.",
                inline=False
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    # Get the PointManager cog instance, which holds a reference to the database manager.
    point_manager_cog = bot.get_cog("PointManager")
    if not point_manager_cog:
        # This error can happen if point_manager.py is not loaded or is loaded after this cog.
        logger.error("❌ 'PointManager' cog not found. It must be loaded before 'exchange_system'.")
        return

    # Create an instance of the ExchangeCog class, passing the required managers.
    # The log error indicates that ExchangeCog's __init__ method expects these arguments directly.
    cog = ExchangeCog(bot)
    await bot.add_cog(cog)
    logger.info("✅ Exchange System (ExchangeCog) 로드 완료.")