# slot_machine.py
from __future__ import annotations
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from collections import Counter

# 안전한 point_manager import
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    print("⚠️ point_manager가 없어 포인트 기능이 비활성화됩니다.")
    
    # ✅ 개선된 MockPointManager
    class MockPointManager:
        user_points = {}

        @staticmethod
        async def add_point(bot, guild_id, user_id, amount):
            MockPointManager.user_points[user_id] = await MockPointManager.get_point(bot, guild_id, user_id) + amount

        @staticmethod
        async def get_point(bot, guild_id, user_id):
            return MockPointManager.user_points.get(user_id, 10000)

        @staticmethod
        async def is_registered(bot, guild_id, user_id):
            return True

        @staticmethod
        async def register_user(bot, guild_id, user_id):
            MockPointManager.user_points[user_id] = 10000

    point_manager = MockPointManager()

# 슬롯 심볼 및 확률 설정
SLOT_SYMBOLS = ["🍀", "🍋", "🍒", "🔔", "❌"]
SLOT_MULTIPLIERS = {"🍀": 100, "🍋": 10, "🍒": 5, "🔔": 2, "❌": 0}
SLOT_WEIGHTS = {"🍀": 1, "🍋": 3, "🍒": 5, "🔔": 8, "❌": 10}
TWO_MATCH_MULTIPLIER = 0.1

class SlotMachineView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: int, user: discord.User, bet: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = str(guild_id)
        self.user = user
        self.bet = bet
        self.button_clicked = False
        self.message = None

    @discord.ui.button(label="🎰 슬롯 돌리기!", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(self.user.id)
        try:
            if interaction.user != self.user:
                return await interaction.response.send_message("❗ 본인만 슬롯을 돌릴 수 있어요!", ephemeral=True)

            if self.button_clicked:
                return await interaction.response.send_message("⚠️ 이미 슬롯을 돌렸습니다.", ephemeral=True, delete_after=5)

            self.button_clicked = True

            if not await point_manager.is_registered(self.bot, self.guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            if current_balance < self.bet:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {self.bet:,}원",
                    ephemeral=True
                )

            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, -self.bet)

            await interaction.response.defer()
            if self.message is None:
                self.message = await interaction.original_response()

            weighted_symbols = list(SLOT_WEIGHTS.keys())
            weights = list(SLOT_WEIGHTS.values())

            result = random.choices(weighted_symbols, weights=weights, k=3)

            for i in range(5):
                spin = result if i == 4 else random.choices(weighted_symbols, weights=weights, k=3)
                try:
                    embed = discord.Embed(
                        title="🎰 슬롯머신 돌리는 중...",
                        description=f"**{' | '.join(spin)}**",
                        color=discord.Color.yellow()
                    )
                    embed.add_field(name="🎯 진행률", value=f"{i+1}/5", inline=True)
                    await self.message.edit(embed=embed, view=self)
                    await asyncio.sleep(0.4)
                except Exception as e:
                    print(f"메시지 편집 오류 (회전 {i+1}): {e}")

            symbol_counts = Counter(result)
            most_common_symbol, count = symbol_counts.most_common(1)[0]

            if count == 3:
                multiplier = SLOT_MULTIPLIERS[most_common_symbol]
                if multiplier > 0:
                    reward = int(self.bet * multiplier)
                    if POINT_MANAGER_AVAILABLE:
                        await point_manager.add_point(self.bot, self.guild_id, uid, reward)

                    if most_common_symbol == "🍀":
                        result_text = f"🎉 💰 JACKPOT! 🍀 x3 💰"
                        outcome = f"+{reward:,}원 대박!"
                        result_color = discord.Color.gold()
                    else:
                        result_text = f"🎊 대박! {most_common_symbol} x3"
                        outcome = f"+{reward:,}원 획득"
                        result_color = discord.Color.green()
                else:
                    result_text = f"😢 꽝! {most_common_symbol} x3"
                    outcome = f"-{self.bet:,}원 차감"
                    result_color = discord.Color.red()

            elif count == 2:
                if most_common_symbol == "❌":
                    result_text = f"😢 꽝! {most_common_symbol} x2"
                    outcome = f"-{self.bet:,}원 차감"
                    result_color = discord.Color.red()
                else:
                    refund = int(self.bet * TWO_MATCH_MULTIPLIER)
                    if POINT_MANAGER_AVAILABLE:
                        await point_manager.add_point(self.bot, self.guild_id, uid, refund)
                    result_text = f"✨ 2개 일치! {most_common_symbol} x2"
                    outcome = f"+{refund:,}원 소보상"
                    result_color = discord.Color.yellow()

            else:
                result_text = "😢 꽝! 일치하는 심볼 없음"
                outcome = f"-{self.bet:,}원 차감"
                result_color = discord.Color.red()

            button.disabled = True
            button.label = "게임 완료"
            button.style = discord.ButtonStyle.secondary

            final_balance = await point_manager.get_point(self.bot, self.guild_id, uid)

            embed = discord.Embed(
                title="🎰 슬롯머신 게임 결과",
                color=result_color
            )
            embed.add_field(name="🎯 슬롯 결과", value=f"**{' | '.join(result)}**", inline=False)
            embed.add_field(name=f"🎮 {self.user.display_name}님의 결과", value=result_text, inline=False)
            embed.add_field(name="💰 획득/손실", value=outcome, inline=False)
            embed.add_field(name="💳 현재 잔액", value=f"{final_balance:,}원", inline=False)

            try:
                await self.message.edit(content=None, embed=embed, view=self)
            except Exception as e:
                print(f"최종 메시지 수정 오류: {e}")
                await interaction.followup.send("❌ 결과를 표시하는 중 오류가 발생했습니다.", ephemeral=True)

        except Exception as e:
            print(f"슬롯머신 게임 오류: {e}")
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, self.bet)
            try:
                await interaction.followup.send("❌ 게임 처리 중 오류가 발생했습니다. 배팅 금액은 복구되었습니다.", ephemeral=True)
            except:
                pass
        finally:
            self.stop()

    async def on_timeout(self):
        try:
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary

            if self.message:
                embed = discord.Embed(
                    title="⏰ 슬롯머신 게임 - 시간 만료",
                    description="게임이 시간 초과로 종료되었습니다.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"슬롯머신 타임아웃 처리 오류: {e}")

class SlotMachineCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="슬롯머신", description="🎰 슬롯머신 게임을 플레이합니다.")
    @app_commands.describe(배팅="배팅할 현금 (기본값: 10원, 최대 5,000원)")
    async def slot_command(self, interaction: discord.Interaction, 배팅: int = 10):
        try:
            uid = str(interaction.user.id)
            guild_id = str(interaction.guild.id)

            if not await point_manager.is_registered(self.bot, guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)

            if 배팅 < 1 or 배팅 > 5000:
                return await interaction.response.send_message("⚠️ 배팅 금액은 1~3,000원 사이여야 합니다.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, guild_id, uid)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원",
                    ephemeral=True
                )

            embed = discord.Embed(
                title="🎰 카지노 슬롯머신",
                color=discord.Color.red()
            )
            embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
            embed.add_field(name="💳 현재 잔액", value=f"{current_balance:,}원", inline=True)
            embed.add_field(
                name="🎰 심볼 배당률 & 3연속 확률",
                value="🍀 x100 (0.05%) | 🍋 x10 (1.4%) | 🍒 x5 (6.3%) | 🔔 x2 (25.9%) | ❌ x0 (50.7%)",
                inline=False
            )
            embed.add_field(
                name="✨ 게임 규칙",
                value="• **3개 일치**: 해당 심볼 배당률 적용\n• **2개 일치**: 배팅액의 10% 소보상 (❌ 제외)\n• **미일치**: 배팅 금액 손실",
                inline=False
            )
            embed.add_field(
                name="⚠️ 경고",
                value="이 게임은 **확률적으로 손실**이 발생하도록 설계되었습니다.\n계획적이고 적당한 게임을 즐기세요!",
                inline=False
            )
            embed.set_footer(text="슬롯 돌리기 버튼을 눌러 운을 시험해보세요!")

            await interaction.response.send_message(
                embed=embed,
                view=SlotMachineView(self.bot, guild_id, interaction.user, 배팅)
            )

        except Exception as e:
            print(f"슬롯머신 명령어 오류: {e}")
            try:
                await interaction.response.send_message("❌ 게임 시작 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# Cog 등록
async def setup(bot):
    await bot.add_cog(SlotMachineCog(bot))