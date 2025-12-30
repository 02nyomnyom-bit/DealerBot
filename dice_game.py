# dice_game.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
import random
import asyncio

# --- 시스템 연동부 ---
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False

try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
except ImportError:
    STATS_AVAILABLE = False

DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

# 상수 설정 (블랙잭과 동일하게 적용)
MAX_BET = 5000  # 최대 배팅금: 5천 원
PUSH_RETENTION = 0.95 # 무승부 시 5% 수수료 제외 (95%만 지급)
WINNER_RETENTION = 0.95  # 승리 시 5% 수수료 제외 (95%만 지급)

# 통계 기록 헬퍼 함수
def record_dice_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "주사위", bet, payout, is_win)
        except Exception as e:
            print(f"통계 기록 오류: {e}")

# --- 1단계: 메인 모드 선택 View ---
class DiceModeSelectView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.bet = bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 이 메뉴는 명령어 실행자만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🤖 싱글 모드 (vs 봇)", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 포인트 선차감 (블랙잭 방식 적용)
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)

        bot_val = random.randint(1, 6)
        user_val = random.randint(1, 6)
        
        diff = user_val - bot_val
        payout = 0
        is_win = False

        if diff > 0: # 승리
            payout = self.bet * 2 # 선차감했으므로 배팅금의 2배를 지급 (본전 + 수익)
            result_text = f"🏆 승리! (+{self.bet:,}원)"
            is_win = True
        elif diff < 0: # 패배
            payout = 0
            result_text = f"💀 패배... (-{self.bet:,}원)"
        else: # 무승부
            payout = int(self.bet * PUSH_RETENTION) # 10% 수수료 차감 후 환불
            result_text = f"🤝 무승부! (수수료 10% 제외 {payout:,}원 환불)"

        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)
        
        record_dice_game(str(self.user.id), self.user.display_name, self.bet, payout, is_win)

        embed = discord.Embed(title="🎲 싱글 주사위 결과", color=discord.Color.blue())
        embed.description = f"**{self.user.display_name}**: {DICE_EMOJIS[user_val]} ({user_val})\n**봇**: {DICE_EMOJIS[bot_val]} ({bot_val})\n\n**{result_text}**"
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="👥 멀티 모드 (플레이어)", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        view = MultiSetupView(self.bot, self.user, self.bet)
        await interaction.response.edit_message(embed=embed, view=view)

# --- 2단계: 멀티 세부 설정 View ---
class MultiSetupView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="대결할 상대를 선택하세요!")
        
        async def select_callback(inter: discord.Interaction):
            target = user_select.values[0]
            if target.id == self.user.id or target.bot:
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            
            # 양측 포인트 체크 및 선차감
            if POINT_MANAGER_AVAILABLE:
                p1_bal = await point_manager.get_point(self.bot, inter.guild_id, str(self.user.id))
                p2_bal = await point_manager.get_point(self.bot, inter.guild_id, str(target.id))
                if p1_bal < self.bet or p2_bal < self.bet:
                    return await inter.response.send_message("❌ 참가자 중 잔액이 부족한 사람이 있습니다.", ephemeral=True)
                
                await point_manager.add_point(self.bot, inter.guild_id, str(self.user.id), -self.bet)
                await point_manager.add_point(self.bot, inter.guild_id, str(target.id), -self.bet)

            await self.start_game(inter, target)

        user_select.callback = select_callback
        view = View(); view.add_item(user_select)
        await interaction.response.edit_message(content="상대를 지목해주세요.", embed=None, view=view)

    @discord.ui.button(label="🔓 공개 대전 (아무나)", style=discord.ButtonStyle.success)
    async def public_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 방장 포인트 선차감
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        await self.start_game(interaction, None)

    async def start_game(self, interaction, target):
        view = MultiDiceView(self.bot, self.user, self.bet, opponent=target)
        embed = discord.Embed(title="🎲 주사위 대결", color=discord.Color.gold())
        embed.add_field(name="💰 배팅액", value=f"{self.bet:,}원"); embed.add_field(name="P1", value=self.user.mention)
        embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

# --- 3단계: 멀티플레이 게임 진행 View ---
class MultiDiceView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.game_completed = False # [변경] is_finished -> game_completed
        self.message = None

    async def on_timeout(self):
        if self.game_completed: # [변경]
            return
        
        guild_id = self.message.guild.id
        refund_text = "⏰ **시간 초과!** 게임이 취소되었습니다.\n"
        
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
            refund_text += f"- {self.p1.mention}님 {self.bet:,}원 환불\n"
            if self.p2:
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)
                refund_text += f"- {self.p2.mention}님 {self.bet:,}원 환불"

        embed = discord.Embed(title="❌ 게임 자동 취소", description=refund_text, color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    async def finish_game(self):
        self.game_completed = True # [변경]
        
    @discord.ui.button(label="🎲 주사위 굴리기", style=discord.ButtonStyle.danger)
    async def roll(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 공개 모드 참가자 등록 및 선차감
        if self.p2 is None and interaction.user.id != self.p1.id:
            bal = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
            if bal < self.bet:
                return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
            self.p2 = interaction.user
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, interaction.guild_id, str(self.p2.id), -self.bet)

        if interaction.user.id == self.p1.id:
            if self.p1_rolled: return await interaction.response.send_message("이미 굴리셨습니다.", ephemeral=True)
            self.p1_val = random.randint(1, 6); self.p1_rolled = True
        elif self.p2 and interaction.user.id == self.p2.id:
            if self.p2_rolled: return await interaction.response.send_message("이미 굴리셨습니다.", ephemeral=True)
            self.p2_val = random.randint(1, 6); self.p2_rolled = True
        else:
            return await interaction.response.send_message("❌ 대결 참가자가 아닙니다.", ephemeral=True)

        await interaction.response.defer()
        if self.p1_rolled and self.p2_rolled: await self.finish_game()
        else:
            embed = self.message.embeds[0]
            embed.set_footer(text=f"✅ {interaction.user.display_name} 완료!")
            await self.message.edit(embed=embed, view=self)

    async def finish_game(self):
        guild_id = self.message.guild.id
        winner = None
        if self.p1_val > self.p2_val: winner = self.p1; res_msg = f"🏆 {self.p1.mention} 승리!"
        elif self.p1_val < self.p2_val: winner = self.p2; res_msg = f"🏆 {self.p2.mention} 승리!"
        else: res_msg = "🤝 무승부!"

        if winner:
            payout = self.bet * 2
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), payout)
            reward_msg = f"💰 승자가 **{payout:,}원**을 획득했습니다!"
        else:
            # 🤝 멀티 무승부 수수료 적용
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_msg = f"🤝 각자 수수료 10%를 제외한 **{refund:,}원**이 환불되었습니다."

        embed = discord.Embed(title="🎲 대결 결과", description=f"{self.p1.mention}: {DICE_EMOJIS[self.p1_val]} ({self.p1_val})\n{self.p2.mention}: {DICE_EMOJIS[self.p2_val]} ({self.p2_val})\n\n**{res_msg}**\n{reward_msg}", color=discord.Color.purple())
        await self.message.edit(embed=embed, view=None)

# --- Cog 클래스 ---
class DiceGameCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="주사위게임", description="싱글/멀티 주사위 게임 (최대 5,000원)")
    async def dice_game(self, interaction: discord.Interaction, 배팅: int = 100):
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터 가능합니다.", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)

        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
        if balance < 배팅: return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)

        view = DiceModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎲 **주사위 게임** (배팅: {배팅:,}원)\n※ 무승부 시 수수료 10%가 발생합니다.", view=view)

async def setup(bot):
    await bot.add_cog(DiceGameCog(bot))