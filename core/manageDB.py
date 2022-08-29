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
        self.pos: List = obj_info["tracker_bbox_info"]
        self.traj: List = obj_info["obj_id"]
        self.init_time: int = monotonic()
        self.last_time: int = monotonic()


class PgieObjList:
    # TODO 단일 obj를 관리하는 방법 고안 (현재는 obj list를 관리하는 방법임.): register, update, remove
    def __init__(self, obj_info_list):
        self.obj_info_list = obj_info_list
        self.obj_list: List = list()
        # 정보 Extract
        # 리스트 업데이트

    # TODO tiler_sink_pad_buffer_probe를 PgieObjList에 def로 넣는다.
    def tiler_sink_pad_buffer_probe(pad, info, u_data):
        msg: Dict = dict()
        gst_buffer = info.get_buffer()

        parsed_msg = parse_buffer2msg(gst_buffer, msg)
        # print("parsed_msg", parsed_msg)
        for frame_info in parsed_msg["frame_list"]:
            for obj_info in frame_info["obj_list"]:
                print(PgieObjList(obj_info))

        # obj_info_list = parsed_msg["obj_list"]
        # for obj_info in obj_info_list:
        #     obj_list = PgieObjList(obj_info_list).update()

        # obj_result = retrieve_pgie_obj(obj_list[i_obj])

        # print("msg", msg)
        return Gst.PadProbeReturn.OK

    def update(self):

        pass

    def _extract_obj_info(self):
        for obj_info in self.obj_info_list:
            # obj 데이터클래스 초기화
            # obj list에 없으면 초기 등록
            # 있으면 업데이트
            # 시간 지나면 제거
            obj = PgieObj(obj_info)
            self._register(obj)

    def _remove(self):
        pass

    def _register(self, obj):
        if len(self.obj_list) == 0:
            self.obj_list.append(obj)
        else:
            pass
