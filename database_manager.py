# database_manager.py
from __future__ import annotations
import sqlite3
import os
import logging
import threading
from typing import Dict, List, Optional, Literal, Union
import math
from datetime import datetime, date, timedelta
from pathlib import Path

# ✅ 기본 리더보드 설정 (다른 모듈에서 참조 가능)
DEFAULT_LEADERBOARD_SETTINGS = {
    "attendance_cash": 3000,
    "attendance_xp": 100,
    "streak_cash_per_day": 100,      # 연속 출석일당 추가 현금
    "streak_xp_per_day": 10,         # 연속 출석일당 추가 XP
    "max_streak_bonus_days": 30,     # 연속 보너스가 적용되는 최대 일수
    "weekly_cash_bonus": 1000,
    "weekly_xp_bonus": 500,
    "monthly_cash_bonus": 10000,
    "monthly_xp_bonus": 5000,
    "exchange_fee_percent": 5,
    "daily_exchange_limit": 10
}

# ✅ 로깅 설정
def setup_logging():
    """데이터베이스 매니저 전용 로깅 설정"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger("database_manager")
    logger.setLevel(logging.INFO)
    
    # 중복 핸들러 방지
    if not logger.handlers:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        logger.setLevel(logging.ERROR)
        # 파일 핸들러
        file_handler = logging.FileHandler(log_dir / 'database.log', encoding='utf-8')
        logger.addHandler(file_handler)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logging()

class DatabaseManager:
    def __init__(self, guild_id: str):
        self.guild_id = guild_id
        self.db_path = self._get_db_path(guild_id)
        self.thread_local = threading.local()
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 데이터베이스 초기화 및 테이블 생성
        with self.get_connection() as conn:
            conn.execute('PRAGMA foreign_keys = ON')
        
        self._create_tables()
        logger.info(f"✅ 데이터베이스 매니저 초기화 완료: {self.db_path}")

    def _get_db_path(self, guild_id: str) -> str:
        """길드 ID에 따라 데이터베이스 파일 경로를 결정합니다."""
        guild_db_dir = Path("data/guilds")
        guild_db_dir.mkdir(parents=True, exist_ok=True)
        return str(guild_db_dir / f"{guild_id}.db")

    def get_connection(self) -> sqlite3.Connection:
        """
        ✅ 스레드 안전성을 위한 스레드-로컬 데이터베이스 연결을 가져옵니다.
        연결이 없으면 새로 생성하고, 있으면 기존 연결을 반환합니다.
        """
        if not hasattr(self.thread_local, 'conn') or self.thread_local.conn is None:
            try:
                self.thread_local.conn = sqlite3.connect(self.db_path)
                self.thread_local.conn.row_factory = sqlite3.Row
                logger.debug(f"새로운 DB 연결 생성: {self.db_path} (스레드: {threading.get_ident()})")
            except sqlite3.Error as e:
                logger.error(f"❌ DB 연결 실패: {e}", exc_info=True)
                raise  # 연결 실패 시 예외를 다시 발생시켜 호출자에게 알림
        return self.thread_local.conn
    
    def create_table(self, table_name: str, schema: str):
        """
        ✅ 새로운 기능: 외부에서 테이블을 생성할 수 있는 범용 함수
        """
        try:
            with self.get_connection() as conn:
                conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})")
                conn.commit()
                logger.info(f"✅ '{table_name}' 테이블 생성 또는 확인 완료.")
                return True
        except sqlite3.Error as e:
            logger.error(f"❌ 테이블 '{table_name}' 생성 중 오류 발생: {e}")
            return False

    def _create_tables(self):
        """테이블 생성 및 스키마 마이그레이션"""
        # 기존의 테이블 생성 로직을 새로운 create_table 함수로 대체
        # users 테이블에 guild_id 추가 및 복합 PRIMARY KEY 설정
        self.create_table(
            "users",
            """
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            username TEXT DEFAULT '',
            display_name TEXT DEFAULT '',
            cash INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, guild_id)
            """
        )
        self.create_table(
            "attendance",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            attendance_date DATE NOT NULL,
            streak_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, attendance_date)
            """
        )
        self.create_table(
            "enhancement",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            level INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
            """
        )
        self.create_table(
            "point_transactions",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            balance_after INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        self.create_table(
            "user_xp",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            guild_id TEXT NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, guild_id)
            """
        )
        self.create_table(
            "leaderboard_settings",
            """
            guild_id TEXT NOT NULL PRIMARY KEY,
            attendance_cash INTEGER DEFAULT 3000,
            attendance_xp INTEGER DEFAULT 100,
            streak_cash_per_day INTEGER DEFAULT 100,
            streak_xp_per_day INTEGER DEFAULT 10,
            max_streak_bonus_days INTEGER DEFAULT 30,
            weekly_cash_bonus INTEGER DEFAULT 1000,
            weekly_xp_bonus INTEGER DEFAULT 500,
            monthly_cash_bonus INTEGER DEFAULT 10000,
            monthly_xp_bonus INTEGER DEFAULT 5000,
            gift_fee_rate REAL DEFAULT 0.1,
            exchange_fee_percent INTEGER DEFAULT 5,
            daily_exchange_limit INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        self.create_table(
            "voice_time",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            total_time INTEGER DEFAULT 0,
            last_join TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id)
            """
        )
        self.create_table(
            "voice_time_log",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            join_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            leave_time TIMESTAMP,
            duration_minutes INTEGER DEFAULT 0,
            is_speaking INTEGER DEFAULT 0
            """
        )
        self.create_table(
            "levelup_channels",
            """
            channel_id TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                # 스키마 마이그레이션: users 테이블에 display_name 컬럼이 없으면 추가
                cursor.execute("PRAGMA table_info(users)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # 기존 users 테이블에 guild_id가 없는 경우 마이그레이션 로직 (복잡하므로 일단 생략)
                # 이 변경은 기존 데이터베이스와의 호환성을 깨뜨릴 수 있습니다.
                # 실제 배포 시에는 마이그레이션 스크립트가 필요합니다.
                
                if 'display_name' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
                    logger.info("✅ users 테이블에 'display_name' 컬럼 추가 완료.")

                # 스키마 마이그레이션: users 테이블에 cash 컬럼이 없으면 추가
                if 'cash' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN cash INTEGER DEFAULT 0")
                    logger.info("✅ users 테이블에 'cash' 컬럼 추가 완료.")

                # user_xp 테이블에 guild_id 컬럼이 없으면 추가
                cursor.execute("PRAGMA table_info(user_xp)")
                user_xp_columns = [col[1] for col in cursor.fetchall()]
                if 'guild_id' not in user_xp_columns:
                    cursor.execute("ALTER TABLE user_xp ADD COLUMN guild_id TEXT")
                    logger.info("✅ user_xp 테이블에 'guild_id' 컬럼 추가 완료.")
                    # 기존 레코드에 guild_id 채워넣기 (현재 DatabaseManager 인스턴스의 guild_id 사용)
                    cursor.execute("UPDATE user_xp SET guild_id = ? WHERE guild_id IS NULL", (self.guild_id,))
                    logger.info(f"✅ 기존 user_xp 레코드에 guild_id '{self.guild_id}' 채워넣기 완료.")
                    # UNIQUE 제약 조건 다시 생성 (기존 데이터가 없거나 충돌이 없을 경우)
                    # 이 부분은 기존 데이터에 따라 실패할 수 있으므로 주의
                    try:
                        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_xp_unique ON user_xp (user_id, guild_id)")
                        logger.info("✅ user_xp 테이블에 UNIQUE(user_id, guild_id) 제약 조건 추가 완료.")
                    except sqlite3.IntegrityError:
                        logger.warning("⚠️ user_xp 테이블에 기존 중복 데이터가 있어 UNIQUE 제약 조건 추가 실패. 수동 확인 필요.")
                
                conn.commit()
                logger.info("✅ 모든 테이블 생성 및 스키마 검증 완료.")
            except sqlite3.Error as e:
                logger.error(f"❌ 테이블 생성/마이그레이션 중 심각한 오류 발생: {e}")
                # 오류 발생 시 롤백
                conn.rollback()
    def get_or_create_user(self, user_id: str, username: str) -> bool:
            """
            사용자를 조회하고, 없으면 생성합니다.
            성공적으로 조회 또는 생성되면 True를 반환합니다.
            """
            if not self.guild_id:
                logger.error("❌ get_or_create_user: guild_id가 설정되지 않았습니다.")
                return False

            try:
                # 사용자 조회
                user_data = self.get_user(user_id)
                if user_data:
                    return True # 사용자가 이미 존재하면 True 반환

                # 사용자 생성 (기본값으로)
                success = self.create_user(user_id, username)
                if success:
                    logger.info(f"사용자 {username} ({user_id})를 데이터베이스에 등록했습니다.")
                    return True
                else:
                    logger.error(f"사용자 {username} ({user_id}) 등록에 실패했습니다.")
                    return False
            except Exception as e:
                logger.error(f"get_or_create_user 실행 중 오류 발생: {e}")
                return False
            
    
            
    def get_connection(self):
        """데이터베이스 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str, params: tuple = (), fetch_type: Literal['one', 'all', 'none'] = 'none') -> Optional[Union[sqlite3.Row, List[sqlite3.Row]]]:
        """쿼리를 실행하고 결과를 반환 (자동 커밋 포함)"""
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
            
                # INSERT, UPDATE, DELETE 쿼리는 변경사항을 커밋
                if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()
            
                if fetch_type == 'one':
                    return cursor.fetchone()
                elif fetch_type == 'all':
                    return cursor.fetchall()
                else:
                    return None
        except sqlite3.Error as e:
            logger.error(f"❌ DB 쿼리 오류: {e} - 쿼리: {query}", exc_info=True)
            return None
    
    # ==================== 사용자 관리 ====================
    def create_user(self, user_id: str, username: str = '', display_name: str = '', initial_cash: int = 0):
        if not self.guild_id:
            logger.error("❌ create_user: guild_id가 설정되지 않았습니다.")
            return False
        try:
            self.execute_query('''
            INSERT INTO users (user_id, guild_id, username, display_name, cash)
            VALUES (?, ?, ?, ?, ?)
            ''', (user_id, self.guild_id, username, display_name, initial_cash))
            # 예외가 없으면 성공
            logger.info(f"[DB] 사용자 생성 성공: {user_id} - {display_name} ({initial_cash}원) (Guild: {self.guild_id})")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"[DB] 이미 존재하는 사용자: {user_id} (Guild: {self.guild_id})")
            return False
        except Exception as e:
            logger.error(f"[DB] 사용자 생성 중 오류: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
        """사용자 정보 조회"""
        if not self.guild_id:
            logger.error("❌ get_user: guild_id가 설정되지 않았습니다.")
            return None
        result = self.execute_query('SELECT * FROM users WHERE user_id = ? AND guild_id = ?', (user_id, self.guild_id), 'one')
        return dict(result) if result else None

    def update_user_cash(self, user_id: str, new_cash: int):
        """사용자 현금 업데이트"""
        if not self.guild_id:
            logger.error("❌ update_user_cash: guild_id가 설정되지 않았습니다.")
            return None
        return self.execute_query('''
        UPDATE users
        SET cash = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND guild_id = ?
        ''', (new_cash, user_id, self.guild_id))
    
    def add_user_cash(self, user_id: str, amount: int):
        """사용자에게 현금 추가"""
        if not self.guild_id:
            logger.error("❌ add_user_cash: guild_id가 설정되지 않았습니다.")
            return None
        current_cash = self.get_user_cash(user_id)
        if current_cash is None:
            # 사용자가 없으면 생성하고 현금 추가
            self.create_user(user_id, initial_cash=amount)
            return amount
        new_cash = current_cash + amount
        self.update_user_cash(user_id, new_cash)
        return new_cash

    def get_user_cash(self, user_id: str) -> Optional[int]:
        """사용자 현금 조회"""
        if not self.guild_id:
            logger.error("❌ get_user_cash: guild_id가 설정되지 않았습니다.")
            return None
        user = self.get_user(user_id)
        return user['cash'] if user else None
    
    def get_all_users(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """모든 사용자 조회"""
        if not self.guild_id:
            logger.error("❌ get_all_users: guild_id가 설정되지 않았습니다.")
            return []
        query = 'SELECT * FROM users WHERE guild_id = ? ORDER BY created_at DESC'
        params = [self.guild_id]
        if limit:
            query += f' LIMIT ? OFFSET ?'
            params.extend([limit, offset])
        results = self.execute_query(query, tuple(params), 'all')
        return [dict(row) for row in results] if results else []

    def get_user_count(self) -> int:
        """총 사용자 수"""
        if not self.guild_id:
            logger.error("❌ get_user_count: guild_id가 설정되지 않았습니다.")
            return 0
        result = self.execute_query('SELECT COUNT(*) FROM users WHERE guild_id = ?', (self.guild_id,), 'one')
        return result[0] if result else 0
    
    def delete_user(self, user_id: str) -> Dict[str, int]:
        """특정 사용자의 모든 데이터 삭제"""
        if not self.guild_id:
            logger.error("❌ delete_user: guild_id가 설정되지 않았습니다.")
            return {}
        deleted_counts = {}
        with self.get_connection() as conn:
            # users 테이블은 guild_id와 user_id로 삭제
            deleted_counts['users'] = self._delete_from_table(conn, 'users', user_id, self.guild_id)
            # 나머지 테이블은 user_id로 삭제 (현재 DB가 이미 길드별로 분리되어 있으므로 guild_id는 필요 없음)
            for table in ['user_xp', 'attendance', 'enhancement', 'point_transactions', 'voice_time', 'voice_time_log', 'levelup_channels']:
                deleted_counts[table] = self._delete_from_table(conn, table, user_id)
        return deleted_counts

    def _delete_from_table(self, conn, table_name, user_id, guild_id: Optional[str] = None):
        """특정 테이블에서 사용자 데이터 삭제"""
        cursor = conn.cursor()
        if table_name == 'users' and guild_id:
            cursor.execute(f'DELETE FROM {table_name} WHERE user_id = ? AND guild_id = ?', (user_id, guild_id))
        else:
            cursor.execute(f'DELETE FROM {table_name} WHERE user_id = ?', (user_id,))
        count = cursor.rowcount
        conn.commit()
        return count
    
    def get_user_ranking(self, user_id: str) -> Optional[int]:
        """사용자의 현금 순위 조회"""
        if not self.guild_id:
            logger.error("❌ get_user_ranking: guild_id가 설정되지 않았습니다.")
            return None
        query = """
        SELECT ranking FROM (
            SELECT user_id, RANK() OVER (ORDER BY cash DESC) AS ranking
            FROM users
            WHERE guild_id = ?
        ) WHERE user_id = ?
        """
        result = self.execute_query(query, (self.guild_id, user_id), 'one')
        return result['ranking'] if result else None
    
    # ==================== XP 시스템 ====================
    def ensure_user_xp_exists(self, user_id: str):
        """사용자 XP 레코드가 없으면 생성"""
        if not self.guild_id:
            logger.error("❌ ensure_user_xp_exists: guild_id가 설정되지 않았습니다.")
            return None
        return self.execute_query('''
            INSERT OR IGNORE INTO user_xp (user_id, xp, level)
            VALUES (?, 0, 1)
        ''', (user_id,))
    
    def get_user_xp(self, user_id: str) -> Dict:
        """특정 사용자의 XP 데이터를 가져오는 함수 (딕셔너리 반환)"""
        if not self.guild_id:
            logger.error("❌ get_user_xp: guild_id가 설정되지 않았습니다.")
            return {'xp': 0, 'level': 1}
        try:
            result = self.execute_query(
                "SELECT xp, level FROM user_xp WHERE user_id = ?",
                (user_id,), 
                'one'
            )
            return dict(result) if result else {'xp': 0, 'level': 1}
        except Exception as e:
            logger.error(f"❌ DB 오류: XP 조회 실패 - {e}")
            return {'xp': 0, 'level': 1}
    
    def add_user_xp(self, user_id: str, xp_gain: int):
        """사용자에게 XP 추가"""
        if not self.guild_id:
            logger.error("❌ add_user_xp: guild_id가 설정되지 않았습니다.")
            return None
    
        # 쿼리에서 user_id, guild_id를 모두 사용하도록 수정
        return self.execute_query(
            "INSERT INTO user_xp (user_id, guild_id, xp, level) VALUES (?, ?, ?, 1) "
           "ON CONFLICT(user_id, guild_id) DO UPDATE SET xp = xp + ?, updated_at = CURRENT_TIMESTAMP",
            (user_id, self.guild_id, xp_gain, xp_gain), 'none'
        )

    def calculate_level_from_xp(self, xp: int) -> int:
        """XP로부터 레벨 계산"""
        if xp < 0:
            return 1
        return max(1, int(math.sqrt(xp / 100)) + 1)
    
    def calculate_xp_for_level(self, level: int) -> int:
        """레벨에 필요한 XP 계산"""
        if level <= 1:
            return 0
        return (level - 1) ** 2 * 100
    
    def get_xp_leaderboard(self, limit: int = 10) -> List[Dict]:
        """XP 리더보드 조회"""
        if not self.guild_id:
            logger.error("❌ get_xp_leaderboard: guild_id가 설정되지 않았습니다.")
            return []
        results = self.execute_query('''
            SELECT ux.*, u.username, u.display_name 
            FROM user_xp ux
            LEFT JOIN users u ON ux.user_id = u.user_id AND u.guild_id = ?
            ORDER BY ux.xp DESC
            LIMIT ?
        ''', (self.guild_id, limit), 'all')
        
        return [dict(row) for row in results] if results else []
    

    # ==================== 보이스 시스템 ====================
    def add_user_voice_time(self, user_id: str, minutes_to_add: int):
        """사용자의 총 통화 시간을 업데이트하거나 생성합니다."""
        if not self.guild_id:
            logger.error("❌ add_user_voice_time: guild_id가 설정되지 않았습니다.")
            return None
        return self.execute_query(
            "INSERT INTO voice_time (user_id, total_time) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET total_time = total_time + ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id = ?",
            (user_id, minutes_to_add, minutes_to_add, user_id), 'none'
        )
    
    def add_voice_activity(self, user_id: str, duration: int):
        """음성 활동 로그를 추가하고, voice_time 테이블을 업데이트합니다."""
        if not self.guild_id:
            logger.error("❌ add_voice_activity: guild_id가 설정되지 않았습니다.")
            return False
        try:
            with self.get_connection() as conn:
                # voice_time_log에 상세 기록 추가
                conn.execute('''
                    INSERT INTO voice_time_log (user_id, duration_minutes)
                    VALUES (?, ?)
                ''', (user_id, duration))

                # voice_time에 총 시간 업데이트
                conn.execute('''
                    INSERT INTO voice_time (user_id, total_time)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                    total_time = total_time + excluded.total_time,
                    updated_at = CURRENT_TIMESTAMP
                ''', (user_id, duration))
                
                conn.commit()
                logger.info(f"✅ 음성 활동 기록 성공: user_id={user_id}, duration={duration}분 (Guild: {self.guild_id})")
                return True
        except sqlite3.Error as e:
            logger.error(f"❌ 음성 활동 기록 중 오류 발생: {e}", exc_info=True)
            return False

    # ==================== 출석 시스템 ====================
    def get_attendance_stats(self, user_id: str) -> Optional[Dict]:
        """
        사용자의 총 출석 일수 및 연속 출석 일수 조회
        """
        if not self.guild_id:
            logger.error("❌ get_attendance_stats: guild_id가 설정되지 않았습니다.")
            return None
        query = "SELECT COUNT(*) as total_days FROM attendance WHERE user_id = ?"
        total_days = self.execute_query(query, (user_id,), 'one')

        streak_query = """
        SELECT COUNT(*) as streak_days
        FROM (
            SELECT
                attendance_date,
                julianday(attendance_date) - ROW_NUMBER() OVER(ORDER BY attendance_date) as grp
            FROM attendance
            WHERE user_id = ?
        )
        GROUP BY grp
        ORDER BY MAX(attendance_date) DESC
        LIMIT 1
        """
        streak_days = self.execute_query(streak_query, (user_id,), 'one')

        if not total_days or not streak_days:
            return None
        
        return {
            'total_days': total_days['total_days'],
            'streak_days': streak_days['streak_days']
        }
    
    def get_user_attendance_history(self, user_id: str):
        """
        사용자의 모든 출석 기록을 가져와서 최신순으로 정렬하여 반환합니다.
        """
        if not self.guild_id:
            logger.error("❌ get_user_attendance_history: guild_id가 설정되지 않았습니다.")
            return []
        query = "SELECT attendance_date FROM attendance WHERE user_id = ? ORDER BY attendance_date DESC"
        records = self.execute_query(query, (user_id,), 'all')
        if records:
            return [row['attendance_date'] for row in records]
        return []
    
    def record_attendance(self, user_id: str) -> Dict:
        """출석 체크 (연속 출석 일수 자동 계산)"""
        if not self.guild_id:
            logger.error("❌ record_attendance: guild_id가 설정되지 않았습니다.")
            return {'success': False, 'message': 'guild_id가 설정되지 않았습니다.', 'streak': 0}
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        existing = self.execute_query('''
            SELECT * FROM attendance 
            WHERE user_id = ? AND attendance_date = ?
        ''', (user_id, today), 'one')
        
        if existing:
            return {'success': False, 'message': '이미 오늘 출석했습니다', 'streak': dict(existing)['streak_count']}
        
        yesterday_record = self.execute_query('''
            SELECT streak_count FROM attendance 
            WHERE user_id = ? AND attendance_date = ?
        ''', (user_id, yesterday), 'one')
        
        streak_count = yesterday_record['streak_count'] + 1 if yesterday_record else 1
        
        self.execute_query('''
            INSERT INTO attendance (user_id, attendance_date, streak_count)
            VALUES (?, ?, ?)
        ''', (user_id, today, streak_count))
        
        return {'success': True, 'message': '출석 완료', 'streak': streak_count, 'date': today.strftime('%Y-%m-%d')}

    def get_user_attendance_streak(self, user_id: str) -> int:
        """사용자의 현재 연속 출석 일수 조회"""
        if not self.guild_id:
            logger.error("❌ get_user_attendance_streak: guild_id가 설정되지 않았습니다.")
            return 0
        today = date.today()
    
        result = self.execute_query('''
            SELECT streak_count FROM attendance
            WHERE user_id = ? AND attendance_date = ?
        ''', (user_id, today), 'one')
    
        if result:
            return result['streak_count']
    
        yesterday = today - timedelta(days=1)
        yesterday_result = self.execute_query('''
            SELECT streak_count FROM attendance
            WHERE user_id = ? AND attendance_date = ?
        ''', (user_id, yesterday), 'one')
    
        return yesterday_result['streak_count'] if yesterday_result else 0

    def has_attended_today(self, user_id: str) -> bool:
        """사용자가 오늘 이미 출석했는지 확인"""
        if not self.guild_id:
            logger.error("❌ has_attended_today: guild_id가 설정되지 않았습니다.")
            return False
        today = date.today()
        result = self.execute_query('''
            SELECT 1 FROM attendance
            WHERE user_id = ? AND attendance_date = ?
        '''
        , (user_id, today), 'one')
        return result is not None

    def get_attendance_leaderboard(self, limit: int = 10) -> List[Dict]:
        """연속 출석일 리더보드 조회"""
        if not self.guild_id:
            logger.error("❌ get_attendance_leaderboard: guild_id가 설정되지 않았습니다.")
            return []
        
        # 오늘 날짜를 기준으로 연속 출석일이 유효한 사용자만 필터링
        today = date.today().strftime('%Y-%m-%d')
        
        query = f"""
            SELECT
                u.user_id,
                u.username,
                u.display_name,
                a.streak_count as current_streak
            FROM users u
            JOIN attendance a ON u.user_id = a.user_id
            WHERE u.guild_id = ?
            AND a.attendance_date = ? -- 오늘 날짜로 출석한 기록만 고려
            ORDER BY current_streak DESC
            LIMIT ?
        """
        results = self.execute_query(query, (self.guild_id, today, limit), 'all')
        
        return [dict(row) for row in results] if results else []
        
    # ==================== 강화 시스템 ====================
    def get_enhancement_data(self, user_id: str) -> Dict:
        """강화 데이터 조회"""
        if not self.guild_id:
            logger.error("❌ get_enhancement_data: guild_id가 설정되지 않았습니다.")
            return {'user_id': user_id, 'level': 0, 'success_count': 0, 'fail_count': 0}
        result = self.execute_query('SELECT * FROM enhancement WHERE user_id = ?', (user_id,), 'one')
        return dict(result) if result else {'user_id': user_id, 'level': 0, 'success_count': 0, 'fail_count': 0}

    def update_enhancement(self, user_id: str, level: int, success_count: int, fail_count: int):
        """강화 데이터 업데이트"""
        if not self.guild_id:
            logger.error("❌ update_enhancement: guild_id가 설정되지 않았습니다.")
            return None
        return self.execute_query('''
            INSERT OR REPLACE INTO enhancement 
            (user_id, level, success_count, fail_count, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, level, success_count, fail_count))
    
    # ==================== 거래 내역 ====================
    def add_transaction(self, user_id: str, transaction_type: str, amount: int, description: str = ''):
        """거래 내역 추가"""
        if not self.guild_id:
            logger.error("❌ add_transaction: guild_id가 설정되지 않았습니다.")
            return None
        balance_after = self.get_user_cash(user_id)
        if balance_after is None:
            balance_after = 0
            
        return self.execute_query('''
            INSERT INTO point_transactions 
            (user_id, transaction_type, amount, balance_after, description)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, transaction_type, amount, balance_after, description))

    def get_user_transactions(self, user_id: str, limit: int = 10) -> List[Dict]:
        """사용자 거래 내역 조회"""
        if not self.guild_id:
            logger.error("❌ get_user_transactions: guild_id가 설정되지 않았습니다.")
            return []
        results = self.execute_query('''
            SELECT * FROM point_transactions 
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (user_id, limit), 'all')
        return [dict(row) for row in results] if results else []
    
    # ==================== 리더보드 ====================
    def get_cash_leaderboard(self, limit: int = 10) -> List[Dict]:
        """현금 리더보드"""
        if not self.guild_id:
            logger.error("❌ get_cash_leaderboard: guild_id가 설정되지 않았습니다.")
            return []
        results = self.execute_query('''
            SELECT user_id, username, display_name, cash
            FROM users 
            WHERE guild_id = ? AND cash > 0
            ORDER BY cash DESC
            LIMIT ?
        ''', (self.guild_id, limit), 'all')
        return [dict(row) for row in results] if results else []

    def get_total_cash_stats(self) -> Dict:
        """총 현금 통계"""
        if not self.guild_id:
            logger.error("❌ get_total_cash_stats: guild_id가 설정되지 않았습니다.")
            return {'total_cash': 0, 'total_users': 0, 'avg_cash': 0}
        result = self.execute_query('''
            SELECT 
                SUM(cash) as total_cash,
                COUNT(*) as total_users,
                AVG(cash) as avg_cash
            FROM users
            WHERE guild_id = ? AND cash > 0
        ''', (self.guild_id,), 'one')
        return dict(result) if result and result[0] is not None else {'total_cash': 0, 'total_users': 0, 'avg_cash': 0}
    
    # ==================== 설정 관리 ====================
    def get_leaderboard_settings(self) -> Dict:
        """리더보드 설정 조회"""
        if not self.guild_id:
            logger.error("❌ get_leaderboard_settings: guild_id가 설정되지 않았습니다.")
            return DEFAULT_LEADERBOARD_SETTINGS # 길드 ID가 없으면 기본 설정 반환
        
        result = self.execute_query('SELECT * FROM leaderboard_settings WHERE guild_id = ?', (self.guild_id,), 'one')
        
        if result:
            return dict(result)
        else:
            # 설정이 없으면 기본값으로 삽입 후 반환
            self.update_leaderboard_settings(DEFAULT_LEADERBOARD_SETTINGS)
            return DEFAULT_LEADERBOARD_SETTINGS
    
    def update_leaderboard_settings(self, settings: Dict):
        """리더보드 설정 업데이트"""
        if not self.guild_id:
            logger.error("❌ update_leaderboard_settings: guild_id가 설정되지 않았습니다.")
            return None
        
        # guild_id를 settings 딕셔너리에 추가
        settings_with_guild_id = settings.copy()
        settings_with_guild_id['guild_id'] = self.guild_id

        columns = list(settings_with_guild_id.keys())
        placeholders = ', '.join(['?'] * len(columns))
        set_clauses = [f"{col} = ?" for col in columns]
        params = list(settings_with_guild_id.values())
        
        # INSERT OR REPLACE를 사용하여 기존 레코드가 있으면 업데이트, 없으면 삽입
        query = f'''
            INSERT OR REPLACE INTO leaderboard_settings ({', '.join(columns)}, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP)
        '''
        # params에 updated_at이 없으므로 추가
        self.execute_query(query, tuple(params))
        logger.info(f"✅ 길드 {self.guild_id}의 리더보드 설정 업데이트 완료.")

    # ==================== 기타 유틸리티 ====================
    def get_database_stats(self) -> Dict:
        """데이터베이스 통계"""
        stats = {}
        tables = ['users', 'user_xp', 'attendance', 'enhancement', 'point_transactions', 'voice_time', 'voice_time_log', 'levelup_channels', 'leaderboard_settings']
        
        for table in tables:
            try:
                # users 테이블은 guild_id로 필터링
                if table == 'users' and self.guild_id:
                    result = self.execute_query(f'SELECT COUNT(*) FROM {table} WHERE guild_id = ?', (self.guild_id,), 'one')
                else:
                    result = self.execute_query(f'SELECT COUNT(*) FROM {table}', (), 'one')
                stats[table] = result[0] if result else 0
            except sqlite3.Error:
                stats[table] = 0
        
        if os.path.exists(self.db_path):
            stats['file_size'] = os.path.getsize(self.db_path)
        else:
            stats['file_size'] = 0
        
        return stats
    
    def format_money(self, amount: int) -> str:
        """돈 형식 포맷"""
        return f"{amount:,}원"
    
    def format_xp(self, xp: int) -> str:
        """XP 형식 포맷"""
        return f"{xp:,} XP"

# ==================== 호환성 함수들 ====================
# 이 함수들은 이제 guild_id를 인자로 받아야 합니다.
def get_guild_db_manager(guild_id: str) -> DatabaseManager:
    """특정 길드에 대한 DatabaseManager 인스턴스를 반환합니다."""
    return DatabaseManager(guild_id=guild_id)

def load_points(guild_id: str) -> Dict[str, int]:
    db = get_guild_db_manager(guild_id)
    results = db.execute_query('SELECT user_id, cash FROM users WHERE guild_id = ? AND cash > 0', (guild_id,), 'all')
    return {row['user_id']: row['cash'] for row in results} if results else {}

def save_points(guild_id: str, points_data: Dict[str, int]):
    db = get_guild_db_manager(guild_id)
    for user_id, cash in points_data.items():
        db.update_user_cash(user_id, cash)

def add_point(guild_id: str, user_id: str, amount: int):
    db = get_guild_db_manager(guild_id)
    return db.add_user_cash(user_id, amount)

def get_point(guild_id: str, user_id: str) -> Optional[int]:
    db = get_guild_db_manager(guild_id)
    return db.get_user_cash(user_id)

def is_registered(guild_id: str, user_id: str) -> bool:
    db = get_guild_db_manager(guild_id)
    return db.get_user(user_id) is not None

if __name__ == "__main__":
    # 테스트를 위해 임시 길드 ID 사용
    test_guild_id = "test_guild_123"
    db = DatabaseManager(guild_id=test_guild_id)
    logger.info("데이터베이스 매니저 초기화 완료")
    logger.info(f"통계: {db.get_database_stats()}")

    # 사용자 생성 및 조회 테스트
    db.create_user("user1", "TestUser1", "테스트유저1", 1000)
    user = db.get_user("user1")
    logger.info(f"User1: {user}")

    db.add_user_cash("user1", 500)
    user = db.get_user("user1")
    logger.info(f"User1 after add cash: {user}")

    # XP 테스트
    db.add_user_xp("user1", 200)
    xp_data = db.get_user_xp("user1")
    logger.info(f"User1 XP: {xp_data}")

    # 출석 테스트
    attendance_result = db.record_attendance("user1")
    logger.info(f"User1 attendance: {attendance_result}")

    # 리더보드 설정 테스트
    settings = db.get_leaderboard_settings()
    logger.info(f"Leaderboard settings: {settings}")
    db.update_leaderboard_settings({'attendance_cash': 5000})
    settings = db.get_leaderboard_settings()
    logger.info(f"Leaderboard settings after update: {settings}")

    # 다른 길드 테스트
    test_guild_id_2 = "test_guild_456"
    db2 = DatabaseManager(guild_id=test_guild_id_2)
    db2.create_user("user1", "TestUser1_Guild2", "테스트유저1_길드2", 2000)
    user2 = db2.get_user("user1")
    logger.info(f"User1 in Guild2: {user2}")
    logger.info(f"Stats for Guild2: {db2.get_database_stats()}")

    # 기존 전역 db_manager 사용 시 경고/오류 발생 확인
    # db_manager = DatabaseManager() # 이 라인은 이제 guild_id가 없으므로 기본 DB를 사용합니다.
    # db_manager.create_user("global_user", "GlobalUser", "글로벌유저") # 이 경우 guild_id가 None이므로 오류 발생
    # logger.info(f"Global DB stats: {db_manager.get_database_stats()}")