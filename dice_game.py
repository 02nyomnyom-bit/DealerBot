# dice_game.py - 주사위 게임 (통계 기록 추가)
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View
from typing import Literal, Optional
import random
import asyncio # ✅ 비동기 대기 및 애니메이션을 위해 추가

# ✅ 통계 시스템 안전 임포트 (추가)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (주사위)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (주사위)")

# point_manager 임포트
try:
    import point_manager
    POINT_MANAGER_AVAILABLE = True
except ImportError:
    POINT_MANAGER_AVAILABLE = False
    
    class MockPointManager:
        @staticmethod
        async def is_registered(bot, guild_id, user_id): 
            return True
    
        @staticmethod
        async def get_point(bot, guild_id, user_id):
            return 10000
    
        @staticmethod
        async def add_point(bot, guild_id, user_id, amount):
            return True
    
        @staticmethod
        async def register_user(bot, guild_id, user_id):
            pass

    point_manager = MockPointManager()

# 주사위 이모지
DICE_EMOJIS = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}

# ✅ 통계 기록 도우미 함수 (통계 시스템이 있을 경우에만 실행)
async def record_dice_stats(user_id, is_single, result, bet, win_amount=0):
    if STATS_AVAILABLE:
        try:
            game_type = "single_dice" if is_single else "multi_dice"
            await stats_manager.record_game(
                user_id=user_id,
                game_type=game_type,
                result=result, # "win" or "lose" or "draw"
                bet_amount=bet,
                win_amount=win_amount
            )
        except Exception as e:
            print(f"주사위 게임 통계 기록 오류: {e}")

# ✅ 싱글 주사위 게임 View (봇과 대결)
class SingleDiceView(View):
    def __init__(self, bot: commands.Bot, user: discord.User, bet: int):
        super().__init__(timeout=60)
        self.bot = bot
        self.user = user
        self.bet = bet
        self.message = None
        self.game_started = False
        self.guild_id = user.guild.id

    @discord.ui.button(label="🎲 주사위 굴리기", style=discord.ButtonStyle.primary)
    async def roll_dice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❗ 본인만 주사위를 굴릴 수 있습니다.", ephemeral=True)
        
        if self.game_started:
            return await interaction.response.send_message("⚠️ 이미 게임이 시작되었습니다.", ephemeral=True)
        
        self.game_started = True
        button.disabled = True
        
        await self.roll_dice(interaction)

    async def roll_dice(self, interaction: discord.Interaction):
        uid = str(self.user.id)
        gid = str(self.guild_id)
        
        try:
            # 잔액 재검증
            current_balance = await point_manager.get_point(self.bot, gid, uid)
            if current_balance < self.bet:
                await interaction.response.edit_message(
                    content=f"❌ 잔액 부족으로 게임을 시작할 수 없습니다. (현재 잔액: {current_balance:,}원)",
                    embed=None,
                    view=None
                )
                self.stop()
                return

            # 배팅 금액 차감
            await point_manager.add_point(self.bot, gid, uid, -self.bet)
            
            # 애니메이션 시작 메시지
            await interaction.response.edit_message(
                embed=None,
                content=f"🎲 **주사위 굴리는 중...**\n\n👤 **{self.user.display_name}** 배팅: {self.bet:,}원"
            )
            self.message = await interaction.original_response()

            # ✅ 주사위 굴리는 애니메이션 (랜덤 눈금)
            dice_faces = list(DICE_EMOJIS.values())
            animation_turns = 5 
            
            for i in range(animation_turns):
                current_face = random.choice(dice_faces) # ✅ 랜덤으로 이모지 선택
                content = (
                    f"{current_face} **주사위 굴리는 중...** {current_face}\n\n"
                    f"👤 **{self.user.display_name}** 배팅: {self.bet:,}원"
                )
                await self.message.edit(content=content, view=self, embed=None)
                await asyncio.sleep(0.3) 

            # 결과 계산
            user_roll = random.randint(1, 6)
            bot_roll = random.randint(1, 6)
            
            # 승부 판정
            if user_roll > bot_roll:
                winner_roll = user_roll
                loser_roll = bot_roll
                winner_name = self.user.display_name
                
                # 승리: 배팅 금액 * 2 지급 (이미 차감된 금액 + 승리 보상)
                reward = self.bet * 2
                await point_manager.add_point(self.bot, gid, uid, reward)
                outcome = f"🎉 **{winner_name}**님 승리! +{reward:,}원 획득"
                color = discord.Color.green()
                await record_dice_stats(uid, True, "win", self.bet, reward - self.bet)
            
            elif bot_roll > user_roll:
                winner_roll = bot_roll
                loser_roll = user_roll
                winner_name = self.bot.user.display_name # 봇 이름
                
                # 패배: 이미 차감됨
                outcome = f"😢 **{winner_name}** 승리. -{self.bet:,}원 차감"
                color = discord.Color.red()
                await record_dice_stats(uid, True, "lose", self.bet, -self.bet)

            else:
                # 무승부: 배팅 금액 반환
                reward = self.bet
                await point_manager.add_point(self.bot, gid, uid, reward)
                outcome = "🤝 무승부! 배팅 금액이 반환되었습니다."
                color = discord.Color.gold()
                await record_dice_stats(uid, True, "draw", self.bet, 0)
                
                
            # 최종 잔액 조회
            final_balance = await point_manager.get_point(self.bot, gid, uid)

            # 결과 임베드 생성
            embed = discord.Embed(
                title="🎲 싱글 주사위 게임 결과",
                description=outcome,
                color=color
            )
            embed.add_field(name=f"👤 {self.user.display_name}의 주사위", value=f"{DICE_EMOJIS[user_roll]} **{user_roll}**", inline=True)
            embed.add_field(name=f"🤖 {self.bot.user.display_name}의 주사위", value=f"{DICE_EMOJIS[bot_roll]} **{bot_roll}**", inline=True)
            embed.add_field(name="💰 현재 잔액", value=f"{final_balance:,}원", inline=False)
            embed.set_footer(text=f"배팅 금액: {self.bet:,}원")

            await self.message.edit(content=None, embed=embed, view=None)
            self.stop()
            
        except Exception as e:
            print(f"싱글 주사위 게임 오류: {e}")
            try:
                await interaction.followup.send("❌ 게임 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass


    async def on_timeout(self):
        try:
            if not self.game_started:
                # 게임 시작 전에 타임아웃된 경우
                for item in self.children:
                    item.disabled = True
                    item.label = "시간 만료"
                    item.style = discord.ButtonStyle.secondary
                
                if self.message:
                    embed = discord.Embed(
                        title="⏰ 게임 시간 만료",
                        description="주사위 굴리기 전에 게임이 시간 초과로 종료되었습니다.",
                        color=discord.Color.orange()
                    )
                    await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"싱글 주사위 타임아웃 처리 오류: {e}")


# ✅ 멀티 주사위 게임 View (유저 간 대결)
class MultiDiceView(View):
    def __init__(self, bot: commands.Bot, player1: discord.User, bet: int, opponent: Optional[discord.User] = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.player1 = player1
        self.bet = bet
        self.opponent = opponent
        self.player2 = None
        self.rolls = {}
        self.message = None
        self.guild_id = player1.guild.id
        self.paid_users = set()

    @discord.ui.button(label="🎲 주사위 굴리기", style=discord.ButtonStyle.primary)
    async def roll_dice_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        uid = str(user.id)
        gid = str(self.guild_id)

        try:
            # 1. 플레이어 확정 및 검증
            is_player1 = user == self.player1

            if self.opponent:
                if user not in [self.player1, self.opponent]:
                    return await interaction.response.send_message("❌ 이 게임에 참여할 수 없습니다.", ephemeral=True)
                if user == self.opponent:
                    self.player2 = self.opponent
            else: # 자유 참여 모드
                if not is_player1 and not self.player2:
                    self.player2 = user
                elif not is_player1 and self.player2 and user != self.player2:
                    return await interaction.response.send_message("❌ 이미 다른 플레이어가 참여했습니다.", ephemeral=True)

            if self.player2 and user not in [self.player1, self.player2]:
                 return await interaction.response.send_message("❌ 이 게임에 참여할 수 없습니다.", ephemeral=True)


            # 2. 이미 굴렸는지 검증
            if uid in self.rolls:
                return await interaction.response.send_message("⚠️ 이미 주사위를 굴렸습니다.", ephemeral=True)

            # 3. 잔액 검증
            current_balance = await point_manager.get_point(self.bot, gid, uid)
            if current_balance < self.bet:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다! (현재 잔액: {current_balance:,}원)", ephemeral=True
                )

            # 4. 배팅 금액 차감 (한 번만)
            if uid not in self.paid_users:
                await point_manager.add_point(self.bot, gid, uid, -self.bet)
                self.paid_users.add(uid)

            # 5. 주사위 굴리기
            roll = random.randint(1, 6)
            self.rolls[uid] = {"user": user, "roll": roll}
            
            await interaction.response.send_message(
                f"✅ {user.mention}님이 주사위를 굴렸습니다! ({DICE_EMOJIS[roll]} **{roll}**)", ephemeral=True
            )
            
            # --- [메시지 업데이트] ---
            if self.message:
                embed = self.message.embeds[0]
                
                # P2 필드 업데이트 (참가자 확정 시)
                p2_index = -1
                for i, field in enumerate(embed.fields):
                    if field.name.startswith('**플레이어2**'):
                        p2_index = i
                        break
                
                if self.player2 and p2_index != -1:
                    embed.set_field_at(
                        index=p2_index,
                        name=f"**플레이어2**: {self.player2.mention}",
                        value=f"굴림: {DICE_EMOJIS[self.rolls[str(self.player2.id)]['roll']]} ({self.rolls[str(self.player2.id)]['roll']})" if str(self.player2.id) in self.rolls else "대기 중",
                        inline=True
                    )
                
                # P1 필드 업데이트
                p1_index = -1
                for i, field in enumerate(embed.fields):
                    if field.name.startswith('**플레이어1**'):
                        p1_index = i
                        break

                if p1_index != -1:
                    embed.set_field_at(
                        index=p1_index,
                        name=f"**플레이어1**: {self.player1.mention}",
                        value=f"굴림: {DICE_EMOJIS[self.rolls[str(self.player1.id)]['roll']]} ({self.rolls[str(self.player1.id)]['roll']})" if str(self.player1.id) in self.rolls else "대기 중",
                        inline=True
                    )

                # 풋터 메시지 업데이트
                if self.player1 and self.player2 and len(self.rolls) == 2:
                    embed.set_footer(text="두 플레이어 모두 주사위를 굴렸습니다! 결과 공개!")
                elif self.player1 and self.player2:
                    embed.set_footer(text="상대방의 주사위 굴림을 기다리는 중...")
                elif self.player1 and not self.player2:
                    embed.set_footer(text="다른 플레이어의 참여를 기다리는 중...")
                
                await self.message.edit(embed=embed, view=self)

            # 6. 두 명 모두 굴렸으면 결과 처리
            if self.player1 and self.player2 and len(self.rolls) == 2:
                await self.show_results(interaction)

        except Exception as e:
            print(f"멀티 주사위 굴림 오류: {e}")
            try:
                await interaction.followup.send("❌ 주사위 굴림 중 오류가 발생했습니다.", ephemeral=True)
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
                title="🎲 멀티 주사위 게임 결과 계산 중",
                description="주사위를 굴리는 중...",
                color=discord.Color.yellow()
            )
            
            if self.message:
                await self.message.edit(embed=embed, view=self)
            else:
                # 이미 주사위 굴리기에서 응답했으므로 followup 사용
                await interaction.followup.send(embed=embed, view=self) 
                self.message = await interaction.original_response()

            # 플레이어 데이터 정리
            uids = list(self.rolls.keys())
            user1_data = self.rolls[uids[0]]
            user2_data = self.rolls[uids[1]]

            # ✅ 애니메이션 효과 (주사위 눈금으로 랜덤 순환)
            dice_faces = list(DICE_EMOJIS.values()) 
            animation_turns = 5 
            
            for i in range(animation_turns):
                current_face = random.choice(dice_faces) # ✅ 랜덤으로 이모지 선택
                
                embed.description = (
                    f"{current_face} **최종 결과 공개 카운트다운...** {current_face}\n\n"
                    f"👤 **{user1_data['user'].display_name}**: {DICE_EMOJIS[user1_data['roll']]} (??)\n"
                    f"👤 **{user2_data['user'].display_name}**: {DICE_EMOJIS[user2_data['roll']]} (??)\n\n"
                    f"💰 총 배팅 금액: {self.bet * 2:,}원"
                )
                try:
                    await self.message.edit(embed=embed, view=self)
                    await asyncio.sleep(0.3)
                except:
                    pass

            # 승부 판정
            roll1 = user1_data['roll']
            roll2 = user2_data['roll']
            winner_data = None
            loser_data = None
            is_draw = False

            if roll1 > roll2:
                winner_data = user1_data
                loser_data = user2_data
            elif roll2 > roll1:
                winner_data = user2_data
                loser_data = user1_data
            else:
                is_draw = True

            # 포인트 처리 및 결과 메시지
            result_color = discord.Color.gold()
            
            if is_draw:
                # 무승부: 배팅 금액 반환
                for uid in self.paid_users:
                    await point_manager.add_point(self.bot, self.guild_id, uid, self.bet)
                
                result_text = "🤝 무승부! 배팅 금액이 반환되었습니다."
                result_color = discord.Color.gold()
                await record_dice_stats(str(user1_data['user'].id), False, "draw", self.bet, 0)
                await record_dice_stats(str(user2_data['user'].id), False, "draw", self.bet, 0)
                
            else:
                # 승리: 총 배팅 금액 (배팅 * 2) 획득
                winner_uid = str(winner_data['user'].id)
                win_amount = self.bet * 2
                await point_manager.add_point(self.bot, self.guild_id, winner_uid, win_amount)
                
                result_text = f"🎉 **{winner_data['user'].display_name}**님 승리! +{win_amount:,}원 획득"
                result_color = discord.Color.green()

                # 통계 기록 (승/패)
                await record_dice_stats(winner_uid, False, "win", self.bet, win_amount - self.bet)
                await record_dice_stats(str(loser_data['user'].id), False, "lose", self.bet, -self.bet)

            # 최종 잔액 조회
            balance1 = await point_manager.get_point(self.bot, self.guild_id, str(user1_data['user'].id))
            balance2 = await point_manager.get_point(self.bot, self.guild_id, str(user2_data['user'].id))

            # 결과 임베드
            embed = discord.Embed(
                title="🎲 멀티 주사위 게임 결과",
                description=result_text,
                color=result_color
            )
            embed.add_field(name=f"👤 {user1_data['user'].display_name}", value=f"{DICE_EMOJIS[roll1]} **{roll1}**", inline=True)
            embed.add_field(name=f"👤 {user2_data['user'].display_name}", value=f"{DICE_EMOJIS[roll2]} **{roll2}**", inline=True)
            
            if is_draw:
                embed.add_field(name="💰 포인트 변동", value="0원", inline=False)
            else:
                embed.add_field(name="💰 최종 획득/손실", value=f"{win_amount:,}원 / -{self.bet:,}원", inline=False)
            
            embed.add_field(
                name="💰 현재 잔액", 
                value=f"**{user1_data['user'].display_name}**: {balance1:,}원\n**{user2_data['user'].display_name}**: {balance2:,}원", 
                inline=False
            )

            await self.message.edit(embed=embed, view=None)
            self.stop()
            
        except Exception as e:
            print(f"멀티 주사위 게임 결과 처리 오류: {e}")
            try:
                # 주사위 굴리기에서 이미 interaction.response.send_message를 사용했으므로 followup 사용
                await interaction.followup.send("❌ 게임 결과 처리 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass


    async def on_timeout(self):
        try:
            # 타임아웃 시 배팅 금액 반환
            if len(self.paid_users) > 0 and len(self.rolls) < 2:
                # 게임이 완료되지 않고 (2명 모두 주사위를 굴리지 않고) 타임아웃된 경우에만 반환
                for user_id in self.paid_users:
                    # process_choice에서 차감된 금액을 반환
                    await point_manager.add_point(self.bot, self.guild_id, user_id, self.bet)
            
            for item in self.children:
                item.disabled = True
                item.label = "시간 만료"
                item.style = discord.ButtonStyle.secondary
            
            if self.message:
                embed = discord.Embed(
                    title="⏰ 게임 시간 만료",
                    description="게임이 시간 초과로 종료되었습니다.\n참여한 플레이어의 배팅 금액이 반환되었습니다.",
                    color=discord.Color.orange()
                )
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"멀티 주사위 타임아웃 처리 오류: {e}")

# ✅ 주사위 게임 Cog
class DiceGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="주사위", description="주사위를 굴려 봇 또는 다른 플레이어와 대결합니다.")
    @app_commands.describe(
        모드="싱글(봇과 대결) 또는 멀티(다른 유저와 대결)",
        배팅="배팅할 현금 (기본값: 10원, 최대 5,000원)",
        상대방="멀티 모드에서 특정 상대방 지정 (선택사항)"
    )
    async def dice_game(
        self,
        interaction: discord.Interaction,
        모드: Literal["싱글", "멀티"],
        배팅: int = 10,
        상대방: Optional[discord.User] = None
    ):
        try:
            uid = str(interaction.user.id)
            gid = str(interaction.guild.id)
            
            # 기본 검증
            if not await point_manager.is_registered(self.bot, gid, uid):
                return await interaction.response.send_message("❗ 먼저 `/등록`을 해주세요.", ephemeral=True)

            if 배팅 < 10 or 배팅 > 5000:
                return await interaction.response.send_message("❗ 배팅은 10~5,000원 사이여야 합니다.", ephemeral=True)

            current_balance = await point_manager.get_point(self.bot, gid, uid)
            if current_balance < 배팅:
                return await interaction.response.send_message(
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {current_balance:,}원\n💸 필요 금액: {배팅:,}원", 
                    ephemeral=True
                )

            # 싱글 모드
            if 모드 == "싱글":
                embed = discord.Embed(
                    title="🎲 싱글 주사위 게임",
                    description=f"주사위를 굴려 봇({self.bot.user.display_name})보다 높은 숫자가 나오면 승리!",
                    color=discord.Color.blue()
                )
                embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
                embed.add_field(name="🎯 승리 조건", value="더 높은 주사위 숫자", inline=True)
                embed.add_field(name="🏆 승리 보상", value=f"{배팅 * 2:,}원", inline=True)
                embed.set_footer(text="주사위 굴리기 버튼을 눌러 게임을 시작하세요!")

                view = SingleDiceView(self.bot, interaction.user, 배팅)
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()

            # 멀티 모드
            else:
                if 상대방:
                    if 상대방.id == interaction.user.id:
                        return await interaction.response.send_message("❌ 자기 자신과는 게임할 수 없습니다.", ephemeral=True)
                    if 상대방.bot:
                        return await interaction.response.send_message("❌ 봇과는 멀티 게임을 할 수 없습니다.", ephemeral=True)
                    
                    if not await point_manager.is_registered(self.bot, gid, str(상대방.id)):
                        return await interaction.response.send_message(f"❌ {상대방.mention}님이 등록되어 있지 않습니다.", ephemeral=True)
                    
                    if await point_manager.get_point(self.bot, gid, str(상대방.id)) < 배팅:
                        return await interaction.response.send_message(f"❌ {상대방.mention}님의 잔액이 부족합니다.", ephemeral=True)

                embed = discord.Embed(
                    title="🎲 멀티 주사위 게임",
                    description="두 플레이어가 각각 주사위를 굴려 더 높은 숫자가 나오는 사람이 승리합니다.",
                    color=discord.Color.green()
                )
                embed.add_field(name="💰 배팅 금액", value=f"{배팅:,}원", inline=True)
                embed.add_field(name="🏆 승리 보상", value=f"{배팅 * 2:,}원", inline=True)
                embed.add_field(name="👤 플레이어1", value=interaction.user.mention, inline=False)
                embed.add_field(name="👤 플레이어2", value=상대방.mention if 상대방 else '참여자 대기 중', inline=False)

                if 상대방:
                    embed.set_footer(text=f"지정된 상대방 ({상대방.display_name})이 버튼을 눌러 참여해주세요!")
                else:
                    embed.set_footer(text="누구나 주사위 굴리기 버튼을 눌러 참여 가능합니다!")

                view = MultiDiceView(self.bot, interaction.user, 배팅, opponent=상대방)
                await interaction.response.send_message(embed=embed, view=view)
                view.message = await interaction.original_response()

        except Exception as e:
            print(f"주사위 게임 명령어 오류: {e}")
            try:
                await interaction.response.send_message("❌ 주사위 게임 생성 중 오류가 발생했습니다.", ephemeral=True)
            except:
                pass

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(DiceGameCog(bot))