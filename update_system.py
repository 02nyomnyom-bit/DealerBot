# update_system.py
from __future__ import annotations
import datetime
import discord
from discord import app_commands
from discord.ext import commands, tasks
import json
import os
from typing import Dict, List, Optional

# 설정 파일 경로
DATA_DIR = "data"                                                       # 데이터 저장 폴더
REALTIME_UPDATES_FILE = os.path.join(DATA_DIR, "realtime_updates.json") # 현재 활성 업데이트 파일
ARCHIVED_UPDATES_FILE = os.path.join(DATA_DIR, "archived_updates.json") # 삭제/만료된 업데이트 보관 파일

os.makedirs(DATA_DIR, exist_ok=True)

# ✅ 실시간 업데이트 관리 함수들
def load_realtime_updates():
    """실시간 업데이트 목록 로드"""
    if not os.path.exists(REALTIME_UPDATES_FILE):
        return []
    try:
        with open(REALTIME_UPDATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"실시간 업데이트 로드 오류: {e}")
        return []

def save_realtime_updates(updates):
    """실시간 업데이트 목록 저장"""
    try:
        with open(REALTIME_UPDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(updates, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"실시간 업데이트 저장 오류: {e}")
        return False

def load_archived_updates():
    """보관된 업데이트 목록 로드"""
    if not os.path.exists(ARCHIVED_UPDATES_FILE):
        return []
    try:
        with open(ARCHIVED_UPDATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"보관된 업데이트 로드 오류: {e}")
        return []

def save_archived_updates(updates):
    """보관된 업데이트 목록 저장"""
    try:
        with open(ARCHIVED_UPDATES_FILE, "w", encoding="utf-8") as f:
            json.dump(updates, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"보관된 업데이트 저장 오류: {e}")
        return False

def add_realtime_update(title: str, description: str, author: str, priority: str = "일반") -> bool:
    """새로운 업데이트를 추가합니다. 추가 전 오래된(24시간 경과) 업데이트를 정리합니다."""
    try:
        updates = load_realtime_updates()
        
        # 업데이트 추가 전 자동 정리 실행
        remove_old_updates()
        
        # ID 생성 (기존 최대 ID + 1)
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
        result = save_realtime_updates(updates)
        
        if result:
            print(f"✅ 새 실시간 업데이트 추가: [{priority}] {title} (작성자: {author})")
        
        return result
    except Exception as e:
        print(f"실시간 업데이트 추가 오류: {e}")
        return False

def delete_update_by_id(update_id: int) -> bool:
    """ID로 특정 업데이트 삭제"""
    try:
        updates = load_realtime_updates()
        archived = load_archived_updates()
        
        # 삭제할 업데이트 찾기
        update_to_delete = None
        for update in updates:
            if update.get("id") == update_id:
                update_to_delete = update
                break
        
        if update_to_delete:
            # 삭제된 업데이트를 보관소에 추가
            update_to_delete["archived_date"] = datetime.datetime.now().isoformat()
            update_to_delete["archived_reason"] = "관리자에 의한 수동 삭제"
            archived.append(update_to_delete)
            save_archived_updates(archived)
            
            # 원본에서 삭제
            updated_list = [update for update in updates if update.get("id") != update_id]
            save_realtime_updates(updated_list)
            
            print(f"🗑️ 업데이트 ID {update_id} 삭제 완료 (보관소에 저장됨)")
            return True
        
        return False
    except Exception as e:
        print(f"업데이트 삭제 오류: {e}")
        return False
    
def clear_all_updates() -> bool:
    """모든 실시간 및 보관된 업데이트를 삭제"""
    try:
        save_realtime_updates([])
        save_archived_updates([])
        print("🗑️ 모든 실시간 및 보관된 업데이트 정리 완료")
        return True
    except Exception as e:
        print(f"모든 업데이트 정리 오류: {e}")
        return False

def remove_old_updates() -> int:
    """하루 지난 업데이트 자동 삭제 및 보관"""
    try:
        updates = load_realtime_updates()
        archived = load_archived_updates()
        current_date = datetime.datetime.now()
        
        # 24시간 이전 업데이트 필터링
        filtered_updates = []
        removed_count = 0
        
        for update in updates:
            try:
                update_time = datetime.datetime.fromisoformat(update["timestamp"])
                time_diff = (current_date - update_time).total_seconds()
                
                if time_diff < 2592000:  # 한달 미만인 업데이트만 유지
                    filtered_updates.append(update)
                else:
                    # 보관된 업데이트에 추가
                    update["archived_date"] = current_date.isoformat()
                    update["archived_reason"] = "한달 경과로 자동 보관"
                    archived.append(update)
                    removed_count += 1
                    print(f"📦 보관: [{update.get('priority', '일반')}] {update['title']}")
            except Exception as e:
                print(f"업데이트 날짜 파싱 오류: {e}")
                # 파싱 실패한 업데이트는 유지 (안전 조치)
                filtered_updates.append(update)
        
        if removed_count > 0:
            save_realtime_updates(filtered_updates)
            save_archived_updates(archived)
            print(f"🗑️ {removed_count}개의 오래된 업데이트를 자동 삭제하고 보관했습니다.")
        
        return removed_count
    except Exception as e:
        print(f"자동 정리 오류: {e}")
        return 0

def get_realtime_updates_summary(limit: int = 5) -> str:
    """실시간 업데이트 요약 생성 (우선순위별 정렬)"""
    try:
        updates = load_realtime_updates()
        
        if not updates:
            return "📝 **현재 등록된 실시간 업데이트가 없습니다.**\n\n관리자가 `/실시간업데이트추가` 명령어로 새로운 업데이트를 추가할 수 있습니다."
        
        # 우선순위별 정렬 (긴급 > 중요 > 일반)
        priority_order = {"긴급": 1, "중요": 2, "일반": 3}
        sorted_updates = sorted(
            updates, 
            key=lambda x: (priority_order.get(x.get("priority", "일반"), 3), x.get("timestamp", ""))
        )
        
        summary_lines = []
        
        for i, update in enumerate(sorted_updates[:limit]):
            priority = update.get("priority", "일반")
            priority_emoji = {"긴급": "🚨", "중요": "⚠️", "일반": "📌"}.get(priority, "📌")
            
            timestamp = update.get("timestamp", "")
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%m/%d %H:%M")
            except:
                time_str = "시간미상"
            
            title = update.get("title", "제목 없음")
            description = update.get("description", "설명 없음")
            author = update.get("author", "익명")
            
            summary_lines.append(f"{priority_emoji} **{title}**")
            summary_lines.append(f"   {description}")
            summary_lines.append(f"   *{time_str} | {author}*")
            
            if i < len(sorted_updates[:limit]) - 1:
                summary_lines.append("")
        
        return "\n".join(summary_lines)
        
    except Exception as e:
        print(f"업데이트 요약 생성 오류: {e}")
        return "❌ 업데이트 요약을 생성하는 중 오류가 발생했습니다."

def get_update_statistics() -> Dict:
    """업데이트 시스템 통계 생성"""
    try:
        updates = load_realtime_updates()
        archived = load_archived_updates()
        
        # 우선순위별 통계
        priority_counts = {"긴급": 0, "중요": 0, "일반": 0}
        for update in updates:
            priority = update.get("priority", "일반")
            if priority in priority_counts:
                priority_counts[priority] += 1
        
        # 오늘 추가된 업데이트 수
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for update in updates if update.get("date") == today)
        
        return {
            "total_active": len(updates),
            "total_archived": len(archived),
            "today_count": today_count,
            "priority_counts": priority_counts,
            "last_updated": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        print(f"통계 생성 오류: {e}")
        return {
            "total_active": 0,
            "total_archived": 0, 
            "today_count": 0,
            "priority_counts": {"긴급": 0, "중요": 0, "일반": 0},
            "last_updated": datetime.datetime.now().isoformat()
        }

# ✅ Discord Commands Cog
class RealtimeUpdateSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # self.auto_cleanup_task.start() # ❌ 자동 정리 작업 시작 중단
    
    @app_commands.command(name="업데이트추가", description="[관리자 전용] 새로운 업데이트를 추가합니다.")
    @app_commands.describe(제목="업데이트 제목", 내용="업데이트 내용", 우선순위="우선순위 (긴급/중요/일반)")
    async def add_update(self, interaction: discord.Interaction, 제목: str, 내용: str, 우선순위: str = "일반"):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 사용 가능합니다.", ephemeral=True)
            return
        
        processed_description = 내용.replace("\\n", "\n")
        success = add_realtime_update(제목, processed_description, interaction.user.display_name, 우선순위)
        
        if success:
            priority_emoji = {"긴급": "🚨", "중요": "⚠️", "일반": "📌"}.get(우선순위, "📌")
            embed = discord.Embed(
                title="실시간 업데이트 추가 완료",
                description=f"{priority_emoji} **{제목}**\n{processed_description}",
                color=discord.Color.green()
            )
            embed.set_footer(text="이 업데이트는 관리자가 삭제할 때까지 유지됩니다.")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ 업데이트 추가에 실패했습니다.", ephemeral=True)

    @app_commands.command(name="업데이트목록", description="현재 실시간 업데이트 목록을 확인합니다")
    async def list_updates(self, interaction: discord.Interaction):
        updates = load_realtime_updates()
        
        if not updates:
            embed = discord.Embed(
                title="📝 업데이트 목록",
                description="현재 등록된 업데이트가 없습니다.",
                color=discord.Color.light_grey()
            )
        else:
            # 우선순위별 정렬
            priority_order = {"긴급": 1, "중요": 2, "일반": 3}
            sorted_updates = sorted(
                updates, 
                key=lambda x: (priority_order.get(x.get("priority", "일반"), 3), x.get("timestamp", ""))
            )
            
            embed = discord.Embed(
                title="📝 업데이트 목록",
                description=f"총 {len(updates)}개의 활성 업데이트",
                color=discord.Color.blue()
            )
            
            for update in sorted_updates[:10]:  # 최대 10개만 표시
                priority = update.get("priority", "일반")
                priority_emoji = {"긴급": "🚨", "중요": "⚠️", "일반": "📌"}.get(priority, "📌")
                
                timestamp = update.get("timestamp", "")
                try:
                    dt = datetime.datetime.fromisoformat(timestamp)
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    time_str = "시간미상"
                
                title = update.get("title", "제목 없음")
                description = update.get("description", "설명 없음")
                author = update.get("author", "익명")
                update_id = update.get("id", "N/A")
                
                field_name = f"{priority_emoji} {title} (ID: {update_id})"
                field_value = f"{description}\n*{time_str} | {author}*"
                
                embed.add_field(name=field_name, value=field_value, inline=False)
        
        stats = get_update_statistics()
        embed.add_field(
            name="📊 통계",
            value=f"긴급: {stats['priority_counts']['긴급']}개 | "
                  f"중요: {stats['priority_counts']['중요']}개 | "
                  f"일반: {stats['priority_counts']['일반']}개",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="업데이트삭제", description="[관리자 전용] 특정 ID의 업데이트를 삭제합니다.")
    @app_commands.describe(업데이트_id="삭제할 업데이트의 ID")
    async def delete_update(self, interaction: discord.Interaction, 업데이트_id: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return
        
        success = delete_update_by_id(업데이트_id)
        
        if success:
            embed = discord.Embed(
                title="✅ 업데이트 삭제 완료",
                description=f"ID {업데이트_id} 업데이트가 삭제되고 보관소에 저장되었습니다.",
                color=discord.Color.orange()
            )
        else:
            embed = discord.Embed(
                title="❌ 삭제 실패",
                description=f"ID {업데이트_id}에 해당하는 업데이트를 찾을 수 없습니다.",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="전체업데이트정리", description="[관리자 전용] 모든 실시간 및 보관된 업데이트를 삭제합니다.")
    async def clear_all_updates_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return

        success = clear_all_updates()
        
        if success:
            embed = discord.Embed(
                title="✅ 전체 업데이트 삭제 완료",
                description="모든 실시간 및 보관된 업데이트가 완전히 삭제되었습니다. 이 작업은 되돌릴 수 없습니다.",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="❌ 삭제 실패",
                description="업데이트를 삭제하는 중 오류가 발생했습니다.",
                color=discord.Color.red()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="업데이트통계", description="[관리자 전용] 시스템 통계를 확인합니다.")
    async def update_stats(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자만 사용할 수 있는 명령어입니다.", ephemeral=True)
            return
        
        stats = get_update_statistics()
        
        embed = discord.Embed(
            title="📊 실시간 업데이트 시스템 통계",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="ℹ️ 시스템 정보",
            value="• 업데이트는 관리자가 수동으로 삭제해야 합니다.\n"
                  "• 삭제된 업데이트는 보관소에 저장됩니다.\n"
                  "• 자동 정리 기능이 비활성화되었습니다.",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 우선순위별 분포",
            value=f"🚨 **긴급**: {stats['priority_counts']['긴급']}개\n"
                  f"⚠️ **중요**: {stats['priority_counts']['중요']}개\n"
                  f"📌 **일반**: {stats['priority_counts']['일반']}개",
            inline=True
        )
        
        embed.add_field(
            name="ℹ️ 시스템 정보",
            value="• 업데이트는 24시간 후 자동 보관됩니다\n"
                  "• 삭제된 업데이트는 보관소에 저장됩니다\n"
                  "• 1시간마다 자동 정리가 실행됩니다",
            inline=False
        )
        
        try:
            last_updated = datetime.datetime.fromisoformat(stats['last_updated'])
            embed.set_footer(text=f"마지막 업데이트: {last_updated.strftime('%Y-%m-%d %H:%M:%S')}")
        except:
            embed.set_footer(text="통계 생성 시간: 알 수 없음")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    async def record_game(self, guild_id, user_id, game_type, bet, win_amount):
            """
            다른 시스템(강화, 슬롯, 경마)에서 호출하는 공통 인터페이스
            """
            # 승리 여부 판단: 당첨금이 배팅금보다 크면 승리
            is_win = win_amount > bet
            # 순수익 계산 (당첨금 - 배팅금)
            earn_points = win_amount - bet
        
            # 기존에 존재하는 update_stats 메서드 호출
            return await self.update_stats(guild_id, user_id, game_type, is_win, earn_points)
    
    @app_commands.command(name="업데이트", description="실시간 업데이트 내용만 확인합니다.")
    async def show_updates_only(self, interaction: discord.Interaction):
        updates = load_realtime_updates()
        
        if not updates:
            embed = discord.Embed(
                title="📝 실시간 업데이트",
                description="현재 등록된 실시간 업데이트가 없습니다.",
                color=discord.Color.light_grey()
            )
            embed.add_field(
                name="ℹ️ 안내",
                value="관리자가 `/실시간업데이트추가` 명령어로\n새로운 업데이트를 추가할 수 있습니다.",
                inline=False
            )
        else:
            embed = discord.Embed(
                title="📝 실시간 업데이트",
                description=get_realtime_updates_summary(8),  # 최대 8개 표시
                color=discord.Color.blue()
            )
        
        stats = get_update_statistics()
        embed.add_field(
            name="📊 업데이트 현황",
            value=f"**활성**: {stats['total_active']}개 | **오늘**: {stats['today_count']}개",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ 우선순위",
            value=f"🚨{stats['priority_counts']['긴급']} ⚠️{stats['priority_counts']['중요']} 📌{stats['priority_counts']['일반']}",
            inline=True
        )
        
        embed.set_footer(text=f"마지막 확인: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(name="안녕", description="딜러양과 인사하고 최신 뉴스를 확인합니다.")
    async def hello_with_updates(self, interaction: discord.Interaction):
        # 기본 인사말
        embed = discord.Embed(
            title="👋 안녕하세요! 딜러양입니다",
            description=f"{interaction.user.display_name}님, 어서오세요! 🎉",
            color=discord.Color.gold()
        )
        
        # 현재 시간
        now = datetime.datetime.now()
        embed.add_field(
            name="🕐 현재 시간",
            value=now.strftime("%Y년 %m월 %d일 %H시 %M분"),
            inline=True
        )
        
        # 시스템 상태
        embed.add_field(
            name="⚡ 시스템 상태",
            value="🟢 정상 운영 중",
            inline=True
        )
        
        # 실시간 업데이트 요약
        updates_summary = get_realtime_updates_summary(3)  # 최대 3개
        embed.add_field(
            name="📝 최신 업데이트",
            value=updates_summary,
            inline=False
        )
        
        # 통계 정보
        stats = get_update_statistics()
        embed.add_field(
            name="📊 업데이트 현황",
            value=f"활성: {stats['total_active']}개 | 오늘: {stats['today_count']}개",
            inline=True
        )
        
        embed.add_field(
            name="💡 도움말",
            value="`/도움말` - 명령어 확인\n`/업데이트` - 업데이트만 보기",
            inline=True
        )
        
        embed.set_footer(text="딜러양 v1.5.10 | 실시간 업데이트 시스템 가동 중")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(RealtimeUpdateSystem(bot))