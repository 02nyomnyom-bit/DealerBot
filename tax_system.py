# tax_system.py - 세금 시스템 (수정본)
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional, Tuple, Literal
import json
import os
from discord.ui import View, Button

# 외부 유틸리티 및 DB 임포트 로직 (기존 동일)
try:
    from common_utils import log_admin_action, format_xp, now_str
except ImportError:
    def log_admin_action(message: str): print(f"[ADMIN LOG] {message}")
    def format_xp(xp: int) -> str: return f"{xp:,} XP"
    def now_str() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_import_database():
    try:
        from database_manager import get_guild_db_manager
        return get_guild_db_manager, True
    except ImportError:
        return None, False

get_guild_db_manager_func, DATABASE_AVAILABLE = safe_import_database()
DATA_DIR = "data"
TAX_SETTINGS_FILE = os.path.join(DATA_DIR, "tax_settings.json")
os.makedirs(DATA_DIR, exist_ok=True)

# --- 신규: 자산 선택 뷰 ---
class TaxTypeSelectView(View):
    def __init__(self, cog, interaction: discord.Interaction, role: discord.Role, percent: float):
        super().__init__(timeout=60)
        self.cog = cog
        self.interaction = interaction
        self.role = role
        self.percent = percent

    @discord.ui.button(label="현금 수거", style=discord.ButtonStyle.green, emoji="💵")
    async def collect_cash(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.process_tax_collection(interaction, self.role, self.percent, "cash")
        self.stop()

    @discord.ui.button(label="XP 수거", style=discord.ButtonStyle.blurple, emoji="✨")
    async def collect_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.process_tax_collection(interaction, self.role, self.percent, "xp")
        self.stop()

# --- 페이징 뷰 (기존 유지 및 소폭 수정) ---
class TaxPagingView(View):
    def __init__(self, title, members_list, chunk_size=15):
        super().__init__(timeout=120)
        self.title = title
        self.members_list = members_list
        self.chunk_size = chunk_size
        self.current_index = chunk_size

    @discord.ui.button(label="다음 목록 보기", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_chunk = self.members_list[self.current_index : self.current_index + self.chunk_size]
        embed = discord.Embed(
            title=f"{self.title} (추가 {self.current_index // self.chunk_size + 1}P)",
            description="\n".join(next_chunk),
            color=discord.Color.orange()
        )
        self.current_index += self.chunk_size
        if self.current_index >= len(self.members_list):
            button.disabled = True
            button.label = "마지막 페이지"
        await interaction.response.send_message(embed=embed, ephemeral=False, view=self if not button.disabled else None)

class TaxSystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="세금수거", description="[관리자 전용] 특정 역할 유저들에게 세금을 수거합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정)
    @app_commands.describe(역할="세금을 수거할 역할", 퍼센트="징수할 비율 (%)")
    async def collect_tax_percent(self, interaction: discord.Interaction, 역할: discord.Role, 퍼센트: float):
        if not 0 < 퍼센트 <= 100:
            return await interaction.response.send_message("❌ 퍼센트는 0보다 크고 100 이하이어야 합니다.", ephemeral=True)
        
        embed = discord.Embed(
            title="💰 수거 자산 선택",
            description=f"**대상 역할:** {역할.mention}\n**징수 비율:** {퍼센트}%\n\n어떤 자산을 수거하시겠습니까?",
            color=discord.Color.blue()
        )
        view = TaxTypeSelectView(self, interaction, 역할, 퍼센트)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def process_tax_collection(self, interaction: discord.Interaction, 역할: discord.Role, 퍼센트: float, tax_type: Literal["cash", "xp"]):
        await interaction.response.defer()
        
        db = get_guild_db_manager_func(str(interaction.guild.id))
        members = 역할.members
        
        tax_results = []
        failed_members = [] # 마이너스 잔액 인원
        total_collected = 0
        success_count = 0
        
        unit = "원" if tax_type == "cash" else "XP"
        type_name = "현금" if tax_type == "cash" else "경험치"

        for member in members:
            if member.bot: continue
            
            user_data = db.get_user(str(member.id))
            if not user_data: continue
            
            # 자산 값 가져오기
            current_val = user_data.get(tax_type, 0)
            
            # [요구사항] 이미 만원이하인 경우 제외
            if current_val < 10000:
                failed_members.append(f"{member.display_name}: 🛑 {current_val:,}{unit}")
                continue
            
            tax_amount = int(current_val * (퍼센트 / 100))
            after_val = current_val - tax_amount
            
            if tax_amount > 0:
                if tax_type == "cash":
                    db.update_user_cash(str(member.id), after_val)
                else:
                    try:
                        db.update_user_xp(str(member.id), after_val) 
                    except AttributeError:
                        # 일반적인 대체 함수명 예시
                        db.update_user_exp(str(member.id), after_val)
                
                db.add_transaction(str(member.id), f"세금징수({type_name})", -tax_amount, f"{역할.name} 세금 {퍼센트}%")
                success_count += 1
                total_collected += tax_amount

            tax_results.append(f"{member.display_name} {current_val:,}{unit} -> {after_val:,}{unit} (-{tax_amount:,})")

        # 결과 임베드 생성
        embed = discord.Embed(
            title=f"💰 {type_name} 세금 수거 결과",
            description=f"**역할:** {역할.name}\n**비율:** {퍼센트}%\n**총 수거액:** ✨ `{total_collected:,}{unit}` ✨",
            color=discord.Color.gold() if tax_type == "cash" else discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )

        # 상세 내역 (성공 유저)
        chunk_size = 15
        if tax_results:
            first_chunk = tax_results[:chunk_size]
            formatted_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(first_chunk)])
            embed.add_field(name=f"📊 수거 내역 ({success_count}명)", value=f"```\n{formatted_list}```", inline=False)
        else:
            embed.add_field(name="📊 수거 내역", value="```\n수거 대상자가 없습니다.```", inline=False)

        # [요구사항] 수거 불가 인원 표시
        if failed_members:
            fail_list = "\n".join(failed_members[:10]) # 너무 많을 경우 대비 10명 제한
            if len(failed_members) > 10: fail_list += f"\n외 {len(failed_members)-10}명..."
            embed.add_field(name="🚫 수거 불가 인원 (잔액 부족)", value=f"```\n{fail_list}```", inline=False)

        embed.set_footer(text=f"관리자 {interaction.user.display_name}에 의해 집행됨")

        if len(tax_results) > chunk_size:
            view = TaxPagingView(f"{역할.name} {type_name} 수거 상세", tax_results)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

        log_admin_action(f"[세금수거] {interaction.user.display_name} : {역할.name} {type_name} {퍼센트}% 수거 (총액: {total_collected})")

async def setup(bot: commands.Bot):
    await bot.add_cog(TaxSystemCog(bot))