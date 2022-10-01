from typing import List, Dict
from dataclasses import dataclass
from dto import PgieObj


@dataclass
class EventConfig:
    source_id: str
    enable: bool
    name: str
    roi: List[List[float]]
    label: str
    timeout: float


class Event:
    def __init__(self, event_config: EventConfig):
        self.stream_id = event_config.source_id
        self.enable = event_config.enable
        self.event_name = event_config.name
        self.label = event_config.label  # pgie class label
        self.event_timeout = event_config.timeout
        self.roi = event_config.roi

        self.obj_list: List[PgieObj] = []  # 이벤트에 등록될 object의 리스트를 초기화
