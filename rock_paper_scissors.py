# rock_paper_scissors.py - 가위바위보
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
PUSH_RETENTION = 1.0
WINNER_RETENTION = 1.0
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
    async def scissors_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "가위")

    @discord.ui.button(label="바위", emoji="✊", style=discord.ButtonStyle.gray)
    async def rock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "바위")

    @discord.ui.button(label="보", emoji="✋", style=discord.ButtonStyle.gray)
    async def paper_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_game(interaction, "보")

    async def process_game(self, interaction, user_choice):
        bot_choice = random.choice(["가위", "바위", "보"])
        
        if user_choice == bot_choice:
            result = "무승부"
            payout = int(self.bet * PUSH_RETENTION)
        elif (user_choice == "가위" and bot_choice == "보") or \
             (user_choice == "바위" and bot_choice == "가위") or \
             (user_choice == "보" and bot_choice == "바위"):
            result = "승리"
            payout = int(self.bet * 2 * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, interaction.guild_id, str(self.user.id), payout)
        else:
            result = "패배"
            payout = 0
        
        record_rps_game(str(self.user.id), self.user.display_name, self.bet, payout, result == "승리")

        embed = discord.Embed(title="🎮 가위바위보 결과", color=discord.Color.gold() if result == "승리" else discord.Color.red())
        embed.description = f"**{self.user.display_name}**: {RPS_EMOJIS[user_choice]}\n**봇**: {RPS_EMOJIS[bot_choice]}\n\n**결과: {result}!**\n"
        embed.description += f"정산: {payout:,}원" if result == "무승부" else f"정산: {payout:,}원"
        
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
        self.choices = {}  # {user_id: "가위"} 형태로 저장
        self.message = None
        self.game_completed = False

    async def on_timeout(self):
        if self.game_completed:
            return

        guild_id = self.message.guild.id
        refund_msg = "⏰ **시간 초과!** 게임이 취소되었습니다.\n"
        
        if POINT_MANAGER_AVAILABLE:
            # 방장(p1)은 항상 환불
            await point_manager.add_point(self.bot, guild_id, str(self.p1.id), self.bet)
            refund_msg += f"- {self.p1.mention}님 환불 완료\n"
            # 참여자(p2)가 존재하면 환불
            if self.p2:
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), self.bet)
                refund_msg += f"- {self.p2.mention}님 환불 완료"

        embed = discord.Embed(title="❌ 게임 취소", description=refund_msg, color=discord.Color.red())
        await self.message.edit(embed=embed, view=None)

    @discord.ui.button(label="✌️ 가위", style=discord.ButtonStyle.gray)
    async def scissors(self, interaction, button): await self.make_choice(interaction, "가위")
    @discord.ui.button(label="✊ 바위", style=discord.ButtonStyle.gray)
    async def rock(self, interaction, button): await self.make_choice(interaction, "바위")
    @discord.ui.button(label="✋ 보", style=discord.ButtonStyle.gray)
    async def paper(self, interaction, button): await self.make_choice(interaction, "보")

    async def make_choice(self, interaction: discord.Interaction, choice: str):
        user = interaction.user
        
        # 1. 이미 선택한 유저인지 확인
        if user.id in self.choices:
            return await interaction.response.send_message("❌ 이미 선택하셨습니다.", ephemeral=True)

        # 2. 플레이어 자격 및 공개 대전 난입 처리
        if user.id == self.p1.id:
            pass # 방장은 이미 포인트가 차감된 상태임
        elif self.p2 is not None:
            # 지정 대전인데 다른 사람이 누른 경우
            if user.id != self.p2.id:
                return await interaction.response.send_message("❌ 이 게임의 참가자가 아닙니다.", ephemeral=True)
        else:
            # 공개 대전(p2가 None)인 경우 첫 번째 누른 사람이 p2가 됨
            if POINT_MANAGER_AVAILABLE:
                bal = await point_manager.get_point(self.bot, interaction.guild_id, str(user.id))
                if (bal or 0) < self.bet:
                    return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)
                await point_manager.add_point(self.bot, interaction.guild_id, str(user.id), -self.bet)
            
            self.p2 = user # 참가자 확정
            
            # P2 참가 사실을 원래 메시지에 업데이트
            original_embed = self.message.embeds[0]
            original_embed.set_field_at(1, name="P2", value=self.p2.mention)
            await self.message.edit(embed=original_embed)
            await interaction.channel.send(f"⚔️ {user.mention}님이 대결에 참가했습니다!", delete_after=5)

        # 3. 선택 저장 및 응답
        self.choices[user.id] = choice
        await interaction.response.send_message(f"✅ {choice}를 선택하셨습니다!", ephemeral=True)

        # 4. 두 명 모두 선택 완료 시 결과 발표
        if len(self.choices) == 2:
            await self.finish_game_logic()

    async def finish_game_logic(self):
        self.game_completed = True
        c1 = self.choices[self.p1.id]
        c2 = self.choices[self.p2.id]
        guild_id = self.message.guild.id
        
        # 승패 판정 로직
        if c1 == c2:
            winner = None
            res = "🤝 무승부"
        elif (c1 == "가위" and c2 == "보") or (c1 == "바위" and c2 == "가위") or (c1 == "보" and c2 == "바위"):
            winner = self.p1
            res = f"🏆 {self.p1.display_name} 승리!"
        else:
            winner = self.p2
            res = f"🏆 {self.p2.display_name} 승리!"

        # 정산
        if winner:
            reward = int((self.bet * 2) * WINNER_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(winner.id), reward)
            msg = f"💰 승자에게 **{reward:,}원**이 지급되었습니다."
            record_rps_game(str(self.p1.id), self.p1.display_name, self.bet, reward if winner == self.p1 else 0, winner == self.p1)
            record_rps_game(str(self.p2.id), self.p2.display_name, self.bet, reward if winner == self.p2 else 0, winner == self.p2)
        else:
            refund = int(self.bet * PUSH_RETENTION)
            if POINT_MANAGER_AVAILABLE:
                await point_manager.add_point(self.bot, guild_id, str(self.p1.id), refund)
                await point_manager.add_point(self.bot, guild_id, str(self.p2.id), refund)
            msg = f"🤝 각자 **{refund:,}원**씩 환불되었습니다."

        embed = discord.Embed(
            title="🎮 가위바위보 대결 결과", 
            description=f"### {res}\n{msg}\n\n**{self.p1.display_name}**: {RPS_EMOJIS[c1]}\n**{self.p2.display_name}**: {RPS_EMOJIS[c2]}", 
            color=discord.Color.purple()
        )
        await self.message.edit(embed=embed, view=None)

# --- Cog 클래스 ---
class RPSCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="가위바위보", description="가위바위보 게임을 시작합니다. (100원 ~ 5,000원)")
    async def rps(self, interaction: discord.Interaction, 배팅: int = 100):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'point_2' 권한이 있는지 체크 (channel_config.py의 value="point_2"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "point_2", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        # XP 시스템을 가져와서 실행
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        if 배팅 < 100: return await interaction.response.send_message("❌ 최소 100원부터 가능합니다.", ephemeral=True)
        if 배팅 > MAX_BET: return await interaction.response.send_message(f"❌ 최대 배팅금은 {MAX_BET:,}원입니다.", ephemeral=True)
        
        # balance가 None일 경우를 대비해 0으로 치환
        balance = await point_manager.get_point(self.bot, interaction.guild_id, str(interaction.user.id))
        user_balance = balance if balance is not None else 0
        
        if user_balance < 배팅: 
            return await interaction.response.send_message("❌ 잔액이 부족합니다.", ephemeral=True)

        view = RPSModeSelectView(self.bot, interaction.user, 배팅)
        await interaction.response.send_message(f"🎮 **가위바위보 모드 선택** (배팅: {배팅:,}원)", view=view)

async def setup(bot):
    await bot.add_cog(RPSCog(bot))