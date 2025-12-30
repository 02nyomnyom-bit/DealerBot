# yabawi_game.py - 수정본
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
import random
import asyncio

# 설정 상수
SUCCESS_RATES = [0.6, 0.55, 0.5, 0.45, 0.4] #각 라운드 별 성공률
MAX_CHALLENGES = 5
WINNER_RETENTION = 0.95  # 승리 시 95%만 지급 (5% 수수료)
active_games_by_user = set()

# (기존 통계/포인트 매니저 임포트 로직은 동일하게 유지)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False

try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    class MockPointManager:
        @staticmethod
        async def is_registered(bot, guild_id, user_id): return True
        @staticmethod
        async def get_point(bot, guild_id, user_id): return 10000
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount): pass
    point_manager = MockPointManager()

# ✅ 통계 기록 헬퍼 함수
def record_yabawi_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(user_id=user_id, username=username, game_name="yabawi", is_win=is_win, bet=bet, payout=payout)
        except: pass

class YabawiGameView(View):
    def __init__(self, bot: commands.Bot, user: discord.User, base_bet: int, guild_id: str):
        super().__init__(timeout=120) # 2분 제한
        self.bot = bot
        self.user = user
        self.user_id = str(user.id)
        self.guild_id = guild_id
        self.base_bet = base_bet
        self.wins = 0
        self.current_pot = base_bet
        self.ended = False
        self.processing = False # 중복 클릭 방지 플래그
        self.initial_bet_deducted = False
        self.real_position = random.randint(0, 2)

        for i in range(3):
            self.add_item(CupButton("🥤", i))

    async def on_timeout(self):
        """시간 초과 시 자동 환불 로직"""
        if not self.ended:
            self.ended = True
            active_games_by_user.discard(self.user_id)
            
            # 배팅이 이미 나갔고, 승리가 0회인 경우(첫 판에서 잠수) 환불
            if self.initial_bet_deducted and self.wins == 0:
                await point_manager.add_point(self.bot, self.guild_id, self.user_id, self.base_bet)
                refund_msg = f"⏰ 시간 초과! 입력이 없어 {self.base_bet:,}원이 환불되었습니다."
            else:
                refund_msg = "⏰ 시간 초과로 게임이 종료되었습니다."

            try:
                # 메시지 업데이트 (버튼 비활성화)
                for item in self.children:
                    item.disabled = True
                await self.message.edit(content=refund_msg, view=self)
            except: pass

    def reset_for_next(self):
        self.real_position = random.randint(0, 2)
        self.processing = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 본인의 게임만 참여할 수 있습니다.", ephemeral=True)
            return False
        if self.processing:
            await interaction.response.send_message("⏳ 처리 중입니다. 잠시만 기다려주세요.", ephemeral=True)
            return False
        return True

    async def handle_choice(self, interaction: discord.Interaction, chosen_idx: int):
        self.processing = True
        
        # 첫 배팅 차감
        if not self.initial_bet_deducted:
            current_balance = await point_manager.get_point(self.bot, self.guild_id, self.user_id)
            if current_balance < self.base_bet:
                self.processing = False
                return await interaction.response.send_message("❌ 잔액이 부족합니다!", ephemeral=True)
            
            await point_manager.add_point(self.bot, self.guild_id, self.user_id, -self.base_bet)
            self.initial_bet_deducted = True

        # 승패 판정 (단순화: 위치가 같으면 무조건 성공)
        is_correct = (chosen_idx == self.real_position)
        
        # 이모지 표시 생성
        cups = []
        for i in range(3):
            if i == chosen_idx:
                cups.append("👑" if is_correct else "❌")
            elif i == self.real_position:
                cups.append("💰")
            else:
                cups.append("⬜")
        cups_display = " ".join(cups)

        if is_correct:
            self.wins += 1
            self.current_pot *= 2
            
            if self.wins >= MAX_CHALLENGES:
                # 최대 연승 시 수수료 적용 지급
                final_payout = int(self.current_pot * WINNER_RETENTION)
                await point_manager.add_point(self.bot, self.guild_id, self.user_id, final_payout)
                record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, final_payout, True)
                
                self.ended = True
                active_games_by_user.discard(self.user_id)
                
                embed = discord.Embed(title="🏆 야바위 전설!", description=f"5연승 달성! 수수료를 제외한 보상이 지급됩니다.\n{cups_display}", color=discord.Color.gold())
                embed.add_field(name="💰 최종 수령액", value=f"{final_payout:,}원 (5% 수수료 제외)")
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                # 다음 단계 진행 여부 묻기
                embed = discord.Embed(title="🎉 성공!", description=f"정답입니다! 현재 {self.wins}연승 중!\n{cups_display}", color=discord.Color.green())
                embed.add_field(name="💰 현재 잠재 보상", value=f"{self.current_pot:,}원")
                
                self.clear_items()
                self.add_item(ContinueButton())
                self.add_item(StopButton())
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            # 실패 처리 (위로금 없음 또는 기존 연승 비례 - 여기서는 전액 상실로 일반적 처리)
            # 만약 기존 로직처럼 위로금을 주려면 여기서 current_pot의 일부를 지급
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
        embed.add_field(name="💵 최종 수령액", value=f"{final_payout:,}원 (5% 수수료)")
        await interaction.response.edit_message(embed=embed, view=None)

class ContinueButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🚀 다음 단계 도전!", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: YabawiGameView = self.view
        
        # [수정] 다음 라운드 진행을 위해 플래그 초기화
        view.reset_for_next() 
        # reset_for_next() 함수 안에 이미 self.processing = False가 있으므로 
        # 이 함수가 정상적으로 호출되는지 확인하세요.
        
        view.clear_items()
        for i in range(3):
            view.add_item(CupButton("🥤", i))
        
        embed = discord.Embed(title=f"🔥 {view.wins + 1}단계 도전", description="공이 든 컵을 고르세요!", color=discord.Color.purple())
        await interaction.response.edit_message(embed=embed, view=view)

# (YabawiGameCog 클래스 부분은 기존과 거의 동일하나, view.message 저장을 위해 수정)
class YabawiGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="야바위게임", description="야바위 게임을 시작합니다.")
    async def yabawi_game(self, interaction: discord.Interaction, 배팅: int = 10):
        user_id = str(interaction.user.id)
        if user_id in active_games_by_user:
            return await interaction.response.send_message("❗ 이미 진행 중인 게임이 있습니다.", ephemeral=True)

        if 배팅 < 100 or 배팅 > 1000:
            return await interaction.response.send_message("❗ 배팅은 100~1,000원 사이만 가능합니다.", ephemeral=True)

        view = YabawiGameView(self.bot, interaction.user, 배팅, str(interaction.guild_id))
        embed = discord.Embed(title="🎩 야바위 준비!", description="컵을 섞고 있습니다...", color=discord.Color.light_grey())
        
        await interaction.response.send_message(embed=embed)
        view.message = await interaction.original_response()
        
        await asyncio.sleep(1)
        embed.title = "🎩 야바위 게임 시작!"
        embed.description = "공이 든 컵을 고르세요!"
        embed.add_field(name="💰 배팅", value=f"{배팅:,}원")
        await view.message.edit(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(YabawiGameCog(bot))