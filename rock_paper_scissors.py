# rock_paper_scissors.py - 가위바위보 게임 (통계 기록 추가)
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
from typing import Literal, Optional
import random

# ✅ 통계 시스템 안전 임포트 (추가)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (가위바위보)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (가위바위보)")

# point_manager 임포트
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    
    # Mock functions
    class MockPointManager:
        @staticmethod
        def is_registered(user_id):
            return True
        @staticmethod
        def get_point(user_id):
            return 10000
        @staticmethod
        def add_point(user_id, amount):
            pass
        @staticmethod
        def register_user(user_id):
            pass
    
    point_manager = MockPointManager()

# 사용자별 활성 게임 추적
active_games_by_user = set()

def determine_winner(choice1, choice2):
    """승부 판정"""
    if choice1 == choice2:
        return "무승부"
    if (choice1 == "가위" and choice2 == "보") or \
       (choice1 == "바위" and choice2 == "가위") or \
       (choice1 == "보" and choice2 == "바위"):
        return "플레이어 1 승"
    else:
        return "플레이어 2 승"

def with_emoji(choice):
    """선택을 이모지로 변환"""
    return {"가위": "✂️", "바위": "🗿", "보": "📄"}.get(choice, choice)

# ✅ 통계 기록 헬퍼 함수 (추가)
def record_rps_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    """가위바위보 게임 통계 기록"""
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(
                user_id=user_id,
                username=username,
                game_name="rock_paper_scissors",
                is_win=is_win,
                bet=bet,
                payout=payout
            )
        except Exception as e:
            print(f"❌ 가위바위보 통계 기록 실패: {e}")

class SinglePlayView(View):
    def __init__(self, user, channel_id, betting_point):
        super().__init__(timeout=60)
        self.user = user
        self.channel_id = channel_id
        self.betting_point = betting_point

    async def on_timeout(self):
        try:
            await self.user.send("⏰ 가위바위보 게임이 시간 초과로 종료되었습니다.")
        except:
            pass
        active_games_by_user.discard(self.user.id)
        self.stop()

    @discord.ui.button(label="✂️ 가위", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction, button):
        await self.process_choice(interaction, "가위")

    @discord.ui.button(label="🗿 바위", style=discord.ButtonStyle.success) 
    async def rock(self, interaction, button):
        await self.process_choice(interaction, "바위")

    @discord.ui.button(label="📄 보", style=discord.ButtonStyle.danger)
    async def paper(self, interaction, button):
        await self.process_choice(interaction, "보")

    async def process_choice(self, interaction, choice):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 선택할 수 있어요.", ephemeral=True)

        user_id = str(interaction.user.id)
        
        # 포인트 차감
        point_manager.add_point(user_id, -self.betting_point)
        
        # 봇 선택
        bot_choice = random.choice(["가위", "바위", "보"])
        result = determine_winner(choice, bot_choice)
        
        # 결과에 따른 보상 및 통계 기록
        if result == "플레이어 1 승":
            reward = self.betting_point * 3
            point_manager.add_point(user_id, reward)
            result_msg = "🎉 승리!"
            reward_msg = f"+{reward:,}원 획득"
            embed_color = discord.Color.green()
            is_win = True
            payout = reward
        elif result == "플레이어 2 승":
            result_msg = "😢 패배!"
            reward_msg = f"-{self.betting_point:,}원 차감"
            embed_color = discord.Color.red()
            is_win = False
            payout = 0
        else:
            # 무승부 시 배팅 금액 반환
            point_manager.add_point(user_id, self.betting_point)
            result_msg = "🤝 무승부!"
            reward_msg = "배팅 금액 반환"
            embed_color = discord.Color.gold()
            is_win = False
            payout = self.betting_point

        # ✅ 통계 기록 (추가)
        record_rps_game(user_id, interaction.user.display_name, self.betting_point, payout, is_win)

        for child in self.children:
            child.disabled = True
            child.style = discord.ButtonStyle.secondary

        # 최종 잔액 조회
        final_balance = point_manager.get_point(user_id)

        # 결과 임베드 생성
        embed = discord.Embed(
            title="✂️ 가위바위보 게임 결과",
            description=result_msg,
            color=embed_color
        )
        
        embed.add_field(
            name="🎯 선택 & 결과",
            value=f"**{self.user.display_name}**: {with_emoji(choice)}\n**딜러**: {with_emoji(bot_choice)}",
            inline=False
        )
        
        embed.add_field(name="🏆 결과", value=reward_msg, inline=True)
        embed.add_field(name="💰 현재 잔액", value=f"{final_balance:,}원", inline=True)
        embed.set_footer(text=f"배팅 금액: {self.betting_point:,}원")

        await interaction.response.edit_message(content=None, embed=embed, view=self)

        active_games_by_user.discard(self.user.id)
        self.stop()

class MultiPlayP1View(View):
    def __init__(self, user, channel_id, bet, opponent=None):
        super().__init__(timeout=60)
        self.user = user
        self.channel_id = channel_id
        self.bet = bet
        self.opponent = opponent
        self.choice = None

    async def on_timeout(self):
        try: await self.user.send("⏹️ 시간 초과로 게임이 종료되었습니다.")
        except: pass
        active_games_by_user.discard(self.user.id)
        if self.opponent:
            active_games_by_user.discard(self.opponent.id)
        self.stop()

    @discord.ui.button(label="✌", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction, button): await self.set_choice(interaction, "가위")

    @discord.ui.button(label="✊", style=discord.ButtonStyle.success)
    async def rock(self, interaction, button): await self.set_choice(interaction, "바위")

    @discord.ui.button(label="✋", style=discord.ButtonStyle.danger)
    async def paper(self, interaction, button): await self.set_choice(interaction, "보")

    async def set_choice(self, interaction, choice):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 선택할 수 있어요.", ephemeral=True)

        self.choice = choice
        await interaction.response.send_message("✅ 선택 완료! 상대방을 기다립니다.", ephemeral=True)
        self.stop()

class MultiPlayP2View(View):
    def __init__(self, p1_user, p1_choice, bet, p2_target=None):
        super().__init__(timeout=60)
        self.p1_user = p1_user
        self.p1_choice = p1_choice
        self.bet = bet
        self.p2_user = None
        self.p2_target = p2_target

    async def on_timeout(self):
        active_games_by_user.discard(self.p1_user.id)
        if self.p2_target:
            active_games_by_user.discard(self.p2_target.id)
        self.stop()

    @discord.ui.button(label="✌", style=discord.ButtonStyle.primary)
    async def scissors(self, interaction, button): await self.set_choice(interaction, "가위")

    @discord.ui.button(label="✊", style=discord.ButtonStyle.success)
    async def rock(self, interaction, button): await self.set_choice(interaction, "바위")

    @discord.ui.button(label="✋", style=discord.ButtonStyle.danger)
    async def paper(self, interaction, button): await self.set_choice(interaction, "보")

    async def set_choice(self, interaction, choice):
        user = interaction.user
        
        # 참여 자격 확인
        if self.p2_target:
            if user != self.p2_target:
                return await interaction.response.send_message("❗ 이 게임에 참여할 수 없습니다.", ephemeral=True)
        else:
            if user == self.p1_user:
                return await interaction.response.send_message("❗ 본인과는 게임할 수 없습니다.", ephemeral=True)

        user_id = str(user.id)
        p1_id = str(self.p1_user.id)

        # 등록 및 잔액 확인
        if not point_manager.is_registered(user_id):
            return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

        if point_manager.get_point(user_id) < self.bet:
            return await interaction.response.send_message("❗ 잔액이 부족합니다.", ephemeral=True)

        self.p2_user = user
        
        # 배팅 차감
        point_manager.add_point(p1_id, -self.bet)
        point_manager.add_point(user_id, -self.bet)

        result = determine_winner(self.p1_choice, choice)

        # 결과 처리 및 통계 기록
        if result == "플레이어 1 승":
            point_manager.add_point(p1_id, self.bet)
            point_manager.add_point(user_id, -self.bet)
            result_msg = f"🏅 {self.p1_user.mention} 승! +{self.bet}원"
            # ✅ 통계 기록 (추가)
            record_rps_game(p1_id, self.p1_user.display_name, self.bet, self.bet, True)
            record_rps_game(user_id, user.display_name, self.bet, 0, False)
        elif result == "플레이어 2 승":
            point_manager.add_point(user_id, self.bet)
            point_manager.add_point(p1_id, -self.bet)
            result_msg = f"🏅 {self.p2_user.mention} 승! +{self.bet}원"
            # ✅ 통계 기록 (추가)
            record_rps_game(p1_id, self.p1_user.display_name, self.bet, 0, False)
            record_rps_game(user_id, user.display_name, self.bet, self.bet, True)
        else:
            result_msg = "🤝 무승부! 포인트 변동 없음."
            # ✅ 통계 기록 (추가)
            record_rps_game(p1_id, self.p1_user.display_name, self.bet, self.bet, False)
            record_rps_game(user_id, user.display_name, self.bet, self.bet, False)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content=(
                f"{self.p1_user.mention}: {with_emoji(self.p1_choice)}\n"
                f"{self.p2_user.mention}: {with_emoji(choice)}\n"
                f"🏆 결과: {result_msg}\n"
                f"✅ 게임이 종료되었습니다."
            ),
            view=self
        )

        active_games_by_user.discard(self.p1_user.id)
        active_games_by_user.discard(self.p2_user.id)
        self.stop()

# ✅ Cog 등록
class RockPaperScissors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="가위바위보", description="가위바위보 게임 시작")
    @app_commands.describe(
        모드="싱글 또는 멀티 선택",
        배팅="배팅할 현금 (1~1,000원), 미입력시 10원이 나갑니다.",
        상대방="(선택 사항) 상대 플레이어를 지정하세요."
    )
    async def rps_command(self, interaction: discord.Interaction, 모드: Literal["싱글", "멀티"], 배팅: int = 10, 상대방: Optional[discord.User] = None):
        uid = interaction.user.id

        if 모드 == "싱글":
            if 배팅 < 1 or 배팅 > 1000:
                return await interaction.response.send_message("❗ 싱글 모드는 1~1,000원 사이여야 합니다.", ephemeral=True)

            user_id = str(interaction.user.id)
            if not point_manager.is_registered(user_id):
                point_manager.register_user(user_id)

            if point_manager.get_point(user_id) < 배팅:
                return await interaction.response.send_message(
                    f"❌ 현재 잔액이 부족하여 게임을 시작할 수 없습니다.\n💰 현재 잔액: {point_manager.get_point(user_id)}원",
                    ephemeral=True
                )

            # 개선된 게임 설명 임베드
            embed = discord.Embed(
                title="✂️ 가위바위보 게임 (싱글)",
                description="봇과 가위바위보 대결을 펼쳐보세요!",
                color=discord.Color.blue()
            )
            embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
            embed.add_field(name="🏆 승리 시", value=f"+{배팅 * 3:,}원 (3배!)", inline=True)
            embed.add_field(name="\u200b", value="\u200b", inline=False)

            await interaction.response.send_message(
                embed=embed,
                view=SinglePlayView(interaction.user, interaction.channel.id, 배팅)
            )
            return

        if 상대방:
            if 상대방.id == uid:
                return await interaction.response.send_message("❗ 자신과는 게임할 수 없습니다.", ephemeral=True)
            if 상대방.id in active_games_by_user:
                return await interaction.response.send_message("❗ 상대방이 이미 게임 중입니다.", ephemeral=True)

            active_games_by_user.add(상대방.id)
            p1_view = MultiPlayP1View(interaction.user, interaction.channel.id, 배팅, 상대방)

            await interaction.response.send_message(
                f"🎮 멀티 가위바위보 (지정) 시작! 배팅: {배팅}원\n{interaction.user.mention}님, 선택해주세요.",
                view=p1_view
            )
        else:
            p1_view = MultiPlayP1View(interaction.user, interaction.channel.id, 배팅)
            await interaction.response.send_message(
                f"🎮 멀티 가위바위보 (공개) 시작! 배팅: {배팅}원\n{interaction.user.mention}님, 선택해주세요.",
                view=p1_view
            )

        await p1_view.wait()

        if not p1_view.choice:
            active_games_by_user.discard(uid)
            if 상대방:
                active_games_by_user.discard(상대방.id)
            return

        await interaction.followup.send(
            f"{interaction.user.mention}님이 선택을 완료했습니다!\n"
            f"{상대방.mention if 상대방 else '도전할 사람'}님, 아래 버튼을 눌러 주세요!",
            view=MultiPlayP2View(interaction.user, p1_view.choice, 배팅, 상대방)
        )

# ✅ Cog setup
async def setup(bot: commands.Bot):
    await bot.add_cog(RockPaperScissors(bot))
    print("✅ 가위바위보 게임 (통계 기록 포함) 로드 완료")