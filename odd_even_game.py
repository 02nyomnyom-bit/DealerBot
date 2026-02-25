# odd_even_game.py - 홀짝
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
import random
import asyncio

# --- 시스템 연동부 ---
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
MAX_BET = 3000              # 최대 배팅금: 3천 원
PUSH_RETENTION = 0.8        # 무승부 시 수수료 (20%)
WINNER_RETENTION = 0.8      # 승리 시 수수료 (20%)

DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

def record_odd_even_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "odd_even", bet, payout, is_win)
        except: pass
        
# --- 애니메이션 유틸리티 ---
async def play_dice_animation(message: discord.InteractionMessage, base_embed: discord.Embed):
    dice_faces = list(DICE_EMOJIS.values())
    for _ in range(3):  # 횟수를 줄여 속도 향상
        current_face = random.choice(dice_faces)
        base_embed.description = f"🎲 **주사위를 굴리는 중...** {current_face}"
        await message.edit(embed=base_embed) # 애니메이션 도중 view를 건드리지 않음
        await asyncio.sleep(0.5)

# --- 1단계: 모드 선택 View ---
class OddEvenModeSelectView(View):
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
        
        embed = discord.Embed(title="🤖 홀짝: 싱글 모드", description="주사위 결과가 **홀**일지 **짝**일지 예측하세요!", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=SingleOddEvenView(self.bot, self.user, self.bet))

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

# --- 2단계: 싱글 게임 진행 View ---
class SingleOddEvenView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="홀 (1,3,5)", style=discord.ButtonStyle.danger, emoji="🔴")
    async def choose_odd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "홀")

    @discord.ui.button(label="짝 (2,4,6)", style=discord.ButtonStyle.primary, emoji="🔵")
    async def choose_even(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "짝")

    async def process_game(self, interaction: discord.Interaction, user_choice):
        # 1. 응답 지연 처리
        await interaction.response.defer()
    
        try:
            # 메시지 객체 확보
            message = await interaction.original_response()
        except Exception as e:
            print(f"메시지 확보 실패: {e}")
            return

        # 2. 버튼 즉시 제거 (중복 클릭 방지)
        anim_embed = discord.Embed(title="🎲 결과 확인 중...", color=discord.Color.light_grey())
        await message.edit(embed=anim_embed, view=None)

        # 3. 애니메이션 실행
        await play_dice_animation(message, anim_embed)

        # 4. 결과 계산 및 정산
        dice_val = random.randint(1, 6)
        actual = "홀" if dice_val % 2 != 0 else "짝"
        is_win = (user_choice == actual)
        
        # 배팅금의 2배 정산 (승리 시)
        payout = int(self.bet * 2 * WINNER_RETENTION) if is_win else 0
        if POINT_MANAGER_AVAILABLE and is_win:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)
    
        if STATS_AVAILABLE:
            stats_manager.record_game(str(self.user.id), self.user.display_name, "홀짝", self.bet, payout, is_win)

        # 5. 최종 결과 출력
        result_embed = discord.Embed(title="🎲 홀짝 결과", color=discord.Color.gold() if is_win else discord.Color.red())
        result_text = "🏆 맞췄습니다!" if is_win else "💀 틀렸습니다..."
        result_embed.description = (
            f"선택: **{user_choice}**\n"
            f"결과: {DICE_EMOJIS[dice_val]} ({dice_val}) -> **{actual}**\n\n"
            f"**{result_text}**\n"
            f"정산: {payout:,}원\n*20%의 딜러비가 차감된 후 지급됩니다."
        )
    
        await message.edit(embed=result_embed)

# --- 3단계: 멀티 세부 설정 View ---
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
        view = MultiOddEvenView(self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="⚔️ 홀짝 대결", description=f"배팅액: {self.bet:,}원\n두 분 모두 홀 또는 짝을 선택해주세요!", color=discord.Color.orange())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
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

class MultiOddEvenView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.choices = {}
        self.message = None
        self.game_completed = False
        
    async def on_timeout(self):
        if self.game_completed: return
        guild_id = self.message.guild.id
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
            if self.p2: await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)
        embed = discord.Embed(title="❌ 타임아웃 환불", description="⏰ 두 분 모두 선택하지 않아 게임이 취소되었습니다.", color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    @discord.ui.button(label="홀", style=discord.ButtonStyle.primary)
    async def odd_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "홀")

    @discord.ui.button(label="짝", style=discord.ButtonStyle.secondary)
    async def even_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.make_choice(interaction, "짝")

    async def make_choice(self, interaction, choice):
        if self.p2 is None and interaction.user.id != self.p1.id:
            self.p2 = interaction.user
            if POINT_MANAGER_AVAILABLE: await point_manager.add_point(self.bot, interaction.guild_id, str(self.p2.id), -self.bet)

        if interaction.user.id not in [self.p1.id, self.p2.id if self.p2 else None]:
            return await interaction.response.send_message("❌ 참가자가 아닙니다.", ephemeral=True)
        
        if interaction.user.id in self.choices:
            return await interaction.response.send_message("이미 선택하셨습니다!", ephemeral=True)

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ {choice}를 선택하셨습니다!", ephemeral=True)

        if len(self.choices) == 2:
            await self.finish_game_logic()

    async def finish_game_logic(self):
        self.game_completed = True
        
        anim_embed = discord.Embed(title="🎲 결과 확인 중...", color=discord.Color.light_grey())
        await self.message.edit(embed=anim_embed, view=None)

        # 애니메이션 실행
        await play_dice_animation(self.message, anim_embed)
        
        dice_val = random.randint(1, 6)
        actual = "홀" if dice_val % 2 != 0 else "짝"
        guild_id = self.message.guild.id
        
        p1_correct = (self.choices[self.p1.id] == actual)
        p2_correct = (self.choices[self.p2.id] == actual)

        if p1_correct and not p2_correct: winner = self.p1
        elif p2_correct and not p1_correct: winner = self.p2
        else: winner = None

        if winner:
            total_pot = self.bet * 2
            reward = int(total_pot * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE: await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            res_msg = f"🏆 {winner.mention} 승리! **{reward:,}원** 획득!\n*20%의 딜러비가 차감된 후 지급됩니다."
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            res_msg = f"🤝 무승부! (**{refund:,}원** 환불)\n*20%의 딜러비가 차감된 후 지급됩니다."

        result_embed = discord.Embed(title="🎲 홀짝 대결 결과", color=discord.Color.purple())
        result_embed.description = (
            f"결과: {DICE_EMOJIS[dice_val]} ({dice_val}) -> **{actual}**\n\n"
            f"**{res_msg}**\n"
            f"{self.p1.mention}: {self.choices[self.p1.id]}\n"
            f"{self.p2.mention}: {self.choices.get(self.p2.id, '선택 안 함')}"
        )

        await self.message.edit(embed=result_embed)

# --- Cog 클래스 ---
class OddEvenCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="홀짝", description="홀짝 게임을 시작합니다.(100원 ~ 3,000원)")
    async def odd_even(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'odd_even' 권한이 있는지 체크 (channel_config.py의 value="odd_even"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "odd_even", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터!", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        if POINT_MANAGER_AVAILABLE:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
            if balance < 배팅: return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        view = OddEvenModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎲 **홀짝 게임 모드 선택** (배팅: {배팅:,}원)", view=view)

async def setup(bot):
    await bot.add_cog(OddEvenCog(bot))