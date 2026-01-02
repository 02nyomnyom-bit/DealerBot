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

# --- 애니메이션 유틸리티 ---
async def play_dice_animation(message: discord.InteractionMessage, base_embed: discord.Embed):
    """주사위 굴리는 애니메이션 효과"""
    dice_faces = list(DICE_EMOJIS.values())
    for i in range(5): 
        current_face = random.choice(dice_faces)
        base_embed.description = f"🎲 **주사위가 굴러가고 있습니다...** {current_face}"
        # view=None을 제거하여 애니메이션 도중 View 구조가 깨지는 것을 방지
        await message.edit(embed=base_embed) 
        await asyncio.sleep(0.4)

# 통계 기록 헬퍼 함수
def record_dice_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "주사위", bet, payout, is_win)
        except Exception as e:
            print(f"통계 기록 오류: {e}")

# --- 1단계: 모드 선택 View ---
class DiceModeSelectView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 명령어 실행자만 선택 가능합니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="🤖 싱글 모드", style=discord.ButtonStyle.secondary, emoji="👤")
    async def single_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        
        # 싱글 모드는 즉시 주사위를 굴립니다.
        await interaction.response.defer()
        message = await interaction.original_response()
        
        # 애니메이션 시작
        anim_embed = discord.Embed(title="🤖 주사위: 싱글 모드", color=discord.Color.blue())
        await play_dice_animation(message, anim_embed)
        
        # 결과 계산
        dice_val = random.randint(1, 6)
        payout = self.bet * 2 if dice_val >= 4 else 0 # 4 이상 승리 예시

        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)
        
        is_win = payout > 0
        if STATS_AVAILABLE:
            stats_manager.record_game(str(self.user.id), self.user.display_name, "주사위", self.bet, payout, is_win)

        embed = discord.Embed(title="🎲 주사위 결과", color=discord.Color.gold() if is_win else discord.Color.red())
        result_text = "🏆 승리!" if is_win else "💀 패배..."
        embed.description = f"결과: {DICE_EMOJIS[dice_val]} ({dice_val})\n\n**{result_text}**\n정산: {payout:,}원"
        await message.edit(embed=embed, view=None)

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="상대방과 주사위 숫자가 높은 사람이 승리합니다.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

# --- 2단계: 멀티 세부 설정 View ---
class MultiSetupView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="대결 상대를 선택하세요.")
        async def callback(inter: discord.Interaction):
            target = user_select.values[0]
            if target.id == self.user.id or target.bot:
                return await inter.response.send_message("❌ 올바른 상대를 선택하세요.", ephemeral=True)
            
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, inter.guild_id, str(self.user.id), -self.bet)
                await point_manager.add_point(self.bot, inter.guild_id, str(target.id), -self.bet)
            await self.start_multi(inter, target)
        
        v = View(); user_select.callback = callback; v.add_item(user_select)
        await interaction.response.edit_message(content="상대를 선택해주세요.", embed=None, view=v)

    @discord.ui.button(label="🔓 공개 대전 (아무나)", style=discord.ButtonStyle.success)
    async def public_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)
        await self.start_multi(interaction, None)

    async def start_multi(self, interaction, target):
        view = MultiDiceView(self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="⚔️ 주사위 대결", description=f"배팅액: {self.bet:,}원\n상대방이 참여하면 주사위가 굴러갑니다!", color=discord.Color.orange())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

# --- 3단계: 멀티 게임 진행 View ---
class MultiDiceView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.message = None
        self.game_completed = False
        self.rolling = False # 애니메이션 중복 실행 방지 플래그

    @discord.ui.button(label="🎲 주사위 던지기", style=discord.ButtonStyle.danger)
    async def roll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. 메시지 객체 확보 (self.message가 없을 경우를 대비)
        if not self.message:
            self.message = await interaction.original_response()

        # 2. 참가자 확인 및 P2 등록
        if self.p2 is None and interaction.user.id != self.p1.id:
            self.p2 = interaction.user
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, interaction.guild_id, str(self.p2.id), -self.bet)
        
        if interaction.user.id not in [self.p1.id, self.p2.id if self.p2 else None]:
            return await interaction.response.send_message("❌ 대결 참가자가 아닙니다.", ephemeral=True)

        if self.p2 is None:
            return await interaction.response.send_message("⌛ 상대방을 기다리는 중입니다.", ephemeral=True)

        # 3. 게임 실행 (애니메이션 및 정산)
        if not self.rolling:
            self.rolling = True
            await interaction.response.defer() # 응답 지연 처리
            await self.finish_game_logic()
        else:
            await interaction.response.send_message("🎲 이미 주사위가 굴러가고 있습니다!", ephemeral=True)

    async def finish_game_logic(self):
        # 결과 선계산
        p1_roll = random.randint(1, 6)
        p2_roll = random.randint(1, 6)
        guild_id = self.message.guild.id
        
        # 애니메이션 실행 (기존 베이스 임베드 활용)
        anim_embed = discord.Embed(title="⚔️ 주사위 대결 진행 중", color=discord.Color.yellow())
        await play_dice_animation(self.message, anim_embed)
        
        # 결과 판정
        if p1_roll > p2_roll:
            winner, res_msg = self.p1, f"🏆 {self.p1.mention} 승리!"
        elif p2_roll > p1_roll:
            winner, res_msg = self.p2, f"🏆 {self.p2.mention} 승리!"
        else:
            winner, res_msg = None, "🤝 무승부! 배팅금이 환불됩니다."

        # 포인트 정산 로직
        reward_text = ""
        if winner:
            reward = int(self.bet * 2 * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            reward_text = f"\n수수료 제외 **{reward:,}원** 획득!"
            if STATS_AVAILABLE: # 통계 기록
                stats_manager.record_game(str(self.p1.id), self.p1.display_name, "주사위", self.bet, reward if winner == self.p1 else 0, winner == self.p1)
                stats_manager.record_game(str(self.p2.id), self.p2.display_name, "주사위", self.bet, reward if winner == self.p2 else 0, winner == self.p2)
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_text = f"\n각자 5% 제외 **{refund:,}원** 환불"

        # 최종 임베드 출력
        self.game_completed = True
        embed = discord.Embed(title="🎲 최종 결과", color=discord.Color.purple())
        embed.description = f"{res_msg}{reward_text}"
        embed.add_field(name=f"{self.p1.display_name}", value=f"{DICE_EMOJIS[p1_roll]} ({p1_roll})", inline=True)
        embed.add_field(name=f"{self.p2.display_name}", value=f"{DICE_EMOJIS[p2_roll]} ({p2_roll})", inline=True)
        
        await self.message.edit(embed=embed, view=None)

# --- Cog 클래스 ---
class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="주사위", description="주사위 게임을 시작합니다.(100원 ~ 5,000원)")
    async def dice_game(self, interaction: discord.Interaction, 배팅: int = 100):
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터!", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        if POINT_MANAGER_AVAILABLE:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
            if balance < 배팅: return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        view = DiceModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎲 **주사위 게임 모드 선택** (배팅: {배팅:,}원)", view=view)

async def setup(bot):
    await bot.add_cog(DiceCog(bot))