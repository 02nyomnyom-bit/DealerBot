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
            stats_manager.record_game(user_id, username, "블랙잭", bet, payout, is_win)
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
    def __init__(self, cog, bot, user, bet):
        super().__init__(timeout=60)
        self.cog, self.bot, self.user, self.bet = cog, bot, user, bet
        self.message = None # 메시지 저장을 위해 추가

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 명령어 실행자만 선택할 수 있습니다.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # 타임아웃 시 processing_users에서 사용자 제거
        self.cog.processing_users.discard(self.user.id)
        if self.message:
            try:
                await self.message.edit(view=None) # 버튼 비활성화
            except discord.NotFound:
                pass # 메시지가 이미 삭제되었을 수 있음
        self.stop()

    @discord.ui.button(label="🤖 싱글 모드", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 포인트 선차감 (싱글)
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        
        view = BlackjackView(self.cog, self.user, self.bet, self.bot)
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
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.cog, self.bot, self.user, self.bet))

class MultiSetupView(View):
    def __init__(self, cog, bot, user, bet):
        super().__init__(timeout=60)
        self.cog, self.bot, self.user, self.bet = cog, bot, user, bet
        self.message = None # 메시지 저장을 위해 추가

    async def on_timeout(self):
        # 타임아웃 시 processing_users에서 사용자 제거
        self.cog.processing_users.discard(self.user.id)
        if self.message:
            try:
                await self.message.edit(view=None) # 버튼 비활성화
            except discord.NotFound:
                pass # 메시지가 이미 삭제되었을 수 있음
        self.stop()

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="상대를 선택하세요.")
        async def callback(inter: discord.Interaction):
            target = user_select.values[0]
            if target.id == self.user.id or target.bot:
                # 에러 발생 시 processing_users에서 사용자 제거
                self.cog.processing_users.discard(self.user.id)
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            
            # 두 명 포인트 선차감 (먹튀 방지)
            if POINT_MANAGER_AVAILABLE:
                p1_bal = await point_manager.get_point(self.bot, inter.guild_id, str(self.user.id))
                p2_bal = await point_manager.get_point(self.bot, inter.guild_id, str(target.id))
                
                # --- 수정된 부분: None 값을 0으로 변환 ---
                p1_bal = p1_bal if p1_bal is not None else 0
                p2_bal = p2_bal if p2_bal is not None else 0
                # --------------------------------------

                if p1_bal < self.bet or p2_bal < self.bet:
                    # 에러 발생 시 processing_users에서 사용자 제거
                    self.cog.processing_users.discard(self.user.id)
                    return await inter.response.send_message("❌ 참가자 중 잔액이 부족한 사람이 있습니다.", ephemeral=True)
                
                await point_manager.add_point(self.bot, inter.guild_id, str(self.user.id), -self.bet)
                
                # 타겟도 게임 시작 전에 processing_users에 추가
                self.cog.processing_users.add(target.id)
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
        view = MultiBlackjackView(self.cog, self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="🃏 1:1 블랙잭 대결", color=discord.Color.gold())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        embed.set_footer(text="참가자는 아래 버튼을 눌러 게임을 진행하세요!")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

class MultiBlackjackView(View):
    def __init__(self, cog, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.cog, self.bot, self.p1, self.bet, self.p2 = cog, bot, p1, bet, p2
        self.game_completed = False
        
        self.game = BlackjackGame(bet) 
        self.p1_cards = [self.game.draw_card(), self.game.draw_card()]
        self.p2_cards = [] # P2는 참가 시점에 카드를 받음
        self.p1_done = False
        self.p2_done = False
        self.message = None

    async def on_timeout(self):
        if self.game_completed:
            return
            
        self.game_completed = True
        
        # 타임아웃 시 processing_users에서 사용자 제거
        self.cog.processing_users.discard(self.p1.id)
        if self.p2:
            self.cog.processing_users.discard(self.p2.id)

        # 타임아웃 시 배팅금 100% 환불 로직
        if POINT_MANAGER_AVAILABLE and self.message:
            guild_id = self.message.guild.id
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
            if self.p2:
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)

        try:
            embed = discord.Embed(
                title="⏰ 게임 무효화", 
                description="입력 시간이 초과되어 게임이 취소되었습니다. 배팅금은 전액 환불되었습니다.", 
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
        except:
            pass

    async def check_user(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        # P2가 없는 공개 대전 상태
        if self.p2 is None:
            if user.id == self.p1.id:
                await interaction.response.send_message("❌ 상대방을 기다리고 있습니다.", ephemeral=True)
                return False
            
            # P2로 참가 처리
            if POINT_MANAGER_AVAILABLE:
                balance = await point_manager.get_point(self.bot, interaction.guild_id, str(user.id))
                if (balance or 0) < self.bet:
                    # 에러 발생 시 processing_users에서 사용자 제거
                    self.cog.processing_users.discard(self.p1.id) # P1 (방장) 플래그도 지워야 함
                    return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
                # P2도 게임 시작 전에 processing_users에 추가
                self.cog.processing_users.add(user.id)
                await point_manager.add_point(self.bot, interaction.guild_id, str(user.id), -self.bet)
            
            self.p2 = user
            self.p2_cards = [self.game.draw_card(), self.game.draw_card()]
            await interaction.channel.send(f"🃏 {user.mention}님이 블랙잭 대결에 참가했습니다!", delete_after=10)
            return True

        # 참가자가 아닌 경우
        if user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
            return False
        
        return True

    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        
        user_id = interaction.user.id
        player_cards = self.p1_cards if user_id == self.p1.id else self.p2_cards
        
        # 이미 턴을 마친 경우
        if (user_id == self.p1.id and self.p1_done) or (user_id == self.p2.id and self.p2_done):
            return await interaction.response.send_message("이미 턴을 마쳤습니다.", ephemeral=True)

        player_cards.append(self.game.draw_card())
        
        if self.game.calculate_hand_value(player_cards) > 21: # 버스트
            if user_id == self.p1.id: self.p1_done = True
            else: self.p2_done = True
        
        await interaction.response.defer()
        if self.p1_done and self.p2_done: await self.finish_game()
        else: await self.update_view()

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
        p1_status = '💥 버스트!' if p1_val > 21 else ('✋ 스탠드' if self.p1_done else '🃏 고민 중')
        
        embed.add_field(name=f"👤 {self.p1.display_name}", value=f"점수: {p1_val}\n상태: {p1_status}")

        if self.p2:
            p2_val = self.game.calculate_hand_value(self.p2_cards)
            p2_status = '💥 버스트!' if p2_val > 21 else ('✋ 스탠드' if self.p2_done else '🃏 고민 중')
            embed.add_field(name=f"👤 {self.p2.display_name}", value=f"점수: {p2_val}\n상태: {p2_status}")
        else:
            embed.add_field(name="👤 상대방 대기 중", value="점수: ??\n상태: ⚔️ 대기")
            
        await self.message.edit(embed=embed, view=self)

    async def finish_game(self):
        self.game_completed = True
        v1 = self.game.calculate_hand_value(self.p1_cards)
        v2 = self.game.calculate_hand_value(self.p2_cards)
        guild_id = self.message.guild.id
        
        winner, p1_payout, p2_payout = None, 0, 0
        
        # 승패 판정 로직
        if v1 > 21 and v2 > 21: result = "무승부 (둘 다 버스트)"
        elif v1 > 21: winner = self.p2; result = f"{self.p2.mention} 승리!"
        elif v2 > 21: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v1 > v2: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v2 > v1: winner = self.p2; result = f"{self.p2.mention} 승리!"
        else: result = "무승부!"

        if winner:
            reward = int((self.bet * 2) * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            reward_msg = f"💰 {winner.mention} 승리! 수수료 제외 **{reward:,}원** 획득!"
            if winner.id == self.p1.id: p1_payout = reward
            else: p2_payout = reward
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_msg = f"🤝 무승부! 수수료 5%를 제외한 **{refund:,}원**이 환불되었습니다."
            p1_payout = p2_payout = refund

        record_blackjack_game(str(self.p1.id), self.p1.display_name, self.bet, p1_payout, winner == self.p1)
        record_blackjack_game(str(self.p2.id), self.p2.display_name, self.bet, p2_payout, winner == self.p2)

        final_embed = discord.Embed(title="🏁 게임 종료", description=f"**{result}**\n{reward_msg}\n\n"
                                                                  f"{self.p1.mention}: {v1}점\n{self.p2.mention}: {v2}점", 
                                    color=discord.Color.gold())
        await self.message.edit(embed=final_embed, view=None)
        self.stop()
        self.cog.processing_users.discard(self.p1.id)
        if self.p2:
            self.cog.processing_users.discard(self.p2.id)

    async def check_user(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        # P2가 없는 공개 대전 상태
        if self.p2 is None:
            if user.id == self.p1.id:
                await interaction.response.send_message("❌ 상대방을 기다리고 있습니다.", ephemeral=True)
                return False
            
            # P2로 참가 처리
            if POINT_MANAGER_AVAILABLE:
                balance = await point_manager.get_point(self.bot, interaction.guild_id, str(user.id))
                if (balance or 0) < self.bet:
                    await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
                    return False
                await point_manager.add_point(self.bot, interaction.guild_id, str(user.id), -self.bet)
            
            self.p2 = user
            self.p2_cards = [self.game.draw_card(), self.game.draw_card()]
            await interaction.channel.send(f"🃏 {user.mention}님이 블랙잭 대결에 참가했습니다!", delete_after=10)
            return True

        # 참가자가 아닌 경우
        if user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
            return False
        
        return True

    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        
        user_id = interaction.user.id
        player_cards = self.p1_cards if user_id == self.p1.id else self.p2_cards
        
        # 이미 턴을 마친 경우
        if (user_id == self.p1.id and self.p1_done) or (user_id == self.p2.id and self.p2_done):
            return await interaction.response.send_message("이미 턴을 마쳤습니다.", ephemeral=True)

        player_cards.append(self.game.draw_card())
        
        if self.game.calculate_hand_value(player_cards) > 21: # 버스트
            if user_id == self.p1.id: self.p1_done = True
            else: self.p2_done = True
        
        await interaction.response.defer()
        if self.p1_done and self.p2_done: await self.finish_game()
        else: await self.update_view()

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
        p1_status = '💥 버스트!' if p1_val > 21 else ('✋ 스탠드' if self.p1_done else '🃏 고민 중')
        
        embed.add_field(name=f"👤 {self.p1.display_name}", value=f"점수: {p1_val}\n상태: {p1_status}")

        if self.p2:
            p2_val = self.game.calculate_hand_value(self.p2_cards)
            p2_status = '💥 버스트!' if p2_val > 21 else ('✋ 스탠드' if self.p2_done else '🃏 고민 중')
            embed.add_field(name=f"👤 {self.p2.display_name}", value=f"점수: {p2_val}\n상태: {p2_status}")
        else:
            embed.add_field(name="👤 상대방 대기 중", value="점수: ??\n상태: ⚔️ 대기")
            
        await self.message.edit(embed=embed, view=self)

    async def finish_game(self):
        self.game_completed = True
        v1 = self.game.calculate_hand_value(self.p1_cards)
        v2 = self.game.calculate_hand_value(self.p2_cards)
        guild_id = self.message.guild.id
        
        winner, p1_payout, p2_payout = None, 0, 0
        
        # 승패 판정 로직
        if v1 > 21 and v2 > 21: result = "무승부 (둘 다 버스트)"
        elif v1 > 21: winner = self.p2; result = f"{self.p2.mention} 승리!"
        elif v2 > 21: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v1 > v2: winner = self.p1; result = f"{self.p1.mention} 승리!"
        elif v2 > v1: winner = self.p2; result = f"{self.p2.mention} 승리!"
        else: result = "무승부!"

        if winner:
            reward = int((self.bet * 2) * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            reward_msg = f"💰 {winner.mention} 승리! 수수료 제외 **{reward:,}원** 획득!"
            if winner.id == self.p1.id: p1_payout = reward
            else: p2_payout = reward
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_msg = f"🤝 무승부! 수수료 5%를 제외한 **{refund:,}원**이 환불되었습니다."
            p1_payout = p2_payout = refund

        record_blackjack_game(str(self.p1.id), self.p1.display_name, self.bet, p1_payout, winner == self.p1)
        record_blackjack_game(str(self.p2.id), self.p2.display_name, self.bet, p2_payout, winner == self.p2)

        final_embed = discord.Embed(title="🏁 게임 종료", description=f"**{result}**\n{reward_msg}\n\n"
                                                                  f"{self.p1.mention}: {v1}점\n{self.p2.mention}: {v2}점", 
                                    color=discord.Color.gold())
        await self.message.edit(embed=final_embed, view=None)
        self.stop()

# --- 기존 BlackjackView 및 Cog (일부 수정) ---

class BlackjackView(View):
    def __init__(self, cog, user: discord.User, bet: int, bot: commands.Bot):
        super().__init__(timeout=120)
        self.cog = cog  
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
        
        payout = 0
        is_win = self.game.result in ["win", "dealer_bust"]
        is_blackjack_win = self.game.is_blackjack(self.game.player_cards) and is_win

        if is_blackjack_win:
            payout = int(self.bet * 2.5 * WINNER_RETENTION)
        elif is_win:
            payout = int(self.bet * 2 * WINNER_RETENTION)
        elif self.game.result == "push":
            payout = int(self.bet * PUSH_RETENTION)

        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, guild_id, uid, payout)

        record_blackjack_game(uid, self.user.display_name, self.bet, payout, is_win)

        final_embed = self.create_game_embed(final=True)
        result_text = f"{self.game.result.upper()} (정산: {payout:,}원)"
        if is_blackjack_win:
            result_text = f"BLACKJACK! {result_text}"
        final_embed.add_field(name="결과", value=result_text, inline=False)
        
        if interaction: 
            await interaction.response.edit_message(embed=final_embed, view=None)
        else: 
            await self.message.edit(embed=final_embed, view=None)

# --- BlackjackCog 명령어 부분 ---
class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processing_users = set() # 현재 게임을 플레이 중인 사용자 ID

    @app_commands.command(name="블랙잭", description="🃏 블랙잭을 시작합니다.(100원 ~ 6,000원)")
    @app_commands.describe(배팅="배팅할 금액을 입력하세요. (100원 ~ 6,000원)")
    async def blackjack_game(self, interaction: discord.Interaction, 배팅: int = 100):
        user_id = interaction.user.id
        
        # 0. 이미 게임을 플레이 중인지 확인
        if user_id in self.processing_users:
            return await interaction.response.send_message("❌ 이미 블랙잭 게임을 플레이 중입니다.", ephemeral=True)
        
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
        
        # 1. 배팅 금액 제한 체크
        if 배팅 < 100:
            return await interaction.response.send_message("❌ 최소 배팅 금액은 100원입니다.", ephemeral=True)
        if 배팅 > MAX_BET:
            return await interaction.response.send_message(f"❌ 최대 배팅 금액은 {MAX_BET:,}원입니다.", ephemeral=True)

        # 2. 잔액 체크
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(user_id))
        if balance < 배팅:
            return await interaction.response.send_message(f"❌ 잔액이 부족합니다. (보유: {balance:,}원)", ephemeral=True)

        # 3. 게임 시작 플래그 설정
        self.processing_users.add(user_id)
        
        view = BlackjackModeSelectView(self, self.bot, interaction.user, 배팅) # self (Cog) 전달
        await interaction.response.send_message(f"🃏 **블랙잭 모드 선택** (배팅: {배팅:,}원)\n※ 무승부 시 수수료 5%가 차감됩니다.", view=view)
        view.message = await interaction.original_response()
        
async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))