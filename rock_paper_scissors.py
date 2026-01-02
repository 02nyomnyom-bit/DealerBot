import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, UserSelect
import random
import asyncio

# --- 시스템 연동 및 설정 ---
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

# 상수 및 데이터
MAX_BET = 5000              # 최대 배팅금
PUSH_RETENTION = 0.95       # 무승부 시 5% 수수료 제외 (95%만 지급)
WINNER_RETENTION = 0.95     # 승리 시 5% 수수료 제외 (95%만 지급)
RPS_EMOJIS = {"가위": "✌️", "바위": "✊", "보": "✋"}

def record_rps_game(user_id: str, username: str, bet: int, payout: int, is_win: bool):
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game(user_id, username, "가위바위보", bet, payout, is_win)
        except: pass

# --- [상호작용 1단계] 초기 모드 선택창 ---
class RPSModeSelectView(View):
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
        # 포인트 선차감
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), -self.bet)

        embed = discord.Embed(title="🤖 가위바위보: 싱글 모드", description="무엇을 내실지 선택해주세요!", color=discord.Color.blue())
        await interaction.response.edit_message(embed=embed, view=SingleRPSView(self.bot, self.user, self.bet))

    @discord.ui.button(label="👥 멀티 모드", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def multi_mode(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="👥 멀티플레이 설정", description="대결 방식을 선택하세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=MultiSetupView(self.bot, self.user, self.bet))

# --- [싱글 모드 로직] ---
class SingleRPSView(View):
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="가위", emoji="✌️", style=discord.ButtonStyle.gray)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "가위")

    @discord.ui.button(label="바위", emoji="✊", style=discord.ButtonStyle.gray)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "바위")

    @discord.ui.button(label="보", emoji="✋", style=discord.ButtonStyle.gray)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "보")

    async def process_game(self, interaction, user_choice):
        bot_choice = random.choice(["가위", "바위", "보"])
        
        # 승패 판정
        if user_choice == bot_choice: result = "무승부"; payout = int(self.bet * PUSH_RETENTION)
        elif (user_choice == "가위" and bot_choice == "보") or \
             (user_choice == "바위" and bot_choice == "가위") or \
             (user_choice == "보" and bot_choice == "바위"):
            result = "승리"; payout = self.bet * 2
        else: result = "패배"; payout = 0

        if POINT_MANAGER_AVAILABLE and payout > 0:
            await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)
        
        record_rps_game(str(self.user.id), self.user.display_name, self.bet, payout, result == "승리")

        embed = discord.Embed(title="🎮 가위바위보 결과", color=discord.Color.gold() if result == "승리" else discord.Color.red())
        embed.description = f"**{self.user.display_name}**: {RPS_EMOJIS[user_choice]}\n**봇**: {RPS_EMOJIS[bot_choice]}\n\n**결과: {result}!**\n"
        embed.description += f"정산: {payout:,}원 (수수료 포함)" if result == "무승부" else f"정산: {payout:,}원"
        
        await interaction.response.edit_message(embed=embed, view=None)

# --- [멀티 모드 로직] ---
class MultiSetupView(View):
    """두 명의 유저가 각자 비밀리에 선택한 후 결과를 비교"""
    def __init__(self, bot, user, bet):
        super().__init__(timeout=60)
        self.bot, self.user, self.bet = bot, user, bet

    @discord.ui.button(label="🎯 상대 지정하기", style=discord.ButtonStyle.secondary)
    async def select_opponent(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_select = UserSelect(placeholder="상대를 선택하세요.")
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
        view = MultiRPSView(self.bot, self.user, self.bet, target)
        embed = discord.Embed(title="⚔️ 가위바위보 대결", description=f"배팅액: {self.bet:,}원\n두 분 모두 아래 버튼 중 하나를 눌러주세요!", color=discord.Color.orange())
        embed.add_field(name="P1", value=self.user.mention); embed.add_field(name="P2", value=target.mention if target else "대기 중...")
        await interaction.response.edit_message(content=None, embed=embed, view=view)
        view.message = await interaction.original_response()

class MultiRPSView(View):
    def __init__(self, bot, p1, bet, p2=None):
        super().__init__(timeout=60)
        self.bot, self.p1, self.bet, self.p2 = bot, p1, bet, p2
        self.choices = {}
        self.message = None
        self.game_completed = False # 이름을 is_finished에서 변경

    async def on_timeout(self):
        if self.game_completed: # 변경된 이름 적용
            return

        guild_id = self.message.guild.id
        refund_msg = "⏰ **시간 초과!** 게임이 취소되었습니다.\n"
        
        # 선차감된 포인트 환불 로직
        # 1. 방장(p1)은 항상 선차감되었으므로 무조건 환불
        if POINT_MANAGER_AVAILABLE:
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
        refund_msg += f"- {self.p1.mention}님에게 {self.bet:,}원 환불 완료\n"

        # 2. 상대방(p2)이 있고, 배팅이 이미 된 상태라면 환불
        # (공개 대전에서 참여 버튼을 누른 경우나, 지정 대전에서 이미 돈이 나간 경우)
        if self.p2:
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)
            refund_msg += f"- {self.p2.mention}님에게 {self.bet:,}원 환불 완료"

        # 화면 업데이트 (버튼 제거 및 안내)
        embed = discord.Embed(title="❌ 게임 취소", description=refund_msg, color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    async def finish_game(self):
        self.is_finished = True # 정상 종료되었으므로 timeout 이벤트 무시

    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.gray)
    async def scissors(self, interaction, button): await self.make_choice(interaction, "가위")
    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.gray)
    async def rock(self, interaction, button): await self.make_choice(interaction, "바위")
    @discord.ui.button(label="✋ 보", style=discord.ButtonStyle.gray)
    async def paper(self, interaction, button): await self.make_choice(interaction, "보")

    async def make_choice(self, interaction: discord.Interaction, choice: str):
        user_id = interaction.user.id
    
        # 1. 플레이어 판별
        if user_id == self.p1.id:
            if self.p1_choice:
                return await interaction.response.send_message("❌ 이미 선택하셨습니다.", ephemeral=True)
            self.p1_choice = choice
        elif self.p2 and user_id == self.p2.id:
            if self.p2_choice:
                return await interaction.response.send_message("❌ 이미 선택하셨습니다.", ephemeral=True)
            self.p2_choice = choice
        elif self.p2 is None:
            if user_id == self.p1.id:
                return await interaction.response.send_message("❌ 상대방을 기다려주세요.", ephemeral=True)
    
            # 1. p2를 즉시 할당하여 다른 사람의 난입을 빛의 속도로 차단
            self.p2 = interaction.user 
    
            # 2. 그 후 포인트 체크 및 차감
        if POINT_MANAGER_AVAILABLE:
            balance = await point_manager.get_point(self.bot, interaction.guild_id, str(user_id))
            if (balance or 0) < self.bet:
                self.p2 = None # 잔액 부족 시 다시 자리를 비움
                return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
            await point_manager.add_point(self.bot, interaction.guild_id, str(user_id), -self.bet)
    
        # 3. 주사위 값 할당
        self.p2_val = random.randint(1, 6)
        self.p2_rolled = True
        await interaction.channel.send(f"⚔️ {interaction.user.mention}님이 대결에 참가했습니다!")
    
        # 여기서 self.p2를 먼저 할당하여 다른 사람의 난입을 즉시 차단 (Race Condition 방지)
        self.p2 = interaction.user 
    
        if POINT_MANAGER_AVAILABLE:
        
            # 포인트 체크 및 차감
            if POINT_MANAGER_AVAILABLE:
                bal = await point_manager.get_point(self.bot, interaction.guild_id, str(user_id))
                if (bal or 0) < self.bet:
                    return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
                await point_manager.add_point(self.bot, interaction.guild_id, str(user_id), -self.bet)

            self.p2 = interaction.user
            self.p2_choice = choice
            await interaction.channel.send(f"⚔️ {interaction.user.mention}님이 가위바위보 대결에 난입했습니다!")
        else:
            return await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
        
        if interaction.user.id in self.choices:
            return await interaction.response.send_message("이미 선택하셨습니다!", ephemeral=True)

        self.choices[interaction.user.id] = choice
        await interaction.response.send_message(f"✅ {choice}를 선택하셨습니다!", ephemeral=True)

        if len(self.choices) == 2:
            await self.finish_game_logic()

    async def finish_game_logic(self): # 이름 변경
        self.game_completed = True # 변수명 수정
        c1, c2 = self.choices[self.p1.id], self.choices[self.p2.id]
        guild_id = self.message.guild.id
        
        if c1 == c2: winner = None; res = "무승부"
        elif (c1 == "가위" and c2 == "보") or (c1 == "바위" and c2 == "가위") or (c1 == "보" and c2 == "바위"):
            winner = self.p1; res = f"{self.p1.mention} 승리!"
        else: winner = self.p2; res = f"{self.p2.mention} 승리!"

        if winner:
            total_pot = self.bet * 2
            reward = int(total_pot * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            msg = f"💰 승자가 수수료 제외 **{reward:,}원**을 획득했습니다!"
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            msg = f"🤝 10% 수수료를 제외하고 각자 **{refund:,}원**씩 환불되었습니다."

        embed = discord.Embed(title="🎮 가위바위보 대결 결과", description=f"**{res}**\n{msg}\n\n{self.p1.mention}: {RPS_EMOJIS[c1]}\n{self.p2.mention}: {RPS_EMOJIS[c2]}", color=discord.Color.purple())
        await self.message.edit(embed=embed, view=None)

# --- Cog 클래스 ---
class RPSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="가위바위보", description="가위바위보 게임을 시작합니다. (100원 ~ 5,000원)")
    async def rps(self, interaction: discord.Interaction, 배팅: int = 100):
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터 가능합니다.", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
        if balance < 배팅: return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)

        view = RPSModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎮 **가위바위보 모드 선택** (배팅: {배팅:,}원)\n※ 무승부 시 수수료 5%가 차감됩니다.", view=view)

async def setup(bot):
    await bot.add_cog(RPSCog(bot))