# statistics_system.py - 통계 명령어
from __future__ import annotations
import os
import json
import datetime
from calendar import monthrange
import logging
from collections import defaultdict
from typing import Dict, List, Any, Optional
import discord
from discord import app_commands
from discord.ext import commands

# 한국 시간대 설정 (UTC+9)
KST = datetime.timezone(datetime.timedelta(hours=9))

# ✅ 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ 게임 분류 정의 (클래스 내부나 상단에 추가)
SINGLE_GAMES = ["slot_machine", "yabawi_game", "blackjack", "dice_game", "rock_paper_scissors", "odd_even_game"]
MULTI_GAMES = ["blackjack", "dice_game", "rock_paper_scissors", "odd_even_game"]

# ✅ 데이터 파일 경로 및 설정
STATS_CONFIG = {
    "game_stats_file": 'data/game_statistics.json',
    "user_activity_file": 'data/user_activity.json',
    "daily_stats_file": 'data/daily_statistics.json',
    "backup_interval": 100,
    "max_daily_records": 365,
    "enable_real_time": True
}

# 데이터 디렉토리 생성
os.makedirs("data", exist_ok=True)

# ✅ 통계 관리자 클래스 (디버깅 기능 추가)
class StatisticsManager:
    # `db_cog` 인자를 추가하여 DatabaseCog 인스턴스를 받도록 변경
    def __init__(self, db_cog: Any): # Any 대신 DatabaseCog 타입을 사용하는 것이 더 좋습니다.
        self.db_cog = db_cog
        self.game_stats = self.load_game_stats()
        self.user_activity = self.load_user_activity()
        self.daily_stats = self.load_daily_stats()
        self.backup_counter = 0
        
        # ✅ 강제 타입 보장
        self._ensure_data_integrity()
        
        # 실시간 캐시
        self.real_time_cache = {
            "hourly_games": defaultdict(int),
            "active_users": set(),
            "session_start": datetime.datetime.now(KST)
        }
        
        # ✅ 디버깅 카운터 추가
        self.debug_stats = {
            "record_calls": 0,
            "successful_records": 0,
            "failed_records": 0,
            "last_record_time": None,
            "last_game_recorded": None
        }
        
        logger.info("✅ 통계 시스템 초기화 완료")
        print(f"🔍 통계 시스템 디버그 모드 활성화")

    def _ensure_data_integrity(self):
        """데이터 무결성 강제 보장"""
        # user_activity가 dict가 아니면 강제로 dict로 변환
        if not isinstance(self.user_activity, dict):
            logger.warning(f"user_activity 타입 오류: {type(self.user_activity)} -> dict로 강제 변환")
            self.user_activity = {}
        
        # game_stats가 dict가 아니면 강제로 초기화
        if not isinstance(self.game_stats, dict):
            logger.warning(f"game_stats 타입 오류: {type(self.game_stats)} -> 기본값으로 초기화")
            self.game_stats = self.create_empty_game_stats()
        
        # daily_stats가 dict가 아니면 강제로 dict로 변환
        if not isinstance(self.daily_stats, dict):
            logger.warning(f"daily_stats 타입 오류: {type(self.daily_stats)} -> dict로 강제 변환")
            self.daily_stats = {}

    def create_empty_game_stats(self) -> Dict:
        """빈 게임 통계 구조 생성"""
        return {
            "games": {
                "rock_paper_scissors": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "dice_game": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "odd_even": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "blackjack": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "slot_machine": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "yabawi": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0},
                "enhancement": {"attempts": 0, "success": 0, "total_spent": 0},
                "ladder_game": {"played": 0, "won": 0, "total_reward": 0},
                "horse_racing": {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0}
            },
            "total_games": 0,
            "total_users": 0,
            "created_date": datetime.datetime.now(KST).isoformat(),
            "last_updated": datetime.datetime.now(KST).isoformat()
        }

    def load_game_stats(self) -> Dict:
        """게임 통계 데이터 로드 (안전성 강화)"""
        try:
            if os.path.exists(STATS_CONFIG["game_stats_file"]):
                with open(STATS_CONFIG["game_stats_file"], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 타입 검증
                    if isinstance(data, dict):
                        print(f"📊 기존 게임 통계 로드됨: {len(data.get('games', {}))}개 게임")
                        return data
                    else:
                        logger.warning("game_stats 파일이 dict가 아닙니다. 기본값으로 초기화합니다.")
                        return self.create_empty_game_stats()
            else:
                print("📊 새로운 게임 통계 파일 생성")
                return self.create_empty_game_stats()
        except Exception as e:
            logger.error(f"게임 통계 로드 실패: {e}")
            return self.create_empty_game_stats()

    def load_user_activity(self) -> Dict:
        """사용자 활동 데이터 로드 (완전 안전성 강화)"""
        try:
            if os.path.exists(STATS_CONFIG["user_activity_file"]):
                with open(STATS_CONFIG["user_activity_file"], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # ✅ 강제 타입 검증 및 변환
                    if isinstance(data, dict):
                        print(f"👥 기존 사용자 활동 로드됨: {len(data)}명")
                        return data
                    elif isinstance(data, list):
                        logger.warning("user_activity가 list입니다. dict로 변환합니다.")
                        return {}
                    elif data is None:
                        logger.warning("user_activity가 None입니다. 빈 dict로 초기화합니다.")
                        return {}
                    else:
                        logger.warning(f"user_activity 타입 오류: {type(data)}. 빈 dict로 초기화합니다.")
                        return {}
            else:
                print("👥 새로운 사용자 활동 파일 생성")
                return {}
        except json.JSONDecodeError as e:
            logger.error(f"user_activity JSON 파싱 오류: {e}. 빈 dict로 초기화합니다.")
            return {}
        except Exception as e:
            logger.error(f"사용자 활동 로드 실패: {e}. 빈 dict로 초기화합니다.")
            return {}

    def load_daily_stats(self) -> Dict:
        """일일 통계 데이터 로드 (안전성 강화)"""
        try:
            if os.path.exists(STATS_CONFIG["daily_stats_file"]):
                with open(STATS_CONFIG["daily_stats_file"], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return self._cleanup_old_daily_stats(data)
                    else:
                        logger.warning("daily_stats가 dict가 아닙니다. 빈 dict로 초기화합니다.")
                        return {}
            else:
                return {}
        except Exception as e:
            logger.error(f"일일 통계 로드 실패: {e}")
            return {}

    def _cleanup_old_daily_stats(self, data: Dict) -> Dict:
        """오래된 일일 통계 정리"""
        try:
            if not isinstance(data, dict):
                return {}
                
            cutoff_date = datetime.date.today() - datetime.timedelta(days=STATS_CONFIG["max_daily_records"])
            cutoff_str = cutoff_date.isoformat()
            
            cleaned_data = {}
            for date_str, stats in data.items():
                if isinstance(date_str, str) and date_str >= cutoff_str:
                    cleaned_data[date_str] = stats
            
            return cleaned_data
        except Exception as e:
            logger.error(f"일일 통계 정리 오류: {e}")
            return {}

    def save_all_stats(self) -> bool:
        """모든 통계 데이터 저장 (완전 안전성 강화)"""
        try:
            # ✅ 저장 전 데이터 무결성 재확인
            self._ensure_data_integrity()
            
            # 게임 통계 저장
            if isinstance(self.game_stats, dict):
                self.game_stats["last_updated"] = datetime.datetime.now(KST).isoformat()
                with open(STATS_CONFIG["game_stats_file"], 'w', encoding='utf-8') as f:
                    json.dump(self.game_stats, f, indent=2, ensure_ascii=False)
                print(f"💾 게임 통계 저장됨: {self.game_stats.get('total_games', 0)}게임")
            else:
                logger.error("game_stats가 dict가 아닙니다. 저장을 건너뜁니다.")

            # 사용자 활동 저장 (강제 dict 보장)
            if isinstance(self.user_activity, dict):
                with open(STATS_CONFIG["user_activity_file"], 'w', encoding='utf-8') as f:
                    json.dump(self.user_activity, f, indent=2, ensure_ascii=False)
                print(f"👥 사용자 활동 저장됨: {len(self.user_activity)}명")
            else:
                logger.warning("user_activity가 dict가 아닙니다. 빈 dict로 저장합니다.")
                with open(STATS_CONFIG["user_activity_file"], 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2, ensure_ascii=False)
                self.user_activity = {}

            # 일일 통계 저장
            if isinstance(self.daily_stats, dict):
                with open(STATS_CONFIG["daily_stats_file"], 'w', encoding='utf-8') as f:
                    json.dump(self.daily_stats, f, indent=2, ensure_ascii=False)
            else:
                logger.warning("daily_stats가 dict가 아닙니다. 빈 dict로 저장합니다.")
                with open(STATS_CONFIG["daily_stats_file"], 'w', encoding='utf-8') as f:
                    json.dump({}, f, indent=2, ensure_ascii=False)
                self.daily_stats = {}

            return True
        except Exception as e:
            logger.error(f"통계 저장 실패: {e}")
            return False
        
    def record_game(self, user_id, user_name, game_name, bet, reward, is_win):
        """슬롯머신 등 외부 호출용 호환 메서드"""
        self.record_game_play(
            user_id=str(user_id),
            username=user_name,
            game_name="slot_machine", # 통계 시스템에 등록된 이름
            is_win=is_win,
            bet_amount=bet,
            payout=reward
        )
        print(f"[기록] {user_name}: {game_name} 결과 - 배팅: {bet}, 획득: {reward}, 승리: {is_win}")
    

    def record_game_play(self, user_id: str, username: str, game_name: str, is_win: bool, bet_amount: int = 0, payout: int = 0, is_multi: bool = False):
        """게임 플레이 기록 (안전성 강화 + 디버깅)"""
        try:
            # ✅ 디버깅 카운터 업데이트
            self.debug_stats["record_calls"] += 1
            self.debug_stats["last_record_time"] = datetime.datetime.now(KST).isoformat()
            self.debug_stats["last_game_recorded"] = game_name
            
            print(f"🎮 게임 기록 시도: {game_name} | 사용자: {username} | 승리: {is_win} | 배팅: {bet_amount} | 지급: {payout}")
            
            # ✅ 데이터 무결성 재확인
            self._ensure_data_integrity()
            
            # 게임 통계 업데이트
            if isinstance(self.game_stats, dict) and "games" in self.game_stats:
                if game_name not in self.game_stats["games"]:
                    # 신규 게임 초기화 (기존 필드 유지)
                    self.game_stats["games"][game_name] = {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0, "single_played": 0, "multi_played": 0}
                
                # 게임 통계 업데이트 로직 내부에 추가
                game_stats = self.game_stats["games"][game_name]

                # 모드별 횟수 기록 추가
                mode_key = "multi_played" if is_multi else "single_played"
                game_stats[mode_key] = game_stats.get(mode_key, 0) + 1

                # 전체 플레이 횟수 (기존 코드 유지)
                game_stats["played"] = game_stats.get("played", 0) + 1

                # ✅ 싱글/멀티 횟수 분리 기록
                if is_multi:
                    game_stats["multi_played"] = game_stats.get("multi_played", 0) + 1
                else:
                    game_stats["single_played"] = game_stats.get("single_played", 0) + 1

                # 플레이 모드 결정
                mode = "multi" if is_multi else "single"
        
                # 데이터 구조에 모드별 카운트 추가 (기존 구조 유지하며 확장)
                mode_key = f"{mode}_played"
                game_stats[mode_key] = game_stats.get(mode_key, 0) + 1
                
                # 강화 시스템 특별 처리
                if game_name == "enhancement":
                    game_stats["attempts"] = game_stats.get("attempts", 0) + 1
                    if is_win:
                        game_stats["success"] = game_stats.get("success", 0) + 1
                    game_stats["total_spent"] = game_stats.get("total_spent", 0) + bet_amount
                    print(f"🔧 강화 통계 업데이트: 시도 {game_stats['attempts']}, 성공 {game_stats['success']}")
                else:
                    if is_win:
                        game_stats["won"] = game_stats.get("won", 0) + 1
                    game_stats["total_bet"] = game_stats.get("total_bet", 0) + bet_amount
                    game_stats["total_payout"] = game_stats.get("total_payout", 0) + payout
                    print(f"🎲 {game_name} 통계 업데이트: 플레이 {game_stats['played']}, 승리 {game_stats['won']}")

            # 사용자 활동 통계 업데이트 (안전하게)
            if isinstance(self.user_activity, dict):
                if user_id not in self.user_activity:
                    self.user_activity[user_id] = {
                        "username": username,
                        "first_game": datetime.datetime.now(KST).isoformat(),
                        "last_game": datetime.datetime.now(KST).isoformat(),
                        "total_games": 0,
                        "total_won": 0,
                        "total_bet": 0,
                        "total_payout": 0,
                        "games_played": {}
                    }
                    print(f"👤 새 사용자 '{username}' 등록됨")
                
                user_stats = self.user_activity[user_id]
                user_stats["username"] = username  # 이름 업데이트
                user_stats["last_game"] = datetime.datetime.now(KST).isoformat()
                user_stats["total_games"] = user_stats.get("total_games", 0) + 1
                
                if is_win:
                    user_stats["total_won"] = user_stats.get("total_won", 0) + 1
                
                user_stats["total_bet"] = user_stats.get("total_bet", 0) + bet_amount
                user_stats["total_payout"] = user_stats.get("total_payout", 0) + payout
                
                # 게임별 통계
                if "games_played" not in user_stats:
                    user_stats["games_played"] = {}
                
                if game_name not in user_stats["games_played"]:
                    user_stats["games_played"][game_name] = {"played": 0, "won": 0, "total_bet": 0, "total_payout": 0}
                
                game_user_stats = user_stats["games_played"][game_name]
                game_user_stats["played"] = game_user_stats.get("played", 0) + 1
                if is_win:
                    game_user_stats["won"] = game_user_stats.get("won", 0) + 1
                game_user_stats["total_bet"] = game_user_stats.get("total_bet", 0) + bet_amount
                game_user_stats["total_payout"] = game_user_stats.get("total_payout", 0) + payout

            # 실시간 캐시 업데이트
            self.real_time_cache["active_users"].add(user_id)
            current_hour = datetime.datetime.now(KST).strftime("%Y-%m-%d-%H")
            self.real_time_cache["hourly_games"][current_hour] += 1

            # 자동 저장 (백업 카운터 기반)
            self.backup_counter += 1
            if self.backup_counter >= STATS_CONFIG["backup_interval"]:
                success = self.save_all_stats()
                self.backup_counter = 0
                print(f"💾 자동 백업 완료: {success}")

            # ✅ 성공 카운터 업데이트
            self.debug_stats["successful_records"] += 1
            print(f"✅ 게임 기록 성공 - 총 기록: {self.debug_stats['successful_records']}")

        except Exception as e:
            # ✅ 실패 카운터 업데이트
            self.debug_stats["failed_records"] += 1
            logger.error(f"게임 플레이 기록 오류: {e}")
            print(f"❌ 게임 기록 실패: {e}")

    def get_server_stats(self, guild_id: int) -> Dict: # guild_id 인자 추가
        """서버 전체 통계 반환 (완전 오류 수정 및 게임 통계 정확한 카운트)"""
        try:
            # ✅ 실행 전 데이터 무결성 확인
            self._ensure_data_integrity()
            
            # ✅ 게임 통계 정확한 계산
            total_games = 0
            total_wins = 0
            total_bets = 0
            total_payouts = 0
            
            if isinstance(self.game_stats, dict) and "games" in self.game_stats:
                games_data = self.game_stats["games"]
                for game_name, game_data in games_data.items():
                    if isinstance(game_data, dict):
                        # 강화 시스템은 attempts로 계산
                        if game_name == "enhancement":
                            total_games += game_data.get("attempts", 0)
                            total_wins += game_data.get("success", 0)
                            total_bets += game_data.get("total_spent", 0)
                        else:
                            total_games += game_data.get("played", 0)
                            total_wins += game_data.get("won", 0)
                            total_bets += game_data.get("total_bet", 0)
                            total_payouts += game_data.get("total_payout", 0)
            
            # 계산된 값으로 game_stats 업데이트
            if isinstance(self.game_stats, dict):
                self.game_stats["total_games"] = total_games
            
            # ✅ total_users 완전 안전 계산
            total_users = 0
            try:
                if isinstance(self.user_activity, dict):
                    total_users = len(self.user_activity)
                else:
                    logger.warning(f"user_activity 타입 오류: {type(self.user_activity)}. 0으로 설정합니다.")
                    total_users = 0
            except Exception as e:
                logger.error(f"total_users 계산 오류: {e}. 0으로 설정합니다.")
                total_users = 0
            
            # 실시간 통계
            real_time_stats = self._get_real_time_stats()
            
            # 경제 통계 (안전하게)
            economy_stats = {}
            # DatabaseCog를 통해 guild_db_manager 인스턴스 가져오기
            guild_db_manager = self.db_cog.get_manager(str(guild_id)) # guild_id를 문자열로 변환하여 전달
            DATABASE_AVAILABLE = guild_db_manager is not None # db_manager 인스턴스 존재 여부로 판단
            
            try:
                economy_stats = {
                    "total_points_consumed": total_bets,
                    "total_points_distributed": total_payouts,
                    "house_edge": self._calculate_house_edge(),
                    "total_wins": total_wins,
                    "win_rate": round((total_wins / max(total_games, 1)) * 100, 2)
                }
                
                # 데이터베이스 통계 추가 (기존 메서드 사용)
                if DATABASE_AVAILABLE:
                    try:
                        # 현금 리더보드를 통해 이 현금 계산
                        leaderboard = guild_db_manager.get_cash_leaderboard(1000)  # 상위 1000명
                        if leaderboard:
                            db_total_cash = sum(user.get('cash', 0) for user in leaderboard)
                            economy_stats["db_total_cash"] = db_total_cash
                            economy_stats["db_active_users"] = len(leaderboard)
                        
                        # 데이터베이스 통계
                        db_stats = guild_db_manager.get_database_stats()
                        if db_stats and 'users' in db_stats:
                            economy_stats["db_total_users"] = db_stats['users']
                    except Exception as db_e:
                        logger.warning(f"데이터베이스 경제 통계 조회 실패: {db_e}")
                        
            except Exception as e:
                logger.error(f"경제 통계 계산 오류: {e}")
                economy_stats = {
                    "total_points_consumed": 0,
                    "total_points_distributed": 0,
                    "house_edge": 0.0,
                    "error": str(e)
                }

            # ✅ 디버깅 정보 추가
            debug_info = {
                "record_calls": self.debug_stats["record_calls"],
                "successful_records": self.debug_stats["successful_records"],
                "failed_records": self.debug_stats["failed_records"],
                "last_record_time": self.debug_stats["last_record_time"],
                "last_game_recorded": self.debug_stats["last_game_recorded"]
            }

            print(f"📊 통계 조회 결과: 총 게임 {total_games}, 사용자 {total_users}, 기록 호출 {self.debug_stats['record_calls']}")

            return {
                "total_games": total_games,
                "total_users": total_users,
                "games": self.game_stats.get('games', {}),
                "economy": economy_stats,
                "real_time": real_time_stats,
                "debug_info": debug_info,
                "server_info": {
                    "bot_version": "v6",
                    "last_updated": self.game_stats.get("last_updated", "Unknown"),
                    "created_date": self.game_stats.get("created_date", "Unknown")
                }
            }
        except Exception as e:
            logger.error(f"서버 통계 조회 오류: {e}")
            return {
                "error": str(e),
                "total_games": 0,
                "total_users": 0,
                "games": {},
                "economy": {},
                "real_time": {"error": "통계 계산 오류"},
                "server_info": {"bot_version": "v6", "status": "error"}
            }

    def _get_real_time_stats(self) -> Dict:
        """실시간 통계 계산"""
        try:
            now = datetime.datetime.now(KST)
            session_duration = now - self.real_time_cache["session_start"]
            
            # 시간 단위로 변환
            hours = session_duration.total_seconds() / 3600
            
            return {
                "session_uptime": str(session_duration).split('.')[0],  # 마이크로초 제거
                "active_users_count": len(self.real_time_cache["active_users"]),
                "hourly_games": dict(self.real_time_cache["hourly_games"]),
                "games_per_hour": round(sum(self.real_time_cache["hourly_games"].values()) / max(hours, 0.1), 2)
            }
        except Exception as e:
            logger.error(f"실시간 통계 계산 오류: {e}")
            return {"error": str(e)}

    def _calculate_house_edge(self) -> float:
        """하우스 엣지 계산"""
        try:
            total_bet = sum(game.get('total_bet', 0) for game in self.game_stats.get('games', {}).values())
            total_payout = sum(game.get('total_payout', 0) for game in self.game_stats.get('games', {}).values())
            
            if total_bet > 0:
                return round(((total_bet - total_payout) / total_bet) * 100, 2)
            return 0.0
        except Exception as e:
            logger.error(f"하우스 엣지 계산 오류: {e}")
            return 0.0

# ✅ 호환성 메서드 (기존 코드와의 호환성 유지)
    def record_game_activity(self, user_id: str, username: str, game_name: str, **kwargs):
        """게임 활동 기록 (향상된 호환성 + 디버깅)"""
        try:
            print(f"🔄 record_game_activity 호출됨: {game_name} | {username} | {kwargs}")
            
            # 기본 매개변수 추출
            is_win = kwargs.get('is_win', False)
            bet_amount = kwargs.get('bet_amount', kwargs.get('bet', 0))  # 호환성을 위해 'bet'도 체크
            payout = kwargs.get('payout', 0)
            attempts = kwargs.get('attempts', 1)
            total_spent = kwargs.get('total_spent', 0)
            
            # 강화 시스템 특별 처리
            if game_name == "enhancement":
                # 강화는 bet_amount와 payout 대신 total_spent 사용
                self.record_game_play(user_id, username, game_name, is_win, total_spent, 0)
            else:
                # 일반 게임
                self.record_game_play(user_id, username, game_name, is_win, bet_amount, payout)
                
        except Exception as e:
            logger.error(f"게임 활동 기록 오류: {e}")
            print(f"❌ record_game_activity 실패: {e}")

# ✅ 게임 한국어 이름 매핑
    def get_game_korean_name(self, game_name: str) -> str:
        """게임 영문명을 한국어로 변환"""
        korean_names = {
            "rock_paper_scissors": "가위바위보",
            "dice_game": "주사위 게임",
            "odd_even": "홀짝 게임",
            "blackjack": "블랙잭",
            "slot_machine": "슬롯머신",
            "yabawi": "야바위",
            "enhancement": "강화 시스템",
            "ladder_game": "사다리타기",
            "horse_racing": "경마"
        }
        return korean_names.get(game_name, game_name)

    def get_game_rankings(self, game_name: str, limit: int = 10) -> List[Dict]:
        """특정 게임의 사용자 순위 반환"""
        try:
            self._ensure_data_integrity()
            
            if not isinstance(self.user_activity, dict):
                return []
                
            rankings = []
            for user_id, user_stats in self.user_activity.items():
                if isinstance(user_stats, dict) and "games_played" in user_stats:
                    game_stats = user_stats["games_played"].get(game_name, {})
                    if game_stats and game_stats.get("played", 0) > 0:
                        win_rate = round((game_stats.get("won", 0) / game_stats.get("played", 1)) * 100, 1)
                        rankings.append({
                            "user_id": user_id,
                            "username": user_stats.get("username", "Unknown"),
                            "played": game_stats.get("played", 0),
                            "won": game_stats.get("won", 0),
                            "win_rate": win_rate,
                            "total_bet": game_stats.get("total_bet", 0),
                            "total_payout": game_stats.get("total_payout", 0),
                            "net_gain": game_stats.get("total_payout", 0) - game_stats.get("total_bet", 0)
                        })
            
            # 플레이 횟수로 정렬
            rankings.sort(key=lambda x: x["played"], reverse=True)
            return rankings[:limit]
            
        except Exception as e:
            logger.error(f"게임 순위 조회 오류: {e}")
            return []

    # ✅ 디버깅 메서드 추가
    def get_debug_info(self) -> Dict:
        """디버깅 정보 반환"""
        return {
            "debug_stats": self.debug_stats,
            "file_exists": {
                "game_stats": os.path.exists(STATS_CONFIG["game_stats_file"]),
                "user_activity": os.path.exists(STATS_CONFIG["user_activity_file"]),
                "daily_stats": os.path.exists(STATS_CONFIG["daily_stats_file"])
            },
            "data_types": {
                "game_stats": type(self.game_stats).__name__,
                "user_activity": type(self.user_activity).__name__,
                "daily_stats": type(self.daily_stats).__name__
            },
            "data_sizes": {
                "game_stats_games": len(self.game_stats.get('games', {})),
                "user_activity_users": len(self.user_activity) if isinstance(self.user_activity, dict) else 0,
                "daily_stats_days": len(self.daily_stats) if isinstance(self.daily_stats, dict) else 0
            }
        }

# ✅ 전역 통계 관리자 인스턴스 (이제 StatisticsCog 내에서 초기화됩니다)
# stats_manager = StatisticsManager()

# ===== Discord Cog =====

class StatisticsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # DatabaseCog를 bot에서 가져오기
        self.db_cog = self.bot.get_cog("DatabaseManager")
        
        if not self.db_cog:
            logger.error("❌ DatabaseManager Cog를 찾을 수 없습니다. 통계 기능이 제한됩니다.")
            self.stats = None # 통계 관리자 초기화 실패
        else:
            self.stats = StatisticsManager(self.db_cog) # DatabaseCog 인스턴스를 전달

    @app_commands.command(name="통계", description="[관리자 전용] 서버 전체 게임 통계를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def server_statistics(self, interaction: discord.Interaction):
        if not self.stats:
            return await interaction.response.send_message("❌ 시스템 오류: 통계 시스템이 로드되지 않았습니다.", ephemeral=True)
            
        await interaction.response.defer()
        
        try:
            # StatisticsManager에서 데이터를 가져옴
            games = self.stats.game_stats.get("games", {})
            server_stats = self.stats.get_server_stats(interaction.guild_id)
            now = datetime.datetime.now(KST)
            
            # ✅ 통계 기간 계산
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_day = monthrange(now.year, now.month)[1]
            period_str = f"한국기준 {now.month}월 1일 ~ {now.month}월 {last_day}일"

            embed = discord.Embed(
                title="📊 서버 게임 종합 통계",
                description=f"📅 **통계 기간**: {period_str}",
                color=discord.Color.blue()
            )

            # 1️⃣ 기본 정보
            embed.add_field(
                name="📌 기본 정보",
                value=f"총 게임 수: **{server_stats['total_games']:,}회**\n"
                      f"총 사용자 수: **{server_stats['total_users']:,}명**",
                inline=False
            )

            # 2️⃣ 경제 통계
            eco = server_stats.get('economy', {})
            # ❌ Richardson 문자열 제거 (올바른 숫자 포맷팅 적용)
            embed.add_field(
                name="💰 경제 통계",
                value=f"총 배팅액: **{eco.get('total_points_consumed', 0):,}원**\n"
                      f"총 지급액: **{eco.get('total_points_distributed', 0):,}원**\n"
                      f"전체 승률: **{eco.get('win_rate', 0):.1f}%**",
                inline=False
            )

            # 3️⃣ 싱글 게임 TOP 5 (데이터 가공 및 필드 추가)
            single_list = []
            for g_name in SINGLE_GAMES:
                if g_name in games:
                    data = games[g_name]
                    count = data.get('single_played', data.get('played', 0))
                    if count > 0:
                        single_list.append((self.stats.get_game_korean_name(g_name), count))

            if single_list:
                single_list.sort(key=lambda x: x[1], reverse=True) # 횟수 순 정렬
                single_text = "\n".join([f"• {name}: **{count:,}회**" for name, count in single_list[:5]])
                embed.add_field(name="🎮 인기 싱글 게임 (TOP 5)", value=single_text, inline=True)

            # 4️⃣ 멀티 게임 TOP 5 (데이터 가공 및 필드 추가)
            multi_list = []
            for g_name in MULTI_GAMES:
                if g_name in games:
                    data = games[g_name]
                    count = data.get('multi_played', 0)
                    if count > 0:
                        multi_list.append((self.stats.get_game_korean_name(g_name), count))

            if multi_list:
                multi_list.sort(key=lambda x: x[1], reverse=True) # 횟수 순 정렬
                multi_text = "\n".join([f"• {name}: **{count:,}회**" for name, count in multi_list[:5]])
                embed.add_field(name="👥 인기 멀티 게임 (TOP 5)", value=multi_text, inline=True)
            elif not single_list:
                embed.add_field(name="ℹ️ 안내", value="아직 기록된 게임 데이터가 없습니다.", inline=False)

            # 5️⃣ 하단 정보
            embed.set_footer(text=f"기준: 한국 표준시 | 마지막 업데이트: {now.strftime('%Y-%m-%d %H:%M')}")
            
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"통계 출력 오류: {e}")
            # traceback을 출력하여 상세 에러 확인 (디버깅용)
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ 통계 생성 중 오류가 발생했습니다: {e}")

    # ✅ 디버깅 명령어 추가
    @app_commands.command(name="통계디버그", description="[관리자 전용] 통계 시스템 디버깅 정보를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def statistics_debug(self, interaction: discord.Interaction):
        if not self.stats:
            return await interaction.response.send_message("❌ 통계 시스템이 초기화되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        try:
            debug_info = self.stats.get_debug_info()
            
            embed = discord.Embed(
                title="🔍 통계 시스템 디버그 정보",
                description="통계 시스템의 상태와 디버깅 정보입니다.",
                color=discord.Color.orange()
            )
            
            # 디버그 통계
            debug_stats = debug_info.get('debug_stats', {})
            embed.add_field(
                name="📊 기록 통계",
                value=f"총 호출: {debug_stats.get('record_calls', 0)}회\n" +
                      f"성공: {debug_stats.get('successful_records', 0)}회\n" +
                      f"실패: {debug_stats.get('failed_records', 0)}회\n" +
                      f"마지막 기록: {debug_stats.get('last_record_time', 'None')}\n" +
                      f"마지막 게임: {debug_stats.get('last_game_recorded', 'None')}",
                inline=False
            )
            
            # 파일 존재 여부
            file_exists = debug_info.get('file_exists', {})
            embed.add_field(
                name="📁 파일 상태",
                value=f"게임 통계: {'✅' if file_exists.get('game_stats') else '❌'}\n" +
                      f"사용자 활동: {'✅' if file_exists.get('user_activity') else '❌'}\n" +
                      f"일일 통계: {'✅' if file_exists.get('daily_stats') else '❌'}",
                inline=True
            )
            
            # 데이터 크기
            data_sizes = debug_info.get('data_sizes', {})
            embed.add_field(
                name="📏 데이터 크기",
                value=f"게임 종류: {data_sizes.get('game_stats_games', 0)}개\n" +
                      f"사용자 수: {data_sizes.get('user_activity_users', 0)}명\n" +
                      f"일일 기록: {data_sizes.get('daily_stats_days', 0)}일",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 디버깅 정보 조회 실패: {e}")

# setup 함수
async def setup(bot):
    await bot.add_cog(StatisticsCog(bot))