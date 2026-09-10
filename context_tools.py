"""旅行 Hero Flow 的上下文工具适配层。

当前实现返回明确标注的演示数据。真实 Calendar/Weather 服务只需实现同名方法，
Agent planner 与 Dynamic UI 不需要随之改写。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Protocol


class CalendarTool(Protocol):
    def upcoming_trip(self, utterance: str) -> dict[str, Any]: ...


class WeatherTool(Protocol):
    def forecast(self, destination: str, start_date: str, days: int) -> dict[str, Any]: ...


class DemoCalendarTool:
    """从旅行意图生成稳定的演示日程。"""

    def upcoming_trip(self, utterance: str) -> dict[str, Any]:
        start = date.today() + timedelta(days=7)
        return {
            "source": "Demo Calendar adapter",
            "title": "深圳产品交流行程",
            "destination": "深圳",
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=3)).isoformat(),
            "days": 4,
            "intent": utterance,
        }


class DemoWeatherTool:
    """返回适合演示装备规划的天气上下文。"""

    def forecast(self, destination: str, start_date: str, days: int) -> dict[str, Any]:
        return {
            "source": "Demo Weather adapter",
            "destination": destination,
            "start_date": start_date,
            "days": days,
            "temperature": "27–32°C",
            "conditions": ["高温", "阵雨", "强紫外线"],
            "rain_probability": 65,
            "uv_index": 8,
        }
