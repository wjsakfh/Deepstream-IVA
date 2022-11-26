from typing import List, Dict, Any
from dataclasses import dataclass
from dto import PgieObj


@dataclass
class EventConfig:
    source_id: str
    event_id: str
    enable: bool
    name: str
    roi: List[List[float]]
    label: str


class Event:
    def __init__(self, event_config: EventConfig):
        self.source_id = event_config.source_id
        self.event_id = event_config.event_id
        self.enable = event_config.enable
        self.name = event_config.name
        self.label = event_config.label  # pgie class label
        self.event_timeout = event_config.timeout
        self.roi = event_config.roi

        self.obj_list: List[PgieObj] = []  # 이벤트에 등록될 object의 리스트를 초기화

        self.info: Dict[str, Any] = {"count_in": 0, "count_out": 0, "mask_in":0, "mask_out":0, "status": str()}