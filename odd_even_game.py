#odd_even_game.py
from __future__ import annotations
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from typing import Literal, Optional

# 안전한 point_manager import
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    print("⚠️ point_manager가 없어 포인트 기능이 비활성화됩니다.")
    
    # point_manager 모의 함수들
    class MockPointManager:
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount):
            pass
        @staticmethod
        async def get_point(bot, guild_id, user_id):
            return 10000  # 테스트용 기본값
        @staticmethod
        async def is_registered(bot, guild_id, user_id):
            return True
        @staticmethod
        async def register_user(bot, guild_id, user_id):
            pass
    
    point_manager = MockPointManager()

ODD_EVEN_EMOJI = {
    "홀": "🔴",
    "짝": "🔵"
}

DICE_EMOJIS = {
    1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"
}

# ✅ 싱글 홀짝 게임 View
class OddEvenSingleView(View):
    def __init__(self, bot: commands.Bot, guild_id: int, user: discord.User, bet: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = guild_id
        self.user = user
        self.bet = bet
        self.choice_made = False
        self.message = None

    @discord.ui.button(label="홀 🔴", style=discord.ButtonStyle.danger)
    async def choose_odd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "홀")

    @discord.ui.button(label="짝 🔵", style=discord.ButtonStyle.primary)
    async def choose_even(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "짝")

    async def process_choice(self, interaction: discord.Interaction, choice: str):
        try:
            if interaction.user != self.user:
                return await interaction.response.send_message("❗ 본인만 선택할 수 있어요.", ephemeral=True)

            if self.choice_made:
                return await interaction.response.send_message("⚠️ 이미 선택을 완료했습니다.", ephemeral=True)
            
            self.choice_made = True
            uid = str(self.user.id)

            # 검증 (게임 시작 시점에 재확인)
            if not await point_manager.is_registered(self.bot, self.guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)
            
            current_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            if current_balance < self.bet:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {self.bet:,}원", 
                    ephemeral=True
                )

            # 배팅 금액 차감 (게임 시작 시점)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, -self.bet)

            # 게임 진행
            await interaction.response.defer()
            if self.message is None:
                 self.message = await interaction.original_response()

            await self.message.edit(
                content=f"🎮 **홀짝 게임 진행 중**\n\n🎯 {self.user.mention}님의 선택: {ODD_EVEN_EMOJI[choice]} **{choice}**\n🎲 주사위를 굴리는 중...", 
                view=self
            )

            # 애니메이션 효과
            for i in range(5):
                dice_display = DICE_EMOJIS[random.randint(1, 6)]
                await asyncio.sleep(0.4)
                try:
                    await self.message.edit(content=f"🎲 주사위 굴리는 중... {dice_display} ({i+1}/5)")
                except:
                    pass

            # 결과 계산
            roll = random.randint(1, 6)
            result = "홀" if roll % 2 == 1 else "짝"
            
            # 포인트 처리
            if choice == result:
                # 승리: 배팅 금액 * 2 지급 (이미 차감된 금액 + 승리 보상)
                reward = self.bet * 2
                if POINT_MANAGER_AVAILABLE:
                    await point_manager.add_point(self.bot, self.guild_id, uid, reward)
                outcome = f"🎉 정답! +{reward:,}원 획득"
                result_color = "🟢"
                embed_color = discord.Color.green()
            else:
                # 패배: 이미 차감됨
                outcome = f"😢 오답! -{self.bet:,}원 차감"
                result_color = "🔴"
                embed_color = discord.Color.red()

            # 버튼 비활성화
            for child in self.children:
                child.disabled = True
                child.style = discord.ButtonStyle.secondary

            # 최종 잔액 조회
            final_balance = await point_manager.get_point(self.bot, self.guild_id, uid)

            # 결과 임베드 생성
            embed = discord.Embed(
                title="🎲 홀짝 게임 결과",
                color=embed_color
            )
            embed.add_field(
                name="🎯 선택 & 결과",
                value=f"**{self.user.display_name}의 선택**: {ODD_EVEN_EMOJI[choice]} {choice}\n**주사위 결과**: {DICE_EMOJIS[roll]} {roll} ({ODD_EVEN_EMOJI[result]} {result})",
                inline=False
            )
            embed.add_field(name="🏆 결과", value=outcome, inline=True)
            embed.add_field(name="💰 현재 잔액", value=f"{final_balance:,}원", inline=True)
            embed.set_footer(text=f"배팅 금액: {self.bet:,}원")

            await self.message.edit(content=None, embed=embed, view=self)
            self.stop()

        except Exception as e:
            print(f"싱글 홀짝 게임 오류: {e}")
            try:
                await interaction.followup.send("❌ 게임 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary
            
            if self.message:
                embed = discord.Embed(
                    title="⏰ 게임 시간 만료",
                    description="게임이 시간 초과로 종료되었습니다.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"싱글 홀짝 타임아웃 처리 오류: {e}")

# ✅ 멀티 홀짝 게임 View
class OddEvenMultiView(View):
    def __init__(self, bot: commands.Bot, guild_id: int, player1: discord.User, bet: int, opponent: Optional[discord.User] = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.guild_id = guild_id
        self.player1 = player1
        self.bet = bet
        self.opponent = opponent
        self.player2 = None
        self.choices = {}
        self.message = None
        self.game_started = False
        self.paid_users = set()  # 배팅 금액을 지불한 유저 추적

    @discord.ui.button(label="🎯 게임 참여 / 홀 선택", style=discord.ButtonStyle.danger)
    async def choose_odd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "홀")

    @discord.ui.button(label="🎯 게임 참여 / 짝 선택", style=discord.ButtonStyle.primary)
    async def choose_even(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_choice(interaction, "짝")

    async def process_choice(self, interaction: discord.Interaction, choice: str):
        try:
            user = interaction.user
            uid = str(user.id)

            # 기본 검증
            if not await point_manager.is_registered(self.bot, self.guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            if current_balance < self.bet:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {self.bet:,}원", 
                    ephemeral=True
                )

            # 참여자 검증
            if self.opponent:  # 특정 상대방이 지정된 경우
                if user not in [self.player1, self.opponent]:
                    return await interaction.response.send_message("❌ 이 게임에 참여할 수 없습니다.", ephemeral=True)
            else:  # 오픈 게임
                if len(self.choices) >= 2 and uid not in self.choices:
                    return await interaction.response.send_message("❌ 이미 다른 플레이어가 참여했습니다.", ephemeral=True)

            if uid in self.choices:
                return await interaction.response.send_message("⚠️ 이미 선택을 완료했습니다.", ephemeral=True)

            # 배팅 금액 차감 (한 번만)
            if uid not in self.paid_users:
                if POINT_MANAGER_AVAILABLE:
                    await point_manager.add_point(self.bot, self.guild_id, uid, -self.bet)
                self.paid_users.add(uid)

            # 선택 저장
            self.choices[uid] = {
                "user": user,
                "choice": choice
            }

            if user != self.player1 and not self.player2:
                self.player2 = user

            await interaction.response.send_message(
                f"✅ {user.mention}님이 게임에 참여했습니다!\n🎯 선택: {ODD_EVEN_EMOJI[choice]} **{choice}**", ephemeral=True
            )

            # 게임 상태 업데이트
            if not self.game_started and len(self.choices) == 1:
                self.game_started = True
                
                embed = discord.Embed(
                    title="🎲 홀짝 멀티 게임",
                    description="첫 번째 플레이어가 참여했습니다!\n상대방의 참여를 기다리는 중...",
                    color=discord.Color.orange()
                )
                embed.add_field(name="💰 배팅 금액", value=f"{self.bet:,}원", inline=True)
                embed.add_field(name="👤 참여자", value=f"{len(self.choices)}/2명", inline=True)
                embed.set_footer(text="상대방도 홀 또는 짝을 선택해주세요!")
                
                self.message = await interaction.original_response()
                await self.message.edit(embed=embed, view=self)

            # 두 명 모두 선택했으면 결과 처리
            elif len(self.choices) == 2:
                await self.show_results(interaction)

        except Exception as e:
            print(f"멀티 홀짝 선택 처리 오류: {e}")
            try:
                await interaction.response.send_message("❌ 선택 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

    async def show_results(self, interaction: discord.Interaction):
        try:
            # 버튼 비활성화
            for child in self.children:
                child.disabled = True
                child.label = "게임 진행 중"
                child.style = discord.ButtonStyle.secondary

            # 결과 계산 메시지
            embed = discord.Embed(
                title="🎲 홀짝 게임 결과 계산 중",
                description="주사위를 굴리는 중...",
                color=discord.Color.yellow()
            )
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
            else:
                self.message = await interaction.original_response()
                await self.message.edit(embed=embed, view=self)

            # 애니메이션 효과
            for i in range(5):
                dice_display = DICE_EMOJIS[random.randint(1, 6)]
                embed.description = f"주사위를 굴리는 중... {dice_display} ({i+1}/5)"
                try:
                    await self.message.edit(embed=embed, view=self)
                    await asyncio.sleep(0.4)
                except:
                    pass

            # 주사위 결과
            roll = random.randint(1, 6)
            result = "홀" if roll % 2 == 1 else "짝"

            # 플레이어 데이터 정리
            uids = list(self.choices.keys())
            user1_data = self.choices[uids[0]]
            user2_data = self.choices[uids[1]]

            # 승부 판정 및 포인트 처리
            winners = []
            losers = []
            
            if user1_data["choice"] == result:
                winners.append(user1_data)
            else:
                losers.append(user1_data)
                
            if user2_data["choice"] == result:
                winners.append(user2_data)
            else:
                losers.append(user2_data)

            # 포인트 지급
            if len(winners) == 1:  # 한 명만 맞춤
                winner_uid = str(winners[0]["user"].id)
                if POINT_MANAGER_AVAILABLE:
                    await point_manager.add_point(self.bot, self.guild_id, winner_uid, self.bet * 2)  # 본인 배팅 + 상대방 배팅
                result_text = f"🎉 {winners[0]['user'].mention} 승리!"
                result_color = discord.Color.green()
            else:  # 무승부 (둘 다 맞추거나 둘 다 틀림)
                # 배팅 금액 반환
                for uid in self.paid_users:
                    if POINT_MANAGER_AVAILABLE:
                        await point_manager.add_point(self.bot, self.guild_id, uid, self.bet)
                result_text = "🤝 무승부!"
                result_color = discord.Color.gold()

            # 최종 결과 임베드
            embed = discord.Embed(
                title="🎲 홀짝 멀티 게임 결과",
                description=result_text,
                color=result_color
            )
            
            embed.add_field(
                name="🎲 주사위 결과",
                value=f"{DICE_EMOJIS[roll]} **{roll}** ({ODD_EVEN_EMOJI[result]} {result})",
                inline=False
            )
            
            embed.add_field(
                name="🎯 플레이어 선택",
                value=(
                    f"**{user1_data['user'].display_name}**: {ODD_EVEN_EMOJI[user1_data['choice']]} {user1_data['choice']}\n"
                    f"**{user2_data['user'].display_name}**: {ODD_EVEN_EMOJI[user2_data['choice']]} {user2_data['choice']}"
                ),
                inline=False
            )
            
            embed.add_field(name="💰 배팅 금액", value=f"{self.bet:,}원", inline=True)
            
            if len(winners) == 1:
                embed.add_field(name="🏆 획득 금액", value=f"{self.bet * 2:,}원", inline=True)
            else:
                embed.add_field(name="🔄 반환 금액", value=f"{self.bet:,}원 (각자)", inline=True)
            
            # 현재 잔액 표시
            balance1 = await point_manager.get_point(self.bot, self.guild_id, uids[0])
            balance2 = await point_manager.get_point(self.bot, self.guild_id, uids[1])
            embed.add_field(
                name="💰 현재 잔액", 
                value=f"**{user1_data['user'].display_name}**: {balance1:,}원\n**{user2_data['user'].display_name}**: {balance2:,}원", 
                inline=False
            )

            await self.message.edit(embed=embed, view=self)
            self.stop()

        except Exception as e:
            print(f"홀짝 게임 결과 처리 오류: {e}")
            try:
                await interaction.channel.send("❌ 결과 처리 중 오류가 발생했습니다.")
            except:
                pass

    async def on_timeout(self):
        try:
            # 타임아웃 시 배팅 금액 반환
            if POINT_MANAGER_AVAILABLE:
                for user_id in self.paid_users:
                    await point_manager.add_point(self.bot, self.guild_id, user_id, self.bet)
            
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary
            
            if self.message:
                embed = discord.Embed(
                    title="⏰ 게임 시간 만료",
                    description="게임이 시간 초과로 종료되었습니다.\n배팅 금액이 반환되었습니다.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"멀티 홀짝 타임아웃 처리 오류: {e}")

# ✅ 홀짝 게임 Cog
class OddEvenGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="홀짝", description="홀짝 게임을 플레이합니다.")
    @app_commands.describe(
        모드="싱글(봇과 대결) 또는 멀티(다른 유저와 대결)",
        배팅="배팅할 현금 (기본값: 10원, 최대 1,000원)",
        상대방="멀티 모드에서 특정 상대방 지정 (선택사항)"
    )
    async def odd_even_game(
        self,
        interaction: discord.Interaction,
        모드: Literal["싱글", "멀티"],
        배팅: int = 10,
        상대방: Optional[discord.User] = None
    ):
        try:
            uid = str(interaction.user.id)
            guild_id = str(interaction.guild.id)

            # 기본 검증
            if not await point_manager.is_registered(self.bot, guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

            if 배팅 < 1 or 배팅 > 1000:
                return await interaction.response.send_message("❗ 배팅은 1~1,000원 사이여야 합니다.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, guild_id, uid)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원", 
                    ephemeral=True
                )

            # 싱글 모드
            if 모드 == "싱글":
                embed = discord.Embed(
                    title="🎲 홀짝 싱글 게임",
                    description="주사위 결과가 홀수인지 짝수인지 맞춰보세요!",
                    color=discord.Color.purple()
                )
                embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
                embed.add_field(name="🎯 승리 조건", value="홀/짝 맞추기", inline=True)
                embed.add_field(name="🏆 승리 보상", value=f"{배팅 * 2:,}원", inline=True)
                embed.set_footer(text="홀 또는 짝을 선택하세요!")

                await interaction.response.send_message(
                    embed=embed,
                    view=OddEvenSingleView(self.bot, guild_id, interaction.user, 배팅)
                )

            # 멀티 모드
            else:
                # 상대방 검증
                if 상대방:
                    if 상대방.id == interaction.user.id:
                        return await interaction.response.send_message("❌ 자기 자신과는 게임할 수 없습니다.", ephemeral=True)
                    if 상대방.bot:
                        return await interaction.response.send_message("❌ 봇과는 멀티 게임을 할 수 없습니다.", ephemeral=True)
                    if not await point_manager.is_registered(self.bot, guild_id, str(상대방.id)):
                        return await interaction.response.send_message(f"❌ {상대방.mention}님이 플레이어 등록되어 있지 않습니다.", ephemeral=True)
                    
                    opponent_balance = await point_manager.get_point(self.bot, guild_id, str(상대방.id))
                    if opponent_balance < 배팅:
                        return await interaction.response.send_message(f"❌ {상대방.mention}님의 잔액이 부족합니다. (보유: {opponent_balance:,}원)", ephemeral=True)

                embed = discord.Embed(
                    title="🎲 홀짝 멀티 게임",
                    description="다른 플레이어와 홀짝 대결입니다!",
                    color=discord.Color.orange()
                )
                embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
                embed.add_field(name="👤 플레이어1", value=interaction.user.mention, inline=True)
                embed.add_field(name="👤 플레이어2", value=상대방.mention if 상대방 else "참여자 대기 중", inline=True)
                embed.add_field(name="🏆 승리 조건", value="정답자만 승리", inline=True)
                embed.add_field(name="🏆 승리 보상", value=f"{배팅 * 2:,}원", inline=True)
                embed.add_field(name="⏰ 제한 시간", value="2분", inline=True)
                
                if 상대방:
                    embed.set_footer(text=f"{상대방.display_name}님이 홀 또는 짝을 선택해주세요!")
                else:
                    embed.set_footer(text="누구나 참여할 수 있습니다! 홀 또는 짝을 선택하세요!")

                await interaction.response.send_message(
                    embed=embed,
                    view=OddEvenMultiView(self.bot, guild_id, interaction.user, 배팅, opponent=상대방)
                )

        except Exception as e:
            print(f"홀짝 게임 명령어 오류: {e}")
            try:
                await interaction.response.send_message("❌ 게임 시작 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(OddEvenGameCog(bot))