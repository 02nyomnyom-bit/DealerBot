import discord
from discord import app_commands
from discord.ext import commands
from point_manager import db_manager
import random
import json
import os
import datetime
import traceback
from typing import List, Dict, Optional

# 상금 테이블 및 확률 설정
PRIZE_TABLE = {
    1: {"name": "1등", "prize": 500000, "desc": "일반볼 5개 + 파워볼 일치"},
    2: {"name": "2등", "prize": 100000, "desc": "일반볼 5개 일치"},
    3: {"name": "3등", "prize": 50000, "desc": "일반볼 4개 + 파워볼 일치"},
    4: {"name": "4등", "prize": 20000, "desc": "일반볼 4개 일치"},
    5: {"name": "5등", "prize": 10000, "desc": "일반볼 3개 + 파워볼 일치"},
    6: {"name": "6등", "prize": 5000, "desc": "일반볼 3개 일치"},
    7: {"name": "7등", "prize": 3000, "desc": "일반볼 2개 + 파워볼 일치"},
    8: {"name": "8등", "prize": 2000, "desc": "일반볼 1개 + 파워볼 일치"},
    9: {"name": "보너스", "prize": 1000, "desc": "파워볼 일치"}
}

TICKET_PRICE = 5000
JACKPOT_ACCUMULATION_RATE = 0.5  # 판매 금액의 50%를 잭팟에 적립

class LotteryData:
    def __init__(self, filename="lottery_data.json"):
        self.filename = filename
        self.data = {"round": 1, "total_sales": 0, "jackpot": 0, "last_draw_numbers": [], "last_draw_bonus": None}
        self.load_data()

    def load_data(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.data.update(json.load(f))
            except:
                self.save_data()
        else:
            self.save_data()

    def save_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

class LotteryTickets:
    def __init__(self, filename="lottery_tickets.json"):
        self.filename = filename
        self.tickets = []
        self.load_tickets()

    def load_tickets(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.tickets = json.load(f)
            except:
                self.tickets = []
        else:
            self.tickets = []

    def save_tickets(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.tickets, f, indent=4, ensure_ascii=False)

    def add_ticket(self, user_id, round_num, numbers, bonus):
        self.tickets.append({
            "user_id": str(user_id),
            "round": round_num,
            "numbers": sorted(numbers),
            "bonus": bonus,
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_tickets()

class PurchaseConfirmView(discord.ui.View):
    def __init__(self, lottery_system, user_id, numbers, bonus):
        super().__init__(timeout=30)
        self.lottery_system = lottery_system
        self.user_id = user_id
        self.numbers = numbers
        self.bonus = bonus

    @discord.ui.button(label="구매 확정", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("본인만 클릭할 수 있습니다.", ephemeral=True)

        # 1. 잔액 확인 및 차감
        user_cash = self.lottery_system.db.get_user_cash(self.user_id)
        if user_cash < TICKET_PRICE:
            return await interaction.response.edit_message(content="잔액이 부족합니다.", view=None)

        try:
            # DB 차감
            self.lottery_system.db.add_user_cash(self.user_id, -TICKET_PRICE)
            
            # 잭팟 적립 및 데이터 저장
            self.lottery_system.lottery_data.data['jackpot'] += int(TICKET_PRICE * JACKPOT_ACCUMULATION_RATE)
            self.lottery_system.lottery_data.data['total_sales'] += TICKET_PRICE
            self.lottery_system.lottery_data.save_data()

            # 티켓 생성
            current_round = self.lottery_system.lottery_data.data['round']
            self.lottery_system.lottery_tickets.add_ticket(self.user_id, current_round, self.numbers, self.bonus)

            embed = discord.Embed(title="✅ 로또 구매 완료", color=discord.Color.green())
            embed.add_field(name="번호", value=f"{', '.join(map(str, self.numbers))} [PB: {self.bonus}]")
            embed.set_footer(text=f"현재 1등 누적 상금: {self.lottery_system.db.format_money(PRIZE_TABLE[1]['prize'] + self.lottery_system.lottery_data.data['jackpot'])}")
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
        except Exception as e:
            # 오류 발생 시 복구 로직 (간단화)
            print(f"Purchase Error: {e}")
            await interaction.response.edit_message(content="구매 처리 중 오류가 발생했습니다.", view=None)

class LotterySystem(commands.Cog):
    def __init__(self, bot, db_manager):
        self.bot = bot
        self.db = db_manager
        self.lottery_data = LotteryData()
        self.lottery_tickets = LotteryTickets()

    def check_winning(self, user_nums, user_pb, draw_nums, draw_pb):
        match_count = len(set(user_nums) & set(draw_nums))
        pb_match = (user_pb == draw_pb)

        if match_count == 5 and pb_match: return 1
        if match_count == 5: return 2
        if match_count == 4 and pb_match: return 3
        if match_count == 4: return 4
        if match_count == 3 and pb_match: return 5
        if match_count == 3: return 6
        if match_count == 2 and pb_match: return 7
        if match_count == 1 and pb_match: return 8
        if pb_match: return 9
        return None

    @app_commands.command(name="로또구매", description="파워볼 로또를 구매합니다. (5,000원)")
    @app_commands.describe(numbers="일반볼 5개 (1~28, 쉼표 구분)", pb="파워볼 1개 (0~9)")
    async def buy_lottery(self, interaction: discord.Interaction, numbers: Optional[str] = None, pb: Optional[int] = None):
        if numbers is None: # 자동 구매
            user_nums = random.sample(range(1, 29), 5)
            user_pb = random.randint(0, 9)
        else: # 수동 구매 검증
            try:
                user_nums = [int(n.strip()) for n in numbers.split(',')]
                if len(set(user_nums)) != 5 or any(not (1 <= n <= 28) for n in user_nums):
                    raise ValueError
                if pb is None or not (0 <= pb <= 9):
                    raise ValueError
                user_pb = pb
            except:
                return await interaction.response.send_message("번호 형식이 올바르지 않습니다. (예: 1,2,3,4,5 / 파워볼: 0~9)", ephemeral=True)

        view = PurchaseConfirmView(self, interaction.user.id, user_nums, user_pb)
        await interaction.response.send_message(
            f"🎫 **로또를 구매하시겠습니까?**\n번호: `{', '.join(map(str, sorted(user_nums)))}` [PB: `{user_pb}`]\n가격: `1,000원`",
            view=view
        )

    @app_commands.command(name="로또정보", description="현재 회차 정보 및 누적 잭팟을 확인합니다.")
    async def lottery_info(self, interaction: discord.Interaction):
        data = self.lottery_data.data
        jackpot = data.get('jackpot', 0)
        total_prize = PRIZE_TABLE[1]['prize'] + jackpot

        embed = discord.Embed(title=f"🎰 제 {data['round']}회 파워볼 정보", color=discord.Color.blue())
        embed.add_field(name="현재 1등 예상 상금", value=f"**{self.db.format_money(total_prize)}**", inline=False)
        embed.add_field(name="이월된 상금", value=self.db.format_money(jackpot), inline=True)
        embed.add_field(name="티켓 가격", value="5,000원", inline=True)
        
        rules = "\n".join([f"• {v['name']}: {v['desc']}" for k, v in PRIZE_TABLE.items() if k <= 3])
        embed.add_field(name="주요 당첨 조건", value=rules + "\n...등 총 9등급", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="로또추첨", description="로또 추첨을 진행합니다.[관리자 전용]")
    @app_commands.checks.has_permissions(administrator=True)
    async def draw(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        draw_nums = sorted(random.sample(range(1, 29), 5))
        draw_pb = random.randint(0, 9)
        
        data = self.lottery_data.data
        round_num = data['round']
        jackpot_pool = data.get('jackpot', 0)
        
        current_tickets = [t for t in self.lottery_tickets.tickets if t['round'] == round_num]
        winners = {i: [] for i in range(1, 10)}
        
        for t in current_tickets:
            rank = self.check_winning(t['numbers'], t['bonus'], draw_nums, draw_pb)
            if rank:
                winners[rank].append(t['user_id'])

        # 1등 상금 계산 (기본 + 잭팟)
        first_prize_total = PRIZE_TABLE[1]['prize'] + jackpot_pool
        has_first_winner = len(winners[1]) > 0
        
        summary = []
        for rank, uids in winners.items():
            if not uids: continue
            
            # 상금 결정
            if rank == 1:
                prize_per_person = first_prize_total // len(uids)
            else:
                prize_per_person = PRIZE_TABLE[rank]['prize']
                
            for uid in uids:
                self.db.add_user_cash(int(uid), prize_per_person)
                self.db.add_transaction(int(uid), f"로또 {round_num}회 {rank}등 당첨", prize_per_person)
            
            summary.append(f"**{PRIZE_TABLE[rank]['name']}**: {len(uids)}명 ({self.db.format_money(prize_per_person)}씩)")

        # 데이터 업데이트
        data['last_draw_numbers'] = draw_nums
        data['last_draw_bonus'] = draw_pb
        if has_first_winner:
            data['jackpot'] = 0 # 1등 나오면 잭팟 초기화
        
        data['round'] += 1
        self.lottery_data.save_data()
        
        # 결과 임베드
        embed = discord.Embed(title=f"🎊 제 {round_num}회 추첨 결과", color=discord.Color.gold())
        embed.add_field(name="당첨 번호", value=f" {', '.join(map(str, draw_nums))}  [PB: {draw_pb}]", inline=False)
        embed.add_field(name="당첨 현황", value="\n".join(summary) if summary else "당첨자 없음", inline=False)
        if not has_first_winner:
            embed.set_footer(text=f"1등 당첨자가 없어 상금이 이월되었습니다! (현재 이월금: {self.db.format_money(data['jackpot'])})")
            
        await interaction.followup.send(embed=embed)

async def setup(bot):
    """봇에 LotterySystem Cog를 추가하는 함수"""
    try:
        # 2. 로또 시스템을 등록하면서 공유된 db_manager를 전달합니다.
        await bot.add_cog(LotterySystem(bot, db_manager))
        print("✅ 로또 시스템이 성공적으로 로드되었습니다. (공유 DB 매니저 사용)")
        
    except ImportError:
        # point_manager가 없을 경우를 대비한 예외 처리
        print("⚠️ 경고: point_manager를 찾을 수 없어 로또 시스템 로드에 실패했습니다.")
    except Exception as e:
        print(f"❌ 로또 시스템 로드 중 오류 발생: {e}")