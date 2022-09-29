from Ev import *
from typing import Dict, List

class Stream:
    def __init__(self, stream_id, event_configs:List[EventConfig])
        self.id = stream_id
        self.event_list = [Event(event_config) for event_config in event_configs if event_config.stream_id == stream_id]]