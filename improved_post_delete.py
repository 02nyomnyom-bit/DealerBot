# improved_post_delete.py - 글 삭제
from __future__ import annotations
import discord
from discord import app_commands, Interaction, TextChannel
from discord.ext import commands
from datetime import datetime, timedelta, timezone
import asyncio
from typing import Literal, Optional

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

# ===== 모달 클래스들 =====

class CountInputModal(discord.ui.Modal):
    """개수 입력 모달"""
    def __init__(self):
        super().__init__(title="메시지 개수 입력")
        self.count = None

    count_input = discord.ui.TextInput(
        label="삭제할 메시지 개수",
        placeholder="1부터 1500까지 입력 가능합니다",
        min_length=1,
        max_length=4,
        required=True
    )

    async def on_submit(self, interaction: Interaction):
        try:
            count = int(self.count_input.value)
            if count < 1 or count > 1500:
                await interaction.response.send_message(
                    "❌ 개수는 1부터 1500까지만 입력 가능합니다.", 
                    ephemeral=True
                )
                return
            
            self.count = count
            await interaction.response.send_message(
                f"✅ {count}개 메시지 삭제로 설정되었습니다.", 
                ephemeral=True
            )
            
        except ValueError:
            await interaction.response.send_message(
                "❌ 올바른 숫자를 입력해주세요.", 
                ephemeral=True
            )

class DateInputModal(discord.ui.Modal):
    """날짜 입력 모달"""
    def __init__(self):
        super().__init__(title="날짜 범위 입력")
        self.start_date = None
        self.end_date = None

    start_date_input = discord.ui.TextInput(
        label="시작 날짜 (MM.DD 형식)",
        placeholder="예: 08.01",
        min_length=5,
        max_length=5,
        required=True
    )
    
    end_date_input = discord.ui.TextInput(
        label="종료 날짜 (MM.DD 형식)",
        placeholder="예: 08.07",
        min_length=5,
        max_length=5,
        required=True
    )

    async def on_submit(self, interaction: Interaction):
        try:
            # 날짜 파싱
            start_parts = self.start_date_input.value.split('.')
            end_parts = self.end_date_input.value.split('.')
            
            if len(start_parts) != 2 or len(end_parts) != 2:
                raise ValueError("잘못된 날짜 형식")
            
            start_month, start_day = int(start_parts[0]), int(start_parts[1])
            end_month, end_day = int(end_parts[0]), int(end_parts[1])
            
            current_year = datetime.now(KST).year
            
            # KST timezone으로 날짜 생성
            start_date = datetime(current_year, start_month, start_day, tzinfo=KST)
            end_date = datetime(current_year, end_month, end_day, 23, 59, 59, tzinfo=KST)
            
            # 날짜 검증
            if start_date > end_date:
                await interaction.response.send_message(
                    "❌ 시작 날짜가 종료 날짜보다 늦을 수 없습니다.", 
                    ephemeral=True
                )
                return
            
            # 한 달 제한 확인
            if (end_date - start_date).days > 31:
                await interaction.response.send_message(
                    "❌ 날짜 범위는 최대 한 달(31일)까지만 가능합니다.", 
                    ephemeral=True
                )
                return
            
            self.start_date = start_date
            self.end_date = end_date
            
            await interaction.response.send_message(
                f"✅ {start_date.strftime('%m.%d')} ~ {end_date.strftime('%m.%d')} (한국 시간) 기간으로 설정되었습니다.", 
                ephemeral=True
            )
            
        except (ValueError, IndexError):
            await interaction.response.send_message(
                "❌ 올바른 날짜 형식(MM.DD)으로 입력해주세요.\n예: 08.01", 
                ephemeral=True
            )

# ===== UI 클래스들 =====

class DeleteMethodSelectView(discord.ui.View):
    """삭제 방식 선택 UI"""
    def __init__(self, admin_user):
        super().__init__(timeout=60)
        self.admin_user = admin_user
        self.result = None

    @discord.ui.button(label="🔢 개수로 삭제", style=discord.ButtonStyle.primary)
    async def delete_by_count(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 선택할 수 있습니다.", 
                ephemeral=True
            )
        
        # 개수 입력 모달 표시
        modal = CountInputModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.count is not None:
            self.result = {'type': 'count', 'count': modal.count}
            self.stop()

    @discord.ui.button(label="📅 날짜로 삭제", style=discord.ButtonStyle.secondary)
    async def delete_by_date(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 선택할 수 있습니다.", 
                ephemeral=True
            )
        
        # 날짜 입력 모달 표시
        modal = DateInputModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.start_date is not None and modal.end_date is not None:
            self.result = {
                'type': 'date', 
                'start_date': modal.start_date, 
                'end_date': modal.end_date
            }
            self.stop()

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger)
    async def cancel_selection(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 취소할 수 있습니다.", 
                ephemeral=True
            )
        
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ 글삭제 취소",
                description="글삭제가 취소되었습니다.",
                color=discord.Color.orange()
            ),
            view=None
        )
        self.stop()

    async def on_timeout(self):
        """타임아웃 처리"""
        for item in self.children:
            item.disabled = True

class DeleteConfirmView(discord.ui.View):
    """삭제 확인 UI"""
    def __init__(self, delete_info: dict, channel: TextChannel, admin_user):
        super().__init__(timeout=60)
        self.delete_info = delete_info
        self.channel = channel
        self.admin_user = admin_user

    @discord.ui.button(label="✅ 삭제 실행", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 삭제를 실행할 수 있습니다.", 
                ephemeral=True
            )
        
        await interaction.response.defer(ephemeral=True)
        
        # 진행 상황 표시
        progress_embed = discord.Embed(
            title="🔄 글 삭제 진행 중...",
            description="메시지를 수집하고 삭제하는 중입니다. 잠시만 기다려주세요.",
            color=discord.Color.blue()
        )
        progress_embed.add_field(
            name="⏳ 예상 시간",
            value="메시지 수에 따라 몇 분이 걸릴 수 있습니다.",
            inline=False
        )
        progress_embed.add_field(
            name="🛡️ 안전 조치",
            value="Discord API 제한을 피하기 위해 안전한 속도로 진행됩니다.",
            inline=False
        )
        
        await interaction.edit_original_response(embed=progress_embed, view=None)
        
        try:
            # 삭제 진행
            deleted_count = await self.perform_deletion(interaction)
            
            # 완료 메시지
            embed = discord.Embed(
                title="✅ 글 삭제 완료",
                description=f"**{deleted_count}개**의 메시지가 성공적으로 삭제되었습니다.",
                color=discord.Color.green()
            )
            
            if self.delete_info['type'] == 'count':
                embed.add_field(
                    name="🔢 삭제 조건",
                    value=f"최근 {self.delete_info['count']}개 메시지",
                    inline=True
                )
            else:
                embed.add_field(
                    name="📅 삭제 조건", 
                    value=f"{self.delete_info['start_date'].strftime('%m.%d')} ~ {self.delete_info['end_date'].strftime('%m.%d')}",
                    inline=True
                )
            
            embed.add_field(
                name="📍 채널",
                value=f"#{self.channel.name}",
                inline=True
            )
            
            embed.add_field(
                name="👤 실행자",
                value=self.admin_user.mention,
                inline=True
            )
            
            # 버튼 비활성화
            for item in self.children:
                item.disabled = True
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 삭제 실패",
                description=f"삭제 중 오류가 발생했습니다: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 취소할 수 있습니다.", 
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="❌ 글 삭제 취소",
            description="글 삭제가 취소되었습니다.",
            color=discord.Color.orange()
        )
        
        # 버튼 비활성화
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def perform_deletion(self, interaction: Interaction):
        """실제 삭제 수행 (Rate Limit 안전 버전)"""
        messages_to_delete = []
        
        try:
            if self.delete_info['type'] == 'count':
                # 개수로 삭제 - 안전한 속도로 메시지 수집
                count = 0
                async for message in self.channel.history(limit=None):
                    if count >= self.delete_info['count']:
                        break
                    messages_to_delete.append(message)
                    count += 1
                    
                    # 메시지 수집 중간에도 잠시 대기 (Rate Limit 방지)
                    if count % 100 == 0:
                        print(f"Debug: {count}개 메시지 수집 완료, 잠시 대기...")
                        
                        # 진행 상황 업데이트
                        progress_embed = discord.Embed(
                            title="📥 메시지 수집 중...",
                            description=f"{count}개 메시지 수집 완료",
                            color=discord.Color.blue()
                        )
                        try:
                            await interaction.edit_original_response(embed=progress_embed)
                        except:
                            pass  # Edit 실패해도 계속 진행
                        
                        await asyncio.sleep(1)
                    
            else:
                # 날짜 범위로 삭제 - 안전한 속도로 메시지 수집
                start_date = self.delete_info['start_date']
                end_date = self.delete_info['end_date'] + timedelta(days=1)  # 다음날 0시까지 포함
                
                message_count = 0
                async for message in self.channel.history(
                    after=start_date,
                    before=end_date,
                    limit=None
                ):
                    messages_to_delete.append(message)
                    message_count += 1
                    
                    # 메시지 수집 중간에도 잠시 대기 (Rate Limit 방지)
                    if message_count % 100 == 0:
                        print(f"Debug: {message_count}개 메시지 수집 완료, 잠시 대기...")
                        
                        # 진행 상황 업데이트
                        progress_embed = discord.Embed(
                            title="📥 메시지 수집 중...",
                            description=f"{message_count}개 메시지 수집 완료",
                            color=discord.Color.blue()
                        )
                        try:
                            await interaction.edit_original_response(embed=progress_embed)
                        except:
                            pass  # Edit 실패해도 계속 진행
                        
                        await asyncio.sleep(1)
            
            print(f"Debug: 총 {len(messages_to_delete)}개 메시지 수집 완료")
            
            # 수집 완료 알림
            collect_complete_embed = discord.Embed(
                title="🗑️ 메시지 삭제 시작",
                description=f"총 {len(messages_to_delete)}개 메시지 삭제를 시작합니다...",
                color=discord.Color.orange()
            )
            try:
                await interaction.edit_original_response(embed=collect_complete_embed)
            except:
                pass
            
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = e.response.headers.get('Retry-After', 5)
                print(f"Debug: 메시지 수집 중 Rate Limit 감지, {retry_after}초 대기...")
                await asyncio.sleep(float(retry_after) + 1)
            raise e
        
        # 메시지 삭제 실행
        return await self.bulk_delete_messages(messages_to_delete)

    async def bulk_delete_messages(self, messages):
        """메시지를 효율적으로 삭제 (Rate Limit 안전 버전)"""
        if not messages:
            return 0
        
        deleted_count = 0
        
        # 14일 이내와 이후 메시지 분리
        recent_messages = []
        old_messages = []
        
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=14)
        
        for message in messages:
            if message.created_at > cutoff_date:
                recent_messages.append(message)
            else:
                old_messages.append(message)
        
        print(f"Debug: 최근 메시지 {len(recent_messages)}개, 오래된 메시지 {len(old_messages)}개")
        
        # 14일 이내 메시지는 벌크 삭제 (최대 100개씩)
        for i in range(0, len(recent_messages), 100):
            batch = recent_messages[i:i+100]
            try:
                await self.channel.delete_messages(batch)
                deleted_count += len(batch)
                print(f"Debug: 벌크 삭제 완료 - {len(batch)}개")
                
                # API 제한 방지를 위한 더 긴 딜레이
                await asyncio.sleep(2)  # 1초 → 2초로 증가
                    
            except discord.HTTPException as e:
                print(f"Debug: 벌크 삭제 실패, 개별 삭제로 전환 - {str(e)}")
                
                # Rate Limit 감지시 더 긴 대기
                if e.status == 429:
                    retry_after = e.response.headers.get('Retry-After', 5)
                    print(f"Debug: Rate Limit 감지, {retry_after}초 대기...")
                    await asyncio.sleep(float(retry_after) + 1)
                
                # 벌크 삭제 실패시 개별 삭제
                for message in batch:
                    try:
                        await message.delete()
                        deleted_count += 1
                        await asyncio.sleep(1)  # 0.5초 → 1초로 증가
                    except discord.HTTPException as del_error:
                        if del_error.status == 429:
                            retry_after = del_error.response.headers.get('Retry-After', 3)
                            print(f"Debug: 개별 삭제 Rate Limit, {retry_after}초 대기...")
                            await asyncio.sleep(float(retry_after) + 1)
                        print(f"Debug: 개별 삭제 실패 - {str(del_error)}")
                    except Exception as del_error:
                        print(f"Debug: 개별 삭제 실패 - {str(del_error)}")
                        pass
        
        # 14일 이후 메시지는 개별 삭제
        for message in old_messages:
            try:
                await message.delete()
                deleted_count += 1
                await asyncio.sleep(1)  # 0.5초 → 1초로 증가
                print(f"Debug: 오래된 메시지 삭제 완료")
            except discord.HTTPException as del_error:
                if del_error.status == 429:
                    retry_after = del_error.response.headers.get('Retry-After', 3)
                    print(f"Debug: 오래된 메시지 Rate Limit, {retry_after}초 대기...")
                    await asyncio.sleep(float(retry_after) + 1)
                print(f"Debug: 오래된 메시지 삭제 실패 - {str(del_error)}")
            except Exception as del_error:
                print(f"Debug: 오래된 메시지 삭제 실패 - {str(del_error)}")
                pass
        
        return deleted_count

    async def on_timeout(self):
        """타임아웃 처리"""
        for item in self.children:
            item.disabled = True

# ===== 메인 COG 클래스 =====

class ImprovedPostDeleteCog(commands.Cog):
    """개선된 글삭제 시스템"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="글삭제", description="[관리자 전용] 메시지를 삭제합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def delete_posts(self, interaction: Interaction):      
        # 인터랙티브 삭제 모드
        await self.interactive_delete_mode(interaction)

    async def interactive_delete_mode(self, interaction: Interaction):
        """인터랙티브 삭제 모드"""
        embed = discord.Embed(
            title="🗑️ 글삭제 시스템",
            description="삭제 방식을 선택해주세요:",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="🔢 개수로 삭제",
            value="최근 메시지부터 지정한 개수만큼 삭제\n(최대 1500개)",
            inline=True
        )
        
        embed.add_field(
            name="📅 날짜로 삭제",
            value="특정 날짜 범위의 모든 메시지 삭제\n(최대 한 달 범위)",
            inline=True
        )
        
        embed.add_field(
            name="📍 대상 채널",
            value=f"#{interaction.channel.name}",
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 주의사항",
            value="• 삭제된 메시지는 복구할 수 없습니다\n• 삭제 작업은 취소할 수 있습니다\n• 60초 내에 선택하지 않으면 자동 취소됩니다",
            inline=False
        )
        
        view = DeleteMethodSelectView(interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # 선택 대기
        await view.wait()
        
        if view.result:
            await self.show_delete_confirmation(interaction, view.result)

    async def show_delete_confirmation(self, interaction: Interaction, delete_info: dict):
        """삭제 확인 화면 표시"""
        embed = discord.Embed(
            title="⚠️ 글 삭제 확인",
            description="정말로 다음 조건으로 글을 삭제하시겠습니까?",
            color=discord.Color.red()
        )
        
        if delete_info['type'] == 'count':
            embed.add_field(
                name="🔢 삭제 조건",
                value=f"최근 **{delete_info['count']}개** 메시지",
                inline=False
            )
        else:
            embed.add_field(
                name="📅 삭제 조건",
                value=f"**{delete_info['start_date'].strftime('%m.%d')}** ~ **{delete_info['end_date'].strftime('%m.%d')}** 기간 (KST)",
                inline=False
            )
        
        embed.add_field(
            name="📍 대상 채널",
            value=f"#{interaction.channel.name}",
            inline=True
        )
        
        embed.add_field(
            name="👤 실행자",
            value=interaction.user.mention,
            inline=True
        )
        
        embed.add_field(
            name="⚠️ 주의사항",
            value="• 삭제된 메시지는 복구할 수 없습니다\n• 삭제 과정은 시간이 걸릴 수 있습니다\n• 60초 내에 응답하지 않으면 자동 취소됩니다",
            inline=False
        )
        
        view = DeleteConfirmView(delete_info, interaction.channel, interaction.user)
        
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(ImprovedPostDeleteCog(bot))
    print("✅ 완전 작동 개선된 글삭제 시스템 로드 완료")
