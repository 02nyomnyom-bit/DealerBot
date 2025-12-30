# blackjack.py
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
from typing import List, Optional
import random
import asyncio

# --- 시스템 설정 및 연동 ---
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

# 상수 설정
MAX_BET = 6000  # 최대 배팅금: 6천 원
PUSH_RETENTION = 0.95 # 무승부 시 5% 수수료 제외 (95%만 지급)
WINNER_RETENTION = 0.95  # 승리 시 5% 수수료 제외 (95%만 지급)

# 카드 및 이모지 정의
CARD_DECK = {
    'A♠': ('🂡', 'A♠'), '2♠': ('🂢', '2♠'), '3♠': ('🂣', '3♠'), '4♠': ('🂤', '4♠'), '5♠': ('🂥', '5♠'),
    '6♠': ('🂦', '6♠'), '7♠': ('🂧', '7♠'), '8♠': ('🂨', '8♠'), '9♠': ('🂩', '9♠'), '10♠': ('🂪', '10♠'),
    'J♠': ('🂫', 'J♠'), 'Q♠': ('🂭', 'Q♠'), 'K♠': ('🂮', 'K♠'),
    'A♥': ('🂱', 'A♥'), '2♥': ('🂲', '2♥'), '3♥': ('🂳', '3♥'), '4♥': ('🂴', '4♥'), '5♥': ('🂵', '5♥'),
    '6♥': ('🂶', '6♥'), '7♥': ('🂷', '7♥'), '8♥': ('🂸', '8♥'), '9♥': ('🂹', '9♥'), '10♥': ('🂺', '10♥'),
    'J♥': ('🂻', 'J♥'), 'Q♥': ('🂽', 'Q♥'), 'K♥': ('🂾', 'K♥'),
    'A♦': ('🃁', 'A♦'), '2♦': ('🃂', '2♦'), '3♦': ('🃃', '3♦'), '4♦': ('🃄', '4♦'), '5♦': ('🃅', '5♦'),
    '6♦': ('🃆', '6♦'), '7♦': ('🃇', '7♦'), '8♦': ('🃈', '8♦'), '9♦': ('🃉', '9♦'), '10♦': ('🃊', '10♦'),
    'J♦': ('🃋', 'J♦'), 'Q♦': ('🃍', 'Q♦'), 'K♦': ('🃎', 'K♦'),
    'A♣': ('🃑', 'A♣'), '2♣': ('🃒', '2♣'), '3♣': ('🃓', '3♣'), '4♣': ('🃔', '4♣'), '5♣': ('🃕', '5♣'),
    '6♣': ('🃖', '6♣'), '7♣': ('🃗', '7♣'), '8♣': ('🃘', '8♣'), '9♣': ('🃙', '9♣'), '10♣': ('🃚', '10♣'),
    'J♣': ('🃛', 'J♣'), 'Q♣': ('🃝', 'Q♣'), 'K♣': ('🃞', 'K♣')
}
CARD_BACK = ('🂠', '???')

def record_blackjack_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(user_id, username, "blackjack", is_win, bet, payout)
        except: pass

class BlackjackGame:
    def __init__(self, bet: int):
        self.bet = bet
        self.deck = list(CARD_DECK.keys()) * 4
        random.shuffle(self.deck)
        self.player_cards = [self.draw_card(), self.draw_card()]
        self.dealer_cards = [self.draw_card(), self.draw_card()]
        self.game_over = False
        self.result = None

    def draw_card(self):
        if not self.deck:
            self.deck = list(CARD_DECK.keys()) * 4
            random.shuffle(self.deck)
        return self.deck.pop()

    def calculate_hand_value(self, cards):
        total, aces = 0, 0
        for card in cards:
            rank = card[:-1]
            if rank in ['J', 'Q', 'K', '10']: total += 10
            elif rank == 'A': total += 11; aces += 1
            else: total += int(rank)
        while total > 21 and aces > 0:
            total -= 10; aces -= 1
        return total

    def hit_player(self):
        self.player_cards.append(self.draw_card())
        if self.calculate_hand_value(self.player_cards) > 21:
            self.game_over = True
            self.result = "bust"

    def stand_player(self):
        self.game_over = True
        while self.calculate_hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.draw_card())
        self.determine_winner()

    def determine_winner(self):
        p_val = self.calculate_hand_value(self.player_cards)
        d_val = self.calculate_hand_value(self.dealer_cards)
        if p_val > 21: self.result = "bust"
        elif d_val > 21: self.result = "dealer_bust"
        elif p_val > d_val: self.result = "win"
        elif p_val < d_val: self.result = "lose"
        else: self.result = "push"

    def get_card_display(self, cards, hide_first=False):
        if hide_first:
            return f"{CARD_BACK[0]} " + " ".join([CARD_DECK[c][0] for c in cards[1:]])
        return " ".join([CARD_DECK[c][0] for c in cards])

    def get_card_value(self, card):
        rank = card[:-1]
        if rank in ['J', 'Q', 'K', '10']: return 10
        elif rank == 'A': return 11
        return int(rank)

    def is_blackjack(self, cards):
        return len(cards) == 2 and self.calculate_hand_value(cards) == 21

# --- 모드 선택 및 멀티플레이 View 클래스들 ---

class BlackjackModeSelectView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 명령어 실행자만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🤖 싱글 모드", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 포인트 선차감 (싱글)
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        
        view = BlackjackView(self.user, self.bet, self.bot)
        embed = view.create_game_embed()
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = await interaction.original_response()
        if view.game.is_blackjack(view.game.player_cards):
            view.game.game_over = True
            view.game.determine_winner()
            await view.end_game(None)

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

class MultiSetupView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="상대를 선택하세요.")
        async def callback(inter: discord.Interaction):
            target = user_select.values[0]
            if target.id == self.user.id or target.bot:
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            
            # 두 명 포인트 선차감 (먹튀 방지)
            if POINT_MANAGER_AVAILABLE:
                p1_bal = await point_manager.get_point(self.bot, inter.guild_id, str(self.user.id))
                p2_bal = await point_manager.get_point(self.bot, inter.guild_id, str(target.id))
                if p1_bal < self.bet or p2_bal < self.bet:
                    return await inter.response.send_message("❌ 참가자 중 잔액이 부족한 사람이 있습니다.", ephemeral=True)
                await point_manager.add_point(self.bot, inter.guild_id, str(self.user.id), -self.bet)
                await point_manager.add_point(self.bot, inter.guild_id, str(target.id), -self.bet)

            await self.start_game(inter, target)
        
        view = View(); user_select.callback = callback; view.add_item(user_select)
        await interaction.response.edit_message(content="상대를 지목해주세요.", embed=None, view=view)

    @discord.ui.button(label="🔓 공개 대전 (아무나)", style=discord.ButtonStyle.success)
    async def public_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 방장 포인트만 먼저 차감
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        await self.start_game(interaction, None)

    async def start_game(self, interaction, target):
        view = MultiBlackjackView(self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="🃏 1:1 블랙잭 대결", color=discord.Color.gold())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        embed.set_footer(text="참가자는 아래 버튼을 눌러 게임을 진행하세요!")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

class MultiBlackjackView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.is_finished = False

    async def check_user(self, interaction: discord.Interaction):
        if self.p2 is None and interaction.user.id != self.p1.id:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
            if balance < self.bet:
                await interaction.response.send_message("❌ 잔액이 부족하여 참여할 수 없습니다.", ephemeral=True)
                return False
            self.p2 = interaction.user
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, interaction.guild_id, str(self.p2.id), -self.bet)

        if interaction.user.id not in [self.p1.id, self.p2.id if self.p2 else None]:
            await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.is_finished: return
        
        # 선차감된 금액 100% 환불
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, self.message.guild.id, str(self.p1.id), self.bet)
            if self.p2:
                await point_manager.add_point(self.bot, self.message.guild.id, str(self.p2.id), self.bet)

        embed = discord.Embed(title="⏰ 블랙잭 중단", description="참여자의 응답이 없어 배팅금이 환불되었습니다.", color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    async def finish_game(self):
        self.is_finished = True

    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        is_p1 = interaction.user.id == self.p1.id
        if (is_p1 and self.p1_done) or (not is_p1 and self.p2_done):
            return await interaction.response.send_message("이미 스탠드 상태입니다.", ephemeral=True)

        cards = self.p1_cards if is_p1 else self.p2_cards
        cards.append(self.game.draw_card())

        if self.game.calculate_hand_value(cards) > 21:
            if is_p1: self.p1_done = True
            else: self.p2_done = True
            await interaction.response.send_message("💥 버스트!", ephemeral=True)
            if self.p1_done and self.p2_done: await self.finish_game()
            else: await self.update_view()
        else:
            await interaction.response.defer()
            await self.update_view()

    @discord.ui.button(label="✋ 스탠드", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        if interaction.user.id == self.p1.id: self.p1_done = True
        else: self.p2_done = True
        await interaction.response.defer()
        if self.p1_done and self.p2_done: await self.finish_game()
        else: await self.update_view()

    async def update_view(self):
        embed = discord.Embed(title="🃏 블랙잭 1:1 대결", color=discord.Color.blue())
        p1_val = self.game.calculate_hand_value(self.p1_cards)
        p2_val = self.game.calculate_hand_value(self.p2_cards) if self.p2 else "??"
        embed.add_field(name=f"👤 {self.p1.display_name}", value=f"점수: {p1_val}\n상태: {'✋ 스탠드' if self.p1_done else '🃏 고민 중'}")
        embed.add_field(name=f"👤 {self.p2.display_name if self.p2 else '상대방 대기 중'}", value=f"점수: {p2_val}\n상태: {'✋ 스탠드' if self.p2_done else '🃏 고민 중'}")
        await self.message.edit(embed=embed, view=self)

    async def finish_game(self):
        v1, v2 = self.game.calculate_hand_value(self.p1_cards), self.game.calculate_hand_value(self.p2_cards)
        guild_id = self.message.guild.id
        
        # 승패 판정 로직
        winner = None
        if v1 > 21 and v2 > 21: result = "무승부 (둘 다 버스트)"
        elif v1 > 21: winner = self.p2; result = f"{self.p2.mention} 승리!"
        elif v2 > 21: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v1 > v2: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v2 > v1: winner = self.p2; result = f"{self.p2.mention} 승리!"
        else: result = "무승부!"

        if winner:
            total_pot = self.bet * 2
            reward = int(total_pot * WINNER_RETENTION) # 5% 수수료 차감
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.message.guild.id, str(winner.id), reward)
            reward_msg = f"💰 {winner.mention} 승리! 수수료 제외 **{reward:,}원** 획득!"
        else:
            # 🤝 무승부 시 10% 수수료 적용 (90%만 환불)
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_msg = f"🤝 무승부! 수수료 5%를 제외한 **{refund:,}원**이 환불되었습니다."

        final_embed = discord.Embed(title="🏁 게임 종료", description=f"**{result}**\n{reward_msg}\n\n"
                                                                  f"{self.p1.mention}: {v1}점\n{self.p2.mention}: {v2}점", 
                                    color=discord.Color.gold())
        await self.message.edit(embed=final_embed, view=None)
        self.stop()

# --- 기존 BlackjackView 및 Cog (일부 수정) ---

class BlackjackView(View):
    # 기존 BlackjackView 코드와 동일하나 calculate_hand_value 호출명 확인 필요
    def __init__(self, user: discord.User, bet: int, bot: commands.Bot):
        super().__init__(timeout=120)
        self.user, self.bet, self.bot = user, bet, bot
        self.game = BlackjackGame(bet)
        self.message = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 본인의 게임 버튼만 누를 수 있습니다.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game.hit_player()
        if self.game.game_over: await self.end_game(interaction)
        else: await interaction.response.edit_message(embed=self.create_game_embed(), view=self)
    
    @discord.ui.button(label="✋ 스탠드", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game.stand_player()
        await self.end_game(interaction)

    def create_game_embed(self, final: bool = False) -> discord.Embed:
        p_val = self.game.calculate_hand_value(self.game.player_cards)
        d_val = self.game.calculate_hand_value(self.game.dealer_cards)
        embed = discord.Embed(title="🃏 블랙잭", color=discord.Color.blue())
        embed.add_field(name="플레이어", value=f"{self.game.get_card_display(self.game.player_cards)}\n({p_val}점)")
        d_display = self.game.get_card_display(self.game.dealer_cards, hide_first=not final)
        embed.add_field(name="딜러", value=f"{d_display}\n({'??' if not final else d_val}점)")
        return embed

    async def end_game(self, interaction: discord.Interaction = None):
        self.game.game_over = True
        self.game.determine_winner()
        guild_id = self.message.guild.id
        uid = str(self.user.id)
        
        reward = 0
        if self.game.result in ["win", "dealer_bust"]:
            reward = self.bet * 2
        elif self.game.is_blackjack(self.game.player_cards) and self.game.result == "win":
            reward = int(self.bet * 2.5)
        elif self.game.result == "push":
            # 싱글 모드 무승부 수수료 적용
            reward = int(self.bet * PUSH_RETENTION)

        if POINT_MANAGER_AVAILABLE and reward > 0:
            await point_manager.add_point(self.bot, guild_id, uid, reward)

        # 결과 출력 및 종료
        final_embed = self.create_game_embed(final=True)
        final_embed.add_field(name="결과", value=f"{self.game.result} (정산: {reward:,}원)")
        if interaction: await interaction.response.edit_message(embed=final_embed, view=None)
        else: await self.message.edit(embed=final_embed, view=None)
        self.stop()

# --- [수정] BlackjackCog 명령어 부분 ---
class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="블랙잭", description="🃏 블랙잭 게임 모드를 선택합니다.")
    @app_commands.describe(배팅="배팅할 금액을 입력하세요. (최대 6,000원)")
    async def blackjack_game(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 배팅 금액 제한 체크
        if 배팅 < 100:
            return await interaction.response.send_message("❌ 최소 배팅 금액은 100원입니다.", ephemeral=True)
        if 배팅 > MAX_BET:
            return await interaction.response.send_message(f"❌ 최대 배팅 금액은 {MAX_BET:,}원입니다.", ephemeral=True)

        # 2. 잔액 체크
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
        if balance < 배팅:
            return await interaction.response.send_message(f"❌ 잔액이 부족합니다. (보유: {balance:,}원)", ephemeral=True)

        view = BlackjackModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🃏 **블랙잭 모드 선택** (배팅: {배팅:,}원)\n※ 무승부 시 수수료 10%가 차감됩니다.", view=view)

async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))