# slot_machine.py
import random
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from collections import Counter

# --- 설정 및 확률 데이터 ---
# 슬롯에 표시될 기호들
SLOT_SYMBOLS = ["🍀", "🍋", "🍒", "🔔", "❌"]
# 각 기호가 3개 일치했을 때의 배당률
SLOT_MULTIPLIERS = {"🍀": 100, "🍋": 10, "🍒": 5, "🔔": 2, "❌": 0}
# 가중치 설정: 숫자가 클수록 해당 기호가 나올 확률이 높음 (전체 합 40)
SLOT_WEIGHTS = {"🍀": 3, "🍋": 4, "🍒": 6, "🔔": 7, "❌": 20} 
# 🍀 확률: (3/40)^3 ≒ 0.042% | ❌ 확률: (20/40)^3 = 12.5%
TWO_MATCH_MULTIPLIER = 0.1

# --- 외부 시스템 연동 ---
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
    print("⚠️ point_manager가 없어 포인트 기능이 비활성화됩니다.")

    # point_manager 파일이 없을 경우를 대비
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

class SlotMachineView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_id: str, user: discord.User, bet: int):
        super().__init__(timeout=60)    # 60초간 응답 없으면 버튼 만료
        self.bot = bot
        self.guild_id = str(guild_id)
        self.user = user
        self.bet = bet
        self.is_spinning = False        #현재 슬롯이 돌아가는 중인지 확인 (중복 클릭 방지)
        self.message = None

    @discord.ui.button(label="🎰 슬롯 돌리기!", style=discord.ButtonStyle.primary)
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(self.user.id)
        
        # 1. 권한 및 상태 체크: 명령어를 입력한 본인만 버튼 사용 가능
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(f"❗ {self.user.display_name}님의 게임입니다.", ephemeral=True)
        
        # 이미 실행 중인 경우 중단
        if self.is_spinning:
            return await interaction.response.send_message("⚠️ 이미 슬롯이 돌아가고 있습니다.", ephemeral=True)

        # 2. 초기 응답 및 상태 잠금 (Race Condition 방지)
        self.is_spinning = True
        
        try:
            # 유저의 현재 잔액 확인
            current_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            if current_balance < self.bet:
                self.is_spinning = False
                return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
            
            # 포인트 선 차감: 결과 조작/강제 종료 방지
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, -self.bet)

            # 버튼을 비활성화 상태로 바꾸어 중복 클릭 방지
            button.disabled = True
            button.label = "🎰 돌리는 중..."
            await interaction.response.edit_message(view=self)
            self.message = await interaction.original_response()

            # 3. 결과 계산: 애니메이션을 보여주기 전에 미리 내부적으로 결과 확정
            weighted_symbols = list(SLOT_WEIGHTS.keys())
            weights = list(SLOT_WEIGHTS.values())
            final_result = random.choices(weighted_symbols, weights=weights, k=3)

            # 4. 슬롯 애니메이션 (0.5초 간격으로 4번 가짜 기호를 보여줌)
            for i in range(4):
                temp_spin = random.choices(weighted_symbols, weights=weights, k=3)
                embed = discord.Embed(
                    title="🎰 슬롯머신 돌리는 중...",
                    description=f"**{' | '.join(temp_spin)}**",
                    color=discord.Color.yellow()
                )
                await self.message.edit(embed=embed)
                await asyncio.sleep(0.5)

            # 5. 최종 결과 처리 및 당첨금 계산
            symbol_counts = Counter(final_result)
            most_common, count = symbol_counts.most_common(1)[0]
            reward = 0

            # 3개 모두 일치할 경우
            if count == 3:
                mult = SLOT_MULTIPLIERS[most_common]
                reward = int(self.bet * mult) if mult > 0 else 0
            # 2개만 일치할 경우 (❌는 제외
            elif count == 2 and most_common != "❌":
                reward = int(self.bet * TWO_MATCH_MULTIPLIER)

            # 통계 시스템에 게임 기록 저장
            is_win = reward > self.bet
            if STATS_AVAILABLE:
                stats_manager.record_game(uid, self.user.display_name, "슬롯머신", self.bet, reward, is_win)
            
            # 당첨금(보상) 지급
            if reward > 0 and POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, reward)

            # 최종 잔액 조회
            final_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            
            # 결과 화면 임베드 구성 (이겼을 땐 초록, 졌을 땐 빨강)
            result_color = discord.Color.green() if reward > self.bet else discord.Color.red()
            embed = discord.Embed(title="🎰 슬롯머신 결과", color=result_color)
            embed.add_field(name="🎯 결과", value=f"**{' | '.join(final_result)}**", inline=False)
            embed.add_field(name="손익", value=f"{reward - self.bet:+,}원", inline=True)
            embed.add_field(name="💳 잔액", value=f"{final_balance:,}원", inline=True)
            
            button.label = "게임 종료"
            await self.message.edit(embed=embed, view=self)
            self.stop()

        except Exception as e:
            print(f"오류 발생: {e}")
            # 에러 발생 시에만 복구 시도 (이미 차감된 경우)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, self.bet)
            self.is_spinning = False
            if self.message:
                await self.message.edit(content="❌ 게임 중 오류가 발생하여 배팅액이 환불되었습니다.", view=None)

# --- 슬롯머신 명령어 등록 ---
class SlotMachineCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="슬롯머신", description="🎰 화끈한 한방! 슬롯머신 (100원 ~ 10,000원)")
    async def slot_command(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 확률 설명 자동화 (유지보수 용이)
        total_w = sum(SLOT_WEIGHTS.values())
        prob_info = " | ".join([f"{s} x{SLOT_MULTIPLIERS[s]}" for s in SLOT_SYMBOLS if SLOT_MULTIPLIERS[s] > 0])

        try:
            uid = str(interaction.user.id)
            guild_id = str(interaction.guild.id)

            # 등록 여부 확인
            if not await point_manager.is_registered(self.bot, guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)
            # 배팅 금액 제한 체크
            if 배팅 < 100 or 배팅 > 10000:
                return await interaction.response.send_message("⚠️ 배팅 금액은 100~10,000원 사이여야 합니다.", ephemeral=True)
            # 잔액 충분한지 확인
            current_balance = await point_manager.get_point(self.bot, guild_id, uid)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원",
                    ephemeral=True
                )
            # 게임 시작 안내 메시지
            embed = discord.Embed(
                title="🔥 자극적인 슬롯머신",
                description="대박 확률이 상승했습니다! 하지만 꽝도 그만큼 많으니 주의하세요.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
            embed.add_field(name="💳 현재 잔액", value=f"{current_balance:,}원", inline=True)

            # 각 심볼별 확률 및 배당 안내
            embed.add_field(
                name="🎰 심볼 배당률 & 3연속 확률",
                value="🍀 x100 (0.04%) | 🍋 x10 (0.1%) | 🍒 x5 (0.34%) | 🔔 x2 (0.54%) | ❌ x0 (12.5%)",
                inline=False
            )

            embed.add_field(
                name="✨ 게임 규칙",
                value="• **3개 일치**: 해당 심볼 배당률 적용\n• **2개 일치**: 배팅액의 10% 반환 (❌ 제외)\n• **미일치**: 배팅 금액 손실",
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

async def setup(bot):
    await bot.add_cog(SlotMachineCog(bot))