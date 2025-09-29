# database_manager.py
from __future__ import annotations
import sqlite3
import os
import logging
from typing import Dict, List, Optional, Literal, Union
import math
from datetime import datetime, date, timedelta
from pathlib import Path

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
        
        # 파일 핸들러
        file_handler = logging.FileHandler(log_dir / 'database.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logging()

class DatabaseManager:
    def __init__(self, db_path: str = "data/dotori_bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
        self._create_tables()

    def _init_db(self):
        """데이터베이스 연결 및 설정 초기화"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute('PRAGMA foreign_keys = ON')
            conn.close()
            logger.info("✅ 데이터베이스 초기화 완료.")
        except sqlite3.Error as e:
            logger.error(f"❌ 데이터베이스 초기화 중 오류 발생: {e}")
    
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
        self.create_table(
            "users",
            """
            user_id TEXT PRIMARY KEY,
            username TEXT DEFAULT '',
            display_name TEXT DEFAULT '',
            cash INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        self.create_table(
            "attendance",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            attendance_date DATE NOT NULL,
            streak_count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, user_id, attendance_date)
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
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, user_id)
            """
        )
        self.create_table(
            "leaderboard_settings",
            """
            guild_id TEXT PRIMARY KEY,
            attendance_cash INTEGER DEFAULT 3000,
            attendance_xp INTEGER DEFAULT 100,
            weekly_cash_bonus INTEGER DEFAULT 1000,
            weekly_xp_bonus INTEGER DEFAULT 500,
            monthly_cash_bonus INTEGER DEFAULT 10000,
            monthly_xp_bonus INTEGER DEFAULT 5000,
            gift_fee_rate REAL DEFAULT 0.1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """
        )
        self.create_table(
            "voice_time",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            total_time INTEGER DEFAULT 0,
            last_join TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(guild_id, user_id)
            """
        )
        self.create_table(
            "voice_time_log",
            """
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT NOT NULL,
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
            guild_id TEXT PRIMARY KEY,
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
                if 'display_name' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN display_name TEXT DEFAULT ''")
                    logger.info("✅ users 테이블에 'display_name' 컬럼 추가 완료.")

                # 스키마 마이그레이션: users 테이블에 cash 컬럼이 없으면 추가
                if 'cash' not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN cash INTEGER DEFAULT 0")
                    logger.info("✅ users 테이블에 'cash' 컬럼 추가 완료.")

                conn.commit()
                logger.info("✅ 모든 테이블 생성 및 스키마 검증 완료.")
            except sqlite3.Error as e:
                logger.error(f"❌ 테이블 생성/마이그레이션 중 심각한 오류 발생: {e}")
                # 오류 발생 시 롤백
                conn.rollback()
    def get_or_create_user(self, user_id: str, guild_id: str, username: str) -> bool:
            """
            사용자를 조회하고, 없으면 생성합니다.
            성공적으로 조회 또는 생성되면 True를 반환합니다.
            """
            try:
                # 사용자 조회
                user_data = self.get_user(user_id)
                if user_data:
                    return True # 사용자가 이미 존재하면 True 반환

                # 사용자 생성 (기본값으로)
                success = self.create_user(user_id, guild_id, username)
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
        try:
            self.execute_query('''
            INSERT INTO users (user_id, username, display_name, cash)
            VALUES (?, ?, ?, ?)
            ''', (user_id, username, display_name, initial_cash))
            # 예외가 없으면 성공
            logger.info(f"[DB] 사용자 생성 성공: {user_id} - {display_name} ({initial_cash}원)")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"[DB] 이미 존재하는 사용자: {user_id}")
            return False
        except Exception as e:
            logger.error(f"[DB] 사용자 생성 중 오류: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
        """사용자 정보 조회"""
        result = self.execute_query('SELECT * FROM users WHERE user_id = ?', (user_id,), 'one')
        return dict(result) if result else None

    def update_user_cash(self, user_id: str, new_cash: int):
        """사용자 현금 업데이트"""
        return self.execute_query('''
        UPDATE users
        SET cash = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        ''', (new_cash, user_id))
    
    def add_user_cash(self, user_id: str, amount: int):
        """사용자에게 현금 추가"""
        current_cash = self.get_user_cash(user_id)
        if current_cash is None:
            self.create_user(user_id, initial_cash=amount)
            return amount
        new_cash = current_cash + amount
        self.update_user_cash(user_id, new_cash)
        return new_cash

    def get_user_cash(self, user_id: str) -> Optional[int]:
        """사용자 현금 조회"""
        user = self.get_user(user_id)
        return user['cash'] if user else None
    
    def get_all_users(self, limit: int = None, offset: int = 0) -> List[Dict]:
        """모든 사용자 조회"""
        query = 'SELECT * FROM users ORDER BY created_at DESC'
        if limit:
            query += f' LIMIT {limit} OFFSET {offset}'
        results = self.execute_query(query, (), 'all')
        return [dict(row) for row in results] if results else []

    def get_user_count(self) -> int:
        """총 사용자 수"""
        result = self.execute_query('SELECT COUNT(*) FROM users', (), 'one')
        return result[0] if result else 0
    
    def delete_user(self, user_id: str) -> Dict[str, int]:
        """특정 사용자의 모든 데이터 삭제"""
        deleted_counts = {}
        with self.get_connection() as conn:
            for table in ['users', 'user_xp', 'attendance', 'enhancement', 'point_transactions']:
                deleted_counts[table] = self._delete_from_table(conn, table, user_id)
        return deleted_counts

    def _delete_from_table(self, conn, table_name, user_id):
        """특정 테이블에서 사용자 데이터 삭제"""
        cursor = conn.cursor()
        cursor.execute(f'DELETE FROM {table_name} WHERE user_id = ?', (user_id,))
        count = cursor.rowcount
        conn.commit()
        return count
    
    def get_user_ranking(self, user_id: str) -> Optional[int]:
        """사용자의 현금 순위 조회"""
        query = """
        SELECT ranking FROM (
            SELECT user_id, RANK() OVER (ORDER BY cash DESC) AS ranking
            FROM users
        ) WHERE user_id = ?
        """
        result = self.execute_query(query, (user_id,), 'one')
        return result['ranking'] if result else None
    
    # ==================== XP 시스템 ====================
    def ensure_user_xp_exists(self, guild_id: str, user_id: str):
        """사용자 XP 레코드가 없으면 생성"""
        return self.execute_query('''
            INSERT OR IGNORE INTO user_xp (guild_id, user_id, xp, level)
            VALUES (?, ?, 0, 1)
        ''', (guild_id, user_id))
    
    def get_user_xp(self, guild_id: str, user_id: str) -> Dict:
        """특정 사용자의 XP 데이터를 가져오는 함수 (딕셔너리 반환)"""
        try:
            result = self.execute_query(
                "SELECT xp, level FROM user_xp WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
                'one'
            )
            return dict(result) if result else {'xp': 0, 'level': 1}
        except Exception as e:
            logger.error(f"❌ DB 오류: XP 조회 실패 - {e}")
            return {'xp': 0, 'level': 1}
    
    def add_user_xp(self, guild_id: str, user_id: str, xp_gain: int):
        """사용자에게 XP 추가"""
        return self.execute_query(
            "INSERT INTO user_xp (guild_id, user_id, xp) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = xp + ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id, xp_gain, xp_gain, guild_id, user_id), 'none'
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
    
    def get_xp_leaderboard(self, guild_id: str, limit: int = 10) -> List[Dict]:
        """XP 리더보드 조회"""
        results = self.execute_query('''
            SELECT ux.*, u.username, u.display_name 
            FROM user_xp ux
            LEFT JOIN users u ON ux.user_id = u.user_id
            WHERE ux.guild_id = ?
            ORDER BY ux.xp DESC
            LIMIT ?
        ''', (guild_id, limit), 'all')
        
        return [dict(row) for row in results] if results else []
    

    # ==================== 보이스 시스템 ====================
    def add_user_voice_time(self, guild_id: str, user_id: str, minutes_to_add: int):
        """사용자의 총 통화 시간을 업데이트하거나 생성합니다."""
        return self.execute_query(
            "INSERT INTO voice_time (guild_id, user_id, total_time) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET total_time = total_time + ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id, minutes_to_add, minutes_to_add, guild_id, user_id), 'none'
        )
    
    def add_voice_activity(self, user_id: str, guild_id: str, duration: int):
        """음성 활동 로그를 추가하고, voice_time 테이블을 업데이트합니다."""
        try:
            with self.get_connection() as conn:
                # voice_time_log에 상세 기록 추가
                conn.execute('''
                    INSERT INTO voice_time_log (user_id, guild_id, duration_minutes)
                    VALUES (?, ?, ?)
                ''', (user_id, guild_id, duration))

                # voice_time에 총 시간 업데이트
                conn.execute('''
                    INSERT INTO voice_time (user_id, guild_id, total_time)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, guild_id) DO UPDATE SET
                    total_time = total_time + excluded.total_time,
                    updated_at = CURRENT_TIMESTAMP
                ''', (user_id, guild_id, duration))
                
                conn.commit()
                logger.info(f"✅ 음성 활동 기록 성공: user_id={user_id}, guild_id={guild_id}, duration={duration}분")
                return True
        except sqlite3.Error as e:
            logger.error(f"❌ 음성 활동 기록 중 오류 발생: {e}", exc_info=True)
            return False

    # ==================== 출석 시스템 ====================
    def get_attendance_stats(self, user_id: str) -> Optional[Dict]:
        """
        사용자의 총 출석 일수 및 연속 출석 일수 조회
        """
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
    
    def get_user_attendance_history(self, guild_id: str, user_id: str):
        """
        사용자의 모든 출석 기록을 가져와서 최신순으로 정렬하여 반환합니다.
        """
        query = "SELECT attendance_date FROM attendance WHERE guild_id = ? AND user_id = ? ORDER BY attendance_date DESC"
        records = self.execute_query(query, (guild_id, user_id), 'all')
        if records:
            return [row['attendance_date'] for row in records]
        return []
    
    def record_attendance(self, guild_id: str, user_id: str) -> Dict:
        """출석 체크 (연속 출석 일수 자동 계산)"""
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        existing = self.execute_query('''
            SELECT * FROM attendance 
            WHERE guild_id = ? AND user_id = ? AND attendance_date = ?
        ''', (guild_id, user_id, today), 'one')
        
        if existing:
            return {'success': False, 'message': '이미 오늘 출석했습니다', 'streak': dict(existing)['streak_count']}
        
        yesterday_record = self.execute_query('''
            SELECT streak_count FROM attendance 
            WHERE guild_id = ? AND user_id = ? AND attendance_date = ?
        ''', (guild_id, user_id, yesterday), 'one')
        
        streak_count = yesterday_record['streak_count'] + 1 if yesterday_record else 1
        
        self.execute_query('''
            INSERT INTO attendance (guild_id, user_id, attendance_date, streak_count)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, today, streak_count))
        
        return {'success': True, 'message': '출석 완료', 'streak': streak_count, 'date': today.strftime('%Y-%m-%d')}

    def get_user_attendance_streak(self, user_id: str) -> int:
        """사용자의 현재 연속 출석 일수 조회"""
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
        
    # ==================== 강화 시스템 ====================
    def get_enhancement_data(self, user_id: str) -> Dict:
        """강화 데이터 조회"""
        result = self.execute_query('SELECT * FROM enhancement WHERE user_id = ?', (user_id,), 'one')
        return dict(result) if result else {'user_id': user_id, 'level': 0, 'success_count': 0, 'fail_count': 0}

    def update_enhancement(self, user_id: str, level: int, success_count: int, fail_count: int):
        """강화 데이터 업데이트"""
        return self.execute_query('''
            INSERT OR REPLACE INTO enhancement 
            (user_id, level, success_count, fail_count, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, level, success_count, fail_count))
    
    # ==================== 거래 내역 ====================
    def add_transaction(self, user_id: str, transaction_type: str, amount: int, description: str = ''):
        """거래 내역 추가"""
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
        results = self.execute_query('''
            SELECT user_id, username, display_name, cash
            FROM users 
            WHERE cash > 0
            ORDER BY cash DESC
            LIMIT ?
        ''', (limit,), 'all')
        return [dict(row) for row in results] if results else []

    def get_total_cash_stats(self) -> Dict:
        """총 현금 통계"""
        result = self.execute_query('''
            SELECT 
                SUM(cash) as total_cash,
                COUNT(*) as total_users,
                AVG(cash) as avg_cash
            FROM users
            WHERE cash > 0
        ''', (), 'one')
        return dict(result) if result and result[0] is not None else {'total_cash': 0, 'total_users': 0, 'avg_cash': 0}
    
    # ==================== 설정 관리 ====================
    def get_leaderboard_settings(self, guild_id: str) -> Dict:
        """리더보드 설정 조회"""
        result = self.execute_query('SELECT * FROM leaderboard_settings WHERE guild_id = ?', (guild_id,), 'one')
        
        if result:
            return dict(result)
        else:
            return {
                'guild_id': guild_id,
                'attendance_cash': 3000, 'attendance_xp': 100,
                'weekly_cash_bonus': 1000, 'weekly_xp_bonus': 500,
                'monthly_cash_bonus': 10000, 'monthly_xp_bonus': 5000,
                'gift_fee_rate': 0.1
            }
    
    def update_leaderboard_settings(self, guild_id: str, settings: Dict):
        """리더보드 설정 업데이트"""
        columns = list(settings.keys())
        set_clauses = [f"{col} = ?" for col in columns]
        params = list(settings.values())
        
        query = f'''
            INSERT OR REPLACE INTO leaderboard_settings ({', '.join(columns)}, guild_id, updated_at)
            VALUES ({', '.join(['?'] * len(columns))}, ?, CURRENT_TIMESTAMP)
        '''
        params.append(guild_id)
        
        self.execute_query(query, tuple(params))

    # ==================== 기타 유틸리티 ====================
    def get_database_stats(self) -> Dict:
        """데이터베이스 통계"""
        stats = {}
        tables = ['users', 'user_xp', 'attendance', 'enhancement', 'point_transactions', 'voice_time', 'voice_time_log', 'levelup_channels']
        
        for table in tables:
            try:
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
def load_points() -> Dict[str, int]:
    db = DatabaseManager()
    results = db.execute_query('SELECT user_id, cash FROM users WHERE cash > 0', (), 'all')
    return {row['user_id']: row['cash'] for row in results} if results else {}

def save_points(points_data: Dict[str, int]):
    db = DatabaseManager()
    for user_id, cash in points_data.items():
        db.update_user_cash(user_id, cash)

def add_point(user_id: str, amount: int):
    db = DatabaseManager()
    return db.add_user_cash(user_id, amount)

def get_point(user_id: str) -> Optional[int]:
    db = DatabaseManager()
    return db.get_user_cash(user_id)

def is_registered(user_id: str) -> bool:
    db = DatabaseManager()
    return db.get_user(user_id) is not None

# 싱글톤 인스턴스 생성
db_manager = DatabaseManager()

if __name__ == "__main__":
    db = DatabaseManager()
    logger.info("데이터베이스 매니저 초기화 완료")
    logger.info(f"통계: {db.get_database_stats()}")