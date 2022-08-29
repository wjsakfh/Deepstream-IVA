import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst

from time import monotonic
from typing import List, Dict
from core.utils import parse_buffer2msg
from dataclasses import dataclass

@dataclass
class PgieObj:
    def __init__(self, obj_info):
        self.class_id: int = obj_info["obj_class_id"]
        self.obj_id: int = obj_info["obj_id"]
        self.pos: List[int] = obj_info["tracker_bbox_info"]
        self.traj: List[List[int]] = [obj_info["tracker_bbox_info"]] # traj: trajectory
        self.init_time: float = monotonic()
        self.last_time: float = monotonic()


class MsgManager:
    # TODO 단일 obj를 관리하는 방법 고안 (현재는 obj list를 관리하는 방법임.): register, update, remove
    def __init__(self):
        # self.obj_info_list = obj_info_list
        self.strm_list: List = list()
        self.obj_list: List = list()
        self.timeout: float = 3.0
        # 정보 Extract
        # 리스트 업데이트

    # TODO tiler_sink_pad_buffer_probe를 PgieObjList에 def로 넣는다.
    # TODO async로 obj를 등록할 수 있다면 좋을 듯
    # TODO async로 alarm generator가 processing되어야 함
    def tiler_sink_pad_buffer_probe(self, pad, info, u_data):
        # msg manager
        msg: Dict = dict()
        gst_buffer = info.get_buffer()
        parsed_msg = parse_buffer2msg(gst_buffer, msg)
        self.obj_id_list = [obj.obj_id for obj in self.obj_list]
        self.now = monotonic()
        for frame_info in parsed_msg["frame_list"]:
            for obj_info in frame_info["obj_list"]:
                # pgie_obj생성
                # self.obj_list에 업데이트.
                pgie_obj = PgieObj(obj_info)
                self._update_obj(pgie_obj)
        print("self.obj_id_list", self.obj_id_list)
        # TODO obj등록이 끝난 list는 이벤트 발생알고리즘으로 전달
        # TODO algorithms.line_crossing(self.obj_list)
        return Gst.PadProbeReturn.OK

    def _update_obj(self, pgie_obj):
        # pgie_obj: 현재 등록하려는 obj
        # obj: list에 이미 등록된 obj
        self._register_obj(pgie_obj)
        for obj in self.obj_list:
            self._remove_obj(obj)
            if obj.obj_id == pgie_obj.obj_id:
                obj.last_time = pgie_obj.last_time
                obj.pos = pgie_obj.pos
                obj.traj.append(pgie_obj.pos)
            else:
                pass

        del pgie_obj # 등록을 마치고 메모리에서 삭제한다.

    def _remove_obj(self, obj):
        # 일정시간이 지난 obj는 list에서 지운다.
        if obj.last_time + self.timeout < self.now:
            self.obj_list.remove(obj)
        else:
            pass

    def _register_obj(self, pgie_obj):
        # list에 아무 obj가 등록되지 않았거나
        # 새로운 id의 obj가 나타났을 때 등록을 한다.
        if len(self.obj_list) == 0:
            self.obj_list.append(pgie_obj)
        elif pgie_obj.obj_id not in self.obj_id_list:
            self.obj_list.append(pgie_obj)
        else:
            pass
