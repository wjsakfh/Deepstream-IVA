from typing import List, Dict

class EventConfig:
    stream_id: str
    name: List[str]
    ROI: List[List[float]]
    label: str
    timeout: List[float]

class Event:
    def __init__(self, event_config: EventConfig):
        self.stream_id = event_config.stream_id
        self.event_name = event_config.name
        self.label = event_config.label
        self.event_timeout = event_config.timeout
        self.ROI = event_config.ROI
