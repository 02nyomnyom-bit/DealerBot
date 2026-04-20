# yabawi_game.py - 야바위 게임
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
import random
import asyncio

# 설정 상수
SUCCESS_RATES = [0.6, 0.55, 0.5, 0.45, 0.4] # 각 라운드 별 성공률
MAX_CHALLENGES = 5                          # 최대 도전 가능 횟수 (5연승 시 자동 종료)
WINNER_RETENTION = 0.8                      # 승리 시 수수료 (20%)
active_games_by_user = set()                # 중복 게임 방지를 위한 현재 진행 중인 유저 목록

# 통계 시스템 연동 (모듈이 없을 경우를 대비한 예외 처리)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False

# 포인트 매니저 연동 (잔액 확인 및 지급/차감 담당)
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False

    # 포인트 매니저 부재 시 작동할 모의 클래스
    class MockPointManager:
        @staticmethod
        async def is_registered(bot, guild_id, user_id): return True
        @staticmethod
        async def get_point(bot, guild_id, user_id): return 10000
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount): pass
    point_manager = MockPointManager()

# 게임 결과를 통계 시스템에 기록하는 함수
def record_yabawi_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "yabawi", bet, payout, is_win)
        except: pass

class YabawiGameView(View):
    # 게임 실행자만 버튼을 누를 수 있도록 체크하는 보안 함수
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 이 게임의 명단있는 자만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True
    
    def __init__(self, bot: commands.Bot, user: discord.User, base_bet: int, guild_id: str):
        super().__init__(timeout=120)               # 2분간 입력 없으면 자동 종료
        self.bot = bot
        self.user = user
        self.user_id = str(user.id)
        self.guild_id = guild_id
        self.base_bet = base_bet                    # 초기 배팅 금액
        self.wins = 0                               # 현재 연승 횟수
        self.current_pot = base_bet                 # 현재 쌓인 보상 (승리 시 2배씩 증가)
        self.ended = False                          # 게임 종료 여부
        self.processing = False                     # 중복 클릭 방지용 플래그
        self.initial_bet_deducted = False           # 배팅금 차감 여부
        self.real_position = random.randint(0, 2)   # 공이 숨겨진 실제 위치 (0, 1, 2)

        # 3개의 컵(버튼) 생성
        for i in range(3):
            self.add_item(CupButton("🥤", i))

    async def on_timeout(self):
        """시간 초과 시 처리 (잠수 방지)"""
        if not self.ended:
            self.ended = True
            active_games_by_user.discard(self.user_id)
            
            if self.initial_bet_deducted:
                if self.wins > 0:
                    # 1승 이상이면 현재까지의 보상 지급
                    payout = int(self.current_pot * WINNER_RETENTION)
                    await point_manager.add_point(self.bot, self.guild_id, self.user_id, payout)
                    record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, payout, True)
                    timeout_msg = f"⏰ 시간 초과! 현재까지의 보상 {payout:,}원이 지급되었습니다.\n*10%의 딜러비가 차감된 후 지급됩니다."
                else:
                    # 첫 판에서 잠수 시 원금 환불
                    await point_manager.add_point(self.bot, self.guild_id, self.user_id, self.base_bet)
                    timeout_msg = f"⏰ 시간 초과! 활동이 없어 {self.base_bet:,}원이 환불되었습니다."
            else:
                timeout_msg = "⏰ 시간 초과로 게임이 종료되었습니다."

            try:
                for item in self.children: # 모든 버튼 비활성화
                    item.disabled = True
                await self.message.edit(content=timeout_msg, view=self)
            except: pass

    def reset_for_next(self):
        """다음 라운드를 위해 상태 초기화"""
        self.real_position = random.randint(0, 2)
        self.processing = False

    async def handle_choice(self, interaction: discord.Interaction, chosen_idx: int):
        """확률 판정 후 결과를 시각화하는 로직 (개선 버전)"""
        self.processing = True
        
        # 1. 포인트 차감 로직 (기존과 동일)
        if not self.initial_bet_deducted:
            current_balance = await point_manager.get_point(self.bot, self.guild_id, self.user_id)
            if current_balance < self.base_bet:
                self.processing = False
                active_games_by_user.discard(self.user_id)
                return await interaction.response.send_message("❌ 잔액이 부족합니다!", ephemeral=True)
            
            await point_manager.add_point(self.bot, self.guild_id, self.user_id, -self.base_bet)
            self.initial_bet_deducted = True

            # XP 시스템을 가져와서 실행 (실제 게임 시작 시점에 지급)
            xp_cog = self.bot.get_cog("XPLeaderboardCog")
            if xp_cog:
                await xp_cog.process_command_xp(interaction)

        # 2. 확률 판정 먼저 수행
        current_rate = SUCCESS_RATES[min(self.wins, len(SUCCESS_RATES)-1)]
        is_correct = random.random() < current_rate # 여기서 승패가 먼저 결정됨

        # 3. 판정 결과에 따라 공의 위치(real_position)를 사후 결정
        if is_correct:
            self.real_position = chosen_idx # 맞춘 것으로 판정되면 공을 그 자리에 둠
        else:
            # 틀린 것으로 판정되면, 사용자가 고른 곳이 아닌 다른 곳에 공을 배치
            wrong_positions = [i for i in range(3) if i != chosen_idx]
            self.real_position = random.choice(wrong_positions)
        
        # 4. 결과 시각화 (이미지 버그 해결)
        display_cups = ["⬜", "⬜", "⬜"]

        if is_correct:
            # 맞춘 경우: 선택한 위치에 왕관(또는 보상) 표시
            display_cups[chosen_idx] = "👑" 
        else:
            # 틀린 경우: 실제 공 위치와 내가 틀린 위치를 각각 명확히 표시
            display_cups[self.real_position] = "💰"  # 실제 정답 위치
            display_cups[chosen_idx] = "❌"         # 유저가 선택한 오답 위치

        cups_display = " ".join(display_cups)

        # 5. 후속 처리 (연승 및 보상)
        if is_correct:
            self.wins += 1
            self.current_pot = self.base_bet * (2 ** self.wins)
            
            if self.wins >= MAX_CHALLENGES:
                final_payout = int(self.current_pot * WINNER_RETENTION)
                await point_manager.add_point(self.bot, self.guild_id, self.user_id, final_payout)
                record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, final_payout, True)
                
                self.ended = True
                active_games_by_user.discard(self.user_id)
                
                embed = discord.Embed(title="🏆 전설의 야바위꾼!", description=f"5연승 달성! 보상이 지급됩니다.\n{cups_display}", color=discord.Color.gold())
                embed.add_field(name="💰 최종 수령액", value=f"{final_payout:,}원\n*20%의 딜러비가 차감된 후 지급됩니다.")
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                embed = discord.Embed(title="🎉 성공!", description=f"정답입니다! 현재 {self.wins}연승 중!\n{cups_display}", color=discord.Color.green())
                embed.add_field(name="💰 현재 잠재 보상", value=f"{self.current_pot:,}원")
                
                self.clear_items()
                self.add_item(ContinueButton())
                self.add_item(StopButton())
                self.processing = False
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            self.ended = True
            active_games_by_user.discard(self.user_id)
            record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, 0, False)
            
            embed = discord.Embed(title="💥 꽝!", description=f"틀렸습니다! 공은 다른 곳에 있었네요.\n{cups_display}", color=discord.Color.red())
            await interaction.response.edit_message(embed=embed, view=None)

class CupButton(discord.ui.Button):
    def __init__(self, label: str, index: int):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_choice(interaction, self.index)

class StopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛑 수령하고 중단", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        view: YabawiGameView = self.view
        
        # [수정] 중복 클릭 방지 해제 (필요 시)
        view.processing = False 
        
        final_payout = int(view.current_pot * WINNER_RETENTION)
        await point_manager.add_point(view.bot, view.guild_id, view.user_id, final_payout)
        
        record_yabawi_game(view.user_id, view.user.display_name, view.base_bet, final_payout, True)
        view.ended = True
        active_games_by_user.discard(view.user_id)
        
        embed = discord.Embed(title="💰 게임 종료", description=f"보상을 수령했습니다.", color=discord.Color.blue())
        embed.add_field(name="💵 최종 수령액", value=f"{final_payout:,}원\n*20%의 딜러비가 차감된 후 지급됩니다.")
        await interaction.response.edit_message(embed=embed, view=None)

class ContinueButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚀 다음 단계 도전!", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: YabawiGameView = self.view
        
        # 다음 라운드 진행을 위해 초기화
        view.reset_for_next() 
        # reset_for_next() 함수 안에 이미 self.processing = False가 있으므로 이 함수가 정상적으로 호출되는지 확인하세요.
        
        view.clear_items()
        for i in range(3):
            view.add_item(CupButton("🥤", i))
        
        embed = discord.Embed(title=f"🔥 {view.wins + 1}단계 도전", description="공이 든 컵을 고르세요!", color=discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=view)

class YabawiGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="야바위", description="야바위 게임을 시작합니다.")
    @app_commands.describe(배팅="배팅할 금액을 입력하세요. (100원 ~ 3,000원)")
    async def yabawi_game(self, interaction: discord.Interaction, 배팅: int = 100): # 기본값을 100으로 변경 권장
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'yabawi' 권한이 있는지 체크 (channel_config.py의 value="yabawi"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "yabawi", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        # 게임 시작 등록
        active_games_by_user.add(user_id)

        # 게임 View 인스턴스 생성
        view = YabawiGameView(self.bot, interaction.user, 배팅, str(interaction.guild_id))
        
        # 대기 화면 임베드 생성
        embed = discord.Embed(title="🎩 야바위 준비!", description="컵을 섞고 있습니다...", color=discord.Color.light_grey())
        
        await interaction.response.send_message(embed=embed)
        # 나중에 타임아웃이나 상태 변경 시 메시지를 수정하기 위해 객체 저장
        view.message = await interaction.original_response()
        
        # 1초 대기 후 실제 게임 인터페이스(버튼) 표시
        await asyncio.sleep(1)
        embed.title = "🎩 야바위 게임 시작!"
        embed.description = "공이 든 컵을 고르세요!"
        embed.add_field(name="💰 배팅", value=f"{배팅:,}원")
        
        # 버튼(View)이 포함된 메시지로 업데이트
        await view.message.edit(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(YabawiGameCog(bot))