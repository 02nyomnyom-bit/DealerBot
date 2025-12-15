# dice_game.py - 주사위 게임 (통계 기록 추가)
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from typing import Literal, Optional
import random

# ✅ 통계 시스템 안전 임포트 (추가)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (주사위)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (주사위)")

# point_manager 임포트
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    
    class MockPointManager:
        @staticmethod
        async def is_registered(bot, guild_id, user_id): 
            return True
    
        @staticmethod
        async def get_point(bot, guild_id, user_id):
            return 10000
    
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount):
            return True
    
        @staticmethod
        async def register_user(bot, guild_id, user_id):
            pass

    point_manager = MockPointManager()

# 주사위 이모지
DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

# ✅ 통계 기록 헬퍼 함수 (추가)
def record_dice_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    """주사위 게임 통계 기록"""
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(
                user_id=user_id,
                username=username,
                game_name="dice_game",
                is_win=is_win,
                bet=bet,
                payout=payout
            )
        except Exception as e:
            print(f"❌ 주사위 통계 기록 실패: {e}")

# ✅ 싱글 주사위 게임 View
class SingleDiceView(View):
    def __init__(self, bot: commands.Bot, user: discord.User, bet: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.bet = bet
        self.message = None  # 메시지 저장용

    @discord.ui.button(label="🎲 주사위 굴리기", style=discord.ButtonStyle.primary)
    async def roll_dice(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 주사위를 굴릴 수 있습니다.", ephemeral=True)

        uid = str(interaction.user.id)
        gid = str(interaction.guild_id) 
        
        user_roll = random.randint(1, 6)
        bot_roll = random.randint(1, 6)
        
        if user_roll > bot_roll:
            reward = self.bet * 2
            await point_manager.add_point(self.bot, gid, uid, reward)
            result = f"🎉 승리! +{reward:,}원"
            result_color = "🟢"
            is_win = True
            payout = reward
        elif user_roll < bot_roll:
            await point_manager.add_point(self.bot, gid, uid, -self.bet)
            result = f"😢 패배! -{self.bet:,}원"
            result_color = "🔴"
            is_win = False
            payout = 0
        else:
            result = "🤝 무승부! 포인트 변동 없음"
            result_color = "🟡"
            is_win = False
            payout = self.bet

        record_dice_game(uid, interaction.user.display_name, self.bet, payout, is_win)

        button.disabled = True
        button.label = "게임 완료"
        button.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(
            content=(
                f"{result_color} **주사위 게임 결과** {result_color}\n\n"
                f"🎯 **{self.user.display_name}**: {DICE_EMOJIS[user_roll]} ({user_roll})\n"
                f"🤖 **딜러**: {DICE_EMOJIS[bot_roll]} ({bot_roll})\n\n"
                f"🏆 **결과**: {result}\n"
                f"💰 **현재 잔액**: {await point_manager.get_point(self.bot, gid, uid):,}원"
            ),
            view=self
        )
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
            item.label = "시간 만료"
            item.style = discord.ButtonStyle.secondary
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except Exception:
                pass

# ✅ 멀티 주사위 게임 View
class MultiDiceView(View):
    def __init__(self, bot: commands.Bot, player1: discord.User, bet: int, opponent: Optional[discord.User] = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.player1 = player1
        self.bet = bet
        self.opponent = opponent
        self.player2 = None
        self.player1_roll = None
        self.player2_roll = None
        self.rolled_users = set()
        self.game_started = False
        self.message = None

    @discord.ui.button(label="🎲 게임 참여/주사위 굴리기", style=discord.ButtonStyle.success) # 버튼 라벨 수정
    async def join_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        uid = str(user.id)
        gid = str(interaction.guild_id)

        # 1. 포인트 등록/잔액 확인
        if not await point_manager.is_registered(self.bot, gid, uid):
            return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

        if await point_manager.get_point(self.bot, gid, uid) < self.bet:
            return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        # 2. 플레이어 검증 및 설정
        if self.opponent:
            if user not in [self.player1, self.opponent]:
                return await interaction.response.send_message("❌ 이 게임에 참여할 수 없습니다. 지정된 플레이어만 참여 가능합니다.", ephemeral=True)
            self.player2 = self.opponent # 지정 상대방이 참여하면 player2로 설정
        else:
            if user == self.player1:
                # 게임 시작 전: 첫 번째 플레이어는 단순히 대기 메시지
                if not self.game_started:
                    return await interaction.response.send_message("🎲 다른 플레이어가 참여하면 게임이 시작됩니다.", ephemeral=True)
                # 게임 시작 후: 주사위 굴리기 허용
                self.player2 = self.player2 if self.player2 else None # self.player2가 설정되어 있어야 함

            elif not self.player2: # 자유 참여 & 아직 player2 없음
                self.player2 = user
            
            elif user != self.player2: # 자유 참여 & 이미 player2 있음
                return await interaction.response.send_message("❌ 이미 다른 플레이어가 참여했습니다.", ephemeral=True)
        
        # 3. 게임 시작 로직
        if not self.game_started and self.player1 and self.player2:
            self.game_started = True
            button.style = discord.ButtonStyle.primary
            button.label = "🎲 주사위 굴리기" # 게임 시작 후 버튼 라벨 변경
            
            # 메시지 업데이트 (응답 유형 변경: 이미 original_response가 있으므로 edit)
            await interaction.response.edit_message(
                content=(
                    f"🎮 **멀티 주사위 게임이 시작되었습니다!**\n"
                    f"💰 배팅: {self.bet:,}원\n\n"
                    f"👤 **플레이어1**: {self.player1.mention}\n"
                    f"👤 **플레이어2**: {self.player2.mention}\n\n"
                    f"🎲 각자 버튼을 눌러 주사위를 굴려주세요!"
                ),
                view=self
            )
            # self.message는 이미 초기 /주사위 명령에서 설정됨.
        
        # 4. 주사위 굴리기 로직 (게임이 시작된 경우)
        elif self.game_started and user in [self.player1, self.player2]: # P1, P2 모두 굴릴 수 있도록 수정
            await self.roll_dice_logic(interaction, user)
        
        else:
            # 예상치 못한 상황 방지용
            return await interaction.response.send_message("⚠️ 게임 상태 오류. 잠시 후 다시 시도해 주세요.", ephemeral=True)


    async def roll_dice_logic(self, interaction: discord.Interaction, user: discord.User):
        if user.id in self.rolled_users:
            return await interaction.response.send_message("⚠️ 이미 주사위를 굴렸습니다.", ephemeral=True)

        roll = random.randint(1, 6)
        self.rolled_users.add(user.id)

        if user == self.player1:
            self.player1_roll = roll
        elif user == self.player2:
            self.player2_roll = roll
        else:
            # 이 경우는 발생하면 안되지만 안전 장치
            return await interaction.response.send_message("❌ 게임 플레이어가 아닙니다.", ephemeral=True)

        # 1. 첫 번째 플레이어 굴림 후 메시지 (공개로 수정)
        if len(self.rolled_users) == 1:
            # 기존 메시지를 수정하여 누가 굴렸는지 알림
            await interaction.response.edit_message(
                content=(
                    f"🎮 **멀티 주사위 게임 진행 중**\n"
                    f"💰 배팅: {self.bet:,}원\n\n"
                    f"👤 **{self.player1.display_name}**: {'굴림 완료' if self.player1_roll else '대기중...'}\n"
                    f"👤 **{self.player2.display_name}**: {'굴림 완료' if self.player2_roll else '대기중...'}\n\n"
                    f"✨ **알림**: {user.mention}님이 주사위를 굴렸습니다. 상대방을 기다리는 중..."
                ),
                view=self
            )
            return

        # 2. 두 번째 플레이어 굴림 후 최종 결과 처리
        await interaction.response.defer() # 응답 대기 (이후 edit/followup 사용)

        gid = str(interaction.guild_id)

        p1_id = str(self.player1.id)
        p2_id = str(self.player2.id)
        
        # 포인트 차감 (두 번째 굴림 시점에 최종 차감)
        # Note: join_game에서 잔액 확인을 했으므로, 여기서 차감/분배합니다.
        await point_manager.add_point(self.bot, gid, p1_id, -self.bet)
        await point_manager.add_point(self.bot, gid, p2_id, -self.bet)


        if self.player1_roll > self.player2_roll:
            await point_manager.add_point(self.bot, gid, p1_id, self.bet * 2)
            result_emoji = "🎉"
            result_text = f"{self.player1.mention} 승리!"
            record_dice_game(p1_id, self.player1.display_name, self.bet, self.bet * 2, True)
            record_dice_game(p2_id, self.player2.display_name, self.bet, 0, False)
        elif self.player1_roll < self.player2_roll:
            await point_manager.add_point(self.bot, gid, p2_id, self.bet * 2)
            result_emoji = "🎉"
            result_text = f"{self.player2.mention} 승리!"
            record_dice_game(p1_id, self.player1.display_name, self.bet, 0, False)
            record_dice_game(p2_id, self.player2.display_name, self.bet, self.bet * 2, True)
        else:
            # 무승부 시 배팅 금액 돌려주기 (차감 후 원금만 다시 추가)
            await point_manager.add_point(self.bot, gid, p1_id, self.bet)
            await point_manager.add_point(self.bot, gid, p2_id, self.bet)
            result_emoji = "🤝"
            result_text = "무승부!"
            record_dice_game(p1_id, self.player1.display_name, self.bet, self.bet, False)
            record_dice_game(p2_id, self.player2.display_name, self.bet, self.bet, False)

        for item in self.children:
            item.disabled = True

        # 최종 결과를 기존 메시지에 공개적으로 수정 (공개로 수정됨)
        try:
            if self.message:
                await self.message.edit(content=(
                    f"{result_emoji} **멀티 주사위 게임 최종 결과** {result_emoji}\n\n"
                    f"🎯 **{self.player1.display_name}**: {DICE_EMOJIS[self.player1_roll]} ({self.player1_roll})\n"
                    f"🎯 **{self.player2.display_name}**: {DICE_EMOJIS[self.player2_roll]} ({self.player2_roll})\n\n"
                    f"🏆 **결과**: {result_text}\n"
                    f"💰 **배팅 금액**: {self.bet:,}원\n\n"
                    f"💰 **{self.player1.display_name} 잔액**: {await point_manager.get_point(self.bot, gid, p1_id):,}원\n"
                    f"💰 **{self.player2.display_name} 잔액**: {await point_manager.get_point(self.bot, gid, p2_id):,}원"
                ), view=self)
            else:
                # message가 설정되지 않은 경우 (예외 상황 대비)
                await interaction.followup.send(content=(
                    f"{result_emoji} **멀티 주사위 게임 최종 결과** {result_emoji}\n\n"
                    f"🎯 **{self.player1.display_name}**: {DICE_EMOJIS[self.player1_roll]} ({self.player1_roll})\n"
                    f"🎯 **{self.player2.display_name}**: {DICE_EMOJIS[self.player2_roll]} ({self.player2_roll})\n\n"
                    f"🏆 **결과**: {result_text}\n"
                    f"💰 **배팅 금액**: {self.bet:,}원\n\n"
                    f"💰 **{self.player1.display_name} 잔액**: {await point_manager.get_point(self.bot, gid, p1_id):,}원\n"
                    f"💰 **{self.player2.display_name} 잔액**: {await point_manager.get_point(self.bot, gid, p2_id):,}원"
                ), ephemeral=False) # 결과는 공개
        except Exception as e:
            print(f"결과 메시지 전송 실패: {e}")
            pass
        
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
            item.label = "시간 만료"
            item.style = discord.ButtonStyle.secondary
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except Exception:
                pass

# ✅ 주사위 게임 Cog
class DiceGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="주사위", description="주사위 게임을 플레이합니다.")
    @app_commands.describe(
        모드="싱글(봇과 대결) 또는 멀티(다른 유저와 대결)",
        배팅="배팅할 현금 (기본값: 10원, 싱글 모드 최대 5,000원)",
        상대방="멀티 모드에서 특정 상대방 지정 (선택사항)"
    )
    async def dice_game(
        self,
        interaction: discord.Interaction,
        모드: Literal["싱글", "멀티"],
        배팅: int = 10,
        상대방: Optional[discord.User] = None
    ):
        uid = str(interaction.user.id)
        gid = str(interaction.guild_id) 

        if not await point_manager.is_registered(self.bot, gid, uid):
            return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

        if 배팅 < 10:
            return await interaction.response.send_message("❗ 배팅 금액은 10원 이상이어야 합니다.", ephemeral=True)

        if await point_manager.get_point(self.bot, gid, uid) < 배팅:
            return await interaction.response.send_message("❌ 잔액이 부족합니다!", ephemeral=True)

        if 모드 == "싱글":
            if 배팅 > 5000:
                return await interaction.response.send_message("❗ 싱글 모드는 최대 5,000원까지 배팅 가능합니다.", ephemeral=True)

            embed = discord.Embed(
                title="🎲 싱글 주사위 게임",
                description=f"**배팅**: {배팅:,}원\n**플레이어**: {interaction.user.mention}\n\n주사위를 굴려 딜러보다 높은 숫자를 내세요!",
                color=discord.Color.blue()
            )
            embed.set_footer(text="더 높은 숫자가 나오면 승리! (배율: 2배)")

            view = SingleDiceView(self.bot, interaction.user, 배팅)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()

        else:
            if 상대방:
                if 상대방.id == interaction.user.id:
                    return await interaction.response.send_message("❌ 자기 자신과는 게임할 수 없습니다.", ephemeral=True)
                
                if not await point_manager.is_registered(self.bot, gid, str(상대방.id)):
                    return await interaction.response.send_message("❌ 상대방이 등록되어 있지 않습니다.", ephemeral=True)
                
                if await point_manager.get_point(self.bot, gid, str(상대방.id)) < 배팅:
                    return await interaction.response.send_message("❌ 상대방의 잔액이 부족합니다.", ephemeral=True)

            embed = discord.Embed(
                title="🎲 멀티 주사위 게임",
                description=(
                    f"**배팅**: {배팅:,}원\n"
                    f"**플레이어1**: {interaction.user.mention}\n"
                    f"**플레이어2**: {상대방.mention if 상대방 else '참여자 대기 중...'}\n\n"
                    f"{('지정된 상대방이 버튼을 눌러 참여해주세요!' if 상대방 else '누구나 버튼을 눌러 참여 가능합니다!')}"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text="더 높은 숫자가 나오면 승리! (승자가 모든 배팅 금액 획득)")

            view = MultiDiceView(self.bot, interaction.user, 배팅, opponent=상대방)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()

async def setup(bot: commands.Bot):
    await bot.add_cog(DiceGameCog(bot))
    print("✅ 주사위 게임 (통계 기록 포함) 로드 완료")