# leaderboard_system.py - 통합 리더보드
from __future__ import annotations
import datetime
import discord
from discord import app_commands, Interaction, Member
from discord.ext import commands
from typing import Dict, Optional, List, Any
import math
from database_manager import DEFAULT_LEADERBOARD_SETTINGS

# ✅ 안전한 의존성 import (point_manager는 그대로 유지)
def safe_import_point_manager():
    try:
        import point_manager as pm_module
        return pm_module.get_point, pm_module.add_point, pm_module.set_point, pm_module.is_registered, True
    except ImportError:
        print("⚠️ point_manager 임포트 실패")
        return None, None, None, None, False

def format_money(amount: int) -> str:
    """돈 포맷 함수"""
    return f"{amount:,}원"

def format_xp(xp: int) -> str:
    """XP 포맷 함수"""
    return f"{xp:,} XP"

# ✅ 의존성 로드
get_point, add_point, set_point, is_registered, POINT_MANAGER_AVAILABLE = safe_import_point_manager()

# ===== 메인 COG 클래스 =====

class IntegratedLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_cog: Optional[Any] = None # DatabaseCog 타입을 명시하는 것이 더 좋습니다.
        print("✅ 통합 리더보드 시스템 초기화 완료")

    async def cog_load(self):
        # DatabaseCog가 로드된 후 접근
        self.db_cog = self.bot.get_cog("DatabaseManager")
        if not self.db_cog:
            print("❌ DatabaseManager Cog를 찾을 수 없습니다. 리더보드 기능이 제한됩니다.")
        else:
            print("✅ DatabaseManager Cog 연결 성공.")

    # ===== 통합 리더보드 명령어들 =====
    @app_commands.command(name="통합리더보드", description="[관리자 전용] 서버의 XP 및 자산 통합 통계를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def integrated_stats(self, interaction: discord.Interaction):
        """서버의 전체 XP와 자산(돈) 데이터를 분석하여 리포트를 생성합니다."""
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        if not self.db_cog:
            return await interaction.followup.send("❌ 데이터베이스 매니저를 찾을 수 없습니다.")
        
        db = self.db_cog.get_manager(guild_id)
        
        # 1. XP 통계 쿼리
        xp_stats = db.execute_query('''
            SELECT 
                COUNT(*) as total_users,
                SUM(xp) as total_xp,
                AVG(xp) as avg_xp,
                MAX(xp) as max_xp,
                AVG(level) as avg_level,
                MAX(level) as max_level
            FROM user_xp
            WHERE guild_id = ? AND xp > 0
        ''', (guild_id,), 'one')

        # 2. 금액(포인트) 통계 쿼리
        money_stats = db.execute_query('''
            SELECT 
                SUM(cash) as total_money,
                AVG(cash) as avg_money,
                MAX(cash) as max_money,
                MIN(cash) as min_money
            FROM users
            WHERE user_id IN (SELECT user_id FROM user_xp WHERE guild_id = ?)
        ''', (guild_id,), 'one')

        # 3. 데이터 검증
        if not xp_stats or xp_stats['total_users'] == 0:
            return await interaction.followup.send("❌ 분석할 데이터가 충분하지 않습니다.")

        # 4. 임베드 구성
        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} 통합 데이터 리포트",
            description="서버의 전체 경제 및 성장 지표입니다.",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now()
        )

        # XP 섹션
        xp_text = (
            f"👥 **참여 인원:** {xp_stats['total_users']:,}명\n"
            f"✨ **누적 총 XP:** {int(xp_stats['total_xp']):,} XP\n"
            f"📈 **평균 레벨:** Lv.{xp_stats['avg_level']:.1f}\n"
            f"🏆 **최고 레벨:** Lv.{xp_stats['max_level']}"
        )
        embed.add_field(name="✨ 경험치(XP) 지표", value=xp_text, inline=False)

        # 금액 섹션 (요청하신 항목 포함)
        if money_stats and money_stats['total_money'] is not None:
            money_text = (
                f"💰 **누적 총 금액:** {int(money_stats['total_money']):,}원\n"
                f"📈 **평균 보유액:** {int(money_stats['avg_money']):,}원\n"
                f"🏆 **최고 보유액:** {int(money_stats['max_money']):,}원\n"
                f"📉 **최저 보유액:** {int(money_stats['min_money']):,}원"
            )
            embed.add_field(name="💵 자산(Money) 지표", value=money_text, inline=False)
        else:
            embed.add_field(name="💵 자산(Money) 지표", value="데이터가 없습니다.", inline=False)

        embed.set_footer(text=f"Admin: {interaction.user.display_name} | 분석 완료")
        
        await interaction.followup.send(embed=embed, ephemeral=False)

    @app_commands.command(name="리더보드설정", description="[관리자 전용] 출석 및 환전 등 리더보드 시스템의 모든 설정을 확인하고 수정합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        설정="변경할 설정 항목",
        값="새로운 값"
    )
    @app_commands.choices(설정=[
        app_commands.Choice(name="💰 출석 현금 보상", value="attendance_cash"),
        app_commands.Choice(name="✨ 출석 XP 보상", value="attendance_xp"),
        app_commands.Choice(name="🔥 연속 현금 보너스 일수", value="streak_cash_per_day"),
        app_commands.Choice(name="✨ 연속 XP 보너스 일수", value="streak_xp_per_day"),
        app_commands.Choice(name="🗓️ 최대 연속 보너스 일수", value="max_streak_bonus_days"),
        app_commands.Choice(name="🎁 7일 현금 보너스", value="weekly_cash_bonus"),
        app_commands.Choice(name="✨ 7일 XP 보너스", value="weekly_xp_bonus"),
        app_commands.Choice(name="🏆 30일 현금 보너스", value="monthly_cash_bonus"),
        app_commands.Choice(name="⭐ 30일 XP 보너스", value="monthly_xp_bonus"),
    ])
    async def leaderboard_settings(self, interaction: discord.Interaction, 설정: app_commands.Choice[str] = None, 값: int = None):
        if not self.db_cog:
            return await interaction.response.send_message("❌ 데이터베이스 시스템이 로드되지 않았습니다.", ephemeral=True)

        guild_id = str(interaction.guild.id)
        db = self.db_cog.get_manager(guild_id) # DatabaseCog를 통해 manager 가져오기
        settings = db.get_leaderboard_settings()
        
        default_settings = DEFAULT_LEADERBOARD_SETTINGS

        SETTING_NAMES_KO = {
                            "attendance_cash": "출석 현금 보상",
                            "attendance_xp": "출석 XP 보상",
                            "streak_cash_per_day": "연속 현금 보너스/일",
                            "streak_xp_per_day": "연속 XP 보너스/일",
                            "max_streak_bonus_days": "최대 연속 보너스 일수",
                            "weekly_cash_bonus": "7일 현금 보너스",
                            "weekly_xp_bonus": "7일 XP 보너스",
                            "monthly_cash_bonus": "30일 현금 보너스",
                            "monthly_xp_bonus": "30일 XP 보너스",
                            }
        
        # 설정 확인만 하는 경우
        if 설정 is None or 값 is None:
            embed = discord.Embed(
                title="⚙️ 리더보드 및 출석 설정",
                description="현재 설정값들을 확인하고 수정할 수 있습니다.",
                color=discord.Color.blue()
            )
            
            for key, value in settings.items():
                # guild_id, created_at, updated_at 필드는 표시하지 않음
                if key in ["guild_id", "created_at", "updated_at"]:
                    continue

                if "cash" in key or "bonus" in key:
                    formatted_value = format_money(value)
                elif "xp" in key:
                    formatted_value = format_xp(value)
                else:
                    formatted_value = str(value)
                
                name_ko = SETTING_NAMES_KO.get(key, key.replace("_", " ").title())
                embed.add_field(
                    name=name_ko,
                    value=formatted_value,
                    inline=True
                )
            
            embed.set_footer(text="수정하려면: /리더보드설정 설정:항목 값:숫자")
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
        
        # 설정 변경
        setting_key = 설정.value
        if setting_key not in default_settings: # DEFAULT_SETTINGS 대신 default_settings 사용
            return await interaction.response.send_message("❌ 유효하지 않은 설정 항목입니다.", ephemeral=True)
        
        # 값 유효성 검사
        if 값 < 0:
            return await interaction.response.send_message("❌ 설정값은 0 이상이어야 합니다.", ephemeral=True)
        
        # 설정 업데이트
        old_value = settings.get(setting_key, default_settings.get(setting_key)) # DEFAULT_SETTINGS 대신 default_settings 사용
        
        # 업데이트할 설정 딕셔너리 생성
        updated_settings = {setting_key: 값}
        db.update_leaderboard_settings(updated_settings)
        
        # 업데이트된 설정 다시 로드
        settings = db.get_leaderboard_settings()
            
        embed = discord.Embed(
            title="✅ 설정 변경 완료",
            color=discord.Color.green()
        )
        
        embed.add_field(name="설정 항목", value=설정.name, inline=True)
        embed.add_field(name="이전 값", value=str(old_value), inline=True)
        embed.add_field(name="새 값", value=str(값), inline=True)
        
        embed.set_footer(text=f"변경자: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(IntegratedLeaderboardCog(bot))
    print("✅ 통합 리더보드 시스템 로드 완료 (중복 명령어 해결)")