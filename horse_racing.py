#horse_racing.py - [게임] 경마
from __future__ import annotations
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import List, Optional

# 안전한 point_manager import
try:
    import point_manager as pm_module
    point_manager = pm_module
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    print("⚠️ point_manager가 없어 포인트 기능이 비활성화됩니다.")
    
    # point_manager 모의 함수들
    class MockPointManager:
        @staticmethod
        async def is_registered(bot, guild_id, user_id):
            return True
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount):
            pass
        @staticmethod
        async def get_point(bot, guild_id, user_id):
            return 10000
    
    point_manager = MockPointManager()

# 경마 트랙 설정
TRACK_LENGTH = 20  # 트랙 길이
FINISH_LINE = TRACK_LENGTH - 1  # 결승선
HORSE_EMOJI = "🐎"
TRACK_EMOJI = "."  # 트랙 표시
FINISH_EMOJI = "🏁"
SIGNUP_TIME = 120  # 신청 시간 2분 (초)

class HorseRacing:
    def __init__(self, horses: List[str]):
        self.horses = horses
        self.positions = [0] * len(horses)  # 각 말의 현재 위치
        self.finished_horses = []  # 완주한 말들의 순서
        self.is_racing = False
        
    def move_horses(self):
        """말들을 랜덤하게 이동시킴"""
        for i, horse in enumerate(self.horses):
            if self.positions[i] < FINISH_LINE:
                # 각 말이 0~2칸 랜덤하게 이동
                move = random.randint(0, 2)
                self.positions[i] = min(self.positions[i] + move, FINISH_LINE)
                
                # 결승선에 도착한 말 체크
                if self.positions[i] >= FINISH_LINE and horse not in self.finished_horses:
                    self.finished_horses.append(horse)
    
    def generate_track_display(self):
        """현재 경마 상황을 시각적으로 표시 (오른쪽에서 왼쪽으로)"""
        display_lines = []
        
        for i, horse in enumerate(self.horses):
            # 트랙 생성
            track = [TRACK_EMOJI] * TRACK_LENGTH
            
            # 말의 실제 위치를 오른쪽부터 계산 (오른쪽에서 왼쪽으로 이동)
            display_position = TRACK_LENGTH - 1 - self.positions[i]
            
            # 말의 위치에 말 이모지 배치
            if self.positions[i] < TRACK_LENGTH and display_position >= 0:
                track[display_position] = HORSE_EMOJI
            
            # 결승선 표시 (맨 왼쪽)
            if self.positions[i] >= FINISH_LINE:
                track[0] = HORSE_EMOJI  # 결승선 도착 시 맨 왼쪽에 말 표시
            else:
                track[0] = FINISH_EMOJI  # 결승선 표시
            
            # 라인 구성: |트랙|     유저명
            track_str = "".join(track)
            line = f"|{track_str}|     {horse}"
            display_lines.append(line)
        
        return "\n".join(display_lines)
    
    def generate_simple_track_display(self):
        """간단한 트랙 표시 (최종 결과용, 오른쪽에서 왼쪽으로)"""
        display_lines = []
        
        for i, horse in enumerate(self.horses):
            # 트랙 생성 (공백으로)
            track = [" "] * TRACK_LENGTH
            
            # 말의 실제 위치를 오른쪽부터 계산
            display_position = TRACK_LENGTH - 1 - self.positions[i]
            
            # 말의 위치에 말 이모지 배치
            if self.positions[i] < TRACK_LENGTH and display_position >= 0:
                track[display_position] = HORSE_EMOJI
            
            # 결승선 도착한 말은 맨 왼쪽에 표시
            if self.positions[i] >= FINISH_LINE:
                track[0] = HORSE_EMOJI
            
            # 트랙 문자열 생성
            track_str = "".join(track)
            line = f"|{track_str}|     {horse}"
            display_lines.append(line)
        
        return "\n".join(display_lines)
    
    def is_race_finished(self):
        """경주가 끝났는지 확인"""
        return len(self.finished_horses) >= len(self.horses)
    
    def get_results(self):
        """최종 결과 반환"""
        results = []
        for i, horse in enumerate(self.finished_horses):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"{i+1}등"
            results.append(f"{medal} {horse}")
        return results

class ManualSignupView(discord.ui.View):
    def __init__(self, bot: commands.Bot, max_participants: int, organizer: discord.User):
        super().__init__(timeout=SIGNUP_TIME + 10)
        self.bot = bot
        self.max_participants = max_participants
        self.organizer = organizer
        self.participants = []
        self.message = None
        self.signup_ended = False
        
    @discord.ui.button(label="🏇 참가 신청", style=discord.ButtonStyle.primary)
    async def join_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.signup_ended:
            return await interaction.response.send_message("❌ 신청 시간이 종료되었습니다.", ephemeral=True)
        
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        user_name = interaction.user.display_name
        
        # 등록된 사용자인지 확인 (통일된 확인 방식)
        if not await point_manager.is_registered(self.bot, guild_id, user_id):
            return await interaction.response.send_message(
                "❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!", 
                ephemeral=True
            )
        
        # 이미 참가한 사용자 체크
        if any(p["id"] == interaction.user.id for p in self.participants):
            return await interaction.response.send_message("❌ 이미 참가 신청을 하셨습니다.", ephemeral=True)
        
        # 참가자 추가 (시간 기록 포함)
        import time
        self.participants.append({
            "id": interaction.user.id, 
            "name": user_name, 
            "joined_at": time.time()
        })
        
        # 최대 인원 초과 시 가장 늦게 신청한 사람 제거
        if len(self.participants) > self.max_participants:
            # 가장 늦게 신청한 사람 찾기 (마지막에 추가된 사람)
            removed_participant = self.participants.pop()  # 방금 추가된 사람을 제거
            
            await interaction.response.send_message(
                f"❌ 참가 인원이 가득 차서 신청이 취소되었습니다. ({self.max_participants}명 마감)\n" 
                f"현재 참가자: {', '.join([p['name'] for p in self.participants])}", 
                ephemeral=True
            )
            
            # 임베드 업데이트 (제거된 사람 제외)
            await self.update_signup_embed()
            return
        
        await interaction.response.send_message(
            f"✅ {user_name}님이 경마에 참가하셨습니다! ({len(self.participants)}/{self.max_participants})", 
            ephemeral=True
        )
        
        # 임베드 업데이트
        await self.update_signup_embed()
        
        # 인원이 정확히 가득 찼으면 즉시 시작
        if len(self.participants) == self.max_participants:
            await self.start_race_early()
    
    @discord.ui.button(label="❌ 참가 취소", style=discord.ButtonStyle.secondary)
    async def leave_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.signup_ended:
            return await interaction.response.send_message("❌ 신청 시간이 종료되었습니다.", ephemeral=True)
        
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        
        # 참가자 목록에서 제거
        self.participants = [p for p in self.participants if p["id"] != user_id]
        
        await interaction.response.send_message(f"✅ {user_name}님이 경마 참가를 취소하셨습니다.", ephemeral=True)
        
        # 임베드 업데이트
        await self.update_signup_embed()
    
    async def update_signup_embed(self):
        """신청 현황 업데이트"""
        try:
            embed = discord.Embed(
                title="🐎 경마 참가자 모집 중",
                description="⚠️ **명단에 등록된 자만 참가 가능합니다!**\n아래 버튼을 눌러 경마에 참가하세요!",
                color=discord.Color.blue()
            )
            
            embed.add_field(name="👥 모집 인원", value=f"{self.max_participants}명", inline=True)
            embed.add_field(name="✅ 현재 참가자", value=f"{len(self.participants)}명", inline=True)
            
            # 인원이 가득 찼는지 확인
            if len(self.participants) >= self.max_participants:
                embed.add_field(name="🔥 상태", value="**인원 마감!**", inline=True)
                embed.color = discord.Color.green()
            else:
                embed.add_field(name="⏰ 상태", value="모집 진행 중...", inline=True)
            
            if self.participants:
                participants_text = "\n".join([f"{i+1}. {p['name']}" for i, p in enumerate(self.participants)])
                embed.add_field(name="🏇 참가자 목록", value=participants_text, inline=False)
            else:
                embed.add_field(name="🏇 참가자 목록", value="아직 참가자가 없습니다.", inline=False)
            
            # 인원이 가득 찼을 때 추가 메시지
            if len(self.participants) >= self.max_participants:
                embed.add_field(name="📢 안내", value="인원이 가득 차서 곧 경주가 시작됩니다!", inline=False)
            
            embed.set_footer(text=f"주최자: {self.organizer.display_name} | 2분 후 자동 시작 또는 인원 충족 시 즉시 시작")
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"임베드 업데이트 오류: {e}")
    
    async def start_race_early(self):
        """인원이 가득 찼을 때 즉시 경주 시작"""
        if self.signup_ended:
            return
            
        self.signup_ended = True
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="🎉 인원 모집 완료!",
            description="참가 인원이 가득 차서 경주가 곧 시작됩니다!",
            color=discord.Color.green()
        )
        
        participants_text = "\n".join([f"{i+1}. {p['name']}" for i, p in enumerate(self.participants)])
        embed.add_field(name="🏇 최종 참가자", value=participants_text, inline=False)
        
        try:
            await self.message.edit(embed=embed, view=self)
            
            # 3초 후 경주 시작
            await asyncio.sleep(3)
            await self.start_actual_race()
        except Exception as e:
            print(f"조기 시작 오류: {e}")
    
    async def start_actual_race(self):
        """실제 경주 시작"""
        if len(self.participants) < 2:
            embed = discord.Embed(
                title="❌ 경주 취소",
                description="참가자가 2명 미만이라 경주가 취소되었습니다.",
                color=discord.Color.red()
            )
            try:
                await self.message.edit(embed=embed, view=None)
            except:
                pass
            return
        
        # 참가자 이름 목록 생성
        horse_names = [p["name"] for p in self.participants]
        
        # 자동 경주 뷰 생성
        view = AutoHorseRacingView(horse_names, self.organizer)
        view.message = self.message
        
        # 경주 시작 임베드
        embed = discord.Embed(
            title="🏁 경마 경주 시작!",
            description="경주가 곧 시작됩니다!",
            color=discord.Color.gold()
        )
        
        participants_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(horse_names)])
        embed.add_field(name="🏇 참가자", value=participants_text, inline=False)
        embed.add_field(name="🏁 트랙 길이", value=f"{TRACK_LENGTH}칸", inline=True)
        embed.add_field(name="👥 참가자 수", value=f"{len(horse_names)}명", inline=True)
        
        # 초기 트랙 표시
        racing = HorseRacing(horse_names)
        track_display = racing.generate_simple_track_display()
        embed.add_field(name="🏁 경주 트랙", value=f"```\n{track_display}\n```", inline=False)
        
        try:
            await self.message.edit(embed=embed, view=view)
            
            # 자동으로 경주 시작
            await view.auto_start_race()
        except Exception as e:
            print(f"경주 시작 오류: {e}")
    
    async def on_timeout(self):
        """3분 후 자동 시작"""
        if not self.signup_ended:
            self.signup_ended = True
            await self.start_actual_race()

class AutoHorseRacingView(discord.ui.View):
    def __init__(self, horses: List[str], user: discord.User):
        super().__init__(timeout=300)
        self.racing = HorseRacing(horses)
        self.user = user
        self.message = None
        self.race_started = False
    
    async def auto_start_race(self):
        """자동으로 경주 시작"""
        try:
            # ... (생략: 카운트다운 부분)
            # 카운트다운은 1초 유지
            for count in range(3, 0, -1):
                content = f"🚨 **{count}초 후 시작!**\n```\n{self.racing.generate_track_display()}\n```"
                await self.message.edit(content=content, view=self)
                await asyncio.sleep(1) # <-- 이 부분은 1초 유지

            # 경주 시작 알림
            content = f"🏁 **경주 시작!**\n```\n{self.racing.generate_track_display()}\n```"
            await self.message.edit(content=content, view=self)
            await asyncio.sleep(1) # <-- 이 부분은 1초 유지

            # 경주 진행
            race_turn = 1
            while not self.racing.is_race_finished():
                self.racing.move_horses() 
            
                content = f"🏁 **경주 진행 중... (턴 {race_turn})**\n"
                content += f"```\n{self.racing.generate_track_display()}\n```"
                
                if self.racing.finished_horses:
                    current_finishers = len(self.racing.finished_horses)
                    if current_finishers == 1:
                        content += f"\n🎉 **{self.racing.finished_horses[0]}** 1위로 결승선 통과!"
                    elif current_finishers <= 3:
                        content += f"\n🏆 현재 {current_finishers}마리가 결승선 통과!"
            
                try:
                    await self.message.edit(content=content, view=self)
                except:
                    break # 💥 [필수 수정] pass에서 break로 변경하여 무한 루프 방지!
            
                await asyncio.sleep(0.5) # ⏱️ [추천] 1.2초는 너무 답답하므로 0.5초로 밸런스 조정
                race_turn += 1
            
                if race_turn > 50:
                    break
        
            # 최종 결과 표시
            await self.show_final_results()
        
        except Exception as e:
            print(f"자동 경마 게임 오류: {e}")
    
    async def show_final_results(self):
        """최종 결과 표시"""
        try:
            results = self.racing.get_results()
            
            embed = discord.Embed(
                title="🏆 경마 최종 결과",
                color=discord.Color.gold()
            )
            
            # 최종 트랙 상태 (간단한 형태로)
            embed.add_field(
                name="🏁 최종 트랙",
                value=f"```\n{self.racing.generate_simple_track_display()}\n```",
                inline=False
            )
            
            # 순위 결과
            if results:
                ranking_text = "\n".join(results)
                embed.add_field(
                    name="🥇 최종 순위",
                    value=ranking_text,
                    inline=False
                )
            
            embed.add_field(
                name="📊 경주 정보",
                value=f"참가 말: {len(self.racing.horses)}마리\n경주 거리: {TRACK_LENGTH}칸",
                inline=True
            )
            
            embed.set_footer(text=f"경주 주최자: {self.user.display_name}")
            
            if self.message:
                await self.message.edit(embed=embed, view=None)
                
        except Exception as e:
            print(f"경마 결과 표시 오류: {e}")

class HorseRacingView(discord.ui.View):
    def __init__(self, horses: List[str], user: discord.User):
        super().__init__(timeout=300)
        self.racing = HorseRacing(horses)
        self.user = user  # 주최자
        self.message = None
        self.race_started = False

    # 1. 공통 체크 로직 (View의 예약된 메서드 활용)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 경주 시작은 주최자만 가능합니다!", ephemeral=True)
            return False
        return True

    # 2. 실제 버튼 정의 및 콜백 연결
    @discord.ui.button(label="🏇 경주 시작", style=discord.ButtonStyle.success)
    async def start_race_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 기존 start_race 메서드의 로직을 여기로 옮기거나 호출합니다.
        await self.process_start_race(interaction, button)

    async def process_start_race(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 주최자 확인은 interaction_check에서 이미 수행됨
            if self.race_started:
                return await interaction.response.send_message("⚠️ 이미 경주가 시작되었습니다.", ephemeral=True)
            
            self.race_started = True
            self.racing.is_racing = True
            
            # 버튼 비활성화
            button.disabled = True
            button.label = "경주 진행 중..."
            button.style = discord.ButtonStyle.secondary
            
            await interaction.response.edit_message(
                content="🏁 **경주 시작!**\n말들이 출발선에서 준비 중입니다...",
                view=self
            )
            
            self.message = await interaction.original_response()
            
            for count in range(3, 0, -1):
                content = f"🚨 **{count}초 후 시작!**\n```\n{self.racing.generate_track_display()}\n```"
                await self.message.edit(content=content)
                await asyncio.sleep(1)
            
            # 경주 시작 알림
            content = f"🏁 **경주 시작!**\n```\n{self.racing.generate_track_display()}\n```"
            await self.message.edit(content=content)
            await asyncio.sleep(1) # <-- 이 부분은 1초 유지
            
            # 경주 진행
            race_turn = 1
            while not self.racing.is_race_finished():
                self.racing.move_horses() 
            
                content = f"🏁 **경주 진행 중... (턴 {race_turn})**\n"
                content += f"```\n{self.racing.generate_track_display()}\n```"
                
                if self.racing.finished_horses:
                    current_finishers = len(self.racing.finished_horses)
                    if current_finishers == 1:
                        content += f"\n🎉 **{self.racing.finished_horses[0]}** 1위로 결승선 통과!"
                    elif current_finishers <= 3:
                        content += f"\n🏆 현재 {current_finishers}마리가 결승선 통과!"
            
                try:
                    await self.message.edit(content=content, view=self)
                except:
                    break # 💥 [필수 수정] pass에서 break로 변경하여 무한 루프 방지!
            
                await asyncio.sleep(0.5) # ⏱️ [추천] 1.2초는 너무 답답하므로 0.5초로 밸런스 조정
                race_turn += 1
            
                if race_turn > 50:
                    break 
                
                # 무한루프 방지 (최대 50턴)
                if race_turn > 50:
                    break
            
            # 최종 결과 표시
            await self.show_final_results()
            
        except Exception as e:
            print(f"경마 게임 오류: {e}")
            try:
                await interaction.followup.send("❌ 경주 진행 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass
    
    async def show_final_results(self):
        """최종 결과 표시"""
        try:
            results = self.racing.get_results()
            
            embed = discord.Embed(
                title="🏆 경마 최종 결과",
                color=discord.Color.gold()
            )
            
            # 최종 트랙 상태 (간단한 형태로)
            embed.add_field(
                name="🏁 최종 트랙",
                value=f"```\n{self.racing.generate_simple_track_display()}\n```",
                inline=False
            )
            
            # 순위 결과
            if results:
                ranking_text = "\n".join(results)
                embed.add_field(
                    name="🥇 최종 순위",
                    value=ranking_text,
                    inline=False
                )
            
            embed.add_field(
                name="📊 경주 정보",
                value=f"참가 말: {len(self.racing.horses)}마리\n경주 거리: {TRACK_LENGTH}칸",
                inline=True
            )
            
            embed.set_footer(text=f"경주 주최자: {self.user.display_name}")
            
            # 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True
                item.label = "경주 완료"
                item.style = discord.ButtonStyle.secondary
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
                
        except Exception as e:
            print(f"경마 결과 표시 오류: {e}")
    
    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary
            
            if self.message and not self.race_started:
                embed = discord.Embed(
                    title="⏰ 경마 게임 - 시간 만료",
                    description="경주가 시작되지 않고 시간이 초과되었습니다.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"경마 타임아웃 처리 오류: {e}")

class HorseRacingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="경마", description="[관리자 전용] 경마 게임을 생성합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        모드="경마 모드를 선택하세요",
        인원="수동 모드: 최대 참가자 수 / 자동 모드: 참가자 이름 (쉼표로 구분)"
    )
    @app_commands.choices(모드=[
        app_commands.Choice(name="수동 (참가자 모집)", value="수동"),
        app_commands.Choice(name="자동 (즉시 시작)", value="자동")
    ])
    async def horse_racing(self, interaction: discord.Interaction, 모드: str, 인원: str):
        try:
            if 모드 == "수동":
                # 수동 모드: 참가자 모집
                try:
                    max_participants = int(인원)
                    if max_participants < 2:
                        return await interaction.response.send_message("❌ 최소 2명 이상의 참가자가 필요합니다.", ephemeral=True)
                    if max_participants > 10:
                        return await interaction.response.send_message("❌ 최대 10명까지만 참가할 수 있습니다.", ephemeral=True)
                except ValueError:
                    return await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요. 예: `/경마 수동 4`", ephemeral=True)
                
                # 참가자 모집 뷰 생성
                view = ManualSignupView(self.bot, max_participants, interaction.user)
                
                embed = discord.Embed(
                    title="🐎 경마 참가자 모집",
                    description="⚠️ **명단에 등록된 자만 참가 가능합니다!**\n아래 버튼을 눌러 경마에 참가하세요!",
                    color=discord.Color.blue()
                )
                
                embed.add_field(name="👥 모집 인원", value=f"{max_participants}명", inline=True)
                embed.add_field(name="✅ 현재 참가자", value="0명", inline=True)
                embed.add_field(name="⏰ 모집 시간", value="3분", inline=True)
                embed.add_field(name="🏇 참가자 목록", value="아직 참가자가 없습니다.", inline=False)
                embed.add_field(name="📝 참가 조건", value="명단에 등록된 자만 참가 가능", inline=False)
                
                embed.set_footer(text=f"주최자: {interaction.user.display_name} | 3분 후 자동 시작 또는 인원 충족 시 즉시 시작")
                
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()
                
            else:
                # 자동 모드: 즉시 시작 (관리자가 직접 입력한 이름으로)
                horses = [name.strip() for name in 인원.split(",") if name.strip()]
                
                # 참가자 수 검증
                if len(horses) < 2:
                    return await interaction.response.send_message("❌ 최소 2명 이상의 참가자가 필요합니다.", ephemeral=True)
                
                if len(horses) > 8:
                    return await interaction.response.send_message("❌ 최대 8명까지만 참가할 수 있습니다.", ephemeral=True)
                
                # 중복 이름 확인
                if len(horses) != len(set(horses)):
                    return await interaction.response.send_message("❌ 중복된 이름이 있습니다. 각 참가자는 고유한 이름이어야 합니다.", ephemeral=True)
                
                # 이름 길이 검증
                for horse in horses:
                    if len(horse) > 12:
                        return await interaction.response.send_message(f"❌ '{horse}' 이름이 너무 깁니다. 12자 이하로 입력해주세요.", ephemeral=True)
                    if len(horse) == 0:
                        return await interaction.response.send_message("❌ 빈 이름은 허용되지 않습니다.", ephemeral=True)
                
                # 게임 시작 임베드
                embed = discord.Embed(
                    title="🐎 경마 게임 준비 (자동 모드)",
                    description="경주가 곧 시작됩니다!",
                    color=discord.Color.blue()
                )
                
                # 참가자 목록
                participants_text = "\n".join([f"{i+1}. {horse}" for i, horse in enumerate(horses)])
                embed.add_field(
                    name="🏇 참가자 목록",
                    value=participants_text,
                    inline=False
                )
                
                embed.add_field(name="🏁 트랙 길이", value=f"{TRACK_LENGTH}칸", inline=True)
                embed.add_field(name="👥 참가자 수", value=f"{len(horses)}명", inline=True)
                embed.add_field(name="⏱️ 제한 시간", value="5분", inline=True)
                
                embed.set_footer(text=f"주최자: {interaction.user.display_name} | 경주 시작 버튼을 눌러주세요!")
                
                # 초기 트랙 표시
                racing = HorseRacing(horses)
                track_display = racing.generate_simple_track_display()
                embed.add_field(
                    name="🏁 경주 트랙",
                    value=f"```\n{track_display}\n```",
                    inline=False
                )
                
                view = HorseRacingView(horses, interaction.user)
                
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()
            
        except Exception as e:
            print(f"경마 명령어 오류: {e}")
            try:
                await interaction.response.send_message("❌ 경마 게임 생성 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(HorseRacingCog(bot))