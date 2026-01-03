from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord import Interaction
import asyncio
from datetime import datetime, timedelta, timezone, date
import random
import os
import json

# database_manager 모듈을 안전하게 불러오는 로직 추가
try:
    from database_manager import get_guild_db_manager, DEFAULT_LEADERBOARD_SETTINGS
    DB_AVAILABLE = True
    print("✅ database_manager 모듈 로드 완료")
except ImportError:
    DB_AVAILABLE = False
    print("❌ database_manager 모듈을 찾을 수 없습니다. 출석체크 기능이 비활성화됩니다.")

class AttendanceMasterCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_available = DB_AVAILABLE # Keep this for initial check

        self.korea_tz = timezone(timedelta(hours=9))
        
        # self.settings는 이제 각 명령어에서 guild_id를 기반으로 로드됩니다.
        # 초기화 시점에는 특정 길드 ID가 없으므로 로드하지 않습니다.
        self.settings = DEFAULT_LEADERBOARD_SETTINGS # 기본값으로 초기화
        
        print("✅ 출석체크 마스터 시스템 v4.2 로드 완료 (리더보드 설정 연동)")

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
        if not self.db_available:
            print("❌ calculate_attendance_streak: 데이터베이스를 사용할 수 없습니다.")
            return 0, True
        try:
            db = get_guild_db_manager(guild_id)
            
            # 👈 추가: KST 날짜 객체를 준비합니다.
            today_kst_date = self.get_korean_date_object()

            # 데이터베이스에서 현재 연속 출석일 가져오기
            # 👇 수정: kst_date 인자 전달
            current_streak = db.get_user_attendance_streak(user_id, today_kst_date) 
            
            # 오늘 출석했는지 확인
            # 👇 수정: kst_date 인자 전달
            today_attended = db.has_attended_today(user_id, today_kst_date)
            
            return current_streak, not today_attended
        
        except Exception as e:
            print(f"연속 출석일 계산 중 오류: {e}")
            return 0, True

    @app_commands.command(name="출석체크", description="하루 한번 출석체크 (현금 + XP 동시 지급)")
    async def attendance_check_v2(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        guild_id = str(interaction.guild.id)

        if not self.db_available:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 불러오는 데 실패하여 출석체크 기능이 비활성화되었습니다. 관리자에게 문의해주세요.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = get_guild_db_manager(guild_id)
        
        # 1. 사용자 등록 여부 확인
        if not db.get_user(user_id):
            embed = discord.Embed(
                title="❌ 미등록 사용자",
                description="먼저 `/등록` 명령어로 플레이어 등록을 해주세요!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        try:
            # 설정 로드 (관리자가 변경했을 수 있으므로)
            settings = db.get_leaderboard_settings()

            # 기본 설정과 관리자 설정을 병합하여 최종 유효 설정 생성
            effective_settings = DEFAULT_LEADERBOARD_SETTINGS.copy()
            effective_settings.update(settings)

            # 2. 연속 출석일 및 오늘 출석 가능 여부 확인
            current_streak, can_attend_today = self.calculate_attendance_streak(guild_id, user_id)
            
            # 3. 이미 출석한 경우 처리
            if not can_attend_today:
                embed = discord.Embed(
                    title="⚠️ 이미 출석완료",
                    description=f"**{username}**님은 오늘 이미 출석체크를 완료했습니다!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="📅 다음 출석 가능 시간", value=self.get_next_attendance_time())
                embed.add_field(name="🔥 현재 연속 출석", value=f"{current_streak}일")
                return await interaction.followup.send(embed=embed)
            
            # 4. 출석 기록 저장
            today_str = self.get_korean_date_string()
            
            # 👈 추가: KST 날짜 객체를 준비합니다.
            today_date = self.get_korean_date_object()
            
            # database_manager의 출석 기록 함수 호출
            # 👇 수정: today_date 인자 전달
            record_result = db.record_attendance(user_id, today_date)

            # 5. 새로운 연속 출석일 계산 (오늘 포함)
            # db.record_attendance 결과에서 새로운 연속 출석일을 가져오는 것이 더 정확합니다.
            # new_streak = current_streak + 1 # 이 로직 대신 아래처럼 수정합니다.
            if not record_result['success']:
                # 이미 출석한 경우, record_attendance 함수는 여기서 이미 처리되었어야 합니다.
                # 그러나 혹시 모를 에러 방지를 위해 record_attendance 함수의 리턴 값을 사용합니다.
                new_streak = record_result.get('streak', current_streak)
            else:
                new_streak = record_result['streak']
            
            # 6. 보상 계산 및 지급 (연동된 설정 사용)
            base_cash_reward = effective_settings['attendance_cash']
            base_xp_reward = effective_settings['attendance_xp']

            # ✅ 리더보드 시스템의 설정값을 사용하여 연속 출석 보너스 계산
            bonus_cash_per_day = effective_settings['streak_cash_per_day']
            bonus_xp_per_day = effective_settings['streak_xp_per_day']
            max_bonus_days = effective_settings['max_streak_bonus_days']
            
            # 연속 출석 보너스 (최대 일수까지 증가)
            bonus_days = min(new_streak - 1, max_bonus_days)
            bonus_cash = bonus_days * bonus_cash_per_day
            bonus_xp = bonus_days * bonus_xp_per_day

            # --- 👇 7일/30일 보너스 로직 추가 시작 👇 ---
            
            special_bonus_cash = 0
            special_bonus_xp = 0
            special_message = ""

            # 7일(주간) 특별 보너스 확인 및 추가
            if new_streak % 7 == 0:
                weekly_cash = effective_settings['weekly_cash_bonus']
                weekly_xp = effective_settings['weekly_xp_bonus']
                special_bonus_cash += weekly_cash
                special_bonus_xp += weekly_xp
                special_message = f"🎁 7일 연속 보너스 지급! ({weekly_cash:,}원, {weekly_xp} XP)"

            # 30일(월간) 특별 보너스 확인 및 추가
            if new_streak % 30 == 0:
                monthly_cash = effective_settings['monthly_cash_bonus']
                monthly_xp = effective_settings['monthly_xp_bonus']
                special_bonus_cash += monthly_cash
                special_bonus_xp += monthly_xp
                # 7일 보너스와 동시에 지급될 경우 메시지를 업데이트 (30일이 7일의 배수이므로)
                if new_streak == 30:
                    special_message = f"🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
                elif new_streak > 30 and new_streak % 7 == 0:
                     special_message += f"\n🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
                else:
                    special_message = f"🏆 30일 연속 보너스 지급! ({monthly_cash:,}원, {monthly_xp} XP)"
            
            # --- 👆 7일/30일 보너스 로직 추가 끝 👆 ---

            # 최종 보상 합산
            total_cash = base_cash_reward + bonus_cash + special_bonus_cash
            total_xp = base_xp_reward + bonus_xp + special_bonus_xp
            
            # 현금 및 XP 지급
            db.add_user_cash(user_id, total_cash)
            # 현금 지급 기록에 어떤 보상을 받았는지 명시
            transaction_detail = f"{new_streak}일 연속 출석 보상"
            if special_message:
                 transaction_detail += f" (+ 특별 보너스)"
            
            db.add_transaction(user_id, "출석체크", total_cash, transaction_detail)
            db.add_user_xp(user_id, total_xp)
            
            # 7. 성공 메시지 전송
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
            
            # --- 👇 특별 보너스 메시지 추가 👇 ---
            if special_message:
                embed.add_field(name="🎉 특별 보상 알림", value=special_message, inline=False)
            # --- 👆 특별 보너스 메시지 추가 👆 ---

            embed.add_field(name="💎 총 획득", value=f"**{total_cash:,}원**과 **{total_xp} XP**를 획득했습니다!", inline=False)
            
            embed.set_footer(text=f"출석 시간: {today_str}")
            
            await interaction.followup.send(embed=embed)
                
        except Exception as e:
            print(f"출석체크 처리 중 심각한 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            
            embed = discord.Embed(
                title="❌ 출석체크 오류",
                description="출석체크 처리 중 오류가 발생했습니다. 관리자에게 문의해주세요.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="출석현황", description="나의 현재 출석 현황을 확인합니다.")
    async def attendance_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)

        if not self.db_available:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 불러오는 데 실패하여 출석체크 기능이 비활성화되었습니다. 관리자에게 문의해주세요.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = get_guild_db_manager(guild_id)
        
        if not db.get_user(user_id):
            embed = discord.Embed(
                title="❌ 미등록 사용자",
                description="먼저 `/등록` 명령어로 플레이어 등록을 해주세요!",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)
        
        # 개선된 연속 출석일 계산 사용
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
        
        # 다음 목표 안내
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

        if not self.db_available:
            embed = discord.Embed(
                title="❌ 시스템 오류",
                description="데이터베이스 시스템을 사용할 수 없습니다.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=embed)

        db = get_guild_db_manager(guild_id)
        
        try:
            # 👈 추가: KST 날짜 객체를 준비합니다.
            kst_date = self.get_korean_date_object()

            # 서버의 모든 사용자 출석 현황 조회
            # 👇 수정: kst_date 인자 전달
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