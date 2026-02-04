# tax_system.py - 세금 시스템
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional, Tuple, Literal
import os

# --- 기존 유틸리티 및 임포트 로직 유지 ---
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

# --- 1. 자산 선택 뷰 (버튼 형식) ---
class TaxTypeSelectView(discord.ui.View):
    def __init__(self, cog: 'TaxSystemCog', role: discord.Role, percent: float):
        super().__init__(timeout=60)
        self.cog = cog
        self.role = role
        self.percent = percent

    @discord.ui.button(label="현금 수거", style=discord.ButtonStyle.green, emoji="💵")
    async def collect_cash(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼 비활성화 후 처리
        await self.disable_all_buttons(interaction)
        await self.cog.execute_tax_logic(interaction, self.role, self.percent, "cash")

    @discord.ui.button(label="XP 수거", style=discord.ButtonStyle.blurple, emoji="✨")
    async def collect_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 버튼 비활성화 후 처리
        await self.disable_all_buttons(interaction)
        await self.cog.execute_tax_logic(interaction, self.role, self.percent, "xp")

    async def disable_all_buttons(self, interaction: discord.Interaction):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

# --- 2. 페이징 뷰 (결과 목록 출력용) ---
class TaxPagingView(discord.ui.View):
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

# --- 3. 메인 세금 시스템 Cog ---
class TaxSystemCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="세금수거", description="[관리자 전용] 특정 역할의 유저들에게 세금을 징수합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(역할="세금을 수거할 대상 역할", 퍼센트="징수 비율 (%)")
    async def start_tax_process(self, interaction: discord.Interaction, 역할: discord.Role, 퍼센트: float):
        """1단계: 어떤 자산을 수거할지 선택하는 버튼을 띄웁니다."""
        if 퍼센트 <= 0 or 퍼센트 > 100:
            await interaction.response.send_message("비율은 0보다 크고 100 이하여야 합니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🏦 세금 징수 방식 선택",
            description=f"**대상 역할:** {역할.mention}\n**징수 비율:** `{퍼센트}%`\n\n아래 버튼을 클릭하여 수거할 자산 종류를 선택하세요.",
            color=discord.Color.blue()
        )
        view = TaxTypeSelectView(self, 역할, 퍼센트)
        await interaction.response.send_message(embed=embed, view=view)

    async def execute_tax_logic(self, interaction: discord.Interaction, 역할: discord.Role, 퍼센트: float, tax_type: Literal["cash", "xp"]):
        """2단계: 실제 징수 로직을 수행합니다."""
        # 처리 중임을 알림 (Followup 사용)
        msg = await interaction.followup.send(f"🔄 {역할.name} 역할에 대한 {tax_type.upper()} 세금 징수를 시작합니다...", ephemeral=False)
        
        db = get_guild_db_manager_func(str(interaction.guild.id))
        members = 역할.members
        
        tax_results = []
        failed_members = []
        total_collected = 0
        success_count = 0
        
        unit = "원" if tax_type == "cash" else "XP"
        type_name = "현금" if tax_type == "cash" else "경험치"

        for member in members:
            if member.bot: continue
            user_id = str(member.id)
            current_val = 0

            # 1. 자산 데이터 조회
            if tax_type == "cash":
                user_data = db.get_user(user_id)
                current_val = user_data.get('cash', 0) if user_data else 0
            else:
                xp_data = db.get_user_xp(user_id)
                current_val = xp_data.get('xp', 0) if xp_data else 0

            # 2. 수거 기준 체크 (10,000 미만 제외)
            if current_val < 10000:
                failed_members.append(f"{member.display_name}: 🛑 {current_val:,}{unit}")
                continue
            
            tax_amount = int(current_val * (퍼센트 / 100))
            after_val = current_val - tax_amount
            
            if tax_amount > 0:
                if tax_type == "cash":
                    db.update_user_cash(user_id, after_val)
                else:
                    db.execute_query(
                        "UPDATE user_xp SET xp = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (after_val, user_id)
                    )

                db.add_transaction(user_id, f"세금징수({type_name})", -tax_amount, f"{역할.name} 세금 {퍼센트}%")
                success_count += 1
                total_collected += tax_amount
                tax_results.append(f"{member.display_name} {current_val:,}{unit} -> {after_val:,}{unit} (-{tax_amount:,})")

        # 3. 결과 임베드 생성
        embed = discord.Embed(
            title=f"💰 {type_name} 세금 수거 완료",
            description=f"**역할:** {역할.name}\n**비율:** {퍼센트}%\n**총 수거액:** ✨ `{total_collected:,}{unit}` ✨",
            color=discord.Color.gold() if tax_type == "cash" else discord.Color.purple(),
            timestamp=discord.utils.utcnow()
        )

        chunk_size = 15
        if tax_results:
            first_chunk = tax_results[:chunk_size]
            formatted_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(first_chunk)])
            embed.add_field(name=f"📊 수거 내역 ({success_count}명)", value=f"```\n{formatted_list}```", inline=False)
        else:
            embed.add_field(name="📊 수거 내역", value="```\n수거 대상자가 없습니다.```", inline=False)

        if failed_members:
            fail_list = "\n".join(failed_members[:10])
            if len(failed_members) > 10: fail_list += f"\n외 {len(failed_members)-10}명..."
            embed.add_field(name="🚫 수거 불가 인원 (잔액 부족)", value=f"```\n{fail_list}```", inline=False)

        embed.set_footer(text=f"집행 관리자: {interaction.user.display_name}")

        # 메시지 업데이트 (또는 새로 보내기)
        if len(tax_results) > chunk_size:
            view = TaxPagingView(f"{역할.name} {type_name} 수거 상세", tax_results)
            await msg.edit(content=None, embed=embed, view=view)
        else:
            await msg.edit(content=None, embed=embed)

        log_admin_action(f"[세금수거] {interaction.user.display_name} : {역할.name} {type_name} {퍼센트}% 수거 (총액: {total_collected})")

async def setup(bot: commands.Bot):
    await bot.add_cog(TaxSystemCog(bot))