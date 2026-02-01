# lottery_system.py - 로또 시스템
import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
import datetime
import traceback
from typing import List, Dict, Optional

# 상금 테이블 및 설정
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

class LotteryManager:
    """서버별 로또 데이터 및 티켓 통합 관리 객체"""
    def __init__(self, filename="lottery_guild_data.json"):
        self.filename = os.path.join("data", filename)
        self.guilds = {} # {guild_id: {"data": {...}, "tickets": [...]}}
        self.load_all_data()

    def load_all_data(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.guilds = json.load(f)
            except:
                self.guilds = {}

    def save_all_data(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.guilds, f, indent=4, ensure_ascii=False)

    def get_guild_store(self, guild_id: str):
        if guild_id not in self.guilds:
            self.guilds[guild_id] = {
                "data": {"round": 1, "total_sales": 0, "jackpot": 0, "last_draw_numbers": [], "last_draw_bonus": None},
                "tickets": []
            }
        return self.guilds[guild_id]
    
class PurchaseConfirmView(discord.ui.View):
    def __init__(self, lottery_system, user_id, numbers, bonus, guild_id):
        super().__init__(timeout=30)
        self.lottery_system = lottery_system
        self.user_id = user_id
        self.numbers = numbers
        self.bonus = bonus
        self.guild_id = str(guild_id)

    @discord.ui.button(label="구매 확정", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("본인만 클릭할 수 있습니다.", ephemeral=True)

        try:
            db = self.lottery_system._get_db(interaction.guild.id)
            store = self.lottery_system.manager.get_guild_store(self.guild_id)
            
            if db.get_user_cash(self.user_id) < TICKET_PRICE:
                return await interaction.response.edit_message(content="잔액이 부족합니다.", view=None)

            db.add_user_cash(self.user_id, -TICKET_PRICE)
            
            # 서버별 데이터 업데이트
            store['data']['jackpot'] += int(TICKET_PRICE * JACKPOT_ACCUMULATION_RATE)
            store['data']['total_sales'] += TICKET_PRICE
            store['tickets'].append({
                "user_id": str(self.user_id),
                "round": store['data']['round'],
                "numbers": self.numbers,
                "bonus": self.bonus,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            self.lottery_system.manager.save_all_data()

            embed = discord.Embed(title="✅ 로또 구매 완료", color=discord.Color.green())
            embed.add_field(name="번호", value=f"{', '.join(map(str, self.numbers))} [PB: {self.bonus}]")
            
            total_prize = PRIZE_TABLE[1]['prize'] + store['data']['jackpot']
            embed.set_footer(text=f"현재 1등 누적 상금: {db.format_money(total_prize)}")
            
            await interaction.response.edit_message(content=None, embed=embed, view=None)
        except Exception as e:
            print(f"Purchase Error: {e}")
            await interaction.response.edit_message(content="구매 중 오류 발생", view=None)

class LotteryTickets:
    def __init__(self, filename="lottery_tickets.json"):
        self.filename = os.path.join("data", filename)
        self.tickets = []
        self.load_tickets()

    def load_tickets(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    self.tickets = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.tickets = []
        else:
            self.tickets = []

    def save_tickets(self):
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
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

class TicketPaginatorView(discord.ui.View):
    def __init__(self, tickets, user_name, round_num, db, jackpot_info, per_page=10):
        super().__init__(timeout=60)
        self.tickets = tickets
        self.user_name = user_name
        self.round_num = round_num
        self.db = db
        self.jackpot_info = jackpot_info # 상금 정보 저장
        self.per_page = per_page
        self.current_page = 0
        self.total_pages = (len(tickets) - 1) // per_page + 1

    def create_embed(self):
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        current_tickets = self.tickets[start_idx:end_idx]

        embed = discord.Embed(
            title=f"🎰 제 {self.round_num}회 파워볼 정보 & 티켓 목록",
            color=discord.Color.blue()
        )
        
        # 상단에 상금 정보 추가 (항상 표시)
        embed.add_field(name="현재 1등 예상 상금", value=f"**{self.db.format_money(self.jackpot_info['total'])}**", inline=True)
        embed.add_field(name="이월된 상금", value=self.db.format_money(self.jackpot_info['jackpot']), inline=True)

        # 티켓 목록 문자열 생성
        ticket_list_str = ""
        for i, t in enumerate(current_tickets, 1):
            nums_str = ", ".join(map(str, t['numbers']))
            ticket_list_str += f"**{start_idx + i}번:** `{nums_str}` [PB: {t['bonus']}]\n"

        embed.add_field(
            name=f"🎫 {self.user_name}님의 티켓 (페이지 {self.current_page + 1}/{self.total_pages})", 
            value=ticket_list_str or "구매한 티켓이 없습니다.", 
            inline=False
        )
        embed.set_footer(text=f"총 {len(self.tickets)}개의 티켓 보유 중")
        return embed

    @discord.ui.button(label="이전", style=discord.ButtonStyle.gray)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("첫 페이지입니다.", ephemeral=True)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("마지막 페이지입니다.", ephemeral=True)    

class DrawResultPaginatorView(discord.ui.View):
    def __init__(self, draw_nums, draw_pb, summary_list, round_num):
        super().__init__(timeout=60)
        self.draw_nums = draw_nums
        self.draw_pb = draw_pb
        self.summary = summary_list
        self.round_num = round_num
        self.current_page = 0
        self.per_page = 5  # 한 페이지에 보여줄 항목 수
        self.total_pages = (len(summary_list) - 1) // self.per_page + 1 if summary_list else 1

    def create_embed(self):
        embed = discord.Embed(
            title=f"🎊 제 {self.round_num}회 추첨 결과", 
            color=discord.Color.gold()
        )
        embed.add_field(
            name="럭키 번호", 
            value=f" {', '.join(map(str, self.draw_nums))}  [PB: {self.draw_pb}]", 
            inline=False
        )

        if not self.summary:
            embed.add_field(name="당첨 현황", value="당첨자가 없습니다.", inline=False)
        else:
            start_idx = self.current_page * self.per_page
            end_idx = start_idx + self.per_page
            page_content = "\n".join(self.summary[start_idx:end_idx])
            
            embed.add_field(
                name=f"당첨 현황 (페이지 {self.current_page + 1}/{self.total_pages})", 
                value=page_content, 
                inline=False
            )
        
        embed.set_footer(text="버튼을 눌러 페이지를 이동하세요.")
        return embed

    @discord.ui.button(label="이전", style=discord.ButtonStyle.gray, emoji="◀️")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("첫 페이지입니다.", ephemeral=True)

    @discord.ui.button(label="다음", style=discord.ButtonStyle.gray, emoji="▶️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.send_message("마지막 페이지입니다.", ephemeral=True)
        
class LotterySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.manager = LotteryManager()

    def _get_db(self, guild_id: int):
        point_manager = self.bot.get_cog("PointManager")
        return point_manager._get_db(guild_id) if point_manager else None

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

    @app_commands.command(name="로또구매", description="로또를 구매합니다. (5,000원)")
    @app_commands.describe(numbers="일반볼 5개 (1~28, 쉼표 구분)", pb="파워볼 1개 (0~9)")
    async def buy_lottery(self, interaction: discord.Interaction, numbers: Optional[str] = None, pb: Optional[int] = None):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'lottery' 권한이 있는지 체크 (channel_config.py의 value="lottery"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "lottery", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 익명 메시지 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        # 채널 권한 체크 생략(기존 로직 유지 가능)
        db = self._get_db(interaction.guild.id)
        
        if numbers is None:
            user_nums = sorted(random.sample(range(1, 29), 5))
            user_pb = random.randint(0, 9)
        else:
            try:
                user_nums = sorted([int(n.strip()) for n in numbers.split(',')])
                if len(set(user_nums)) != 5 or any(not (1 <= n <= 28) for n in user_nums): raise ValueError
                if pb is None or not (0 <= pb <= 9): raise ValueError
                user_pb = pb
            except:
                return await interaction.response.send_message("번호 형식이 올바르지 않습니다.", ephemeral=True)

        view = PurchaseConfirmView(self, str(interaction.user.id), user_nums, user_pb, interaction.guild.id)
        await interaction.response.send_message(
            f"🎫 **로또를 구매하시겠습니까?**\n번호: `{', '.join(map(str, user_nums))}` [PB: `{user_pb}`]", view=view
        )
        
    @app_commands.command(name="로또정보", description="상금 정보와 나의 티켓 목록을 확인합니다.")
    async def lottery_info(self, interaction: discord.Interaction):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'lottery' 권한이 있는지 체크 (channel_config.py의 value="lottery"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "lottery", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 해당 명령어가 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        db = self._get_db(interaction.guild.id)
        if db is None:
            return await interaction.response.send_message("데이터베이스 연결 실패", ephemeral=True)

        data = self.lottery_data.data
        round_num = data['round']
        jackpot = data.get('jackpot', 0)
        total_prize = PRIZE_TABLE[1]['prize'] + jackpot
        
        # 상금 정보를 딕셔너리로 묶어서 뷰에 전달
        jackpot_info = {'total': total_prize, 'jackpot': jackpot}
        
        user_id_str = str(interaction.user.id)
        my_tickets = [t for t in self.lottery_tickets.tickets if t['round'] == round_num and t['user_id'] == user_id_str]
        
        if not my_tickets:
            # 티켓이 없을 때는 기본 정보만 출력
            embed = discord.Embed(title=f"🎰 제 {round_num}회 파워볼 정보", color=discord.Color.blue())
            embed.add_field(name="현재 1등 예상 상금", value=f"**{db.format_money(total_prize)}**", inline=True)
            embed.add_field(name="이월된 상금", value=db.format_money(jackpot), inline=True)
            embed.add_field(name="🎫 내 티켓", value="구매한 티켓이 없습니다.", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            # 티켓이 있을 때: 10장씩 보여주는 페이징 뷰 생성
            view = TicketPaginatorView(my_tickets, interaction.user.display_name, round_num, db, jackpot_info, per_page=10)
            await interaction.response.send_message(embed=view.create_embed(), view=view)


    @app_commands.command(name="로또추첨", description="[관리자] 로또 추첨을 진행합니다. 번호를 지정하면 해당 번호로 당첨됩니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def draw(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        db = self._get_db(interaction.guild.id)
        if not db:
            return await interaction.followup.send("데이터베이스를 불러올 수 없습니다.")

        store = self.manager.get_guild_store(str(interaction.guild.id))
        
        # 1. 자동 당첨 번호 결정
        draw_nums = sorted(random.sample(range(1, 29), 5))
        draw_pb = random.randint(0, 9)
        
        data = store['data']
        round_num = data['round']
        current_tickets = store['tickets']
        
        winners = {i: [] for i in range(1, 10)}
        for t in current_tickets:
            rank = self.check_winning(t['numbers'], t['bonus'], draw_nums, draw_pb)
            if rank: winners[rank].append(t['user_id'])

        first_prize_total = PRIZE_TABLE[1]['prize'] + data.get('jackpot', 0)
        summary = []
        mention_list = []
        
        # 2. 상금 지급 로직 및 멘션 리스트 생성
        for rank, uids in winners.items():
            if not uids: continue
            
            prize = first_prize_total // len(uids) if rank == 1 else PRIZE_TABLE[rank]['prize']
            
            unique_winners = set(uids) 
            rank_mentions = [f"<@{uid}>" for uid in unique_winners]
            mention_list.append(f"🏆 **{PRIZE_TABLE[rank]['name']} 당첨자**: {' '.join(rank_mentions)}")

            for uid in uids:
                user_str_id = str(uid)
                db.add_user_cash(user_str_id, prize)
                db.add_transaction(user_str_id, "로또 당첨", prize, f"제 {round_num}회 {rank}등 당첨")
            
            summary.append(f"**{PRIZE_TABLE[rank]['name']}**: {len(uids)}명 ({db.format_money(prize)}씩)")

        # 3. 데이터 업데이트 및 저장
        data['last_draw_numbers'] = draw_nums
        data['last_draw_bonus'] = draw_pb
        if winners[1]: data['jackpot'] = 0
        
        data['round'] += 1
        store['tickets'] = []
        self.manager.save_all_data()

        # 4. 결과 전송
        view = DrawResultPaginatorView(draw_nums, draw_pb, summary, round_num)
        await interaction.followup.send(content="🎊 추첨이 완료되었습니다!", embed=view.create_embed(), view=view)

        # 5. 당첨자 언급
        if mention_list:
            current_message = "🎊 **축하합니다! 당첨자 명단입니다** 🎊\n\n"
            for mention_line in mention_list:
                if len(current_message) + len(mention_line) > 1900:
                    await interaction.channel.send(current_message)
                    current_message = mention_line + "\n"
                else:
                    current_message += mention_line + "\n"
            
            if current_message:
                await interaction.channel.send(current_message)

async def setup(bot):
    await bot.add_cog(LotterySystem(bot))