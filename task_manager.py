import threading
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.tasks = {}  # type_name -> status_dict
            self.initialized = True

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TaskManager, cls).__new__(cls)
            return cls._instance

    def start_task(self, task_type: str, total: int = 0, message: str = "Started"):
        with self._lock:
            self.tasks[task_type] = {
                "status": "running",
                "message": message,
                "current": 0,
                "total": total,
                "percent": 0,
                "start_time": None, # Could add if needed
            }
            logger.debug(f"Task started: {task_type} with total={total}")

    def update_progress(self, task_type: str, current: int, message: str = None):
        with self._lock:
            if task_type in self.tasks:
                task = self.tasks[task_type]
                task["current"] = current
                if message:
                    task["message"] = message
                
                if task["total"] > 0:
                    task["percent"] = round((current / task["total"]) * 100)
                else:
                    task["percent"] = 0
            else:
                logger.warning(f"Attempted to update non-existent task: {task_type}")

    def complete_task(self, task_type: str, message: str = "Completed", result: dict = None):
        with self._lock:
            if task_type in self.tasks:
                task = self.tasks[task_type]
                task["status"] = "completed"
                task["message"] = message
                task["percent"] = 100
                task["result"] = result
                logger.debug(f"Task completed: {task_type}")

    def fail_task(self, task_type: str, error: str):
        with self._lock:
            if task_type in self.tasks:
                task = self.tasks[task_type]
                task["status"] = "failed"
                task["message"] = f"Error: {error}"
                logger.error(f"Task failed: {task_type} - {error}")

    def get_status(self, task_type: str = None) -> dict:
        with self._lock:
            if task_type:
                return self.tasks.get(task_type, {"status": "idle"})
            return self.tasks

# Global singleton
task_manager = TaskManager()
