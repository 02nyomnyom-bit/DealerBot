# attendance_master.py
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Any

class AttendanceMasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_cog: Optional[Any] = None

        self.korea_tz = timezone(timedelta(hours=9))
        self.settings = {} # 임시 빈 딕셔너리로 초기화
    
    async def cog_load(self):
        """Cog가 로드된 후 DatabaseManager Cog를 가져옵니다."""
        self.db_cog = self.bot.get_cog("DatabaseManager")
        if not self.db_cog:
            print("❌ DatabaseManager Cog를 찾을 수 없습니다. 출석체크 기능이 제한됩니다.")
        else:
            print("✅ DatabaseManager Cog 연결 성공.")
            try:
                pass 
            except AttributeError:
                print("⚠️ DEFAULT_LEADERBOARD_SETTINGS 속성을 찾을 수 없어 기본 설정을 사용합니다.")

    def get_korean_date_string(self) -> str:
        """한국 시간 기준 날짜 문자열 반환 (YYYY-MM-DD)"""
        return datetime.now(self.korea_tz).strftime('%Y-%m-%d')
    
    def get_korean_date_object(self) -> date:
        """한국 시간 기준 날짜 객체 반환"""
        return datetime.now(self.korea_tz).date()
    
    def get_next_attendance_time(self) -> str:
        """다음 출석 가능 시간 반환"""
        now = datetime.now(self.korea_tz)
        # 다음 날 자정
        next_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        time_diff = next_day - now
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"{hours}시간 {minutes}분 후"

    def format_xp(self, xp: int) -> str:
        return f"{xp:,} XP"
    
    def calculate_attendance_streak(self, guild_id: str, user_id: str) -> tuple[int, bool]:
        if not self.db_cog:
            print("🚫 calculate_attendance_streak: 데이터베이스를 사용할 수 없습니다.")
            return 0, True
        try:
            db = self.db_cog.get_manager(guild_id)
            today_kst_date = self.get_korean_date_object()
            current_streak = db.get_user_attendance_streak(user_id, today_kst_date) 
            today_attended = db.has_attended_today(user_id, today_kst_date)
            return current_streak, not today_attended
        
        except Exception as e:
            print(f"연속 출석일 계산 중 오류: {e}")
            return 0, True

    @app_commands.command(name="출석체크", description="일일 현금과 경험치 지급")
    async def attendance_check_v2(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild.id)

        if not self.db_cog:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 불러오는 데 실패했습니다.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = self.db_cog.get_manager(guild_id)
        
        if not db.get_user(user_id):
            embed = discord.Embed(
                title="❌ 미등록 사용자",
                description="먼저 `/등록` 명령어로 플레이어 등록을 해주세요!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            settings = db.get_leaderboard_settings()
            default_settings = getattr(self.db_cog, 'DEFAULT_LEADERBOARD_SETTINGS', {
                'attendance_cash': 1000,
                'attendance_xp': 100,
                'streak_cash_per_day': 100,
                'streak_xp_per_day': 10,
                'max_streak_bonus_days': 7,
                'weekly_cash_bonus': 5000,
                'weekly_xp_bonus': 500,
                'monthly_cash_bonus': 20000,
                'monthly_xp_bonus': 2000,
                'exchange_fee_percent': 5,
                'daily_exchange_limit': 10
            })
            effective_settings = default_settings.copy()
            effective_settings.update(settings)

            current_streak, can_attend_today = self.calculate_attendance_streak(guild_id, user_id)
            
            if not can_attend_today:
                embed = discord.Embed(
                    title="⚠️ 이미 출석완료",
                    description=f"**{username}**님은 오늘 이미 출석체크를 완료했습니다!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="📅 다음 출석 가능 시간", value=self.get_next_attendance_time())
                embed.add_field(name="🔥 현재 연속 출석", value=f"{current_streak}일")
                return await interaction.followup.send(embed=embed)
            
            today_date = self.get_korean_date_object()
            today_str = self.get_korean_date_string()
            record_result = db.record_attendance(user_id, today_date)

            if not record_result['success']:
                new_streak = record_result.get('streak', current_streak)
            else:
                new_streak = record_result['streak']
            
            base_cash_reward = effective_settings['attendance_cash']
            base_xp_reward = effective_settings['attendance_xp']

            bonus_cash_per_day = effective_settings['streak_cash_per_day']
            bonus_xp_per_day = effective_settings['streak_xp_per_day']
            max_bonus_days = effective_settings['max_streak_bonus_days']
            
            bonus_days = min(new_streak - 1, max_bonus_days)
            bonus_cash = bonus_days * bonus_cash_per_day
            bonus_xp = bonus_days * bonus_xp_per_day

            special_bonus_cash = 0
            special_bonus_xp = 0
            special_message = ""

            if new_streak % 7 == 0:
                weekly_cash = effective_settings['weekly_cash_bonus']
                weekly_xp = effective_settings['weekly_xp_bonus']
                special_bonus_cash += weekly_cash
                special_bonus_xp += weekly_xp
                special_message = f"🎁 7일 연속 보너스 지급! ({weekly_cash:,}원, {weekly_xp} XP)"

            if new_streak % 30 == 0:
                monthly_cash = effective_settings['monthly_cash_bonus']
                monthly_xp = effective_settings['monthly_xp_bonus']
                special_bonus_cash += monthly_cash
                special_bonus_xp += monthly_xp
                if new_streak == 30:
                    special_message = f"🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
                elif new_streak > 30 and new_streak % 7 == 0:
                     special_message += f"\n🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
                else:
                    special_message = f"🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
            
            total_cash = base_cash_reward + bonus_cash + special_bonus_cash
            total_xp = base_xp_reward + bonus_xp + special_bonus_xp
            
            db.add_user_cash(user_id, total_cash)
            transaction_detail = f"{new_streak}일 연속 출석 보상"
            if special_message:
                 # F541: 플레이스홀더가 없는 f-string을 일반 문자열로 수정
                 transaction_detail += " (+ 특별 보너스)"
            
            db.add_transaction(user_id, "출석체크", total_cash, transaction_detail)
            db.add_user_xp(user_id, total_xp)
            
            embed = discord.Embed(
                title="✅ 출석체크 완료!",
                description=f"**{username}**님의 출석이 정상적으로 기록되었습니다!",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            embed.add_field(name="🔥 연속 출석", value=f"**{new_streak}일** 달성!", inline=False)
            embed.add_field(name="💰 기본 보상", value=f"{base_cash_reward:,}원 | {base_xp_reward} XP", inline=False)
            
            if bonus_cash > 0:
                embed.add_field(name="🎁 연속 보너스", value=f"+{bonus_cash:,}원 | +{bonus_xp} XP", inline=False)
            
            if special_message:
                embed.add_field(name="🎉 특별 보상 알림", value=special_message, inline=False)

            embed.add_field(name="💎 총 획득", value=f"**{total_cash:,}원**과 **{total_xp} XP**를 획득했습니다!", inline=False)
            
            embed.set_footer(text=f"출석 시간: {today_str}")
            
            await interaction.followup.send(embed=embed)
                
        except Exception as e:
            print(f"❌ 출석체크 처리 중 심각한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send("❌ 출석체크 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="출석현황", description="나의 현재 출석 현황을 확인합니다.")
    async def attendance_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if not self.db_cog:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 불러오는 데 실패하여 출석체크 기능이 비활성화되었습니다. 관리자에게 문의해주세요.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = self.db_cog.get_manager(guild_id)
        
        if not db.get_user(user_id):
            embed = discord.Embed(
                title="❌ 미등록 사용자",
                description="먼저 `/등록` 명령어로 플레이어 등록을 해주세요!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        current_streak, can_attend_today = self.calculate_attendance_streak(guild_id, user_id)
        
        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name}님의 출석 현황",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔥 현재 연속 출석일", value=f"**{current_streak}일**", inline=False)
        
        if can_attend_today:
            embed.add_field(name="⭐ 오늘 출석 상태", value="아직 출석하지 않았습니다", inline=False)
        else:
            embed.add_field(name="✅ 오늘 출석 상태", value="출석 완료!", inline=False)
            
        embed.add_field(name="⏰ 다음 출석까지 남은 시간", value=self.get_next_attendance_time(), inline=False)
        
        next_milestones = [3, 7, 30, 100]
        next_milestone = None
        for milestone in next_milestones:
            if current_streak < milestone:
                next_milestone = milestone
                break
        
        if next_milestone:
            days_to_milestone = next_milestone - current_streak
            embed.add_field(
                name="🎯 다음 목표", 
                value=f"{next_milestone}일 연속 출석까지 **{days_to_milestone}일** 남았습니다!", 
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="출석랭킹", description="서버 내 출석 랭킹을 확인합니다.")
    async def attendance_ranking(self, interaction: discord.Interaction):
        """서버 내 연속 출석일 랭킹 표시"""
        await interaction.response.defer()

        guild_id = str(interaction.guild.id)

        if not self.db_cog:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 사용할 수 없습니다.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = self.db_cog.get_manager(guild_id)
        
        try:
            kst_date = self.get_korean_date_object()
            leaderboard = db.get_attendance_leaderboard(10, kst_date)
            
            if not leaderboard:
                embed = discord.Embed(
                    title="🏆 서버 출석 랭킹",
                    description="아직 출석한 사용자가 없습니다.",
                    color=discord.Color.gold()
                )
                return await interaction.followup.send(embed=embed)
            
            embed = discord.Embed(
                title="🏆 서버 출석 랭킹",
                description="연속 출석일 기준 상위 10명",
                color=discord.Color.gold()
            )
            
            for i, data in enumerate(leaderboard, 1):
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                username = data.get('display_name') or data.get('username') or "Unknown"
                streak = data.get('current_streak', 0)
                embed.add_field(
                    name=f"{medal} {username}",
                    value=f"🔥 {streak}일 연속",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"출석 랭킹 조회 중 오류: {e}")
            embed = discord.Embed(
                title="❌ 오류",
                description="출석 랭킹을 불러오는 중 오류가 발생했습니다.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(AttendanceMasterCog(bot))