# odd_even_game.py
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
import random
import asyncio

# --- 시스템 연동부 ---
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False

# 상수 설정
MAX_BET = 5000  # 최대 배팅금: 5천 원
PUSH_RETENTION = 0.95 # 무승부 시 5% 수수료 제외 (95%만 지급)
WINNER_RETENTION = 0.95  # 승리 시 5% 수수료 제외 (95%만 지급)

DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

# --- 1단계: 모드 선택 View ---
class OddEvenModeSelectView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 명령어 실행자만 선택 가능합니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🤖 싱글 모드", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        
        embed = discord.Embed(title="🤖 홀짝: 싱글 모드", description="주사위 결과가 **홀**일지 **짝**일지 예측하세요!", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=SingleOddEvenView(self.bot, self.user, self.bet))

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

# --- 2단계: 싱글 게임 진행 View ---
class SingleOddEvenView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="홀 (1,3,5)", style=discord.ButtonStyle.danger, emoji="🔴")
    async def choose_odd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "홀")

    @discord.ui.button(label="짝 (2,4,6)", style=discord.ButtonStyle.primary, emoji="🔵")
    async def choose_even(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "짝")

    async def process_game(self, interaction, user_choice):
        dice_val = random.randint(1, 6)
        actual = "홀" if dice_val % 2 != 0 else "짝"
        
        is_win = (user_choice == actual)
        payout = self.bet * 2 if is_win else 0

        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)

        embed = discord.Embed(title="🎲 홀짝 결과", color=discord.Color.gold() if is_win else discord.Color.red())
        result_text = "🏆 맞췄습니다!" if is_win else "💀 틀렸습니다..."
        embed.description = f"선택: **{user_choice}**\n결과: {DICE_EMOJIS[dice_val]} ({dice_val}) -> **{actual}**\n\n**{result_text}**\n정산: {payout:,}원"
        await interaction.response.edit_message(embed=embed, view=None)

# --- 3단계: 멀티 세부 설정 View ---
class MultiSetupView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="대결 상대를 선택하세요.")
        async def callback(inter: discord.Interaction):
            target = user_select.values[0]
            if target.id == self.user.id or target.bot:
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, inter.guild_id, str(self.user.id), -self.bet)
                await point_manager.add_point(self.bot, inter.guild_id, str(target.id), -self.bet)
            await self.start_multi(inter, target)
        
        v = View(); user_select.callback = callback; v.add_item(user_select)
        await interaction.response.edit_message(content="상대를 선택해주세요.", embed=None, view=v)

    @discord.ui.button(label="🔓 공개 대전 (아무나)", style=discord.ButtonStyle.success)
    async def public_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        await self.start_multi(interaction, None)

    async def start_multi(self, interaction, target):
        view = MultiOddEvenView(self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="⚔️ 홀짝 대결", description=f"배팅액: {self.bet:,}원\n두 분 모두 홀 또는 짝을 선택해주세요!", color=discord.Color.orange())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

class MultiOddEvenView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.choices = {}
        self.message = None
        self.is_finished = False

    async def on_timeout(self):
        if self.is_finished: return
        
        guild_id = self.message.guild.id
        refund_msg = "⏰ **시간 초과!** 두 분 모두 선택하지 않아 게임이 취소되었습니다.\n"
        
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
            if self.p2:
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)
        
        embed = discord.Embed(title="❌ 타임아웃 환불", description=refund_msg, color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    async def finish_game(self):
        self.is_finished = True

    @discord.ui.button(label="홀", style=discord.ButtonStyle.danger, emoji="🔴")
    async def choose_odd(self, interaction, button): await self.make_choice(interaction, "홀")
    @discord.ui.button(label="짝", style=discord.ButtonStyle.primary, emoji="🔵")
    async def choose_even(self, interaction, button): await self.make_choice(interaction, "짝")

    async def make_choice(self, interaction, choice):
        if self.p2 is None and interaction.user.id != self.p1.id:
            self.p2 = interaction.user
            if POINT_MANAGER_AVAILABLE: await point_manager.add_point(self.bot, interaction.guild_id, str(self.p2.id), -self.bet)

        if interaction.user.id not in [self.p1.id, self.p2.id if self.p2 else None]:
            return await interaction.response.send_message("❌ 참가자가 아닙니다.", ephemeral=True)
        
        if interaction.user.id in self.choices:
            return await interaction.response.send_message("이미 선택하셨습니다!", ephemeral=True)

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ {choice}를 선택하셨습니다!", ephemeral=True)

        if len(self.choices) == 2:
            await self.finish_game()

    async def finish_game(self):
        dice_val = random.randint(1, 6)
        actual = "홀" if dice_val % 2 != 0 else "짝"
        guild_id = self.message.guild.id
        
        p1_correct = (self.choices[self.p1.id] == actual)
        p2_correct = (self.choices[self.p2.id] == actual)

        if p1_correct and not p2_correct: winner = self.p1
        elif p2_correct and not p1_correct: winner = self.p2
        else: winner = None # 둘 다 맞추거나 둘 다 틀림

        if winner:
            total_pot = self.bet * 2
            reward = int(total_pot * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            res_msg = f"🏆 {winner.mention} 승리! 수수료 제외 **{reward:,}원** 획득!"
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            res_msg = f"🤝 무승부! (수수료 10% 제외 **{refund:,}원** 환불)"

        embed = discord.Embed(title="🎲 홀짝 대결 결과", color=discord.Color.purple())
        embed.description = f"결과: {DICE_EMOJIS[dice_val]} ({dice_val}) -> **{actual}**\n\n**{res_msg}**\n"
        embed.description += f"{self.p1.mention}: {self.choices[self.p1.id]}\n{self.p2.mention}: {self.choices[self.p2.id]}"
        await self.message.edit(embed=embed, view=None)

# --- Cog 클래스 ---
class OddEvenCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="홀짝게임", description="홀짝 게임을 시작합니다.(최대 5,000원)")
    async def odd_even(self, interaction: discord.Interaction, 배팅: int = 100):
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터!", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
        if balance < 배팅: return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        view = OddEvenModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎲 **홀짝 게임 모드 선택** (배팅: {배팅:,}원)\n※ 무승부 시 수수료 10%가 차감됩니다.", view=view)

async def setup(bot):
    await bot.add_cog(OddEvenCog(bot))