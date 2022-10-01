from dto import EventConfig, Event
from typing import Dict, List


class Source:
    def __init__(self, source_id, event_configs: List[EventConfig]):
        self.id = source_id
        self.event_list = [Event(event_config) for event_config in event_configs]
