# update_system.py - 업데이트 시스템 (수정본)
from __future__ import annotations
import datetime
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
from typing import Dict, Optional

# 설정 파일 경로
DATA_DIR = "data"                                                       # 데이터 저장 폴더
REALTIME_UPDATES_FILE = os.path.join(DATA_DIR, "realtime_updates.json") # 현재 활성 업데이트 파일
ARCHIVED_UPDATES_FILE = os.path.join(DATA_DIR, "archived_updates.json") # 삭제/만료된 업데이트 보관 파일

os.makedirs(DATA_DIR, exist_ok=True)


# ==================== 데이터 핸들링 함수들 (규격 통일) ====================

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


def remove_old_updates() -> int:
    """오래된 업데이트(예: 한 달 경과) 자동 보관"""
    try:
        updates = load_realtime_updates()
        archived = load_archived_updates()
        current_date = datetime.datetime.now()
        
        filtered_updates = []
        removed_count = 0
        
        for update in updates:
            try:
                update_time = datetime.datetime.fromisoformat(update["timestamp"])
                time_diff = (current_date - update_time).total_seconds()
                
                if time_diff < 2592000:  # 30일(한 달) 미만 유지
                    filtered_updates.append(update)
                else:
                    update["archived_date"] = current_date.isoformat()
                    update["archived_reason"] = "한 달 경과로 자동 보관"
                    archived.append(update)
                    removed_count += 1
            except Exception as e:
                print(f"업데이트 날짜 파싱 오류: {e}")
                filtered_updates.append(update)
        
        if removed_count > 0:
            save_realtime_updates(filtered_updates)
            save_archived_updates(archived)
            print(f"📦 {removed_count}개의 오래된 업데이트를 자동으로 보관함으로 이동했습니다.")
        
        return removed_count
    except Exception as e:
        print(f"자동 정리 오류: {e}")
        return 0


def get_realtime_updates_summary(limit: int = 5) -> str:
    """실시간 업데이트 요약 생성 (우선순위 정렬 반영)"""
    try:
        updates = load_realtime_updates()
        if not updates:
            return "📝 **현재 등록된 실시간 업데이트가 없습니다.**\n\n관리자가 `/업데이트관리` 명령어로 추가할 수 있습니다."
        
        # 1. 우선순위 정렬 (긴급 > 중요 > 일반)
        priority_order = {"🚨 긴급": 1, "⭐ 중요": 2, "📌 일반": 3}
        sorted_updates = sorted(
            updates, 
            key=lambda x: (priority_order.get(x.get("priority", "📌 일반"), 3), x.get("timestamp", ""))
        )
        
        summary_lines = []
        for i, update in enumerate(sorted_updates[:limit]):
            priority = update.get("priority", "📌 일반")
            title = update.get("title", "제목 없음")
            description = update.get("description", "설명 없음")
            author = update.get("author", "익명")
            
            # 시간 포맷팅
            time_str = "시간미상"
            if "timestamp" in update:
                try:
                    dt = datetime.datetime.fromisoformat(update["timestamp"])
                    time_str = dt.strftime("%m/%d %H:%M")
                except:
                    pass

            summary_lines.append(f"{priority} **{title}**")
            summary_lines.append(f"   {description}")
            summary_lines.append(f"   *{time_str} | {author}*")
            
            if i < len(sorted_updates[:limit]) - 1:
                summary_lines.append("")
        
        return "\n".join(summary_lines)
    except Exception as e:
        print(f"요약 생성 오류: {e}")
        return "❌ 업데이트 요약을 생성하는 중 오류가 발생했습니다."


def get_update_statistics() -> Dict:
    """업데이트 시스템 통계 생성"""
    try:
        updates = load_realtime_updates()
        archived = load_archived_updates()
        
        priority_counts = {"🚨 긴급": 0, "⭐ 중요": 0, "📌 일반": 0}
        for u in updates:
            p = u.get("priority", "📌 일반")
            if p in priority_counts:
                priority_counts[p] += 1
                
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        today_count = sum(1 for u in updates if u.get("timestamp", "").startswith(today_str))
        
        return {
            "total_active": len(updates),
            "total_archived": len(archived),
            "today_count": today_count,
            "priority_counts": priority_counts
        }
    except Exception as e:
        print(f"통계 생성 오류: {e}")
        return {"total_active": 0, "total_archived": 0, "today_count": 0}


# ==================== Discord Cog ====================

class RealtimeUpdateSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="업데이트관리", description="[관리자 전용] 시스템 업데이트 내용을 관리합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        작업="수행할 작업을 선택하세요",
        제목="업데이트의 제목 (추가 시 필수)",
        설명="업데이트의 상세 내용 (추가 시 필수)",
        분류="업데이트의 중요도 (추가 시 필수)",
        번호="삭제할 업데이트 ID 번호 (삭제 시 필요)"
    )
    @app_commands.choices(
        작업=[
            app_commands.Choice(name="📝 업데이트 추가", value="add"),
            app_commands.Choice(name="❌ 업데이트 삭제", value="remove"),
            app_commands.Choice(name="📋 전체 목록 확인", value="list")
        ],
        분류=[
            app_commands.Choice(name="🚨 긴급", value="🚨 긴급"),
            app_commands.Choice(name="⭐ 중요", value="⭐ 중요"),
            app_commands.Choice(name="📌 일반", value="📌 일반")
        ]
    )
    async def update_admin(
        self, 
        interaction: discord.Interaction, 
        작업: str, 
        제목: Optional[str] = None,
        설명: Optional[str] = None, 
        분류: Optional[str] = "📌 일반",
        번호: Optional[int] = None
    ):
        # 1. 업데이트 추가
        if 작업 == "add":
            if not 제목 or not 설명:
                return await interaction.response.send_message("❌ 추가를 위해 [제목]과 [설명]을 모두 입력해 주세요.", ephemeral=True)
            
            # 추가 전에 오래된 데이터 자동 정리
            remove_old_updates()
            
            updates = load_realtime_updates()
            new_id = max([u.get("id", 0) for u in updates], default=0) + 1
            now = datetime.datetime.now()
            
            # 통일된 JSON 규격
            new_update = {
                "id": new_id,
                "title": 제목,
                "description": 설명.replace("\\n", "\n"),  # \n 글자를 진짜 엔터로 변환!
                "priority": 분류,
                "author": interaction.user.display_name,
                "timestamp": now.isoformat()
            }
            
            updates.append(new_update)
            save_realtime_updates(updates)
            
            embed = discord.Embed(title="✅ 업데이트 등록 완료", color=discord.Color.green())
            embed.add_field(name=f"{분류} ID: {new_id} | {제목}", value=설명, inline=False)
            await interaction.response.send_message(embed=embed)

        # 2. 업데이트 삭제
        elif 작업 == "remove":
            if 번호 is None:
                return await interaction.response.send_message("❌ 삭제할 업데이트 ID 번호를 입력해 주세요.", ephemeral=True)
            
            updates = load_realtime_updates()
            archived = load_archived_updates()
            
            target = next((u for u in updates if u["id"] == 번호), None)
            
            if target:
                updates.remove(target)
                target["archived_date"] = datetime.datetime.now().isoformat()
                target["archived_reason"] = "관리자에 의한 수동 삭제"
                archived.append(target)
                
                save_realtime_updates(updates)
                save_archived_updates(archived)
                await interaction.response.send_message(f"🗑️ ID {번호}번 업데이트를 삭제하고 보관함으로 이동했습니다.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ ID {번호}번 업데이트를 찾을 수 없습니다.", ephemeral=True)

        # 3. 전체 목록 확인
        elif 작업 == "list":
            updates = load_realtime_updates()
            if not updates:
                return await interaction.response.send_message("ℹ️ 등록된 업데이트가 없습니다.", ephemeral=True)
            
            embed = discord.Embed(title="📋 실시간 업데이트 전체 목록", color=discord.Color.blue())
            for u in updates:
                dt_str = "시간미상"
                try:
                    dt_str = datetime.datetime.fromisoformat(u["timestamp"]).strftime("%Y-%m-%d %H:%M")
                except:
                    pass
                
                embed.add_field(
                    name=f"{u.get('priority', '📌 일반')} ID #{u['id']} - {u['title']}",
                    value=f"{u['description']}\n*(작성자: {u['author']} | {dt_str})*",
                    inline=False
                )
            await interaction.response.send_message(embed=embed, ephemeral=True)


    @app_commands.command(name="안녕", description="보석상과 인사하고 최신 뉴스를 확인합니다.")
    async def hello_with_updates(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="👋 안녕하세요! 보석상입니다",
            description=f"{interaction.user.display_name}님, 어서오세요! 🎉",
            color=discord.Color.gold()
        )
        
        now = datetime.datetime.now()
        embed.add_field(name="🕐 현재 시간", value=now.strftime("%Y년 %m월 %d일 %H시 %M분"), inline=True)
        embed.add_field(name="⚡ 시스템 상태", value="🟢 정상 운영 중", inline=True)
        
        # 수정된 연동 요약
        updates_summary = get_realtime_updates_summary(3)
        embed.add_field(name="📝 최신 업데이트", value=updates_summary, inline=False)
        
        stats = get_update_statistics()
        embed.add_field(
            name="📊 업데이트 현황", 
            value=f"활성: {stats['total_active']}개 | 오늘 추가: {stats['today_count']}개", 
            inline=True
        )
        embed.set_footer(text="보석상 v1.10.10 | 실시간 업데이트 시스템 가동 중")
        
        await interaction.response.send_message(embed=embed, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(RealtimeUpdateSystem(bot))