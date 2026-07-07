# error_handler.py - [시스템] 에러 처리
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import traceback
import sys
import logging
from datetime import datetime, timezone, timedelta
import os
import asyncio
from functools import wraps

# 한국 시간대 설정 (UTC+9)
KST = timezone(timedelta(hours=9))

# ✅ 로깅 설정
os.makedirs('logs', exist_ok=True)

# 파일과 콘솔에 동시 로깅
file_handler = logging.FileHandler('logs/bot_errors.log', encoding='utf-8')
console_handler = logging.StreamHandler(sys.stdout)

# 한글 깨짐 방지
try:
    console_handler.stream.reconfigure(encoding='utf-8')
except AttributeError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger('discord_bot_errors')

# ✅ 커스텀 에러 클래스들
class UserNotRegisteredError(Exception):
    """사용자가 등록되지 않았을 때 발생하는 에러"""
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        super().__init__("사용자가 명단에 등록되지 않았습니다.")

class InsufficientFundsError(Exception):
    """잔액이 부족할 때 발생하는 에러"""
    def __init__(self, required: int, current: int):
        self.required = required
        self.current = current
        super().__init__(f"잔액 부족: 필요 {required:,}원, 보유 {current:,}원")

class CooldownError(Exception):
    """쿨다운 중일 때 발생하는 에러"""
    def __init__(self, remaining: float):
        self.remaining = remaining
        super().__init__(f"쿨다운 중: {remaining:.1f}초 남음")

class GameInProgressError(Exception):
    """이미 게임이 진행 중일 때 발생하는 에러"""
    def __init__(self, game_name: str = "게임"):
        self.game_name = game_name
        super().__init__(f"{game_name}이 이미 진행 중입니다.")

class DatabaseError(Exception):
    """데이터베이스 관련 에러"""
    def __init__(self, operation: str = "", details: str = ""):
        self.operation = operation
        self.details = details
        super().__init__(f"데이터베이스 오류 [{operation}]: {details}")

# ✅ 메인 에러 핸들러 클래스
class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.error_counts = {}  # 에러 발생 빈도 추적
        
        # App command error handler 설정
        self.bot.tree.on_error = self.on_app_command_error

    def _increment_error_count(self, error_type: str):
        """에러 발생 빈도 카운트"""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1

    async def send_error_message(self, interaction_or_ctx, title: str, description: str, ephemeral: bool = True):
        """에러 메시지를 안전하게 전송"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.now(KST)
        )
        embed.set_footer(text="문제가 지속되면 관리자에게 문의해주세요.")
        
        try:
            # Interaction인 경우
            if hasattr(interaction_or_ctx, 'response'):
                if interaction_or_ctx.response.is_done():
                    await interaction_or_ctx.followup.send(embed=embed, ephemeral=ephemeral)
                else:
                    await interaction_or_ctx.response.send_message(embed=embed, ephemeral=ephemeral)
            # Context인 경우
            else:
                await interaction_or_ctx.send(embed=embed)
        except discord.NotFound:
            logger.warning("메시지를 찾을 수 없어 에러 응답을 전송하지 못했습니다.")
        except discord.Forbidden:
            logger.warning("권한이 없어 에러 응답을 전송하지 못했습니다.")
        except discord.HTTPException as e:
            logger.error(f"HTTP 에러로 에러 응답 전송 실패: {e}")
        except Exception as e:
            logger.error(f"예상치 못한 에러로 에러 응답 전송 실패: {e}")

    async def log_error(self, error, command_name: str = None, user: discord.User = None, guild: discord.Guild = None):
        """상세한 에러 로깅"""
        error_type = type(error).__name__
        self._increment_error_count(error_type)
        
        error_info = {
            'timestamp': datetime.now(KST).isoformat(),
            'error_type': error_type,
            'error_message': str(error),
            'command': command_name,
            'user': f"{user.display_name} ({user.id})" if user else None,
            'guild': f"{guild.name} ({guild.id})" if guild else None,
            'error_count': self.error_counts[error_type],
            'traceback': traceback.format_exception(type(error), error, error.__traceback__)
        }
        
        logger.error(f"Error in command '{command_name}': {error_info}")
        
        # 심각한 에러의 경우 추가 로깅
        if error_type in ['DatabaseError', 'PermissionError', 'ConnectionError']:
            logger.critical(f"CRITICAL ERROR: {error_type} - {str(error)}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Prefix 명령어 에러 처리"""
        # 이미 처리된 에러인지 확인
        if hasattr(ctx.command, 'on_error'):
            return

        await self.log_error(error, ctx.command.name if ctx.command else None, ctx.author, ctx.guild)
        
        # CommandInvokeError 내부의 실제 에러 추출
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        # 특정 에러 타입별 처리
        if isinstance(error, commands.MissingRequiredArgument):
            await self.send_error_message(
                ctx,
                "❌ 필수 인수 누락",
                f"**{error.param.name}** 인수가 필요합니다.\n사용법을 확인해주세요.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.BadArgument):
            await self.send_error_message(
                ctx,
                "❌ 잘못된 인수",
                "올바른 형식으로 입력해주세요.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.MissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self.send_error_message(
                ctx,
                "❌ 권한 부족",
                f"이 명령어를 사용하려면 **{perms}** 권한이 필요합니다.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self.send_error_message(
                ctx,
                "🤖 봇 권한 부족",
                f"봇에게 **{perms}** 권한을 부여해주세요.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.CommandOnCooldown):
            await self.send_error_message(
                ctx,
                "⏰ 쿨다운",
                f"이 명령어는 {error.retry_after:.1f}초 후에 사용할 수 있습니다.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.NotOwner):
            await self.send_error_message(
                ctx,
                "❌ 소유자 전용",
                "이 명령어는 봇 소유자만 사용할 수 있습니다.",
                ephemeral=False
            )
        
        elif isinstance(error, commands.CommandNotFound):
            # CommandNotFound는 무시 (스팸 방지)
            return
        
        else:
            # 알 수 없는 에러
            await self.send_error_message(
                ctx,
                "💥 알 수 없는 오류",
                "명령어 처리 중 오류가 발생했습니다.\n관리자에게 문의해주세요.",
                ephemeral=False
            )

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """App 명령어 (슬래시 명령어) 에러 처리"""
        await self.log_error(error, interaction.command.name if interaction.command else None, interaction.user, interaction.guild)

        # CommandInvokeError 내부의 실제 에러 추출
        if isinstance(error, app_commands.CommandInvokeError):
            error = error.original

        # 커스텀 에러 처리
        if isinstance(error, UserNotRegisteredError):
            await self.send_error_message(
                interaction,
                "❗ 미등록 사용자",
                "먼저 `/등록` 명령어로 명단에 등록해주세요!"
            )
        
        elif isinstance(error, InsufficientFundsError):
            await self.send_error_message(
                interaction,
                "❌ 잔액 부족",
                f"현재 잔액: **{error.current:,}원**\n필요 금액: **{error.required:,}원**\n부족한 금액: **{error.required - error.current:,}원**"
            )
        
        elif isinstance(error, CooldownError):
            await self.send_error_message(
                interaction,
                "⏰ 쿨다운",
                f"**{error.remaining:.1f}초** 후에 다시 시도해주세요."
            )
        
        elif isinstance(error, GameInProgressError):
            await self.send_error_message(
                interaction,
                "🎮 게임 진행 중",
                f"현재 **{error.game_name}**이 진행 중입니다.\n게임을 완료한 후 다시 시도해주세요."
            )
        
        elif isinstance(error, DatabaseError):
            await self.send_error_message(
                interaction,
                "💾 데이터베이스 오류",
                f"데이터베이스 작업 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요."
            )
        
        # Discord 기본 에러 처리
        elif isinstance(error, app_commands.MissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self.send_error_message(
                interaction,
                "❌ 권한 부족",
                f"이 명령어를 사용하려면 **{perms}** 권한이 필요합니다."
            )
        
        elif isinstance(error, app_commands.BotMissingPermissions):
            perms = ', '.join(error.missing_permissions)
            await self.send_error_message(
                interaction,
                "🤖 봇 권한 부족",
                f"봇에게 **{perms}** 권한을 부여해주세요."
            )
        
        elif isinstance(error, app_commands.CommandOnCooldown):
            await self.send_error_message(
                interaction,
                "⏰ 쿨다운",
                f"이 명령어는 **{error.retry_after:.1f}초** 후에 사용할 수 있습니다."
            )
        
        elif isinstance(error, app_commands.TransformerError):
            await self.send_error_message(
                interaction,
                "❌ 잘못된 입력",
                "입력값이 올바르지 않습니다. 형식을 확인해주세요."
            )
        
        elif isinstance(error, discord.NotFound):
            await self.send_error_message(
                interaction,
                "🔍 찾을 수 없음",
                "요청한 데이터를 찾을 수 없습니다."
            )
        
        elif isinstance(error, discord.Forbidden):
            await self.send_error_message(
                interaction,
                "❌ 접근 금지",
                "이 작업을 수행할 권한이 없습니다."
            )
        
        elif isinstance(error, discord.HTTPException):
            await self.send_error_message(
                interaction,
                "🌐 네트워크 오류",
                "Discord API 요청 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요."
            )
        
        # 일반적인 Python 에러들
        elif isinstance(error, ValueError):
            await self.send_error_message(
                interaction,
                "❌ 값 오류",
                "입력된 값이 올바르지 않습니다."
            )
        
        elif isinstance(error, TypeError):
            await self.send_error_message(
                interaction,
                "❌ 타입 오류",
                "입력 형식이 올바르지 않습니다."
            )
        
        elif isinstance(error, PermissionError):
            await self.send_error_message(
                interaction,
                "❌ 권한 오류",
                "필요한 권한이 없습니다."
            )
        
        elif isinstance(error, FileNotFoundError):
            await self.send_error_message(
                interaction,
                "📁 파일 없음",
                "필요한 파일을 찾을 수 없습니다."
            )
        
        else:
            # 알 수 없는 에러
            await self.send_error_message(
                interaction,
                "💥 알 수 없는 오류",
                "명령어 처리 중 오류가 발생했습니다.\n관리자에게 문의해주세요."
            )

    @commands.Cog.listener()
    async def on_error(self, event: str, *args, **kwargs):
        """일반 이벤트 에러 처리"""
        exc_type, exc_value, exc_traceback = sys.exc_info()
        
        if exc_type:
            error_info = {
                'timestamp': datetime.now(KST).isoformat(),
                'event': event,
                'error_type': exc_type.__name__,
                'error_message': str(exc_value),
                'traceback': traceback.format_exception(exc_type, exc_value, exc_traceback)
            }
            
            logger.error(f"Error in event '{event}': {error_info}")

    @app_commands.command(name="에러통계", description="[관리자 전용] 에러 발생 통계 확인")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def error_stats(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📊 에러 발생 통계",
            description="봇에서 발생한 에러들의 통계입니다.",
            color=discord.Color.orange(),
            timestamp=datetime.now(KST)
        )
        
        if not self.error_counts:
            embed.add_field(
                name="✅ 상태",
                value="에러가 발생하지 않았습니다!",
                inline=False
            )
        else:
            # 에러를 빈도순으로 정렬
            sorted_errors = sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)
            
            error_list = []
            for error_type, count in sorted_errors[:10]:  # 상위 10개만 표시
                error_list.append(f"**{error_type}**: {count}회")
            
            embed.add_field(
                name="🔥 자주 발생하는 에러 (Top 10)",
                value="\n".join(error_list) if error_list else "없음",
                inline=False
            )
            
            total_errors = sum(self.error_counts.values())
            embed.add_field(
                name="📈 총 에러 수",
                value=f"{total_errors:,}회",
                inline=True
            )
            
            embed.add_field(
                name="🎯 에러 종류",
                value=f"{len(self.error_counts)}개",
                inline=True
            )
        
        embed.set_footer(text=f"{interaction.user.display_name}님이 요청한 통계")
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ✅ 에러 처리 데코레이터
def handle_common_errors(func):
    """공통 에러를 처리하는 데코레이터"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except UserNotRegisteredError:
            interaction = next((arg for arg in args if hasattr(arg, 'response')), None)
            if interaction:
                await safe_send(
                    interaction,
                    "❗ 먼저 `/등록` 명령어로 명단에 등록해주세요!",
                    ephemeral=True
                )
        except InsufficientFundsError as e:
            interaction = next((arg for arg in args if hasattr(arg, 'response')), None)
            if interaction:
                await safe_send(
                    interaction,
                    f"❌ 잔액이 부족합니다!\n💰 현재 잔액: {e.current:,}원\n💸 필요 금액: {e.required:,}원",
                    ephemeral=True
                )
        except CooldownError as e:
            interaction = next((arg for arg in args if hasattr(arg, 'response')), None)
            if interaction:
                await safe_send(
                    interaction,
                    f"⏰ 쿨다운 중입니다. {e.remaining:.1f}초 후에 다시 시도해주세요.",
                    ephemeral=True
                )
        except GameInProgressError as e:
            interaction = next((arg for arg in args if hasattr(arg, 'response')), None)
            if interaction:
                await safe_send(
                    interaction,
                    f"🎮 이미 {e.game_name}이 진행 중입니다. 게임을 완료한 후 다시 시도해주세요.",
                    ephemeral=True
                )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            interaction = next((arg for arg in args if hasattr(arg, 'response')), None)
            if interaction:
                await safe_send(
                    interaction,
                    "💥 예상치 못한 오류가 발생했습니다. 관리자에게 문의해주세요.",
                    ephemeral=True
                )
    return wrapper

# ✅ 안전한 응답 전송 함수
async def safe_send(interaction_or_ctx, content=None, embed=None, view=None, ephemeral=True):
    """안전하게 응답을 전송하는 함수"""
    try:
        if hasattr(interaction_or_ctx, 'response'):
            # Interaction인 경우
            if interaction_or_ctx.response.is_done():
                await interaction_or_ctx.followup.send(
                    content=content, embed=embed, view=view, ephemeral=ephemeral
                )
            else:
                await interaction_or_ctx.response.send_message(
                    content=content, embed=embed, view=view, ephemeral=ephemeral
                )
        else:
            # Context인 경우
            await interaction_or_ctx.send(content=content, embed=embed, view=view)
        return True
    except discord.NotFound:
        logger.warning("메시지를 찾을 수 없어 응답을 전송하지 못했습니다.")
        return False
    except discord.Forbidden:
        logger.warning("권한이 없어 응답을 전송하지 못했습니다.")
        return False
    except discord.HTTPException as e:
        logger.error(f"HTTP 에러로 응답 전송 실패: {e}")
        return False
    except Exception as e:
        logger.error(f"예상치 못한 에러로 응답 전송 실패: {e}")
        return False

# ✅ 안전한 파일 작업 함수
async def safe_file_operation(operation, *args, **kwargs):
    """안전하게 파일 작업을 수행하는 함수"""
    try:
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)
    except FileNotFoundError:
        logger.error(f"파일을 찾을 수 없습니다: {args}")
        return None
    except PermissionError:
        logger.error(f"파일 접근 권한이 없습니다: {args}")
        return None
    except IsADirectoryError:
        logger.error(f"디렉토리에 파일 작업을 시도했습니다: {args}")
        return None
    except OSError as e:
        logger.error(f"OS 레벨 파일 작업 오류: {e}")
        return None
    except Exception as e:
        logger.error(f"파일 작업 중 예상치 못한 오류 발생: {e}")
        return None

# ✅ 안전한 데이터베이스 작업 함수
async def safe_db_operation(operation, *args, **kwargs):
    """안전하게 데이터베이스 작업을 수행하는 함수"""
    try:
        if asyncio.iscoroutinefunction(operation):
            return await operation(*args, **kwargs)
        else:
            return operation(*args, **kwargs)
    except Exception as e:
        logger.error(f"데이터베이스 작업 중 오류: {e}")
        raise DatabaseError(operation.__name__ if hasattr(operation, '__name__') else "unknown", str(e))

# ✅ 재시도 데코레이터
def retry_on_error(max_retries: int = 3, delay: float = 1.0):
    """에러 발생시 재시도하는 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            
            raise last_error
        return wrapper
    return decorator

# ✅ setup 함수
async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
    logger.info("✅ 통합 에러 처리 시스템 로드 완료 (개선된 버전)")