# leaderboard_system.py - 완전 작동 버전 (중복 명령어 해결)
from __future__ import annotations
import os
import datetime
import discord
from discord import app_commands, Interaction, Member
from discord.ext import commands
from typing import Dict, Optional, List
import math

# ✅ 안전한 의존성 import
def safe_import_database():
    try:
        from database_manager import db_manager
        return db_manager, True
    except ImportError:
        print("⚠️ database_manager 임포트 실패")
        return None, False

def safe_import_point_manager():
    try:
        from point_manager import get_point, add_point, set_point, is_registered
        return get_point, add_point, set_point, is_registered, True
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
db_manager, DATABASE_AVAILABLE = safe_import_database()
get_point, add_point, set_point, is_registered, POINT_MANAGER_AVAILABLE = safe_import_point_manager()

# ✅ 설정 파일 관리
DATA_DIR = "data"
LEADERBOARD_SETTINGS_FILE = os.path.join(DATA_DIR, "leaderboard_settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

# 기본 설정값
DEFAULT_SETTINGS = {
    "attendance_cash": 3000,
    "attendance_xp": 100,
    "streak_cash_per_day": 100,      # 연속 출석일당 추가 현금
    "streak_xp_per_day": 10,         # 연속 출석일당 추가 XP
    "max_streak_bonus_days": 30,     # 연속 보너스가 적용되는 최대 일수
    "weekly_cash_bonus": 1000,
    "weekly_xp_bonus": 500,
    "monthly_cash_bonus": 10000,
    "monthly_xp_bonus": 5000,
    "exchange_fee_percent": 5,
    "daily_exchange_limit": 10
}

def load_settings():
    """설정 로드"""
    try:
        import json
        if os.path.exists(LEADERBOARD_SETTINGS_FILE):
            with open(LEADERBOARD_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"설정 로드 실패: {e}")
    return DEFAULT_SETTINGS

def save_settings(settings):
    """설정 저장"""
    try:
        import json
        with open(LEADERBOARD_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"설정 저장 실패: {e}")
        return False

# ===== 메인 COG 클래스 =====

class IntegratedLeaderboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = load_settings()
        print("✅ 통합 리더보드 시스템 초기화 완료")

    # ===== 통합 리더보드 명령어들 =====

    @app_commands.command(name="통합리더보드", description="통합 리더보드를 확인합니다 (현금+XP)")
    @app_commands.describe(
        타입="확인할 리더보드 타입",
        페이지="페이지 번호 (기본: 1)"
    )
    @app_commands.choices(타입=[
        app_commands.Choice(name="💰 현금 순위", value="cash"),
        app_commands.Choice(name="✨ XP 순위", value="xp"),
        app_commands.Choice(name="🏆 통합 순위", value="combined")
    ])
    async def integrated_leaderboard(self, interaction: discord.Interaction, 타입: app_commands.Choice[str] = None, 페이지: int = 1):
        await interaction.response.defer()
        
        try:
            board_type = 타입.value if 타입 else "combined"
            page = max(1, 페이지)
            
            if board_type == "cash":
                await self.show_cash_leaderboard(interaction, page)
            elif board_type == "xp":
                await self.show_xp_leaderboard(interaction, page)
            else:
                await self.show_combined_leaderboard(interaction, page)
                
        except Exception as e:
            await interaction.followup.send(f"❌ 리더보드 조회 중 오류: {str(e)}")
            print(f"리더보드 오류: {e}")

    async def show_cash_leaderboard(self, interaction: discord.Interaction, page: int):
        """현금 리더보드 표시"""
        if not DATABASE_AVAILABLE:
            embed = discord.Embed(
                title="💰 현금 리더보드",
                description="❌ 데이터베이스를 사용할 수 없습니다.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            # 현금 리더보드 조회
            leaderboard = db_manager.get_cash_leaderboard(10)
            
            if not leaderboard:
                embed = discord.Embed(
                    title="💰 현금 리더보드",
                    description="아직 등록된 사용자가 없습니다.",
                    color=discord.Color.gold()
                )
                return await interaction.followup.send(embed=embed)
            
            embed = discord.Embed(
                title=f"💰 현금 리더보드 (페이지 {page})",
                color=discord.Color.gold()
            )
            
            ranking_text = ""
            for i, user in enumerate(leaderboard[:10], 1):
                rank = i
                username = user.get('display_name') or user.get('username') or "Unknown"
                cash = user.get('cash', 0)
                
                # 순위 이모지
                if rank == 1:
                    rank_emoji = "🥇"
                elif rank == 2:
                    rank_emoji = "🥈" 
                elif rank == 3:
                    rank_emoji = "🥉"
                else:
                    rank_emoji = f"**{rank}.**"
                
                ranking_text += f"{rank_emoji} {username}\n   💰 {format_money(cash)}\n\n"
            
            embed.description = ranking_text
            embed.set_footer(text="💡 /등록으로 시작하고 /출석체크로 현금을 받으세요!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 현금 리더보드 조회 실패: {str(e)}")

    async def show_xp_leaderboard(self, interaction: discord.Interaction, page: int):
        """XP 리더보드 표시"""
        if not DATABASE_AVAILABLE:
            embed = discord.Embed(
                title="✨ XP 리더보드",
                description="❌ 데이터베이스를 사용할 수 없습니다.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            guild_id = str(interaction.guild.id)
            
            # XP 리더보드 조회
            leaderboard_data = db_manager.execute_query('''
                SELECT u.user_id, u.username, u.display_name, x.xp, x.level
                FROM user_xp x
                JOIN users u ON x.user_id = u.user_id
                WHERE x.guild_id = ? AND x.xp > 0
                ORDER BY x.xp DESC
                LIMIT 10
            ''', (guild_id,), 'all')
            
            if not leaderboard_data:
                embed = discord.Embed(
                    title="✨ XP 리더보드",
                    description="아직 XP 기록이 없습니다.",
                    color=discord.Color.purple()
                )
                return await interaction.followup.send(embed=embed)
            
            embed = discord.Embed(
                title=f"✨ XP 리더보드 (페이지 {page})",
                color=discord.Color.purple()
            )
            
            ranking_text = ""
            for i, user_data in enumerate(leaderboard_data, 1):
                rank = i
                username = user_data['display_name'] or user_data['username'] or "Unknown"
                
                # 순위 이모지
                if rank == 1:
                    rank_emoji = "🥇"
                elif rank == 2:
                    rank_emoji = "🥈"
                elif rank == 3:
                    rank_emoji = "🥉"
                else:
                    rank_emoji = f"**{rank}.**"
                
                ranking_text += f"{rank_emoji} {username}\n"
                ranking_text += f"   🏆 Lv.{user_data['level']} | ✨ {format_xp(user_data['xp'])}\n\n"
            
            embed.description = ranking_text
            embed.set_footer(text="💡 /내레벨로 내 정보를 확인하세요!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ XP 리더보드 조회 실패: {str(e)}")

    async def show_combined_leaderboard(self, interaction: discord.Interaction, page: int):
        """통합 리더보드 표시"""
        try:
            embed = discord.Embed(
                title="🏆 통합 리더보드",
                description="현금과 XP 상위 랭킹을 한눈에 확인하세요!",
                color=discord.Color.gold()
            )
            
            # 현금 TOP 5
            if DATABASE_AVAILABLE:
                cash_leaderboard = db_manager.get_cash_leaderboard(5)
                if cash_leaderboard:
                    cash_text = ""
                    for i, user in enumerate(cash_leaderboard, 1):
                        username = user.get('display_name') or user.get('username') or "Unknown"
                        cash = user.get('cash', 0)
                        cash_text += f"{i}. {username}: {format_money(cash)}\n"
                    
                    embed.add_field(
                        name="💰 현금 TOP 5",
                        value=cash_text,
                        inline=True
                    )
            
            # XP TOP 5
            if DATABASE_AVAILABLE:
                guild_id = str(interaction.guild.id)
                xp_leaderboard = db_manager.execute_query('''
                    SELECT u.display_name, u.username, x.xp, x.level
                    FROM user_xp x
                    JOIN users u ON x.user_id = u.user_id
                    WHERE x.guild_id = ? AND x.xp > 0
                    ORDER BY x.xp DESC
                    LIMIT 5
                ''', (guild_id,), 'all')
                
                if xp_leaderboard:
                    xp_text = ""
                    for i, user in enumerate(xp_leaderboard, 1):
                        username = user['display_name'] or user['username'] or "Unknown"
                        xp_text += f"{i}. {username}: Lv.{user['level']} ({format_xp(user['xp'])})\n"
                    
                    embed.add_field(
                        name="✨ XP TOP 5",
                        value=xp_text,
                        inline=True
                    )
            
            # 서버 통계
            if DATABASE_AVAILABLE:
                stats = db_manager.get_total_cash_stats()
                guild_id = str(interaction.guild.id)
                
                total_xp_result = db_manager.execute_query(
                    "SELECT COALESCE(SUM(xp), 0) FROM user_xp WHERE guild_id = ?", 
                    (guild_id,), 'one'
                )
                total_xp = total_xp_result[0] if total_xp_result else 0
                
                embed.add_field(
                    name="📊 서버 통계",
                    value=f"총 현금: {format_money(stats.get('total_cash', 0))}\n"
                          f"총 XP: {format_xp(total_xp)}\n"
                          f"등록 사용자: {stats.get('total_users', 0):,}명",
                    inline=False
                )
        
        except Exception as e:
            embed.add_field(
                name="❌ 오류",
                value=f"일부 데이터를 불러올 수 없습니다: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text="💡 /리더보드관리로 관리자 설정 가능")
        await interaction.followup.send(embed=embed)

    # ===== 관리자 명령어들 =====

    @app_commands.command(name="리더보드관리", description="리더보드 시스템 통합 관리 (관리자 전용)")
    async def leaderboard_management(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
        
        settings = load_settings()
        
        embed = discord.Embed(
            title="🎛️ 리더보드 시스템 통합 관리",
            description="리더보드, 출석, 환전 시스템을 통합 관리합니다.",
            color=discord.Color.blue()
        )
        
        # 현재 설정 표시
        embed.add_field(
            name="💰 출석 현금 보상",
            value=f"{format_money(settings.get('attendance_cash', 3000))}",
            inline=True
        )
        
        embed.add_field(
            name="✨ 출석 XP 보상",
            value=f"{format_xp(settings.get('attendance_xp', 100))}",
            inline=True
        )
        
        embed.add_field(
            name="🎁 7일 현금 보너스",
            value=f"{format_money(settings.get('weekly_cash_bonus', 1000))}",
            inline=True
        )
        
        embed.add_field(
            name="✨ 7일 XP 보너스",
            value=f"{format_xp(settings.get('weekly_xp_bonus', 500))}",
            inline=True
        )
        
        embed.add_field(
            name="🏆 30일 현금 보너스",
            value=f"{format_money(settings.get('monthly_cash_bonus', 10000))}",
            inline=True
        )
        
        embed.set_footer(text="관리자만 사용 가능한 통합 관리 시스템")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="리더보드설정", description="리더보드 및 출석 설정을 확인하고 수정합니다 (관리자 전용)")
    @app_commands.describe(
        설정="변경할 설정 항목",
        값="새로운 값"
    )
    @app_commands.choices(설정=[
        app_commands.Choice(name="💰 출석 현금 보상", value="attendance_cash"),
        app_commands.Choice(name="✨ 출석 XP 보상", value="attendance_xp"),
        app_commands.Choice(name="🔥 연속 현금 보너스/일", value="streak_cash_per_day"),
        app_commands.Choice(name="✨ 연속 XP 보너스/일", value="streak_xp_per_day"),
        app_commands.Choice(name="🗓️ 최대 연속 보너스 일수", value="max_streak_bonus_days"),
        app_commands.Choice(name="🎁 7일 현금 보너스", value="weekly_cash_bonus"),
        app_commands.Choice(name="✨ 7일 XP 보너스", value="weekly_xp_bonus"),
        app_commands.Choice(name="🏆 30일 현금 보너스", value="monthly_cash_bonus"),
        app_commands.Choice(name="⭐ 30일 XP 보너스", value="monthly_xp_bonus")
    ])
    async def leaderboard_settings(self, interaction: discord.Interaction, 설정: app_commands.Choice[str] = None, 값: int = None):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", ephemeral=True
            )
        
        SETTING_NAMES_KO = {
                            "attendance_cash": "출석 현금 보상",
                            "attendance_xp": "출석 XP 보상",
                            "weekly_cash_bonus": "7일 현금 보너스",
                            "weekly_xp_bonus": "7일 XP 보너스",
                            "monthly_cash_bonus": "30일 현금 보너스",
                            "monthly_xp_bonus": "30일 XP 보너스",
                            "exchange_fee_percent": "환전 수수료",
                            "daily_exchange_limit": "일일 환전 한도"
                            }
        settings = load_settings()
        
        # 설정 확인만 하는 경우
        if 설정 is None or 값 is None:
            embed = discord.Embed(
                title="⚙️ 리더보드 및 출석 설정",
                description="현재 설정값들을 확인하고 수정할 수 있습니다.",
                color=discord.Color.blue()
            )
            
            for key, value in settings.items():
                if key in ["exchange_fee_percent", "daily_exchange_limit"]:
                    continue

                if key in DEFAULT_SETTINGS:
                    if "cash" in key or "bonus" in key:
                        formatted_value = format_money(value)
                    elif "xp" in key:
                        formatted_value = format_xp(value)
                    elif "percent" in key:
                        formatted_value = f"{value}%"
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
        if setting_key not in DEFAULT_SETTINGS:
            return await interaction.response.send_message("❌ 유효하지 않은 설정 항목입니다.", ephemeral=True)
        
        # 값 유효성 검사
        if 값 < 0:
            return await interaction.response.send_message("❌ 설정값은 0 이상이어야 합니다.", ephemeral=True)
        
        # exchange_fee_percent 검사 제거
        # if setting_key == "exchange_fee_percent" and 값 > 50:
        #     return await interaction.response.send_message("❌ 환전 수수료는 50%를 초과할 수 없습니다.", ephemeral=True)
        
        # 설정 업데이트
        old_value = settings.get(setting_key, 0)
        settings[setting_key] = 값
        
        if save_settings(settings):
            # 설정 업데이트 완료
            self.settings = settings
            
            embed = discord.Embed(
                title="✅ 설정 변경 완료",
                color=discord.Color.green()
            )
            
            embed.add_field(name="설정 항목", value=설정.name, inline=True)
            embed.add_field(name="이전 값", value=str(old_value), inline=True)
            embed.add_field(name="새 값", value=str(값), inline=True)
            
            embed.set_footer(text=f"변경자: {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ 설정 저장에 실패했습니다.", ephemeral=True)

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(IntegratedLeaderboardCog(bot))
    print("✅ 통합 리더보드 시스템 로드 완료 (중복 명령어 해결)")