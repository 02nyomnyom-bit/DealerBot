# dice_game.py - [게임] 주사위
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

# 상수 설정
MAX_BET = 3000              # 최대 배팅금: 3천 원
PUSH_RETENTION = 0.8        # 무승부 시 수수료 (20%)
WINNER_RETENTION = 0.8      # 승리 시 수수료 (20%)

# 애니메이션
async def play_dice_animation(message: discord.InteractionMessage, base_embed: discord.Embed):
    dice_faces = list(DICE_EMOJIS.values())
    for _ in range(3):
        current_face = random.choice(dice_faces)
        base_embed.description = f"🎲 **주사위를 굴리는 중...** {current_face}"
        await message.edit(embed=base_embed)
        await asyncio.sleep(0.5)

# 통계 기록 헬퍼 함수
def record_dice_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "dice_game", bet, payout, is_win)
        except Exception as e:
            print(f"통계 기록 오류: {e}")

# 모드 선택 및 멀티플레이 View
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
        await interaction.response.defer()
        message = await interaction.original_response()
        
        # 포인트 차감
        if POINT_MANAGER_AVAILABLE:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(self.user.id))
            if balance < self.bet:
                return await interaction.followup.send("❌ 잔액이 부족합니다.", ephemeral=True)
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)

        # 애니메이션 실행
        anim_embed = discord.Embed(title="🤖 주사위: 싱글 모드 (vs 봇)", color=discord.Color.blue())
        await play_dice_animation(message, anim_embed)

        user_roll = random.randint(1, 6) # 사용자 주사위
        bot_roll = random.randint(1, 6)  # 봇 주사위

        if user_roll > bot_roll:
            is_win = True
            res_msg = "🏆 승리!"
            payout = int(self.bet * 2 * WINNER_RETENTION)
        elif user_roll < bot_roll:
            is_win = False
            res_msg = "💀 패배..."
            payout = 0
        else:
            is_win = False # 무승부는 승리가 아님
            res_msg = "🤝 무승부!"
            payout = int(self.bet * PUSH_RETENTION) # 무승부 환불 로직 적용

        # 5. 포인트 지급 및 통계 기록
        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)

        record_dice_game(str(self.user.id), self.user.display_name, self.bet, payout, is_win)

        # 6. 최종 결과 표시
        result_embed = discord.Embed(title="🎲 주사위 결과", color=discord.Color.gold() if is_win else discord.Color.red())
        result_embed.description = f"**{res_msg}**\n정산: {payout:,}원\n*20%의 딜러비가 차감된 후 지급됩니다."
        result_embed.add_field(name=f"👤 {self.user.display_name}", value=f"{DICE_EMOJIS[user_roll]} ({user_roll})", inline=True)
        result_embed.add_field(name="🤖 봇", value=f"{DICE_EMOJIS[bot_roll]} ({bot_roll})", inline=True)

        await message.edit(embed=result_embed, view=None)

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="상대방과 주사위 숫자가 높은 사람이 승리합니다.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

# 멀티 지정 View
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

# 멀티 주사위게임 View
class MultiDiceView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.message = None
        self.game_completed = False
        
        # p2가 정해졌는지 여부에 따라 버튼 라벨을 다르게 설정
        button_label = "🎲 주사위 던지기" if self.p2 else "⚔️ 참가하기"
        self.add_item(self.ActionButton(label=button_label))

    async def on_timeout(self):
        if self.game_completed:
            return
        
        # 게임이 완료되지 않고 타임아웃되면, 베팅 금액을 환불합니다.
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, self.message.guild.id, str(self.p1.id), self.bet)
            if self.p2:
                await point_manager.add_point(self.bot, self.message.guild.id, str(self.p2.id), self.bet)

        embed = discord.Embed(title="⏰ 시간 초과", description="게임이 취소되어 배팅금이 환불되었습니다.", color=discord.Color.red())
        try:
            await self.message.edit(embed=embed, view=None)
        except discord.NotFound:
            pass # 메시지가 이미 삭제된 경우

    class ActionButton(discord.ui.Button):
        async def callback(self, interaction: discord.Interaction):
            view: MultiDiceView = self.view
            user = interaction.user

            if view.game_completed:
                return await interaction.response.send_message("이미 종료된 게임입니다.", ephemeral=True)

            # 공개 대전: P2 참가 처리
            if view.p2 is None:
                if user.id == view.p1.id:
                    return await interaction.response.send_message("자신과의 대결에는 참가할 수 없습니다.", ephemeral=True)
                
                view.p2 = user
                if POINT_MANAGER_AVAILABLE:
                    balance = await point_manager.get_point(view.bot, interaction.guild_id, str(user.id))
                    if balance < view.bet:
                        view.p2 = None # 참가 자격 박탈
                        return await interaction.response.send_message("❌ 잔액이 부족하여 참가할 수 없습니다.", ephemeral=True)
                    await point_manager.add_point(view.bot, interaction.guild_id, str(user.id), -view.bet)
                
                # P2 참가 후 즉시 게임 시작
                await interaction.response.defer()
                await view.finish_game_logic()

            # 지정 대전: P1 또는 P2가 버튼을 눌러 게임 시작
            else:
                if user.id not in [view.p1.id, view.p2.id]:
                    return await interaction.response.send_message("❌ 대결 참가자가 아닙니다.", ephemeral=True)
                
                await interaction.response.defer()
                await view.finish_game_logic()

    async def finish_game_logic(self):
        self.game_completed = True
        p1_roll = random.randint(1, 6)
        p2_roll = random.randint(1, 6)
        guild_id = self.message.guild.id
        
        # 애니메이션 실행
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
        p1_payout, p2_payout = 0, 0
        if winner:
            reward = int(self.bet * 2 * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            reward_text = f"\n**{reward:,}원** 획득!\n*20%의 딜러비가 차감된 후 지급됩니다."
            if winner == self.p1: p1_payout = reward
            else: p2_payout = reward
        else: # 무승부
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            reward_text = f"\n**{refund:,}원** 환불\n*20%의 딜러비가 차감된 후 지급됩니다."
            p1_payout = p2_payout = refund

        # 통계 기록 (무승부 포함)
        if STATS_AVAILABLE:
            stats_manager.record_game(str(self.p1.id), self.p1.display_name, "주사위", self.bet, p1_payout, winner == self.p1)
            stats_manager.record_game(str(self.p2.id), self.p2.display_name, "주사위", self.bet, p2_payout, winner == self.p2)

        # 최종 임베드 출력
        result_embed = discord.Embed(title="🎲 최종 결과", color=discord.Color.purple())
        result_embed.description = f"{res_msg}{reward_text}"
        result_embed.add_field(name=f"{self.p1.display_name}", value=f"{DICE_EMOJIS[p1_roll]} ({p1_roll})", inline=True)
        result_embed.add_field(name=f"{self.p2.display_name}", value=f"{DICE_EMOJIS[p2_roll]} ({p2_roll})", inline=True)
    
        await self.message.edit(embed=result_embed, view=None)

# --- Cog 클래스 ---
class DiceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="주사위", description="주사위 게임을 시작합니다.(100원 ~ 3,000원)")
    async def dice_game(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'dice' 권한이 있는지 체크 (channel_config.py의 value="dice"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "dice", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터!", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        if POINT_MANAGER_AVAILABLE:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
            if balance < 배팅: return await interaction.response.send_message("❌ 잔액 부족!", ephemeral=True)

        view = DiceModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎲 **주사위 게임 모드 선택** (배팅: {배팅:,}원)", view=view)

async def setup(bot):
    await bot.add_cog(DiceCog(bot))