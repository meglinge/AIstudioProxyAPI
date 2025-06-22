"""
性能监控模块
"""

import time
import logging
from typing import Dict, List, Optional, Tuple

class PerformanceMonitor:
    """一个用于监控请求处理性能的类。"""

    def __init__(self, req_id: str, enabled: bool = False):
        """
        初始化性能监视器。

        Args:
            req_id (str): 请求的唯一ID。
            enabled (bool): 是否启用监控。如果为False，所有方法将不执行任何操作。
        """
        self.req_id = req_id
        self.enabled = enabled
        self.marks: List[Tuple[str, float]] = []
        if self.enabled:
            # 记录监视器自身初始化的时间点
            self.mark("monitor_init")

    def mark(self, stage_name: str):
        """
        标记一个性能阶段。

        Args:
            stage_name (str): 阶段的名称。
        """
        if not self.enabled:
            return
        self.marks.append((stage_name, time.monotonic()))

    def get_summary(self) -> Optional[Dict[str, float]]:
        """
        获取性能计时的摘要。

        Returns:
            Optional[Dict[str, float]]: 包含各阶段耗时的字典，如果监控被禁用则返回None。
        """
        if not self.enabled or not self.marks:
            return None

        summary: Dict[str, float] = {}
        timings = {name: ts for name, ts in self.marks}

        # 定义需要计算的关键阶段及其起止标记
        key_stages = {
            "队列等待": ("worker_start_processing", "enqueue_time"),
            "获取锁耗时": ("acquired_processing_lock", "worker_start_processing"),
            "模型切换": ("model_switching_end", "model_switching_start"),
            "参数调整": ("parameter_adjustment_end", "parameter_adjustment_start"),
            "提示提交": ("prompt_submission_end", "prompt_submission_start"),
            "响应首包(TTFT)": ("response_first_token", "response_processing_start"),
            "响应总耗时": ("response_processing_end", "response_processing_start"),
            "总处理时间(持锁)": ("lock_released", "acquired_processing_lock"),
            "清理耗时": ("cleanup_finished", "lock_released"),
            "请求总耗时(Worker)": ("cleanup_finished", "worker_start_processing")
        }

        for name, (end_stage, start_stage) in key_stages.items():
            if end_stage in timings and start_stage in timings:
                duration = timings[end_stage] - timings[start_stage]
                summary[name] = round(duration, 4)
        
        return summary

    def log_summary(self, logger: logging.Logger, enqueue_time: Optional[float] = None):
        """
        记录性能摘要日志。

        Args:
            logger (logging.Logger): 用于记录日志的日志器实例。
            enqueue_time (Optional[float]): 请求的入队时间戳。
        """
        if not self.enabled:
            return

        if enqueue_time:
            # 将外部传入的入队时间加入标记列表，以便计算队列等待时间
            self.marks.insert(0, ("enqueue_time", enqueue_time))

        summary = self.get_summary()
        if not summary:
            return

        log_message = f"[{self.req_id}] 性能监控报告 (s):\n"
        for stage, duration in summary.items():
            log_message += f"  - {stage}: {duration:.4f} s\n"
        
        # 计算从入队到完成的总时长
        if "enqueue_time" in dict(self.marks) and self.marks:
            total_duration = self.marks[-1][1] - self.marks[0][1]
            log_message += f"  - 总计 (从入队到完成): {total_duration:.4f} s"

        logger.info(log_message)