# blackjack.py - 블랙잭
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
from typing import List, Optional
import random
import asyncio

# 시스템 설정 및 연동
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
MAX_BET = 6000              # 최대 배팅금: 6천 원
PUSH_RETENTION = 0.8        # 무승부 시 수수료 (20%)
WINNER_RETENTION = 0.8      # 승리 시 수수료 (20%)

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
            stats_manager.record_game(user_id, username, "blackjack", bet, payout, is_win)
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

# 모드 선택 및 멀티플레이 View
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
        self.cog.processing_users.discard(self.user.id)
        if self.message:
            try:
                await self.message.edit(content="완전 종료된 게임", view=None)
            except: pass

    @discord.ui.button(label="🤖 싱글 모드", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if POINT_MANAGER_AVAILABLE:
            p_bal = await point_manager.get_point(self.bot, interaction.guild_id, str(self.user.id))
            if p_bal < self.bet:
                self.cog.processing_users.discard(self.user.id)
                return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
            
            # 실제 포인트 차감 수행
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
    
        # 게임 뷰 생성 및 시작
        view = BlackjackView(self.cog, self.user, self.bet, self.bot)
        embed = view.create_game_embed()

        if view.game.is_blackjack(view.game.player_cards):
            view.game.game_over = True
            view.game.determine_winner()
        
            # 응답 후 메시지 객체 확보 (이 순서가 멈춤 현상을 방지합니다)
            await interaction.response.edit_message(embed=embed, view=None)
            view.message = await interaction.original_response() #
        
            # 정산 로직 호출
            await view.end_game(interaction) #
        else:
            await interaction.response.edit_message(embed=embed, view=view)
            view.message = await interaction.original_response() #

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.cog, self.bot, self.user, self.bet))

# 멀티 지정 View
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
                self.cog.processing_users.discard(self.user.id)
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            
            if target.id in self.cog.processing_users:
                return await inter.response.send_message("❌ 상대방이 이미 다른 게임을 진행 중입니다.", ephemeral=True)
            
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

    @discord.ui.button(label="수락", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction):
        # 1. 지목된 상대방이 맞는지 먼저 확인
        if interaction.user.id != self.p2.id:
            return await interaction.response.send_message("❌ 당신은 이 게임의 상대방이 아닙니다.", ephemeral=True)

        # 2. [핵심] 수락한 사람의 잔액을 실시간으로 확인
        p2_bal = await point_manager.get_point(self.bot, interaction.guild_id, str(self.p2.id))
    
        if p2_bal < self.bet:
            # 돈이 부족하면 게임을 시작하지 않고 종료
            return await interaction.response.send_message(
                f"❌ 잔액이 부족하여 수락할 수 없습니다! (보유: {p2_bal:,}원 / 필요: {self.bet:,}원)", 
                ephemeral=True
            )

        # 3. 잔액이 충분할 때만 게임 시작
        self.value = True
        await interaction.response.defer() # 버튼 클릭 처리
        self.stop() # View 대기 종료

# 멀티 블랙잭 View
class MultiBlackjackView(View):
    def __init__(self, cog, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.cog, self.bot, self.p1, self.bet, self.p2 = cog, bot, p1, bet, p2
        self.game_completed = False
        self.game = BlackjackGame(bet) 
        self.p1_cards = [self.game.draw_card(), self.game.draw_card()]
        self.p2_cards = [] 
        self.p1_done = False
        self.p2_done = False
        self.message = None

    async def on_timeout(self):
        if self.game_completed: return
        self.game_completed = True
        self.cog.processing_users.discard(self.p1.id)
        if self.p2: self.cog.processing_users.discard(self.p2.id)
        
        if POINT_MANAGER_AVAILABLE and self.message:
            try:
                # 타임아웃 시 배팅금 환불 (수수료 없이 100% 환불)
                await point_manager.add_point(self.bot, self.message.guild.id, str(self.p1.id), self.bet)
                if self.p2: await point_manager.add_point(self.bot, self.message.guild.id, str(self.p2.id), self.bet)
                await self.message.edit(content="⏰ 시간 초과로 게임이 무효화되어 환불되었습니다.", embed=None, view=None)
            except: pass
        self.stop()

    async def check_user(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        # P2 참가 처리 (공개 대전 시)
        if self.p2 is None:
            if user.id == self.p1.id:
                await interaction.response.send_message("❌ 상대방을 기다리고 있습니다.", ephemeral=True)
                return False
        
            # 중복 참여 방지
            if user.id in self.cog.processing_users:
                await interaction.response.send_message("❌ 이미 다른 게임을 진행 중입니다.", ephemeral=True)
                return False

            if POINT_MANAGER_AVAILABLE:
                bal = await point_manager.get_point(self.bot, interaction.guild_id, str(user.id))
                if (bal or 0) < self.bet:
                    await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
                    return False
                await point_manager.add_point(self.bot, interaction.guild_id, str(user.id), -self.bet)
        
            self.p2 = user
            self.p2_cards = [self.game.draw_card(), self.game.draw_card()]
            self.cog.processing_users.add(user.id)
            await interaction.channel.send(f"🃏 {user.mention}님이 대결에 참가했습니다!", delete_after=5)
        
            # P2가 참가하자마자 화면 갱신
            await self.update_view()
            # 참가 버튼 누른 것 자체가 하나의 액션이므로 여기서 return False로 끊지 말고 진행하거나 defer 처리
            if not interaction.response.is_done():
                await interaction.response.defer()
            return False # 참가 직후에 바로 히트/스탠드를 누를 수는 없게 설계 (한 번 더 눌러야 함)

        if user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
            return False

        # 권한 체크
        if user.id not in [self.p1.id, self.p2.id]:
            await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_user(interaction): return
        uid = interaction.user.id
        if (uid == self.p1.id and self.p1_done) or (uid == self.p2.id and self.p2_done):
            return await interaction.response.send_message("이미 턴을 마쳤습니다.", ephemeral=True)

        cards = self.p1_cards if uid == self.p1.id else self.p2_cards
        cards.append(self.game.draw_card())
        if self.game.calculate_hand_value(cards) > 21:
            if uid == self.p1.id: self.p1_done = True
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
        for p, cards, done in [(self.p1, self.p1_cards, self.p1_done), (self.p2, self.p2_cards, self.p2_done)]:
            if not p:
                embed.add_field(name="👤 상대 대기 중", value="⚔️ 대기")
                continue
            val = self.game.calculate_hand_value(cards)
            status = '💥 버스트!' if val > 21 else ('✋ 스탠드' if done else '🃏 고민 중')
            embed.add_field(name=f"👤 {p.display_name}", value=f"점수: {val}\n상태: {status}")
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
            reward_msg = f"💰 {winner.mention} 승리! **{reward:,}원** 획득!\n*20%의 딜러비가 차감된 후 지급됩니다."
            if winner.id == self.p1.id: p1_payout = reward
            else: p2_payout = reward
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_msg = f"🤝 무승부! **{refund:,}원**이 환불되었습니다.\n*20%의 딜러비가 차감된 후 지급됩니다."
            p1_payout = p2_payout = refund

        record_blackjack_game(str(self.p1.id), self.p1.display_name, self.bet, p1_payout, winner == self.p1)
        record_blackjack_game(str(self.p2.id), self.p2.display_name, self.bet, p2_payout, winner == self.p2)

        final_embed = discord.Embed(title="🏁 게임 종료", description=f"**{result}**\n{reward_msg}\n\n"
                                                                  f"{self.p1.mention}: {v1}점\n{self.p2.mention}: {v2}점", 
                                    color=discord.Color.gold())
        await self.message.edit(embed=final_embed, view=None)
        
        # [중요] 게임 종료 후 모든 참가자 세션 해제
        self.cog.processing_users.discard(self.p1.id)
        if self.p2: self.cog.processing_users.discard(self.p2.id)
        self.stop()

# 싱글 블랙잭 View
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
        embed.add_field(name="주민", value=f"{self.game.get_card_display(self.game.player_cards)}\n({p_val}점)")
        d_display = self.game.get_card_display(self.game.dealer_cards, hide_first=not final)
        embed.add_field(name="딜러", value=f"{d_display}\n({'??' if not final else d_val}점)")
        return embed

    async def end_game(self, interaction: discord.Interaction = None):
        # 1. 게임 종료 상태 확정 (중복 실행 방지)
        if getattr(self, "_already_ended", False):
            return
        self._already_ended = True
        
        self.game.game_over = True
        self.game.determine_winner()
        
        payout = 0
        is_win = self.game.result in ["win", "dealer_bust"]
        is_blackjack_win = self.game.is_blackjack(self.game.player_cards) and is_win

        if is_blackjack_win:
            # 블랙잭 승리 (배팅금의 2.5배에서 20% 수수료 제외)
            payout = int(self.bet * 2.5 * WINNER_RETENTION) 
        elif is_win:
            # 일반 승리 (배팅금의 2배에서 20% 수수료 제외)
            payout = int(self.bet * 2 * WINNER_RETENTION)
        elif self.game.result == "push":
            # 무승부 (배팅금 그대로 환불받고 싶다면 PUSH_RETENTION을 1.0으로 수정 필요)
            payout = int(self.bet * PUSH_RETENTION)

        # 3. 포인트 지급 (실제 지급은 여기서 딱 한 번만!)
        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)

        record_blackjack_game(str(self.user.id), self.user.display_name, self.bet, payout, is_win)

        final_embed = self.create_game_embed(final=True)
        result_text = f"{self.game.result.upper()} (정산: {payout:,}원)\n*20%의 딜러비가 차감된 후 지급됩니다."
        if is_blackjack_win:
            result_text = f"♣️ BLACKJACK! {result_text}"
        final_embed.add_field(name="결과", value=result_text, inline=False)
        
        # 3. 응답 처리
        try:
            if interaction and not interaction.response.is_done(): 
                await interaction.response.edit_message(embed=final_embed, view=None)
            elif self.message:
                await self.message.edit(embed=final_embed, view=None)
        except: pass
        
        # 4. 게임 종료 후 유저 고정 해제
        self.cog.processing_users.discard(self.user.id)

# 메인 Cog. 명령어
class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.processing_users = set() # 현재 게임을 플레이 중인 사용자 ID

    @app_commands.command(name="블랙잭", description="블랙잭을 시작합니다.(100원 ~ 6,000원)")
    @app_commands.describe(배팅="배팅할 금액을 입력하세요. (100원 ~ 6,000원)")
    async def blackjack_game(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'blackjack' 권한이 있는지 체크 (channel_config.py의 value="blackjack"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "blackjack", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )

        user_id = interaction.user.id
        
        # 이미 게임을 플레이 중인지 확인
        if user_id in self.processing_users:
            return await interaction.response.send_message("❌ 이미 블랙잭 게임을 플레이 중입니다.", ephemeral=True)
        
        # 잔액 체크
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(user_id))
        if balance < 배팅:
            return await interaction.response.send_message(f"❌ 잔액이 부족합니다. (보유: {balance:,}원)", ephemeral=True)

        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)

        # 게임 시작 모드 선택
        self.processing_users.add(user_id)
        
        view = BlackjackModeSelectView(self, self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🃏 **블랙잭 모드 선택** (배팅: {배팅:,}원)", view=view)
        view.message = await interaction.original_response()
        
async def setup(bot):
    await bot.add_cog(BlackjackCog(bot))