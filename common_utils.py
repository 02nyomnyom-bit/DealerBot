# common_utils.py
from __future__ import annotations
import os
import json
import datetime
import re
import logging
import hashlib
import time
from typing import Dict, Any, List, Tuple, Union 
from pathlib import Path
from functools import wraps
import math

# ✅ 로깅 설정
logger = logging.getLogger(__name__)

# ✅ 상수 정의
DEFAULT_DIRECTORIES = ["data", "logs", "backups", "temp", "exports"]
DEFAULT_ENCODING = "utf-8"
DISCORD_EMBED_LIMITS = {
    "title": 256,
    "description": 4096,
    "field_name": 256,
    "field_value": 1024,
    "footer": 2048,
    "author": 256,
    "total_chars": 6000
}

# ==================== 파일 및 디렉토리 관리 ====================

def ensure_directories(directories: List[str] = None) -> bool:
    """필요한 디렉토리들을 생성합니다."""
    if directories is None:
        directories = DEFAULT_DIRECTORIES
    
    try:
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        logger.info(f"디렉토리 생성 완료: {', '.join(directories)}")
        return True
    except Exception as e:
        logger.error(f"디렉토리 생성 실패: {e}")
        return False

def save_json(file_path: str, data: Any, indent: int = 4) -> bool:
    """데이터를 JSON 파일로 저장합니다."""
    try:
        with open(file_path, 'w', encoding=DEFAULT_ENCODING) as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"JSON 저장 실패 ({file_path}): {e}")
        return False
    
def load_json(file_path: str, default_value: Any = None) -> Any:
    """JSON 파일을 로드합니다."""
    if not os.path.exists(file_path):
        return default_value
    
    try:
        with open(file_path, 'r', encoding=DEFAULT_ENCODING) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"JSON 로드 실패 ({file_path}): {e}")
        return default_value
    
def load_json_file(path: str, default: Any = None, create_if_missing: bool = True) -> Dict:
    """JSON 파일을 안전하게 로드합니다."""
    if default is None:
        default = {}
    
    try:
        if not os.path.exists(path):
            if create_if_missing:
                save_json_file(default, path)
                logger.info(f"기본 JSON 파일 생성: {path}")
            return default
        
        with open(path, "r", encoding=DEFAULT_ENCODING) as f:
            data = json.load(f)
            logger.debug(f"JSON 파일 로드 성공: {path}")
            return data
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류 ({path}): {e}")
        # 백업 생성
        backup_path = f"{path}.corrupted_{int(time.time())}"
        try:
            os.rename(path, backup_path)
            logger.info(f"손상된 JSON 파일 백업: {backup_path}")
        except:
            pass
        return default
        
    except Exception as e:
        logger.error(f"JSON 로드 실패 ({path}): {e}")
        return default

def save_json_file(data: Dict, path: str, indent: int = 2, backup: bool = True) -> bool:
    """JSON 파일을 안전하게 저장합니다."""
    try:
        # 디렉토리 생성
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        
        # 기존 파일 백업 (옵션)
        if backup and os.path.exists(path):
            backup_path = f"{path}.backup"
            try:
                import shutil
                shutil.copy2(path, backup_path)
            except:
                pass
        
        # 임시 파일에 먼저 저장 후 원자적 이동
        temp_path = f"{path}.tmp"
        with open(temp_path, "w", encoding=DEFAULT_ENCODING) as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        
        os.replace(temp_path, path)
        logger.debug(f"JSON 파일 저장 성공: {path}")
        return True
        
    except Exception as e:
        logger.error(f"JSON 저장 실패 ({path}): {e}")
        # 임시 파일 정리
        if os.path.exists(f"{path}.tmp"):
            try:
                os.remove(f"{path}.tmp")
            except:
                pass
        return False

def get_file_info(path: str) -> Dict:
    """파일 정보를 상세히 반환합니다."""
    try:
        stat = os.stat(path)
        return {
            "exists": True,
            "size": stat.st_size,
            "size_formatted": format_file_size(stat.st_size),
            "created": datetime.datetime.fromtimestamp(stat.st_ctime),
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime),
            "accessed": datetime.datetime.fromtimestamp(stat.st_atime),
            "is_file": os.path.isfile(path),
            "is_dir": os.path.isdir(path)
        }
    except FileNotFoundError:
        return {"exists": False}
    except Exception as e:
        logger.error(f"파일 정보 조회 실패 ({path}): {e}")
        return {"exists": False, "error": str(e)}

def format_file_size(size_bytes: int) -> str:
    """파일 크기를 읽기 쉬운 형태로 변환합니다."""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    for unit in units:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} EB"

def clean_old_files(directory: str, max_age_days: int = 30, pattern: str = "*") -> int:
    """오래된 파일들을 정리합니다."""
    try:
        cleaned_count = 0
        cutoff_time = time.time() - (max_age_days * 24 * 3600)
        
        for file_path in Path(directory).glob(pattern):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.debug(f"오래된 파일 삭제: {file_path}")
                except:
                    pass
        
        if cleaned_count > 0:
            logger.info(f"오래된 파일 정리 완료: {cleaned_count}개 파일 삭제")
        
        return cleaned_count
    except Exception as e:
        logger.error(f"파일 정리 실패: {e}")
        return 0

# ==================== 포맷팅 함수들 ====================

def format_money(amount: int) -> str:
    """숫자를 금액 형식으로 변환합니다 (예: 1,000)."""
    try:
        return f"{amount:,}"
    except Exception:
        return str(amount)

def format_xp(xp: int, show_commas: bool = True) -> str:
    """XP를 포맷합니다."""
    if show_commas:
        return f"{xp:,} XP"
    else:
        return f"{xp} XP"

def format_percentage(value: float, decimal_places: int = 1, 
                     show_sign: bool = False) -> str:
    """퍼센티지를 포맷합니다."""
    try:
        formatted = f"{value:.{decimal_places}f}"
        if show_sign and value > 0:
            formatted = f"+{formatted}"
        return f"{formatted}%"
    except:
        return "0.0%"

def format_large_number(num: float) -> str:
    """큰 숫자를 K, M, B 단위로 변환합니다."""
    if num < 1000:
        return str(num)
    
    for unit in ['', 'K', 'M', 'B', 'T']:
        if abs(num) < 1000.0:
            return f"{num:.1f}{unit}"
        num /= 1000.0
    return f"{num:.1f}P"

def format_duration(seconds: Union[int, float], precision: str = "auto") -> str:
    """시간을 읽기 쉬운 형태로 포맷합니다."""
    try:
        if seconds < 0:
            return "0초"
        
        units = [
            ("일", 86400),
            ("시간", 3600),
            ("분", 60),
            ("초", 1)
        ]
        
        parts = []
        remaining = int(seconds)
        
        for name, unit_seconds in units:
            if remaining >= unit_seconds:
                count = remaining // unit_seconds
                parts.append(f"{count}{name}")
                remaining %= unit_seconds
                
                if precision == "single" and parts:
                    break
        
        if not parts:
            return "0초"
        
        if precision == "auto" and len(parts) > 2:
            parts = parts[:2]
        
        return " ".join(parts)
    except:
        return "0초"

def format_datetime(dt: datetime.datetime, format_type: str = "default") -> str:
    """날짜시간을 다양한 형식으로 포맷합니다."""
    formats = {
        "default": "%Y-%m-%d %H:%M:%S",
        "date": "%Y-%m-%d",
        "time": "%H:%M:%S",
        "korean": "%Y년 %m월 %d일 %H:%M",
        "short": "%m/%d %H:%M",
        "iso": "%Y-%m-%dT%H:%M:%S",
        "timestamp": "[%Y-%m-%d %H:%M:%S]"
    }
    
    try:
        format_string = formats.get(format_type, formats["default"])
        return dt.strftime(format_string)
    except:
        return str(dt)

# ==================== 시간 관련 함수들 ====================

def now_str() -> str:
    """현재 시간을 문자열로 반환합니다 (YYYY-MM-DD HH:MM:SS)."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str() -> str:
    """오늘 날짜를 문자열로 반환합니다 (YYYY-MM-DD)."""
    return datetime.datetime.now().strftime("%Y-%m-%d")

def parse_date_range(date_string: str, year: int = None) -> Tuple[datetime.datetime, datetime.datetime]:
    """날짜 범위 문자열을 파싱합니다. (예: "08.01-08.08", "2024.01.15-2024.01.20")"""
    if year is None:
        year = datetime.datetime.now().year
    
    # 다양한 날짜 형식 지원
    patterns = [
        # MM.dd-MM.dd 형식
        r'^(\d{2})\.(\d{2})-(\d{2})\.(\d{2})$',
        # YYYY.MM.dd-YYYY.MM.dd 형식
        r'^(\d{4})\.(\d{2})\.(\d{2})-(\d{4})\.(\d{2})\.(\d{2})$',
        # MM/dd-MM/dd 형식
        r'^(\d{2})/(\d{2})-(\d{2})/(\d{2})$',
        # YYYY/MM/dd-YYYY/MM/dd 형식
        r'^(\d{4})/(\d{2})/(\d{2})-(\d{4})/(\d{2})/(\d{2})$'
    ]
    
    for pattern in patterns:
        match = re.match(pattern, date_string.strip())
        if match:
            groups = match.groups()
            
            if len(groups) == 4:  # MM.dd-MM.dd 형식
                start_month, start_day, end_month, end_day = map(int, groups)
                try:
                    start_date = datetime.datetime(year, start_month, start_day, 0, 0, 0)
                    end_date = datetime.datetime(year, end_month, end_day, 23, 59, 59)
                except ValueError as e:
                    raise ValueError(f"잘못된 날짜: {e}")
                    
            elif len(groups) == 6:  # YYYY.MM.dd-YYYY.MM.dd 형식
                start_year, start_month, start_day, end_year, end_month, end_day = map(int, groups)
                try:
                    start_date = datetime.datetime(start_year, start_month, start_day, 0, 0, 0)
                    end_date = datetime.datetime(end_year, end_month, end_day, 23, 59, 59)
                except ValueError as e:
                    raise ValueError(f"잘못된 날짜: {e}")
            
            # 날짜 순서 검증
            if start_date > end_date:
                raise ValueError("시작 날짜가 종료 날짜보다 늦을 수 없습니다.")
            
            # 범위 제한 (최대 1년)
            if (end_date - start_date).days > 365:
                raise ValueError("날짜 범위는 최대 1년까지만 가능합니다.")
            
            return start_date, end_date
    
    # 매칭되는 패턴이 없는 경우
    raise ValueError(
        "날짜 형식이 올바르지 않습니다.\n"
        "지원 형식: MM.dd-MM.dd, YYYY.MM.dd-YYYY.MM.dd, MM/dd-MM/dd, YYYY/MM/dd-YYYY/MM/dd\n"
        "예시: 08.01-08.08, 2024.01.15-2024.01.20"
    )

def get_time_until(target_time: datetime.datetime) -> Dict:
    """특정 시간까지 남은 시간을 계산합니다."""
    try:
        now = datetime.datetime.now()
        delta = target_time - now
        
        if delta.total_seconds() <= 0:
            return {"expired": True, "message": "이미 지났습니다."}
        
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}일")
        if hours > 0:
            parts.append(f"{hours}시간")
        if minutes > 0:
            parts.append(f"{minutes}분")
        if seconds > 0 and not parts:  # 1분 미만인 경우만 초 표시
            parts.append(f"{seconds}초")
        
        return {
            "expired": False,
            "total_seconds": delta.total_seconds(),
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "message": " ".join(parts) if parts else "곧"
        }
    except Exception as e:
        logger.error(f"시간 계산 오류: {e}")
        return {"expired": True, "message": "오류"}

def is_weekend(date: datetime.date = None) -> bool:
    """주말인지 확인합니다."""
    if date is None:
        date = datetime.date.today()
    return date.weekday() >= 5  # 5=토요일, 6=일요일

def get_korean_weekday(date: datetime.date = None) -> str:
    """한국어 요일을 반환합니다."""
    if date is None:
        date = datetime.date.today()
    
    weekdays = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    return weekdays[date.weekday()]

# ==================== 로깅 함수들 ====================

def setup_logger(name: str, log_file: str, level=logging.INFO):
    """개별 로거를 설정합니다."""
    handler = logging.FileHandler(f"logs/{log_file}", encoding=DEFAULT_ENCODING)        
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))

    new_logger = logging.getLogger(name)
    new_logger.setLevel(level)
    new_logger.addHandler(handler)
    
    return new_logger

def log_action(message: str, log_type: str = "GENERAL", log_file: str = "general.log", 
               level: int = logging.INFO):
    """액션을 로그 파일에 기록합니다."""
    timestamp = now_str()
    log_message = f"{timestamp} [{log_type}] {message}"
    
    # 콘솔 출력
    print(log_message)
    
    # 파일 출력
    try:
        os.makedirs("logs", exist_ok=True)
        log_path = os.path.join("logs", log_file)
        with open(log_path, "a", encoding=DEFAULT_ENCODING) as f:
            f.write(log_message + "\n")
    except Exception as e:
        print(f"로그 파일 작성 실패: {e}")

# 특화된 로깅 함수들
def log_cash_action(message: str):
    """현금 관련 액션을 로그에 기록합니다."""
    log_action(message, "CASH", "cash.log")

def log_xp_action(message: str):
    """XP 관련 액션을 로그에 기록합니다."""
    log_action(message, "XP", "xp.log")

def log_user_action(message: str):
    """사용자 관리 액션을 로그에 기록합니다."""
    log_action(message, "USER", "user.log")

def log_game_action(message: str):
    """게임 관련 액션을 로그에 기록합니다."""
    log_action(message, "GAME", "game.log")

def log_admin_action(message: str):
    """관리자 액션을 로그에 기록합니다."""
    log_action(message, "ADMIN", "admin.log")

def log_error_action(message: str):
    """에러를 로그에 기록합니다."""
    log_action(message, "ERROR", "error.log", logging.ERROR)

# ==================== 계산 함수들 ====================
def calculate_level_from_xp(xp: int) -> int:
    """주어진 총 경험치를 기반으로 레벨을 계산합니다."""
    if xp < 0:
        return 0
    
    level = math.sqrt(xp + 2) / 10
    return math.floor(level)

def calculate_xp_for_level(level: int, base_xp: int = 100, exponent: float = 2.0) -> int:
    """특정 레벨에 필요한 XP를 계산합니다."""
    if level <= 1:
        return 0
    try:
        return int(((level - 1) ** exponent) * base_xp)
    except:
        return 0

def calculate_xp_progress(current_xp: int, base_xp: int = 100, exponent: float = 0.5) -> Dict:
    """현재 XP의 진행 상황을 계산합니다."""
    current_level = calculate_level_from_xp(current_xp, base_xp, 1/exponent)
    current_level_xp = calculate_xp_for_level(current_level, base_xp, 1/exponent)
    next_level_xp = calculate_xp_for_level(current_level + 1, base_xp, 1/exponent)
    
    progress_xp = current_xp - current_level_xp
    needed_xp = next_level_xp - current_level_xp
    progress_percentage = (progress_xp / needed_xp * 100) if needed_xp > 0 else 100
    
    return {
        "current_level": current_level,
        "current_xp": current_xp,
        "current_level_xp": current_level_xp,
        "next_level_xp": next_level_xp,
        "progress_xp": progress_xp,
        "needed_xp": needed_xp,
        "progress_percentage": min(100, max(0, progress_percentage))
    }

def calculate_fee(amount: int, fee_rate: float) -> Tuple[int, int]:
    """수수료를 계산하여 (수수료, 최종금액) 튜플을 반환합니다."""
    try:
        fee = int(amount * fee_rate)
        final_amount = max(0, amount - fee)
        return fee, final_amount
    except:
        return 0, amount

def calculate_win_rate(wins: int, total_games: int) -> float:
    """승률을 계산합니다."""
    if total_games <= 0:
        return 0.0
    return min(100.0, max(0.0, (wins / total_games) * 100))

def calculate_compound_interest(principal: float, rate: float, time: int, 
                              compound_frequency: int = 1) -> float:
    """복리 이자를 계산합니다."""
    try:
        return principal * (1 + rate / compound_frequency) ** (compound_frequency * time)
    except:
        return principal

def calculate_statistics(numbers: List[Union[int, float]]) -> Dict:
    """숫자 리스트의 기본 통계를 계산합니다."""
    if not numbers:
        return {"count": 0, "sum": 0, "average": 0, "min": 0, "max": 0, "median": 0}
    
    try:
        sorted_numbers = sorted(numbers)
        count = len(numbers)
        total = sum(numbers)
        average = total / count
        minimum = min(numbers)
        maximum = max(numbers)
        
        # 중간값 계산
        if count % 2 == 0:
            median = (sorted_numbers[count//2 - 1] + sorted_numbers[count//2]) / 2
        else:
            median = sorted_numbers[count//2]
        
        return {
            "count": count,
            "sum": total,
            "average": average,
            "min": minimum,
            "max": maximum,
            "median": median
        }
    except Exception as e:
        logger.error(f"통계 계산 오류: {e}")
        return {"count": 0, "sum": 0, "average": 0, "min": 0, "max": 0, "median": 0}

# ==================== 검증 함수들 ====================

def validate_positive_int(value: Union[str, int], name: str = "값", 
                         min_value: int = 1, max_value: int = None) -> int:
    """양의 정수인지 검증합니다."""
    try:
        num = int(value)
        if num < min_value:
            raise ValueError(f"{name}은(는) {min_value} 이상이어야 합니다.")
        if max_value is not None and num > max_value:
            raise ValueError(f"{name}은(는) {max_value} 이하여야 합니다.")
        return num
    except ValueError as e:
        if "invalid literal" in str(e):
            raise ValueError(f"{name}은(는) 유효한 숫자여야 합니다.")
        raise e

def validate_percentage(value: Union[str, float], name: str = "퍼센티지") -> float:
    """퍼센티지 값인지 검증합니다."""
    try:
        num = float(value)
        if not (0 <= num <= 100):
            raise ValueError(f"{name}은(는) 0~100 사이의 값이어야 합니다.")
        return num
    except ValueError as e:
        if "could not convert" in str(e):
            raise ValueError(f"{name}은(는) 유효한 숫자여야 합니다.")
        raise e

def validate_date_range_length(start_date: datetime.datetime, 
                              end_date: datetime.datetime, 
                              max_days: int = 14) -> bool:
    """날짜 범위가 제한 내에 있는지 검증합니다."""
    delta = end_date - start_date
    if delta.days > max_days:
        raise ValueError(f"날짜 범위는 최대 {max_days}일까지만 가능합니다.")
    return True

def validate_username(username: str, min_length: int = 2, max_length: int = 32) -> str:
    """사용자명을 검증합니다."""
    if not username or not username.strip():
        raise ValueError("사용자명은 비어있을 수 없습니다.")
    
    username = username.strip()
    
    if len(username) < min_length:
        raise ValueError(f"사용자명은 최소 {min_length}자 이상이어야 합니다.")
    
    if len(username) > max_length:
        raise ValueError(f"사용자명은 최대 {max_length}자 이하여야 합니다.")
    
    # 특수문자 제한
    if re.search(r'[<>@#&]', username):
        raise ValueError("사용자명에는 < > @ # & 문자를 사용할 수 없습니다.")
    
    return username

def validate_discord_id(user_id: str) -> str:
    """디스코드 ID를 검증합니다."""
    if not user_id or not user_id.isdigit():
        raise ValueError("유효하지 않은 디스코드 ID입니다.")
    
    if len(user_id) < 17 or len(user_id) > 20:
        raise ValueError("디스코드 ID 길이가 올바르지 않습니다.")
    
    return user_id

# ==================== 데이터 처리 함수들 ====================

def safe_divide(numerator: Union[int, float], denominator: Union[int, float], 
                default: Union[int, float] = 0.0) -> float:
    """안전한 나눗셈을 수행합니다."""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default

def clamp(value: Union[int, float], min_value: Union[int, float], 
          max_value: Union[int, float]) -> Union[int, float]:
    """값을 범위 내로 제한합니다."""
    return max(min_value, min(value, max_value))

def get_percentage_of_total(value: Union[int, float], total: Union[int, float]) -> float:
    """전체에서 차지하는 비율을 계산합니다."""
    return safe_divide(value * 100, total, 0.0)

def normalize_data(data: List[Union[int, float]], target_min: float = 0.0, 
                   target_max: float = 1.0) -> List[float]:
    """데이터를 정규화합니다."""
    if not data:
        return []
    
    try:
        min_val = min(data)
        max_val = max(data)
        
        if min_val == max_val:
            return [target_min] * len(data)
        
        scale = (target_max - target_min) / (max_val - min_val)
        return [(x - min_val) * scale + target_min for x in data]
    except Exception as e:
        logger.error(f"데이터 정규화 오류: {e}")
        return data

def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """리스트를 지정된 크기로 분할합니다."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def merge_dicts(*dicts: Dict, deep: bool = False) -> Dict:
    """여러 딕셔너리를 병합합니다."""
    result = {}
    for d in dicts:
        if deep:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        else:
            result.update(d)
    return result

# ==================== 디스코드 관련 유틸리티 ====================

def truncate_text(text: str, max_length: int = 1024, suffix: str = "...", 
                  word_boundary: bool = True) -> str:
    """텍스트를 Discord embed 제한에 맞게 자릅니다."""
    if len(text) <= max_length:
        return text
    
    if word_boundary:
        # 단어 경계에서 자르기
        truncated = text[:max_length - len(suffix)]
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.8:  # 80% 이상인 경우만 단어 경계 적용
            truncated = truncated[:last_space]
        return truncated + suffix
    else:
        return text[:max_length - len(suffix)] + suffix

def create_progress_bar(current: int, maximum: int, length: int = 10, 
                       filled: str = "█", empty: str = "░", 
                       show_percentage: bool = False) -> str:
    """진행률 바를 생성합니다."""
    if maximum <= 0:
        return empty * length
    
    progress = clamp(current / maximum, 0.0, 1.0)
    filled_length = int(length * progress)
    bar = filled * filled_length + empty * (length - filled_length)
    
    if show_percentage:
        percentage = progress * 100
        return f"{bar} {percentage:.1f}%"
    
    return bar

def create_table(headers: List[str], rows: List[List[str]], 
                 max_width: int = 1024) -> str:
    """간단한 테이블을 생성합니다."""
    if not headers or not rows:
        return "데이터가 없습니다."
    
    try:
        # 열 너비 계산
        col_widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row[:len(headers)]):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # 테이블 생성
        table = []
        
        # 헤더
        header_row = " | ".join(h.ljust(w) for h, w in zip(headers, col_widths))
        table.append(header_row)
        table.append("-" * len(header_row))
        
        # 데이터 행
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) 
                                for i, cell in enumerate(row[:len(headers)]))
            table.append(row_str)
        
        result = "\n".join(table)
        
        # 길이 제한
        if len(result) > max_width:
            return truncate_text(result, max_width, "...\n(테이블이 잘렸습니다)")
        
        return f"```\n{result}\n```"
    except Exception as e:
        logger.error(f"테이블 생성 오류: {e}")
        return "테이블 생성 중 오류가 발생했습니다."

def format_embed_field(name: str, value: str, max_name_length: int = None, 
                      max_value_length: int = None) -> Tuple[str, str]:
    """Discord embed 필드를 포맷합니다."""
    if max_name_length is None:
        max_name_length = DISCORD_EMBED_LIMITS["field_name"]
    if max_value_length is None:
        max_value_length = DISCORD_EMBED_LIMITS["field_value"]
    
    formatted_name = truncate_text(name, max_name_length, "...")
    formatted_value = truncate_text(value, max_value_length, "...")
    
    return formatted_name, formatted_value

def split_long_message(message: str, max_length: int = 2000, 
                      delimiter: str = "\n") -> List[str]:
    """긴 메시지를 Discord 제한에 맞게 분할합니다."""
    if len(message) <= max_length:
        return [message]
    
    parts = []
    lines = message.split(delimiter)
    current_part = ""
    
    for line in lines:
        test_part = current_part + delimiter + line if current_part else line
        
        if len(test_part) <= max_length:
            current_part = test_part
        else:
            if current_part:
                parts.append(current_part)
                current_part = line
            else:
                # 단일 라인이 너무 긴 경우
                parts.extend(chunk_text(line, max_length))
                current_part = ""
    
    if current_part:
        parts.append(current_part)
    
    return parts

def chunk_text(text: str, chunk_size: int) -> List[str]:
    """텍스트를 지정된 크기로 분할합니다."""
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

# ==================== 보안 및 해싱 ====================

def generate_hash(text: str) -> str:
    """텍스트의 MD5 해시를 생성합니다."""
    return hashlib.md5(text.encode(DEFAULT_ENCODING)).hexdigest()

def generate_session_id(length: int = 16) -> str:
    """세션 ID를 생성합니다."""
    import string
    import random
    
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def sanitize_filename(filename: str) -> str:
    """파일명을 안전하게 만듭니다."""
    # 위험한 문자 제거
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # 연속된 점 제거
    filename = re.sub(r'\.{2,}', '.', filename)
    
    # 앞뒤 공백 및 점 제거
    filename = filename.strip('. ')
    
    # 예약된 이름 확인 (Windows)
    reserved_names = ['CON', 'PRN', 'AUX', 'NUL'] + [f'COM{i}' for i in range(1, 10)] + [f'LPT{i}' for i in range(1, 10)]
    if filename.upper() in reserved_names:
        filename = f"_{filename}"
    
    # 길이 제한
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        max_name_length = 255 - len(ext)
        filename = name[:max_name_length] + ext
    
    return filename or "untitled"

# ==================== 설정 관리 ====================

class ConfigManager:
    """향상된 설정 파일 관리 클래스"""
    
    def __init__(self, config_file: str, default_config: Dict, auto_save: bool = True):
        self.config_file = config_file
        self.default_config = default_config.copy()
        self.auto_save = auto_save
        self._cached_config = None
        self._last_modified = 0
        self.config = self.load_config()

    def load_config(self, force_reload: bool = False) -> Dict:
        """설정을 로드합니다."""
        try:
            # 파일 수정 시간 확인
            if os.path.exists(self.config_file):
                current_modified = os.path.getmtime(self.config_file)
                if not force_reload and self._cached_config and current_modified == self._last_modified:
                    return self._cached_config
                self._last_modified = current_modified
            
            loaded_config = load_json_file(self.config_file, {})
            
            # 기본 설정과 병합
            config = merge_dicts(self.default_config, loaded_config, deep=True)
            
            self._cached_config = config
            return config
        except Exception as e:
            logger.error(f"설정 로드 실패: {e}")
            return self.default_config.copy()

    def save_config(self, config: Dict = None) -> bool:
        """설정을 저장합니다."""
        try:
            config_to_save = config or self.config
            success = save_json_file(config_to_save, self.config_file)
            if success:
                self._cached_config = config_to_save.copy()
                self._last_modified = os.path.getmtime(self.config_file)
            return success
        except Exception as e:
            logger.error(f"설정 저장 실패: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """설정값을 가져옵니다. (점 표기법 지원)"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> bool:
        """설정값을 변경합니다. (점 표기법 지원)"""
        try:
            keys = key.split('.')
            config = self.config
            
            # 중첩된 딕셔너리 생성
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            
            if self.auto_save:
                return self.save_config()
            return True
        except Exception as e:
            logger.error(f"설정 변경 실패: {e}")
            return False

    def update(self, updates: Dict) -> bool:
        """여러 설정을 한번에 업데이트합니다."""
        try:
            self.config = merge_dicts(self.config, updates, deep=True)
            if self.auto_save:
                return self.save_config()
            return True
        except Exception as e:
            logger.error(f"설정 업데이트 실패: {e}")
            return False

    def reset_to_default(self) -> bool:
        """설정을 기본값으로 리셋합니다."""
        try:
            self.config = self.default_config.copy()
            return self.save_config()
        except Exception as e:
            logger.error(f"설정 리셋 실패: {e}")
            return False

    def has_key(self, key: str) -> bool:
        """키가 존재하는지 확인합니다."""
        return self.get(key) is not None

    def delete_key(self, key: str) -> bool:
        """키를 삭제합니다."""
        try:
            keys = key.split('.')
            config = self.config
            
            for k in keys[:-1]:
                if k not in config:
                    return False
                config = config[k]
            
            if keys[-1] in config:
                del config[keys[-1]]
                if self.auto_save:
                    return self.save_config()
                return True
            return False
        except Exception as e:
            logger.error(f"키 삭제 실패: {e}")
            return False

# ==================== 데코레이터 ====================

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """재시도 데코레이터"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts >= max_attempts:
                        logger.error(f"함수 {func.__name__} 최대 재시도 횟수 초과: {e}")
                        raise e
                    
                    logger.warning(f"함수 {func.__name__} 재시도 {attempts}/{max_attempts}: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            return None
        return wrapper
    return decorator

def timing(func):
    """실행 시간 측정 데코레이터"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            logger.debug(f"함수 {func.__name__} 실행 시간: {execution_time:.4f}초")
            return result
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(f"함수 {func.__name__} 실행 실패 (소요시간: {execution_time:.4f}초): {e}")
            raise e
    return wrapper

def cache_result(expire_time: int = 300):
    """결과 캐싱 데코레이터"""
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = str(args) + str(sorted(kwargs.items()))
            current_time = time.time()
            
            # 캐시 확인
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                if current_time - cached_time < expire_time:
                    return cached_result
            
            # 함수 실행 및 캐시 저장
            result = func(*args, **kwargs)
            cache[cache_key] = (current_time, result)
            
            # 오래된 캐시 정리
            expired_keys = [k for k, (t, _) in cache.items() if current_time - t >= expire_time]
            for k in expired_keys:
                del cache[k]
            
            return result
        return wrapper
    return decorator

# ==================== 초기화 및 유틸리티 ====================

def get_system_info() -> Dict:
    """시스템 정보를 반환합니다."""
    import platform
    import psutil
    
    try:
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
        }
    except ImportError:
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count()
        }

def cleanup_resources() -> bool:
    """임시 리소스를 정리합니다."""
    try:
        # temp 디렉토리 비우기 등
        temp_path = Path("temp")
        if temp_path.exists():
            for file in temp_path.glob("*"):
                file.unlink()
        
        # 오래된 로그 정리 등 추가 가능
        log_path = Path("logs")
        if log_path.exists():
            # 예: 30일 지난 로그 삭제 로직
            pass
        
        logger.info("리소스 정리 완료")
        return True
    except Exception as e:
        logger.error(f"리소스 정리 실패: {e}")
        return False

def initialize_common_utils(config: Dict = None) -> bool:
    """공통 유틸리티 초기화 함수"""
    try:
        # 기본 디렉토리 생성
        ensure_directories()
        
        # 로깅 설정
        setup_logger("common_utils", "common_utils.log")
        
        # 리소스 정리
        cleanup_resources()
        
        logger.info("✅ 공통 유틸리티 초기화 완료")
        return True
    except Exception as e: 
        print(f"❌ 공통 유틸리티 초기화 실패: {e}")
        return False

# ==================== 모듈 수준 초기화 ====================

# 모듈 로드시 자동 초기화
if __name__ != "__main__":
    initialize_common_utils()

# 모듈이 직접 실행될 때의 테스트 코드
if __name__ == "__main__":
    print("=== Common Utils 테스트 ===")
    
    # 시간 포맷 테스트
    print(f"현재 시간: {now_str()}")
    print(f"오늘 날짜: {today_str()}")
    
    # 포맷팅 테스트
    print(f"금액 포맷: {format_money(1234567)}")
    print(f"큰 숫자 포맷: {format_large_number(1500000)}")
    
    # 날짜 파싱 테스트
    try:
        start, end = parse_date_range("08.01-08.08")
        print(f"날짜 파싱: {start} ~ {end}")
    except Exception as e:
        print(f"날짜 파싱 오류: {e}")
    
    # 진행률 바 테스트
    print(f"진행률 바: {create_progress_bar(75, 100, show_percentage=True)}")
    
    # 시스템 정보
    print(f"시스템 정보: {get_system_info()}")
    
    print("=== 테스트 완료 ===")