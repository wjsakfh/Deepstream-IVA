import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import GObject, Gst

from time import monotonic
from typing import List, Dict
from core.utils import parse_buffer2msg


def retrieve_pgie_obj(msg):
    # ---- retrieve pgie results ---- #
    class_label = msg["objects"][i]["type_id"]
    track_id = int(msg["objects"][i]["track_id"].split("-")[-1], 16)
    H, W = msg["extra"]["height"], msg["extra"]["width"]
    xmin = int(msg["objects"][i]["bbox"]["x"] * W)
    ymin = int(msg["objects"][i]["bbox"]["y"] * H)
    xmax = xmin + int(msg["objects"][i]["bbox"]["width"] * W)
    ymax = ymin + int(msg["objects"][i]["bbox"]["height"] * H)
    pos = [xmin, ymin, xmax, ymax]

    # ---- c_pos is a point of the lowest and middle point of bbox ---- #
    cx = int((xmin + xmax) / 2)
    cy = ymin + (ymax - ymin)
    c_pos = [cx, cy]

    pgie_results = [class_label, track_id, pos, c_pos]

    # ---- retrieve sgie results ---- #
    sgie_labels_info = [
        sgie_label_info
        for sgie_label_info in ev_sgie_class_on_pgie
        if sgie_label_info[0] == class_label
    ]
    sgie_results = [list() for i in range(len(sgie_labels_info))]
    if len(sgie_labels_info) != 0:
        for label_idx in range(len(sgie_labels_info)):
            for class_idx in range(len(msg["objects"][i]["classifier"]["label_info"])):
                if sgie_labels_info[label_idx][0] == class_label:
                    if (
                        sgie_labels_info[label_idx][1]
                        == msg["objects"][i]["classifier"]["label_info"][class_idx][
                            "class_type"
                        ]
                    ):
                        sgie_result = (
                            msg["objects"][i]["classifier"]["label_info"][class_idx][
                                "result_label"
                            ]
                            == sgie_labels_info[label_idx][2]
                        )
                        sgie_results[label_idx] = sgie_result
                    else:
                        pass
                else:
                    pass
    else:
        pass

    return pgie_results, sgie_results


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
        return Gst.PadProbeReturn.OK

    def _update_obj(self, pgie_obj):
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
        if obj.last_time + self.timeout < self.now:
            self.obj_list.remove(obj)
        else:
            pass

    def _register_obj(self, pgie_obj):
        if len(self.obj_list) == 0:
            self.obj_list.append(pgie_obj)
        elif pgie_obj.obj_id not in self.obj_id_list:
            self.obj_list.append(pgie_obj)
        else:
            pass
