# slot_machine.py - 슬롯머신
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
# 🍀 확률: (6/60)^3 = 0.1%
# ❌ 비중: 24/60 = 40% (개별 칸에 ❌가 나올 확률이 40%, 3개 연속 ❌일 확률은 6.4%)
SLOT_WEIGHTS = {"🍀": 6, "🍋": 5, "🍒": 10, "🔔": 15, "❌": 24}
TWO_MATCH_MULTIPLIER = 0.1

# --- 외부 시스템 연동 ---
STATS_AVAILABLE = True 

try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
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
        super().__init__(timeout=60)
        self.bot = bot
        self.guild_id = str(guild_id)
        self.user = user
        self.bet = bet
        self.is_spinning = False
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
            # 1. 포인트 체크 및 선차감
            current_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            if current_balance < self.bet:
                self.is_spinning = False
                return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
            
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, -self.bet)

            # 2. 버튼 비활성화 및 초기 응답
            button.disabled = True
            button.label = "🎰 돌리는 중..."
            # interaction.response.edit_message를 사용해 즉시 반영
            await interaction.response.edit_message(view=self)
            self.message = await interaction.original_response()

            # 3. 결과 미리 계산
            weighted_symbols = list(SLOT_WEIGHTS.keys())
            weights = list(SLOT_WEIGHTS.values())
            final_result = random.choices(weighted_symbols, weights=weights, k=3)

            # 4. 안전한 애니메이션 (횟수 조절 및 예외 처리 강화)
            for i in range(3): # 4번에서 3번으로 줄여 API 부담 감소
                temp_spin = random.choices(weighted_symbols, weights=weights, k=3)
                anim_embed = discord.Embed(
                    title="🎰 슬롯머신 돌리는 중...",
                    description=f"**{' | '.join(temp_spin)}**",
                    color=discord.Color.yellow()
                )
                try:
                    await self.message.edit(embed=anim_embed)
                    await asyncio.sleep(0.7) # 간격을 조금 더 늘려 안정성 확보
                except discord.NotFound: # 메시지가 삭제된 경우 중단
                    break

            # 5. 결과 계산
            symbol_counts = Counter(final_result)
            most_common, count = symbol_counts.most_common(1)[0]
            reward = 0

            # 3개 모두 일치할 경우
            if count == 3:
                mult = SLOT_MULTIPLIERS[most_common]
                reward = int(self.bet * mult)
            
            # 2개만 일치할 경우 (❌는 제외)
            elif count == 2 and most_common != "❌":
                reward = int(self.bet * TWO_MATCH_MULTIPLIER)

            # 6. 정산 및 기록
            is_win = reward > self.bet
            # StatisticsCog를 찾아 직접 기록 호출 (권장 방식)
            stats_cog = self.bot.get_cog("StatisticsCog")
            if stats_cog and stats_cog.stats:
                try:
                    # statistics_system.py의 record_game_play 메서드에 맞춰 호출
                    stats_cog.stats.record_game_play(
                        user_id=uid,
                        username=self.user.display_name,
                        game_name="slot_machine",
                        is_win=is_win,
                        bet_amount=self.bet,
                        payout=reward,
                        is_multi=False  # 슬롯머신은 싱글 게임
                    )
                except Exception as stats_err:
                    print(f"통계 기록 중 오류: {stats_err}")

            # 당첨금(보상) 지급
            if reward > 0 and POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, reward)
            
            # 최종 잔액 조회
            final_balance = await point_manager.get_point(self.bot, self.guild_id, uid)
            
            # 7. 최종 결과 출력
            if reward > self.bet:
                result_color = discord.Color.green() # 이득
            elif reward > 0:
                result_color = discord.Color.yellow() # 일부 환급
            else:
                result_color = discord.Color.red() # 손해

            end_embed = discord.Embed(title="🎰 슬롯머신 결과", color=result_color)
            end_embed.add_field(name="🎯 결과", value=f"**{' | '.join(final_result)}**", inline=False)
            end_embed.add_field(name="손익", value=f"{reward - self.bet:+,}원", inline=True)
            end_embed.add_field(name="💳 잔액", value=f"{final_balance:,}원", inline=True)
            
            button.label = "게임 종료"
            await self.message.edit(embed=end_embed, view=self)
            self.stop()

        except Exception as e:
            print(f"Slot Machine Error: {e}")
            # 이미 포인트가 차감된 경우에만 환불
            if self.is_spinning and POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, self.guild_id, uid, self.bet)

                self.is_spinning = False
                if self.message:
                    try:
                        await self.message.edit(content=f"❌ 오류가 발생하여 환불되었습니다. (사유: {e})", embed=None, view=None)
                    except:
                        pass

# --- 슬롯머신 명령어 등록 ---
class SlotMachineCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="슬롯머신", description="🎰 화끈한 한방! 슬롯머신 (100원 ~ 10,000원)")
    async def slot_command(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'slot' 권한이 있는지 체크 (channel_config.py의 value="slot"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "slot", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        try:
            uid = str(interaction.user.id)
            guild_id = str(interaction.guild.id)

            # 등록 여부 확인
            if not await point_manager.is_registered(self.bot, guild_id, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요.", ephemeral=True)
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

            # 확률 정보 동적 생성
            total_weight = sum(SLOT_WEIGHTS.values())
            prob_lines = []
            for symbol, multiplier in sorted(SLOT_MULTIPLIERS.items(), key=lambda item: item[1], reverse=True):
                if multiplier > 0:
                    prob = (SLOT_WEIGHTS[symbol] / total_weight) ** 3
                    prob_lines.append(f"{symbol} x{multiplier} ({prob:.2%})")
            
            embed.add_field(
                name="🎰 심볼 배당률 & 3연속 확률",
                value=" | ".join(prob_lines),
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