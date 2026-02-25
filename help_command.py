# help_command.py - 도움말
from __future__ import annotations
import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
from typing import Dict, List, Optional

# ✅ 설정 파일 경로
DATA_DIR = "data"
REALTIME_UPDATES_FILE = os.path.join(DATA_DIR, "realtime_updates.json")
ARCHIVED_UPDATES_FILE = os.path.join(DATA_DIR, "archived_updates.json")

os.makedirs(DATA_DIR, exist_ok=True)

try:
    from update_system import get_realtime_updates_summary, get_update_statistics
    UPDATE_SYSTEM_AVAILABLE = True
except ImportError:
    def get_realtime_updates_summary(count=5):
        return "⚠️ 실시간 업데이트 시스템이 로드되지 않았습니다."
    def get_update_statistics():
        return {
            'total_active': 0, 'total_archived': 0, 'today_count': 0,
            'priority_counts': {'긴급': 0, '중요': 0, '일반': 0}
        }

# (기존 load/save 함수들은 동일하게 유지)
def load_realtime_updates():
    if not os.path.exists(REALTIME_UPDATES_FILE): return []
    try:
        with open(REALTIME_UPDATES_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception as e: return []

def save_realtime_updates(updates):
    try:
        with open(REALTIME_UPDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(updates, f, indent=4, ensure_ascii=False)
        return True
    except Exception: return False

def load_archived_updates():
    if not os.path.exists(ARCHIVED_UPDATES_FILE): return []
    try:
        with open(ARCHIVED_UPDATES_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return []

def save_archived_updates(updates):
    try:
        with open(ARCHIVED_UPDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(updates, f, indent=4, ensure_ascii=False)
        return True
    except Exception: return False

def add_realtime_update(title: str, description: str, author: str, priority: str = "일반") -> bool:
    """실시간 업데이트 추가 (자동 삭제 로직 제거됨)"""
    try:
        updates = load_realtime_updates()
        
        # ID 생성
        max_id = max([update.get("id", 0) for update in updates], default=0)
        
        new_update = {
            "id": max_id + 1,
            "title": title,
            "description": description,
            "author": author,
            "priority": priority,
            "timestamp": datetime.datetime.now().isoformat(),
            "date": datetime.datetime.now().strftime("%Y-%m-%d")
        }
        
        updates.append(new_update)
        return save_realtime_updates(updates)
    except Exception as e:
        print(f"추가 오류: {e}")
        return False

def remove_old_updates() -> int:
    """자동 삭제 기능을 비활성화했습니다."""
    # 더 이상 시간을 체크하여 삭제하지 않습니다.
    return 0

# 📖 도움말 카테고리 선택 드롭다운
class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="카테고리를 선택하세요!",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="통합 출석 & XP", description="출석, 레벨업, 순위표 등", emoji="📆", value="attendance"),
                discord.SelectOption(label="현금 시스템", description="현금, 지갑, 선물 등", emoji="💰", value="cash"),
                discord.SelectOption(label="게임 명령어", description="블랙잭, 주사위, 강화 등", emoji="🎮", value="games"),
                discord.SelectOption(label="기타", description="봇 정보, 업데이트 등", emoji="✨", value="other")
            ]
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        embed = discord.Embed(title="📖 도움말 메뉴", color=discord.Color.blue())
        
        if category == "attendance":
            embed.add_field(name="📆 출석 & 보이스 명령어",
                    value=
                        "**`/출석체크`**\n"
                        "일일 현금과 경험치 지급합니다. 연속 보상이 커집니다.\n"
                        "**`/출석현황`**\n"
                        "나의 현재 출석 현황을 확인합니다.\n"
                        "**`/출석랭킹`**\n"
                        "서버 내 출석 랭킹을 확인합니다.\n"
                        "**/보이스랭크**\n"
                        "사용자의 통화 시간을 공개적으로 확인합니다.\n" 
                        "**/보이스통계**\n"
                        "기간별 통화 순위를 공개적으로 확인합니다. (상위 10명)\n",
                    inline=False)
        elif category == "cash":
            embed.add_field(name="💰 현금 & 경험치 명령어",
                    value=
                        "**`/등록`**\n"
                        "서버 명단에 등록합니다.\n"
                        "**`/탈퇴`**\n"
                        "서버에서 탈퇴합니다. (모든 데이터 삭제)\n"
                        "**`/지갑`**\n"
                        "현재 보유 현금을 확인합니다\n"
                        "**`/선물`**\n"
                        "다른 사용자에게 현금을 선물합니다\n"
                        "**/레벨**\n"
                        "자신의 레벨 및 XP를 확인합니다.\n"
                        "**`/현금교환`**\n"
                        "XP를 현금으로 교환합니다. 수수료가 부과됩니다.\n"
                        "**`/경험치교환`**\n"
                        "현금을 XP로 교환합니다. 수수료가 부과됩니다.\n",
                    inline=False)
        elif category == "games":
            embed.add_field(name="🎮 게임 명령어",
                    value=
                        "**`/주사위`**\n"
                        "🎲 주사위 두 개의 합을 겨루는 간단한 게임입니다.\n"
                        "싱글 모드로 봇과 대결하거나, 다른 유저와 현금을 걸고 승부할 수 있습니다.\n"
                        "**`/야바위`**\n"
                        "🏺 세 개의 컵 중 공이 들어있는 컵 하나를 찾아내세요.\n" 
                        "보너스 컵을 찾으면 배팅액의 2배를 돌려받습니다.\n"
                        "**`/가위바위보`**\n"
                        "✌️ 상대방의 수를 예측하여 승리하면 배팅한 현금을 얻습니다.\n"
                        "봇과 대결하며 비길 경우 배팅액을 돌려받습니다.\n"
                        "**`/홀짝`**\n"
                        "⚪ 홀짝 게임 나오는 숫자가 홀수인지 짝수인지 맞히는 직관적인 게임입니다.\n"
                        "50%의 확률에 도전하여 보상을 획득하세요.\n"
                        "**`/슬롯머신`**\n"
                        "🎰세 개의 그림을 맞추는 게임입니다.\n"
                        "클로버가 나오면 배팅액의 최대 100배를 획득합니다.\n"
                        "**`/블랙잭`**\n"
                        "🃏 블랙잭 카드 숫자의 합이 21에 가깝게 만드세요.\n"
                        "봇(딜러)이나 다른 유저와 대결하며, 21을 초과하면 패배합니다.\n"
                        "**`/강화`**\n"
                        "💎 보유한 아이템의 단계를 높여 가치를 올리는 시스템입니다.\n"
                        "단계가 높아질수록 성공 확률이 낮아집니다.\n"
                        "/공격: 다른 사용자의 아이템을 공격하여 강화 단계를 하락시키는 기능입니다.\n"
                        "공격에 성공하면 상대방 아이템의 수치가 떨어지지만, 실패하면 본인의 아이템 수치가 하락하는 리스크가 있습니다.\n"
                        "/강화정보 | /강화순위: 강화 시스템의 상세 확률과 규칙을 확인하거나, 서버에서 가장 높은 강화 단계를 달성한 유저들의 순위를 확인합니다.\n"
                        "/초기화: 관리자 권한으로 모든 강화 데이터를 초기화합니다.\n"
                        "**`/제비뽑기`**\n"
                        "최소 2명에서 최대 12명까지 참여할 수 있는 복불복 게임입니다.\n"
                        "참여 인원과 각 결과 항목(당첨, 꽝 등)을 직접 입력하여 생성합니다.\n"
                        "**`/경마`**\n"
                        "관리자 권한 하에 경마 게임을 생성합니다.\n"
                        "실시간으로 순위가 변하는 레이스를 중계하며, 우승을 가릴수있습니다.",
                    inline=False)
            # 기존 뷰 유지
            view = HelpCategoryView() 
            await interaction.response.edit_message(embed=embed, view=view)
            return

        elif category == "other":
            embed.add_field(name="✨ 기타 명령어",
                    value=
                        "**`/도움말`**\n"
                        "봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.\n"
                        "**`/안녕`**\n"
                        "보석상과 인사하고 최신 업데이트를 확인합니다\n"
                        "**`/익명`**\n"
                        "익명으로 대화 할 수 있습니다.\n"
                        "**/로또구매**\n"
                        "로또를 구매합니다. /로또정보에서 상금 정보와 나의 티켓 목록을 확인합니다.\n" 
                        "/로또추첨을 통해 당첨됩니다.\n",
                            inline=False)

        view = HelpCategoryView()
        await interaction.response.edit_message(embed=embed, view=view)

# 📖 관리자 도움말 카테고리 선택 드롭다운
class AdminHelpCategorySelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="관리자 카테고리를 선택하세요!",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="현금 및 경험치", description="현금, XP, 교환, 세금 등", emoji="💰", value="admin_cash_xp"),
                discord.SelectOption(label="역할 및 채널", description="레벨 역할, 환영 메시지 등", emoji="🛠️", value="admin_roles_channels"),
                discord.SelectOption(label="백업 및 시스템", description="백업, 시스템 통계, 에러 등", emoji="💾", value="admin_system"),
                discord.SelectOption(label="사용자 및 업데이트", description="사용자 관리, 업데이트 시스템 등", emoji="📊", value="admin_users_updates")
            ]
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        embed = discord.Embed(title="📖 도움말 메뉴", color=discord.Color.blue())
        
        if category == "admin_cash_xp":
            embed.add_field(name="🛠️ 현금 및 경험치",
                    value=
                        "**`/사용자정보`**\n"
                        "특정 사용자의 상세 정보를 확인합니다.\n"
                        "**`/등록목록`**\n"
                        "등록된 사용자 목록을 확인합니다.\n"
                        "**`/금액관리`**\n"
                        "특정 사용자의 금액 지급 또는 차감\n"
                        "현금 지급 | 현금 차감\n"
                        "**`/경험치관리`**\n"
                        "특정 사용자의 XP 및 레벨 직접 수정\n"
                        "XP 지급 | XP 차감 | XP 설정 | 레벨 설정\n"
                        "**`/리더보드설정`**\n"
                        "출석 현금 보상 | 출석 XP 보상 | 연속 현금 보너스 일수 | 연속 XP 보너스 일수 | 최대 연속 보너스 일수 | 일 현금 보너스 | 7일 XP 보너스 | 🏆 30일 현금 보너스 | ⭐ 30일 XP 보너스"
                        "**`/획득량관리`**\n"
                        "시스템 XP 획득 및 쿨다운 설정\n"
                        "설정 보기 | 채팅 XP 설정 | 음성 XP 설정 | 명령어 XP 설정 | 채팅 쿨다운 설정 | \n"
                        "**`/교환설정`**\n"
                        "교환 시스템 설정을 변경합니다.\n"
                        "**`/선물설정`**\n"
                        "선물 시스템 설정을 변경합니다.\n"
                        "**`/세금수거`**\n"
                        "특정 역할의 유저들에게 세금을 징수합니다.\n",
                    inline=False)
        elif category == "admin_roles_channels":
            embed.add_field(name="🛠️ 역할 및 채널",
                    value=
                        "**`/역할관리`**\n"
                        "레벨 보상 역할 및 시스템 관리합니다.\n"
                        "레벨 역할 설정 | 레벨 역할 삭제 | 전체 목록 확인 | 제외 역할 등록 | 제외 역할 해제 | 알림 채널 설정\n"
                        "**`/채널설정`**\n"
                        "특정 기능이 작동할 채널을 관리합니다.\n"
                        "카테고리설정: 카테고리 내 모든 채널의 기능을 한 번에 설정합니다.\n"
                        "채널설정확인: 현재 서버의 모든 채널 기능 설정 목록을 보여줍니다.\n" 
                        "**`/대나무숲`**\n"
                        "최근 익명 메시지를 확인합니다.\n"
                        "**`/퇴장로그관리`**\n"
                        "설정/변경 | 비활성화 | 상태 확인 | 최근로그 조회\n" 
                        "**`/환영설정`**\n"
                        "서버의 환영 메시지 시스템을 설정합니다.\n"
                        "**`/레벨업채널설정`**\n"
                        "레벨업 알림을 받을 채널을 설정합니다.\n",
                    inline=False)
        elif category == "admin_system":
            embed.add_field(name="🛠️ 백업 및 시스템",
                    value=
                        "**`/글삭제`**\n"
                        "메시지를 삭제합니다.\n"
                        "**`/경험치데이터확인`**\n"
                        "등록되지 않은 사용자의 경험치 데이터를 확인합니다.\n"
                        "**`/데이터베이스상태`**\n"
                        "현재 데이터베이스 연결 상태를 확인합니다.\n"
                        "**`/보이스초기화`**\n"
                        "통화 시간 데이터를 초기화합니다.\n",
                    inline=False)
            
        elif category == "admin_users_updates":
            embed.add_field(name="🛠️ 통계",
                    value=
                        "**`/레벨순위`**\n"
                        "해당 서버의 XP 순위 확인합니다\n"
                        "**`/현금순위`**\n"
                        "해당 서버의 현금 보유 순위를 확인합니다.\n"
                        "**`/업데이트관리**\n"
                        "시스템 업데이트 내용을 관리합니다.\n"
                        "업데이트 추가 | 업데이트 삭제 | 전체 목록 확인\n"
                        "**`/통계`**\n"
                        "서버 전체 게임 통계를 확인합니다.\n"
                        "/통계디버그: 통계 시스템 디버깅 정보를 확인합니다.\n"
                        "**`/에러통계`**\n"
                        "에러 발생 통계 확인\n",
                    inline=False)
            
        # 뷰 업데이트
        view = AdminHelpCategoryView()
        await interaction.response.edit_message(embed=embed, view=view)

# 뷰 클래스
class AdminHelpCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AdminHelpCategorySelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class HelpCategoryView(discord.ui.View):
    def __init__(self, include_game_select=False):
        super().__init__(timeout=60)
        self.add_item(HelpCategorySelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class HelpCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_start_time = datetime.datetime.now(datetime.timezone.utc)
        print("✅ 도움말 시스템 로드 완료")

    # 일반 사용자를 위한 도움말 명령어
    @app_commands.command(name="도움말", description="봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.")
    async def help_command(self, interaction: discord.Interaction):
        try:
            # 실시간 업데이트 요약 정보 가져오기 (update_system.py 로드 확인)
            updates_summary = "⚠️ 실시간 업데이트 시스템이 로드되지 않았습니다."
            if UPDATE_SYSTEM_AVAILABLE:
                updates_summary = get_realtime_updates_summary()

            # 도움말 임베드 생성
            embed = discord.Embed(
                title="📖 보석상 도움말 메뉴",
                description="아래 드롭다운 메뉴에서 **카테고리**를 선택하여 원하는 명령어의 도움말을 확인하세요.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📢 최신 업데이트",
                value=updates_summary,
                inline=False
            )
        
            embed.set_footer(text="메뉴는 60초 후 만료됩니다")
        
            view = HelpCategoryView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
            
            message = await interaction.original_response()
            view.message = message
            
        except Exception as e:
            print(f"도움말 명령어 오류: {e}")
            embed = discord.Embed(
                title="📖 도움말 메뉴",
                description="일부 기능에 오류가 발생했습니다. 기본 기능은 정상적으로 사용 가능합니다.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # In HelpCommandCog class
    @app_commands.command(name="관리자도움말", description="봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def admin_help_command(self, interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="📖 보석상 관리자 도움말 메뉴",
                description="아래 드롭다운 메뉴에서 **카테고리**를 선택하여 원하는 관리자 명령어의 도움말을 확인하세요.",
                color=discord.Color.blue()
            )
        
            # 관리자 전용 드롭다운 뷰 생성
            view = AdminHelpCategoryView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            message = await interaction.original_response()
            view.message = message
            
        except Exception as e:
            print(f"관리자 도움말 명령어 오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommandCog(bot))