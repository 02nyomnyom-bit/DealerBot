# yabawi_game.py - 야바위 게임 (통계 기록 추가) - 핵심 부분만
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
import random
import asyncio

# ✅ 통계 시스템 안전 임포트 (추가)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (야바위)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (야바위)")

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
            pass
        @staticmethod
        async def register_user(bot, guild_id, user_id):
            pass
    
    point_manager = MockPointManager()

# ✅ 통계 기록 헬퍼 함수 (추가)
def record_yabawi_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    """야바위 게임 통계 기록"""
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(
                user_id=user_id,
                username=username,
                game_name="yabawi",
                is_win=is_win,
                bet=bet,
                payout=payout
            )
        except Exception as e:
            print(f"❌ 야바위 통계 기록 실패: {e}")

# 게임 설정
SUCCESS_RATES = [0.6, 0.55, 0.5, 0.45, 0.4]  # 각 라운드별 성공률
MAX_CHALLENGES = 5
active_games_by_user = set()

class YabawiGameView(View):
    def __init__(self, bot: commands.Bot, user: discord.User, base_bet: int, guild_id: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user
        self.user_id = str(user.id)
        self.guild_id = guild_id
        self.base_bet = base_bet
        self.wins = 0
        self.current_pot = base_bet
        self.challenge_count = 0
        self.ended = False
        self.initial_bet_deducted = False
        self.real_position = random.randint(0, 2)
        self.message = None

        # 컵 버튼 3개 추가
        for i in range(3):
            self.add_item(CupButton("🥤", i, self))

    def reset_for_next(self):
        """다음 라운드 준비"""
        self.real_position = random.randint(0, 2)

    def disable_all(self):
        """모든 버튼 비활성화"""
        for item in self.children:
            item.disabled = True

    async def handle_choice(self, interaction: discord.Interaction, chosen_idx: int):
        """컵 선택 처리"""
        try:
            if interaction.user != self.user:
                return await interaction.response.send_message("❗ 본인만 선택할 수 있어요.", ephemeral=True)
            if self.ended:
                return await interaction.response.send_message("❗ 이미 게임이 끝났어요.", ephemeral=True)

            # 첫 게임 시작 시 배팅 금액 차감
            if not self.initial_bet_deducted:
                current_balance = await point_manager.get_point(self.bot, self.guild_id, self.user_id)
                if current_balance < self.base_bet:
                    return await interaction.response.send_message(
                        f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {self.base_bet:,}원", 
                        ephemeral=True
                    )
                
                if POINT_MANAGER_AVAILABLE:
                    await point_manager.add_point(self.bot, self.guild_id, self.user_id, -self.base_bet) 
                self.initial_bet_deducted = True

            self.challenge_count += 1
            success_rate = SUCCESS_RATES[min(self.wins, MAX_CHALLENGES - 1)]
            success = random.random() < success_rate

            # 컵 표시 함수
            def format_cups(chosen_idx: int, reveal: bool, real_idx: int, success: bool):
                cups = []
                for i in range(3):
                    if i == chosen_idx and i == real_idx and success:
                        cups.append("🤑")  # 성공 시 정답 선택
                    elif i == chosen_idx:
                        cups.append("🔵")  # 유저 선택
                    elif i == real_idx and reveal:
                        cups.append("💰")  # 실제 정답 위치 공개
                    else:
                        cups.append("⬜")  # 나머지
                return f"{' '.join(cups)}"

            cups_display = format_cups(chosen_idx, True, self.real_position, success)

            if success and chosen_idx == self.real_position:
                self.wins += 1
                self.current_pot *= 2
                
                embed = discord.Embed(
                    title="🎉 야바위 게임 - 성공!",
                    description=f"축하합니다! 정답을 맞췄습니다!",
                    color=discord.Color.green()
                )
                embed.add_field(name="🎯 결과", value=cups_display, inline=False)
                embed.add_field(name="🏆 연승", value=f"{self.wins}회", inline=True)
                embed.add_field(name="💰 잠재 보상", value=f"{self.current_pot:,}원", inline=True)

                self.clear_items()

                if self.wins >= MAX_CHALLENGES:
                    if POINT_MANAGER_AVAILABLE:
                        await point_manager.add_point(self.bot, self.guild_id, self.user_id, self.current_pot)
                    
                    # ✅ 통계 기록 (성공 - 최대 도전 완료)
                    record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, self.current_pot, True)
                    
                    self.ended = True
                    active_games_by_user.discard(self.user_id)
                    
                    embed.title = "🏁 야바위 게임 - 최대 도전 성공!"
                    embed.description = "모든 도전을 성공했습니다! 최종 보상을 획득했습니다!"
                    embed.add_field(name="💎 최종 보상", value=f"{self.current_pot:,}원", inline=False)
                    embed.add_field(name="💰 현재 잔액", value=f"{await point_manager.get_point(self.bot, self.guild_id, self.user_id):,}원", inline=True)
                    await interaction.response.edit_message(embed=embed, view=self)
                else:
                    self.add_item(ContinueButton(self))
                    self.add_item(StopButton(self))
                    embed.set_footer(text="다음 라운드를 도전하시겠습니까?")
                    
                    await interaction.response.edit_message(embed=embed, view=self)
            else:
                # 실패 처리
                consolation = 0
                if self.wins > 0:
                    consolation = self.base_bet * (2 ** (self.wins - 1))
                    if POINT_MANAGER_AVAILABLE:
                        await point_manager.add_point(self.bot, self.guild_id, self.user_id, consolation)

                # ✅ 통계 기록 (실패)
                final_payout = consolation if consolation > 0 else 0
                record_yabawi_game(self.user_id, self.user.display_name, self.base_bet, final_payout, False)

                self.ended = True
                active_games_by_user.discard(self.user_id)
                self.disable_all()

                embed = discord.Embed(
                    title="💥 야바위 게임 - 실패!",
                    description="아쉽습니다! 틀렸습니다.",
                    color=discord.Color.red()
                )
                embed.add_field(name="🎯 결과", value=cups_display, inline=False)
                embed.add_field(name="🏆 연승", value=f"{self.wins}회", inline=True)
                embed.add_field(name="🎁 위로 보상", value=f"{consolation:,}원" if consolation else "없음", inline=True)
                embed.add_field(name="💰 현재 잔액", value=f"{await point_manager.get_point(self.bot, self.guild_id, self.user_id):,}원", inline=True)
                
                await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            print(f"야바위 게임 선택 처리 오류: {e}")
            try:
                await interaction.response.send_message("❌ 게임 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ 컵 버튼
class CupButton(discord.ui.Button):
    def __init__(self, label: str, index: int, parent: YabawiGameView):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.index = index
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction):
        await self.parent_view.handle_choice(interaction, self.index)

# ✅ 중단 버튼 (통계 기록 추가)
class StopButton(discord.ui.Button):
    def __init__(self, view: YabawiGameView):
        super().__init__(label="🛑 중단", style=discord.ButtonStyle.secondary, row=1)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.view_ref.user:
                return await interaction.response.send_message("❗ 본인만 중단할 수 있어요.", ephemeral=True)
            if self.view_ref.ended:
                return await interaction.response.send_message("❗ 이미 끝난 게임이에요.", ephemeral=True)

            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.view_ref.bot, self.view_ref.guild_id, self.view_ref.user_id, self.view_ref.current_pot) 


            # ✅ 통계 기록 (중단 - 성공으로 간주)
            record_yabawi_game(self.view_ref.user_id, self.view_ref.user.display_name, 
                             self.view_ref.base_bet, self.view_ref.current_pot, True)

            self.view_ref.ended = True
            active_games_by_user.discard(self.view_ref.user_id)
            self.view_ref.disable_all()

            embed = discord.Embed(
                title="🛑 야바위 게임 - 중단",
                description="도전을 중단했습니다.",
                color=discord.Color.blue()
            )
            embed.add_field(name="🏆 연승", value=f"{self.view_ref.wins}회", inline=True)
            embed.add_field(name="💎 수령 금액", value=f"{self.view_ref.current_pot:,}원", inline=True)
            embed.add_field(name="💰 현재 잔액", value=f"{await point_manager.get_point(self.view_ref.bot, self.view_ref.guild_id, self.view_ref.user_id):,}원", inline=True)
            
            await interaction.response.edit_message(embed=embed, view=self.view_ref)
            
        except Exception as e:
            print(f"야바위 게임 중단 버튼 오류: {e}")
            try:
                await interaction.response.send_message("❌ 중단 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ 도전 버튼
class ContinueButton(discord.ui.Button):
    def __init__(self, view: YabawiGameView):
        super().__init__(label="🚀 도전!", style=discord.ButtonStyle.success, row=1)
        self.view_ref = view

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.view_ref.user:
                return await interaction.response.send_message("❗ 본인만 도전할 수 있어요.", ephemeral=True)

            self.view_ref.reset_for_next()
            self.view_ref.clear_items()

            for i in range(3):
                self.view_ref.add_item(CupButton("🥤", i, self.view_ref))
            self.view_ref.add_item(StopButton(self.view_ref))

            next_stage = self.view_ref.wins + 1
            
            embed = discord.Embed(
                title=f"🔥 야바위 게임 - {next_stage}단계",
                description="새로운 도전이 시작됩니다!",
                color=discord.Color.blue()
            )
            embed.add_field(name="🎯 현재 단계", value=f"{next_stage}/{MAX_CHALLENGES}", inline=True)
            embed.add_field(name="💰 잠재 보상", value=f"{self.view_ref.current_pot:,}원", inline=True)
            embed.set_footer(text="컵을 선택하세요!")

            await interaction.response.edit_message(embed=embed, view=self.view_ref)
            
        except Exception as e:
            print(f"야바위 게임 도전 버튼 오류: {e}")
            try:
                await interaction.response.send_message("❌ 도전 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ 슬래시 명령어 등록
class YabawiGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="야바위게임", description="야바위 게임을 시작합니다.")
    @app_commands.describe(배팅="배팅할 현금 (기본값: 10원, 최대 500원)")
    async def yabawi_game(self, interaction: discord.Interaction, 배팅: int = 10):
        try:
            user_id = str(interaction.user.id)
            guild_id = str(interaction.guild_id) 

            # 등록 확인
            if not await point_manager.is_registered(self.bot, guild_id, user_id):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)

            # 배팅 금액 검증
            if 배팅 < 1 or 배팅 > 500:
                return await interaction.response.send_message("❗ 배팅 금액은 1~500원 사이여야 합니다.", ephemeral=True)

            # 잔액 확인
            current_balance = await point_manager.get_point(self.bot, guild_id, user_id)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원",
                    ephemeral=True
                )

            # 중복 게임 방지
            if user_id in active_games_by_user:
                return await interaction.response.send_message("❗ 이미 진행 중인 야바위 게임이 있습니다.", ephemeral=True)

            active_games_by_user.add(user_id)
            view = YabawiGameView(self.bot, interaction.user, 배팅, guild_id) 

            # 셔플 메시지 먼저 출력
            await interaction.response.send_message("🔄 컵을 섞는 중입니다...")
            await asyncio.sleep(1.5)

            # 게임 시작 메시지로 수정
            embed = discord.Embed(
                title="🎩 야바위 게임 시작!",
                description="공이 들어있는 컵을 찾아보세요!",
                color=discord.Color.purple()
            )
            embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
            embed.add_field(name="📊 1단계 성공률", value=f"{int(SUCCESS_RATES[0] * 100)}%", inline=True)
            embed.add_field(name="🎯 최대 단계", value=f"{MAX_CHALLENGES}단계", inline=True)
            embed.add_field(name="🏆 최대 보상", value=f"{배팅 * (2 ** MAX_CHALLENGES):,}원", inline=True)
            embed.set_footer(text="컵을 선택하세요!")

            game_message = await interaction.original_response()
            await game_message.edit(embed=embed, view=view)
            view.message = game_message

        except Exception as e:
            print(f"야바위 게임 명령어 오류: {e}")
            try:
                if user_id in active_games_by_user:
                    active_games_by_user.discard(user_id)
                await interaction.response.send_message("❌ 게임 시작 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ Cog 등록 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(YabawiGameCog(bot))
    print("✅ 야바위 게임 (통계 기록 포함) 로드 완료")
