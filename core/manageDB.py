import sys
import gi

from core.generator import IntrusionAlarmGenerator

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst

from time import monotonic
from typing import List, Dict
from core.utils import parse_buffer2msg
from dataclasses import dataclass

# from algorithms import point_polygon_test
import cv2, numpy as np
from dto import PgieObj, EventConfig, Event, Source

## interface로 빼두어야 함.
POLYGON = [[0, 0], [0, 1080], [960, 1080], [960, 0]]

# AlarmGenerator를 담고 있기엔 이름의 범위가 좁음
# MsgManager가 들고있는 최종 Result는 self.obj_list 여야함.
# 이를 바깥 쪽에서 쓸 수 있으면 좋을 것 같음.
roi1 = [[0, 0], [0, 1080], [960, 1080], [960, 0]]
roi2 = [[960, 0], [960, 1080], [1920, 1080], [1920, 0]]

# TODO 추후에 사용자가 event config를 등록 또는 수정할 수 있어야한다.

event_config1 = EventConfig(0, True, "intrusion", roi1, "person", 3)
event_config2 = EventConfig(0, True, "intrusion", roi2, "person", 3)
event_config3 = EventConfig(1, True, "intrusion", roi1, "person", 3)
event_config4 = EventConfig(1, True, "intrusion", roi2, "person", 3)
print(event_config4.source_id)
EVENT_CONFIGS = [event_config1, event_config2, event_config3, event_config4]


class MsgManager:
    def __init__(self):
        # self.obj_info_list = obj_info_list
        self.sources: Dict = {}
        self.obj_list: List = []
        self.timeout: float = 3.0
        self.all_event_configs: List[EventConfig] = EVENT_CONFIGS

        # 정보 Extract
        # 리스트 업데이트

    # TODO async로 pgie object에 대한 msg를 msg broker를 통해
    # Event processing 모듈로 전달하고 거기서 모든 것이 처리되도록 해야함.
    # 그래야지 deepstream과 alarm generator를 분리할 수 있을 것임.
    def tiler_sink_pad_buffer_probe(self, pad, info, u_data):
        # msg manager
        msg: Dict = {}
        gst_buffer = info.get_buffer()
        parsed_msg, frame = parse_buffer2msg(gst_buffer, msg)
        # print("parsed_msg", parsed_msg)

        source_msg_list = parsed_msg["frame_list"]  # 각 source들의 msg list
        for source_msg in source_msg_list:
            source_id = source_msg["source_id"]
            # TODO 추후 refactoring 필요. (source event configs를 어디서 업데이트 할 것인지)
            source_event_configs = [
                c for c in self.all_event_configs if c.source_id == source_id
            ]

            if source_id not in self.sources.keys():
                self.sources[source_id] = Source(source_id, source_event_configs)

            source = self.sources[source_id]
            print("source", source.event_list)
            # TODO source의 이벤트에 맞는 object를 관리한다.
            for e in source.event_list:
                # event에 맞는 object update.
                # 먼저 특정 roi에 들어와있는 객체에 대해 판별한다.
                # roi에 들어와있으면 우선 객체에 등록한다.
                for obj_info in source_msg["obj_list"]:
                    e.obj_list = self._update_obj_list(e.obj_list, PgieObj(obj_info))

        # for frame_info in parsed_msg["frame_list"]:
        #     for obj_info in frame_info["obj_list"]:
        #         # pgie_obj생성
        #         # self.obj_list에 업데이트.
        #         pgie_obj = PgieObj(obj_info)
        #         self._update_obj_list(pgie_obj)

        intrusion_alarm_gen = IntrusionAlarmGenerator(self.obj_list, frame)
        intrusion_alarm_gen.run()

        return Gst.PadProbeReturn.OK

    def _update_obj_list(self, event_obj_list, pgie_obj):
        # pgie_obj: 현재 등록하려는 obj
        # obj: list에 이미 등록된 obj
        self._register_obj(event_obj_list, pgie_obj)
        for obj in event_obj_list:
            self._remove_obj(event_obj_list, obj)

            if obj.obj_id == pgie_obj.obj_id:
                obj.last_time = pgie_obj.last_time
                obj.pos = pgie_obj.pos
                obj.bbox = pgie_obj.bbox
                obj.traj.append(pgie_obj.pos)

                obj.update_intrusion_flag(POLYGON)
                obj.update_alarm_state()

        del pgie_obj  # 등록을 마치고 메모리에서 삭제한다.

        return event_obj_list
        
    def _remove_obj(self, event_obj_list, obj):
        # 일정시간이 지난 obj는 list에서 지운다.
        now = monotonic()
        if obj.last_time + self.timeout < now:
            event_obj_list.remove(obj)

    def _register_obj(self, event_obj_list, pgie_obj):
        # list에 아무 obj가 등록되지 않았거나
        # 새로운 id의 obj가 나타났을 때 등록을 한다.
        obj_id_list = [obj.obj_id for obj in event_obj_list]
        if pgie_obj.obj_id not in obj_id_list:
            event_obj_list.append(pgie_obj)
