# exchange_system.py - 교환 시스템
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os
import asyncio
from typing import Optional, Dict, Any, List
import logging

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
def safe_import_point_manager():
    try:
        from point_manager import get_point, add_point, set_point, is_registered
        return get_point, add_point, set_point, is_registered, True
    except ImportError as e:
        logger.warning(f"⚠️ point_manager 임포트 실패: {e}")
        return None, None, None, None, False

# 의존성 로드
get_point, add_point, set_point, is_registered, POINT_MANAGER_AVAILABLE = safe_import_point_manager()

# 설정 파일 관리
DATA_DIR = "data"
EXCHANGE_SETTINGS_FILE = os.path.join(DATA_DIR, "exchange_settings.json")
EXCHANGE_HISTORY_FILE = os.path.join(DATA_DIR, "exchange_history.json")

os.makedirs(DATA_DIR, exist_ok=True)

class ExchangeSystem:
    def __init__(self):
        self.settings_file = EXCHANGE_SETTINGS_FILE
        self.settings = self.load_settings()
        # 변경된 데이터 구조: 모든 기록을 하나의 리스트로 관리
        self.exchange_history = self.load_history() 
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
                json.dump(settings_data, f, indent=4, ensure_ascii=False) # indent와 ensure_ascii 추가
        except Exception as e:
            logger.error(f"❌ 설정 파일 저장 중 오류 발생: {e}")

    def load_history(self) -> List[Dict[str, Any]]:
        """교환 기록 로드 (리스트 형식)"""
        if not os.path.exists(EXCHANGE_HISTORY_FILE):
            self.save_history([])
            logger.info("✅ 교환 기록 파일이 없어 새로 생성했습니다.")
            return []
        try:
            with open(EXCHANGE_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                # 이전 dict 형식 호환
                if isinstance(history, dict):
                    new_history = []
                    for user_id, records in history.items():
                        for record in records:
                            record['user_id'] = user_id
                            new_history.append(record)
                    self.save_history(new_history)
                    return new_history
                return history
        except Exception as e:
            logger.error(f"❌ 교환 기록 로드 오류: {e}")
            return []

    def save_history(self, history: List[Dict[str, Any]]):
        """교환 기록 저장 (리스트 형식)"""
        try:
            with open(EXCHANGE_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4)
        except Exception as e:
            logger.error(f"❌ 교환 기록 저장 오류: {e}")

    def get_user_daily_exchanges(self, user_id: str) -> int:
        """오늘 교환 횟수 계산"""
        today_str = datetime.datetime.now().date().isoformat()
        return sum(1 for entry in self.exchange_history if entry.get('user_id') == user_id and entry['date'].startswith(today_str))

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

    def record_exchange(self, interaction: discord.Interaction, exchange_type: str, amount: int, result: int):
        """교환 기록 저장"""
        self.exchange_history.append({
            "date": datetime.datetime.now().isoformat(),
            "user_id": str(interaction.user.id),
            "guild_id": str(interaction.guild.id),
            "type": exchange_type,
            "amount": amount,
            "result": result
        })
        self.save_history(self.exchange_history)

class ExchangeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.exchange_system = ExchangeSystem()
        self.db_cog: Optional[Any] = None # DatabaseCog 인스턴스를 저장할 변수
        logger.info("✅ 통합 교환 시스템 v6 로드 완료")

    async def cog_load(self):
        """Cog가 로드된 후 DatabaseManager Cog를 가져옵니다."""
        self.db_cog = self.bot.get_cog("DatabaseManager")
        if not self.db_cog:
            logger.error("❌ DatabaseManager Cog를 찾을 수 없습니다. 교환 기능이 제한됩니다.")
        else:
            logger.info("✅ DatabaseManager Cog 연결 성공.")

    # XP를 현금으로 교환
    @app_commands.command(name="현금교환", description="XP를 현금으로 교환합니다. 수수료가 부과됩니다.")
    @app_commands.describe(xp_amount="교환할 XP")
    async def exchange_xp_to_cash(self, interaction: discord.Interaction, xp_amount: int):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'exchange' 권한이 있는지 체크 (channel_config.py의 value="exchange"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "exchange", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 교환이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=False)
        user_id = str(interaction.user.id)
        
        if not await is_registered(self.bot, interaction.guild_id, user_id):
            return await interaction.followup.send("❌ 먼저 `/등록` 명령어로 플레이어 등록을 해주세요!")
            
        if not self.db_cog or not POINT_MANAGER_AVAILABLE:
            return await interaction.followup.send("❌ 시스템 오류: 데이터베이스 또는 포인트 관리 시스템을 불러올 수 없습니다. 관리자에게 문의해주세요.")
        
        if xp_amount <= 0:
            return await interaction.followup.send("❌ 교환할 XP는 0보다 커야 합니다.")
        
        if self.exchange_system.get_user_daily_exchanges(user_id) >= self.exchange_system.settings['일일_제한']:
            return await interaction.followup.send("❌ 일일 교환 횟수 제한에 도달했습니다.")
            
        if not self.exchange_system.check_cooldown(user_id):
            return await interaction.followup.send(f"❌ 쿨다운 중입니다. {self.exchange_system.settings['쿨다운_분']}분 후에 다시 시도해주세요.")

        db = self.db_cog.get_manager(str(interaction.guild.id))
        user_xp_data = db.get_user_xp(user_id)
        current_xp = user_xp_data.get('xp', 0) if user_xp_data else 0
        
        if current_xp < xp_amount:
            return await interaction.followup.send(f"❌ 보유 XP가 부족합니다. 현재 XP: {db.format_xp(current_xp)}")
            
        # XP 차감 및 현금 지급
        try:
            cash_gained = int(xp_amount * self.exchange_system.settings['XP_to_현금_비율'])

           # 1. DB에서 XP 차감
            db.add_user_xp(user_id, -xp_amount)
            # 2. 현금 포인트 추가
            await add_point(self.bot, interaction.guild_id, user_id, cash_gained)
            # 3. ❗ 최신 현금 잔액 직접 조회 (1 방지)
            actual_cash = await get_point(self.bot, interaction.guild_id, user_id)

            self.exchange_system.record_exchange(interaction, "xp_to_cash", xp_amount, cash_gained)
            self.exchange_system.update_cooldown(user_id)
            
            embed = discord.Embed(
                title="✨ XP를 현금으로 교환 완료",
                description=f"{db.format_xp(xp_amount)}를 교환하여 **{db.format_money(cash_gained)}**을(를) 획득했습니다!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 남은 현금", value=f"**{db.format_money(actual_cash)}**", inline=True)
            embed.add_field(name="📊 남은 XP", value=f"**{db.format_xp(db.get_user_xp(user_id)['xp'])}**", inline=True)
           
            embed.set_footer(text=f"현재 교환 비율: 1 XP = {self.exchange_system.settings['XP_to_현금_비율']:.2f}원 | 일일 {self.exchange_system.get_user_daily_exchanges(user_id)}회 사용")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ XP to 현금 교환 중 오류 발생: {e}")
            await interaction.followup.send("❌ 교환 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.")

    # 현금을 XP로 교환
    @app_commands.command(name="경험치교환", description="현금을 XP로 교환합니다. 수수료가 부과됩니다.")
    @app_commands.describe(cash_amount="교환할 현금")
    async def exchange_cash_to_xp(self, interaction: discord.Interaction, cash_amount: int):
        config_cog = self.bot.get_cog("ChannelConfig")
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "exchange", interaction.guild.id)
            if not is_allowed:
                return await interaction.response.send_message("🚫 이 채널은 교환이 허용되지 않은 채널입니다.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        user_id = str(interaction.user.id)
        
        if not await is_registered(self.bot, interaction.guild_id, user_id):
            return await interaction.followup.send("❌ 먼저 `/등록` 명령어로 플레이어 등록을 해주세요!")
        
        if not self.db_cog or not POINT_MANAGER_AVAILABLE:
            return await interaction.followup.send("❌ 시스템 오류가 발생했습니다.")
        
        if self.exchange_system.get_user_daily_exchanges(user_id) >= self.exchange_system.settings['일일_제한']:
            return await interaction.followup.send("❌ 일일 교환 횟수 제한에 도달했습니다.")
        
        if cash_amount <= 0:
            return await interaction.followup.send("❌ 교환할 현금은 0보다 커야 합니다.")
            
        current_cash = await get_point(self.bot, interaction.guild_id, user_id)
        db = self.db_cog.get_manager(str(interaction.guild.id))

        if current_cash < cash_amount:
            return await interaction.followup.send(f"❌ 보유 현금이 부족합니다. 현재 현금: {db.format_money(current_cash)}")
            
        try:
            # 1. 계산 (round를 사용하여 오차 방지)
            xp_gained = round(cash_amount * self.exchange_system.settings['현금_to_XP_비율'])
            
            # 2. 포인트 차감 (단 한 번만 수행)
            await add_point(self.bot, interaction.guild_id, user_id, -cash_amount)
            # 3. XP 추가
            db.add_user_xp(user_id, xp_gained)
            
            # 4. ❗ 중요: 차감 후 실제 DB 잔액을 새로 조회 (1원 오류 해결 핵심)
            actual_remaining_cash = await get_point(self.bot, interaction.guild_id, user_id)

            self.exchange_system.record_exchange(interaction, "cash_to_xp", cash_amount, xp_gained)
            self.exchange_system.update_cooldown(user_id)

            embed = discord.Embed(
                title="💰 현금을 XP로 교환 완료",
                description=f"{db.format_money(cash_amount)}를 교환하여 **{db.format_xp(xp_gained)}**을(를) 획득했습니다!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 남은 현금", value=f"**{db.format_money(actual_remaining_cash)}**", inline=True)
            embed.add_field(name="📊 남은 XP", value=f"**{db.format_xp(db.get_user_xp(user_id)['xp'])}**", inline=True)
            
            embed.set_footer(text=f"현재 교환 비율: 1원 = {self.exchange_system.settings['현금_to_XP_비율']:.2f} XP")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"❌ 교환 중 오류: {e}")
            await interaction.followup.send("❌ 교환 처리 중 오류가 발생했습니다.")

    @app_commands.command(name="교환설정", description="[관리자 전용] 교환 시스템 설정을 변경합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        현금수수료="현금 교환시 차감할 수수료율 (%)",
        경험치수수료="XP 교환시 차감할 수수료율 (%)",
        횟수="하루 최대 교환 횟수",
        쿨다운="교환 쿨다운 시간 (분)"
    )
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

    @app_commands.command(name="교환현황", description="XP/현금 교환 시스템의 현재 상태와 서버의 주간 교환 기록을 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def exchange_status(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # 시스템 설정
        embed = discord.Embed(
            title="🔄 XP | 현금 교환 시스템 현황",
            description="현재 교환 시스템의 설정 및 교환 현황입니다.",
            color=discord.Color.dark_green()
        )
        embed.add_field(
            name="⚙️ 시스템 설정",
            value=f"**현금→XP 수수료**: {self.exchange_system.settings['현금_수수료율']:.1f}%\n"
                  f"**XP→현금 수수료**: {self.exchange_system.settings['XP_수수료율']:.1f}%\n"
                  f"**일일 제한**: {self.exchange_system.settings['일일_제한']}회\n"
                  f"**쿨다운**: {self.exchange_system.settings['쿨다운_분']}분",
            inline=False
        )
        
        # 서버의 주간 교환 기록 (최대 25개)
        now = datetime.datetime.now()
        one_week_ago = now - datetime.timedelta(days=7)
        
        guild_history = [e for e in self.exchange_system.exchange_history if e.get('guild_id') == guild_id]
        
        # 주간 기록 필터링
        weekly_guild_history = []
        for e in guild_history:
            try:
                # naive datetime으로 변환하여 비교
                record_date = datetime.datetime.fromisoformat(e['date'])
                if record_date > one_week_ago:
                    weekly_guild_history.append(e)
            except (ValueError, KeyError):
                continue # 날짜 형식이 잘못된 기록은 건너뜀

        history_text = ""
        if weekly_guild_history:
            recent_exchanges = sorted(weekly_guild_history, key=lambda x: x['date'], reverse=True)
            lines = []
            for exchange in recent_exchanges[:15]: # 상위 15개
                ex_user_id = exchange.get('user_id')
                member = interaction.guild.get_member(int(ex_user_id)) if ex_user_id else None
                user_name = member.display_name if member else f"ID: {ex_user_id}"
                date = datetime.datetime.fromisoformat(exchange['date']).strftime('%m/%d %H:%M')
                type_emoji = "💰→✨" if exchange['type'] == "cash_to_xp" else "✨→💰"
                
                line = f"👤 **{user_name}**: {type_emoji} {exchange['amount']:,} → {exchange['result']:,} ({date})"
                lines.append(line)
            
            history_text = "\n".join(lines)
            if len(weekly_guild_history) > 15:
                history_text += "\n... (외 기록 생략)"
        else:
            history_text = "지난 일주일간 교환 기록이 없습니다."

async def setup(bot: commands.Bot):
    point_manager_cog = bot.get_cog("PointManager")
    if not point_manager_cog:
        logger.error("❌ 'PointManager' cog not found. It must be loaded before 'exchange_system'.")
        return

    cog = ExchangeCog(bot)
    await bot.add_cog(cog)
    logger.info("✅ Exchange System (ExchangeCog) 로드 완료.")