# blackjack.py - 블랙잭 게임 (통계 기록 추가)
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from typing import List, Dict, Tuple
import random

# ✅ 통계 시스템 안전 임포트 (추가)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (블랙잭)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (블랙잭)")

# point_manager 임포트
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    
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

# ✅ 통계 기록 헬퍼 함수 (추가)
def record_blackjack_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    """블랙잭 게임 통계 기록"""
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(
                user_id=user_id,
                username=username,
                game_name="blackjack",
                is_win=is_win,
                bet=bet,
                payout=payout
            )
        except Exception as e:
            print(f"❌ 블랙잭 통계 기록 실패: {e}")

# ✅ 카드 덱 정의
CARD_DECK = {
    # 스페이드 (♠)
    'A♠': ('🂡', 'A♠'), '2♠': ('🂢', '2♠'), '3♠': ('🂣', '3♠'), '4♠': ('🂤', '4♠'), '5♠': ('🂥', '5♠'),
    '6♠': ('🂦', '6♠'), '7♠': ('🂧', '7♠'), '8♠': ('🂨', '8♠'), '9♠': ('🂩', '9♠'), '10♠': ('🂪', '10♠'),
    'J♠': ('🂫', 'J♠'), 'Q♠': ('🂭', 'Q♠'), 'K♠': ('🂮', 'K♠'),
    
    # 하트 (♥)
    'A♥': ('🂱', 'A♥'), '2♥': ('🂲', '2♥'), '3♥': ('🂳', '3♥'), '4♥': ('🂴', '4♥'), '5♥': ('🂵', '5♥'),
    '6♥': ('🂶', '6♥'), '7♥': ('🂷', '7♥'), '8♥': ('🂸', '8♥'), '9♥': ('🂹', '9♥'), '10♥': ('🂺', '10♥'),
    'J♥': ('🂻', 'J♥'), 'Q♥': ('🂽', 'Q♥'), 'K♥': ('🂾', 'K♥'),
    
    # 다이아몬드 (♦)
    'A♦': ('🃁', 'A♦'), '2♦': ('🃂', '2♦'), '3♦': ('🃃', '3♦'), '4♦': ('🃄', '4♦'), '5♦': ('🃅', '5♦'),
    '6♦': ('🃆', '6♦'), '7♦': ('🃇', '7♦'), '8♦': ('🃈', '8♦'), '9♦': ('🃉', '9♦'), '10♦': ('🃊', '10♦'),
    'J♦': ('🃋', 'J♦'), 'Q♦': ('🃍', 'Q♦'), 'K♦': ('🃎', 'K♦'),
    
    # 클럽 (♣)
    'A♣': ('🃑', 'A♣'), '2♣': ('🃒', '2♣'), '3♣': ('🃓', '3♣'), '4♣': ('🃔', '4♣'), '5♣': ('🃕', '5♣'),
    '6♣': ('🃖', '6♣'), '7♣': ('🃗', '7♣'), '8♣': ('🃘', '8♣'), '9♣': ('🃙', '9♣'), '10♣': ('🃚', '10♣'),
    'J♣': ('🃛', 'J♣'), 'Q♣': ('🃝', 'Q♣'), 'K♣': ('🃞', 'K♣')
}

# 카드 뒷면
CARD_BACK = ('🂠', '???')

# ✅ 블랙잭 게임 로직 클래스
class BlackjackGame:
    def __init__(self, bet: int):
        self.bet = bet
        self.deck = list(CARD_DECK.keys())
        random.shuffle(self.deck)
        
        self.player_cards = []
        self.dealer_cards = []
        self.game_over = False
        self.player_stood = False
        self.result = None
        
        # 초기 카드 2장씩 배분
        self.player_cards.append(self.draw_card())
        self.dealer_cards.append(self.draw_card())
        self.player_cards.append(self.draw_card())
        self.dealer_cards.append(self.draw_card())
    
    def draw_card(self) -> str:
        """덱에서 카드 한 장 뽑기"""
        if self.deck:
            return self.deck.pop()
        else:
            # 덱이 비었으면 새로 섞기
            self.deck = list(CARD_DECK.keys())
            random.shuffle(self.deck)
            return self.deck.pop()
    
    def get_card_value(self, card: str) -> int:
        """카드의 숫자 값 계산"""
        rank = card.split('♠')[0].split('♥')[0].split('♦')[0].split('♣')[0]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11  # 에이스는 일단 11로 계산
        else:
            return int(rank)
    
    def calculate_hand_value(self, cards: List[str]) -> int:
        """핸드의 총 값 계산 (에이스 처리 포함)"""
        total = 0
        aces = 0
        
        for card in cards:
            value = self.get_card_value(card)
            if card.startswith('A'):
                aces += 1
            total += value
        
        # 에이스를 1로 바꿔서 21을 넘지 않도록 조정
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        
        return total
    
    def is_blackjack(self, cards: List[str]) -> bool:
        """블랙잭인지 확인 (A + 10점 카드)"""
        if len(cards) != 2:
            return False
        
        values = [self.get_card_value(card) for card in cards]
        return (11 in values or 1 in values) and 10 in values
    
    def get_card_display(self, cards: List[str], hide_first: bool = False) -> str:
        """카드들을 이모지+텍스트로 표시"""
        display_parts = []
        for i, card in enumerate(cards):
            if hide_first and i == 0:
                emoji, text = CARD_BACK
                display_parts.append(f"{emoji}({text})")
            else:
                emoji, text = CARD_DECK[card]
                display_parts.append(f"{emoji}({text})")
        return " ".join(display_parts)
    
    def hit_player(self):
        """플레이어가 카드 한 장 더 받기"""
        if not self.game_over:
            self.player_cards.append(self.draw_card())
            if self.calculate_hand_value(self.player_cards) > 21:
                self.game_over = True
                self.result = "bust"
    
    def stand_player(self):
        """플레이어가 스탠드"""
        self.player_stood = True
        self.dealer_play()
    
    def dealer_play(self):
        """딜러 자동 플레이"""
        while self.calculate_hand_value(self.dealer_cards) < 17:
            self.dealer_cards.append(self.draw_card())
        
        self.game_over = True
        self.determine_winner()
    
    def determine_winner(self):
        """승부 판정"""
        player_value = self.calculate_hand_value(self.player_cards)
        dealer_value = self.game.calculate_hand_value(self.game.dealer_cards)
        
        player_bj = self.is_blackjack(self.player_cards)
        dealer_bj = self.is_blackjack(self.dealer_cards)
        
        if self.result == "bust":
            # 이미 버스트로 설정됨
            pass
        elif player_bj and dealer_bj:
            self.result = "push"
        elif player_bj and not dealer_bj:
            self.result = "blackjack"
        elif dealer_bj and not player_bj:
            self.result = "dealer_blackjack"
        elif dealer_value > 21:
            self.result = "dealer_bust"
        elif player_value > dealer_value:
            self.result = "win"
        elif player_value < dealer_value:
            self.result = "lose"
        else:
            self.result = "push"

# ✅ 블랙잭 게임 View
class BlackjackView(View):
    def __init__(self, user: discord.User, bet: int):
        super().__init__(timeout=120)
        self.user = user
        self.bet = bet
        self.game = BlackjackGame(bet)
        self.message = None
    
    @discord.ui.button(label="🃏 히트", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 조작할 수 있습니다.", ephemeral=True)
        
        if self.game.game_over:
            return await interaction.response.send_message("❗ 이미 게임이 종료되었습니다.", ephemeral=True)
        
        # 카드 한 장 더
        self.game.hit_player()
        
        if self.game.game_over:
            await self.end_game(interaction)
        else:
            # 게임 상태 업데이트
            embed = self.create_game_embed()
            await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="✋ 스탠드", style=discord.ButtonStyle.secondary)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 조작할 수 있습니다.", ephemeral=True)
        
        if self.game.game_over:
            return await interaction.response.send_message("❗ 이미 게임이 종료되었습니다.", ephemeral=True)
        
        # 스탠드 처리
        self.game.stand_player()
        await self.end_game(interaction)
    
    def create_game_embed(self, final: bool = False) -> discord.Embed:
        """게임 상태 임베드 생성"""
        player_value = self.game.calculate_hand_value(self.game.player_cards)
        dealer_value = self.game.calculate_hand_value(self.game.dealer_cards)
        
        if final:
            title = "🃏 블랙잭 - 게임 종료"
            color = self.get_result_color()
            dealer_cards_display = self.game.get_card_display(self.game.dealer_cards, hide_first=False)
        else:
            title = "🃏 블랙잭 - 진행 중"
            color = discord.Color.purple()
            dealer_cards_display = self.game.get_card_display(self.game.dealer_cards, hide_first=True)
            dealer_value = self.game.get_card_value(self.game.dealer_cards[1])  # 보이는 카드만
        
        embed = discord.Embed(title=title, color=color)
        
        # 플레이어 정보
        embed.add_field(
            name=f"👤 {self.user.display_name}의 카드",
            value=f"{self.game.get_card_display(self.game.player_cards)}\n**총 점수**: {player_value}점",
            inline=False
        )
        
        # 딜러 정보
        if final:
            embed.add_field(
                name="🤖 딜러의 카드",
                value=f"{dealer_cards_display}\n**총 점수**: {dealer_value}점",
                inline=False
            )
        else:
            embed.add_field(
                name="🤖 딜러의 카드",
                value=f"{dealer_cards_display}\n**보이는 점수**: {dealer_value}점",
                inline=False
            )
        
        if not final:
            embed.add_field(
                name="⚠️ 주의",
                value="21점을 초과하면 버스트로 패배\n(21 초과 시 버스트)",
                inline=True
            )
            
            embed.add_field(
                name="🎮 다음 행동",
                value="• **히트**: 카드 한 장 더\n• **스탠드**: 현재 상태로 승부",
                inline=True
            )
        
        embed.set_footer(text=f"배팅 금액: {self.bet:,}원")
        return embed
    
    def get_result_color(self) -> discord.Color:
        """결과에 따른 색상 반환"""
        if self.game.result in ["blackjack", "win", "dealer_bust"]:
            return discord.Color.green()
        elif self.game.result == "push":
            return discord.Color.gold()
        else:
            return discord.Color.red()
    
    async def end_game(self, interaction: discord.Interaction = None):
        """게임 종료 처리"""
        uid = str(self.user.id)
        
        # 모든 버튼 비활성화
        for child in self.children:
            child.disabled = True
        
        # 결과에 따른 포인트 처리 및 통계 기록
        reward = 0
        is_win = False
        
        if self.game.result == "blackjack":
            reward = int(self.bet * 2.5)  # 블랙잭은 2.5배
            result_text = "🎉 블랙잭! 축하합니다!"
            result_detail = f"+{reward:,}원 획득 (2.5배!)"
            is_win = True
        elif self.game.result in ["win", "dealer_bust"]:
            reward = self.bet * 2
            if self.game.result == "dealer_bust":
                result_text = "🎉 딜러 버스트로 승리!"
            else:
                result_text = "🎉 승리!"
            result_detail = f"+{reward:,}원 획득 (2배)"
            is_win = True
        elif self.game.result == "push":
            reward = self.bet  # 배팅 금액 반환
            result_text = "🤝 무승부 (푸시)!"
            result_detail = "배팅 금액 반환"
            is_win = False
        else:  # bust, lose, dealer_blackjack
            reward = 0
            if self.game.result == "bust":
                result_text = "💥 버스트! 21을 초과했습니다."
            elif self.game.result == "dealer_blackjack":
                result_text = "🤖 딜러 블랙잭으로 패배!"
            else:
                result_text = "😢 패배!"
            result_detail = f"-{self.bet:,}원 차감"
            is_win = False

        # ✅ 통계 기록 (추가)
        record_blackjack_game(uid, self.user.display_name, self.bet, reward, is_win)
        
        # 포인트 지급
        if POINT_MANAGER_AVAILABLE:
            # interaction이 None일 수 있으므로, guild_id를 안전하게 가져오기
            guild_id = interaction.guild_id if interaction else None
            await point_manager.add_point(self.bot, guild_id, uid, reward)
        
        # 최종 잔액 조회
        final_balance = await point_manager.get_point(self.bot, guild_id, uid) if POINT_MANAGER_AVAILABLE else 10000
        
        # 최종 결과 임베드
        embed = self.create_game_embed(final=True)
        embed.add_field(name="🏆 결과", value=result_text, inline=True)
        embed.add_field(name="💰 획득/손실", value=result_detail, inline=True)
        embed.add_field(name="💳 현재 잔액", value=f"{final_balance:,}원", inline=True)
        
        # 게임 통계 정보
        player_value = self.game.calculate_hand_value(self.game.player_cards)
        dealer_value = self.game.calculate_hand_value(self.game.dealer_cards)
        embed.add_field(
            name="📊 최종 점수",
            value=f"플레이어: {player_value}점\n딜러: {dealer_value}점",
            inline=True
        )
        
        # 블랙잭 여부 표시
        player_bj = self.game.is_blackjack(self.game.player_cards)
        dealer_bj = self.game.is_blackjack(self.game.dealer_cards)
        bj_status = []
        if player_bj:
            bj_status.append("플레이어 블랙잭")
        if dealer_bj:
            bj_status.append("딜러 블랙잭")
        
        if bj_status:
            embed.add_field(
                name="⭐ 특수",
                value="\n".join(bj_status),
                inline=True
            )
        
        # 게임 규칙 정보
        embed.add_field(
            name="📋 블랙잭 규칙",
            value="• **목표**: 21에 가깝게\n• **A**: 1 또는 11\n• **J,Q,K**: 10점\n• **블랙잭**: 2.5배\n• **승리**: 2배\n• **딜러**: 17 이상 스탠드",
            inline=False
        )
        
        try:
            if interaction and not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await self.message.edit(embed=embed, view=self)
        except:
            await self.message.edit(embed=embed, view=self)
        self.stop()
    
    async def on_timeout(self):
        try:
            # 타임아웃 시 자동 스탠드
            if not self.game.game_over:
                self.game.stand_player()
                # 게임 종료 처리를 직접 실행
                uid = str(self.user.id)
                
                # 결과에 따른 포인트 처리
                reward = 0
                is_win = False
                
                if self.game.result == "blackjack":
                    reward = int(self.bet * 2.5)
                    is_win = True
                elif self.game.result in ["win", "dealer_bust"]:
                    reward = self.bet * 2
                    is_win = True
                elif self.game.result == "push":
                    reward = self.bet
                    is_win = False
                else:
                    reward = 0
                    is_win = False

                # 통계 기록 및 포인트 지급
                record_blackjack_game(uid, self.user.display_name, self.bet, reward, is_win)
                if POINT_MANAGER_AVAILABLE:
                    # interaction이 None일 수 있으므로, guild_id를 안전하게 가져오기
                    # on_timeout에서는 interaction 객체가 없으므로, self.message.guild.id를 사용
                    guild_id = self.message.guild.id if self.message and self.message.guild else None
                    await point_manager.add_point(self.bot, guild_id, uid, reward)
            
            # 모든 버튼 비활성화
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary
            
            embed = discord.Embed(
                title="⏰ 블랙잭 게임 - 시간 만료",
                description="시간이 초과되어 자동으로 스탠드 처리되었습니다.",
                color=discord.Color.orange()
            )
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"블랙잭 타임아웃 처리 오류: {e}")

# ✅ 블랙잭 게임 Cog
class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="블랙잭", description="🃏 블랙잭 게임을 플레이합니다.")
    @app_commands.describe(배팅="배팅할 현금 (기본값: 10원, 최대 2,000원)")
    async def blackjack_game(self, interaction: discord.Interaction, 배팅: int = 10):
        try:
            uid = str(interaction.user.id)

            # 등록 확인
            if not await point_manager.is_registered(self.bot, interaction.guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)

            # 배팅 금액 검증
            if 배팅 < 1 or 배팅 > 2000:
                return await interaction.response.send_message("❗ 배팅은 1~2,000원 사이여야 합니다.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, interaction.guild_id, uid)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원", 
                    ephemeral=True
                )

            # 배팅 금액 차감
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, interaction.guild_id, uid, -배팅)

            # 게임 시작
            embed = discord.Embed(
                title="🃏 블랙잭 게임 시작!",
                description="21에 가장 가깝게 만들어보세요!",
                color=discord.Color.purple()
            )
            
            embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
            embed.add_field(name="🎯 목표", value="21에 가깝게!", inline=True)
            embed.add_field(name="🏆 블랙잭 보상", value="2.5배", inline=True)
            
            embed.add_field(
                name="📋 게임 규칙",
                value="• **A**: 1 또는 11점\n• **J, Q, K**: 10점\n• **딜러**: 17 이상에서 스탠드\n• **블랙잭**: A + 10점 카드 = 2.5배\n• **일반 승리**: 2배 지급",
                inline=False
            )
            
            embed.add_field(
                name="🎮 조작법",
                value="• **히트**: 카드 한 장 더\n• **스탠드**: 현재 상태로 승부\n• **21 초과**: 자동 패배 (버스트)",
                inline=False
            )
            
            embed.set_footer(text="히트 또는 스탠드를 선택하세요!")

            view = BlackjackView(interaction.user, 배팅)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            
            # 게임 상황으로 즉시 업데이트
            game_embed = view.create_game_embed()
            await view.message.edit(embed=game_embed, view=view)
            
            # 즉시 블랙잭 체크
            if view.game.is_blackjack(view.game.player_cards):
                view.game.game_over = True
                view.game.determine_winner()
                # 블랙잭인 경우 즉시 종료 처리
                uid = str(interaction.user.id)
                reward = int(배팅 * 2.5)
                record_blackjack_game(uid, interaction.user.display_name, 배팅, reward, True)
                if POINT_MANAGER_AVAILABLE:
                    await point_manager.add_point(self.bot, interaction.guild_id, uid, reward)
                
                # 최종 결과 표시
                final_embed = view.create_game_embed(final=True)
                final_embed.add_field(name="🏆 결과", value="🎉 블랙잭! 축하합니다!", inline=True)
                final_embed.add_field(name="💰 획득", value=f"+{reward:,}원 (2.5배!)", inline=True)
                final_balance = await point_manager.get_point(self.bot, interaction.guild_id, uid) if POINT_MANAGER_AVAILABLE else 10000
                final_embed.add_field(name="💳 현재 잔액", value=f"{final_balance:,}원", inline=True)
                
                # 버튼 비활성화
                for child in view.children:
                    child.disabled = True
                
                await view.message.edit(embed=final_embed, view=view)

        except Exception as e:
            print(f"블랙잭 게임 오류: {e}")
            try:
                await interaction.response.send_message("❌ 게임 시작 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(BlackjackCog(bot))
    print("✅ 블랙잭 게임 (통계 기록 포함) 로드 완료")