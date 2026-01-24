# backup_cog.py
from __future__ import annotations
import os
import zipfile
import logging
import threading
import time
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import traceback
from discord.ext import commands

# ✅ 백업 설정
BACKUP_CONFIG = {
    "backup_interval_hours": 6,
    "max_backups": 30,
    "compress": True,
    "verify_backups": True,
    "backup_on_startup": True,
    "exclude_patterns": [
        "*.tmp", "*.temp", "__pycache__", "*.pyc"
    ],
    "source_files": [
        "data/dotori_bot.db",
        "data/point_data.json",
        "data/voice_time_data.json",
        "data/xp_leaderboard.json",
        "data/levelup_channels.json",
        "data/xp_settings.json"
    ]
}

# ✅ 로깅 설정
def setup_logging():
    """데이터베이스 매니저 전용 로깅 설정"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger("database_manager")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler = logging.FileHandler(log_dir / 'database.log', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logging()

# ✅ 백업 시스템 클래스
class BackupSystem:
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or BACKUP_CONFIG
        self.logger = setup_logging()
        self.base_dir = Path(os.getcwd())
        self.backup_dir = self.base_dir / 'backups'
        self.config_file = self.base_dir / 'backup_config.json'
        
        self.source_files = [self.base_dir / f for f in self.config.get('source_files', [])]

        self.backup_dir.mkdir(exist_ok=True)
        self.is_running = False
        
        self.running = False
        self.backup_thread = None
        self.scheduler_thread = None
        
        self.stats = {
            "total_backups": 0,
            "successful_backups": 0,
            "failed_backups": 0,
            "last_backup_time": None,
            "last_backup_size": 0
        }
        
        self.logger.info("🛡️ 백업 시스템 초기화 완료")
        
    def _load_config(self) -> Dict:
        """설정 파일 로드"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                return {**BACKUP_CONFIG, **loaded_config}
            else:
                self._save_config(BACKUP_CONFIG)
                return BACKUP_CONFIG.copy()
        except Exception as e:
            self.logger.error(f"설정 로드 실패: {e}")
            return BACKUP_CONFIG.copy()
            
    def _save_config(self, config: Dict = None) -> bool:
        """설정 파일 저장"""
        try:
            config_to_save = config or self.config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"설정 저장 실패: {e}")
            return False
            
    def create_backup(self, backup_name: Optional[str] = None) -> Tuple[bool, str]:
        """백업 생성"""
        try:
            self.stats["total_backups"] += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{backup_name}_{timestamp}.zip" if backup_name else f"backup_{timestamp}.zip"
            backup_path = self.backup_dir / filename
            
            self.logger.info(f"백업 생성 시작: {filename}")
            
            files_to_backup = [f for f in self.source_files if f.exists()]
            if not files_to_backup:
                self.stats["failed_backups"] += 1
                return False, "백업할 파일이 없습니다."
            
            with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                backup_info = {
                    "timestamp": datetime.now().isoformat(),
                    "backup_type": "manual" if backup_name else "auto",
                    "backup_version": "2.0",
                    "total_files": len(files_to_backup),
                    "files": [str(f) for f in files_to_backup]
                }
                zipf.writestr("backup_info.json", json.dumps(backup_info, indent=2))
                
                for file_path in files_to_backup:
                    try:
                        zipf.write(file_path, file_path)
                        self.logger.info(f"파일 추가 완료: {file_path}")
                    except Exception as e:
                        self.logger.error(f"파일 추가 실패: {file_path} - {e}")
            
            if self.config.get("verify_backups", True):
                if not self._verify_backup(str(backup_path), [str(f) for f in files_to_backup]):
                    self.stats["failed_backups"] += 1
                    return False, "백업 검증 실패"
            
            backup_size = backup_path.stat().st_size
            self.stats["successful_backups"] += 1
            self.stats["last_backup_time"] = datetime.now().isoformat()
            self.stats["last_backup_size"] = backup_size
            
            self.cleanup_old_backups()
            
            self.logger.info(f"✅ 백업 생성 완료: {filename} ({self.format_size(backup_size)})")
            return True, f"백업 생성 완료: {filename} ({self.format_size(backup_size)})"
            
        except Exception as e:
            self.stats["failed_backups"] += 1
            self.logger.error(f"백업 생성 실패: {traceback.format_exc()}")
            return False, f"백업 생성 실패: {str(e)}"

    def _verify_backup(self, backup_path: str, expected_files: List[str]) -> bool:
        """백업 파일 검증"""
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                bad_file = zipf.testzip()
                if bad_file:
                    self.logger.error(f"손상된 파일 발견: {bad_file}")
                    return False
                
                zip_files = zipf.namelist()
                for expected_file in expected_files:
                    if expected_file not in zip_files:
                        self.logger.error(f"예상 파일 누락: {expected_file}")
                        return False
                
                return True
        except Exception as e:
            self.logger.error(f"백업 검증 실패: {e}")
            return False

    def list_backups(self) -> List[Dict]:
        """백업 목록 조회"""
        backups = []
        
        if not self.backup_dir.exists():
            return backups
        
        for file in self.backup_dir.iterdir():
            if file.suffix == '.zip':
                try:
                    stat = file.stat()
                    info = self.get_backup_info(file.name)
                    
                    backups.append({
                        "name": file.name,
                        "size": stat.st_size,
                        "creation_time": datetime.fromtimestamp(stat.st_ctime),
                        "type": info.get("backup_type", "unknown") if info else "unknown",
                        "file_count": info.get("total_files", 0) if info else 0,
                        "valid": self._verify_backup(str(file), info.get("files", []) if info else [])
                    })
                except Exception as e:
                    self.logger.error(f"백업 정보 조회 실패: {file.name} - {e}")
        
        backups.sort(key=lambda x: x["creation_time"], reverse=True)
        return backups

    def get_backup_info(self, backup_name: str) -> Optional[Dict]:
        """백업 정보 조회"""
        backup_path = self.backup_dir / backup_name
        
        try:
            with zipfile.ZipFile(backup_path, 'r') as zipf:
                if "backup_info.json" in zipf.namelist():
                    info_data = zipf.read("backup_info.json")
                    return json.loads(info_data.decode('utf-8'))
        except Exception as e:
            self.logger.error(f"백업 정보 읽기 실패: {e}")
        
        return None

    def cleanup_old_backups(self) -> int:
        """오래된 백업 정리"""
        try:
            backups = self.list_backups()
            max_backups = self.config.get("max_backups", 30)
            
            if len(backups) <= max_backups:
                return 0
            
            backups_to_delete = backups[max_backups:]
            deleted_count = 0
            
            for backup in backups_to_delete:
                try:
                    backup_path = self.backup_dir / backup["name"]
                    backup_path.unlink()
                    deleted_count += 1
                    self.logger.info(f"오래된 백업 삭제: {backup['name']}")
                except Exception as e:
                    self.logger.error(f"백업 삭제 실패: {backup['name']} - {e}")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"백업 정리 실패: {e}")
            return 0

    def format_size(self, size_bytes: int) -> str:
        """파일 크기 포맷팅"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f}MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f}GB"

    def get_stats(self) -> Dict:
        """백업 통계 조회"""
        return {
            **self.stats,
            "running": self.running,
            "backup_folder": str(self.backup_dir)
        }

    def start_auto_backup(self) -> bool:
        """자동 백업 시작"""
        if self.running:
            return False
        
        self.running = True
        self.backup_thread = threading.Thread(target=self._auto_backup_loop, daemon=True)
        self.backup_thread.start()
        
        self.logger.info("🚀 자동 백업 시작됨")
        return True

    def _auto_backup_loop(self):
        """자동 백업 루프"""
        interval_seconds = self.config.get("backup_interval_hours", 6) * 3600
        
        if self.config.get("backup_on_startup", True):
            self.create_backup("startup")
        
        while self.running:
            try:
                time.sleep(60)
                if not self.running:
                    break
                
                if self.stats["last_backup_time"]:
                    last_backup = datetime.fromisoformat(self.stats["last_backup_time"])
                    if datetime.now() - last_backup < timedelta(seconds=interval_seconds):
                        continue
                
                self.create_backup()
                
            except Exception as e:
                self.logger.error(f"자동 백업 루프 오류: {e}")

    def stop_auto_backup(self) -> bool:
        """자동 백업 중지"""
        if not self.running:
            return False
        
        self.logger.info("자동 백업 중지 중...")
        self.running = False
        
        if self.backup_thread and self.backup_thread.is_alive():
            self.backup_thread.join(timeout=10)
            if self.backup_thread.is_alive():
                self.logger.warning("백업 스레드가 정상적으로 종료되지 않았습니다.")
                return False
        
        self.logger.info("✅ 자동 백업 중지됨")
        return True

# ✅ Discord 백업 Cog 클래스
class BackupCog(commands.Cog):
    def __init__(self, bot, backup_system):
        self.bot = bot
        self.backup_system = backup_system

async def setup(bot: commands.Bot):
    backup_system_instance = BackupSystem()
    await bot.add_cog(BackupCog(bot, backup_system_instance))
    backup_system_instance.start_auto_backup()