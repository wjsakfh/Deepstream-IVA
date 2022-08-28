from time import monotonic
from typing import List, Dict


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
    # TODO 단일 obj를 관리하는 방법 고안 (현재는 obj list를 관리하는 방법임.): register, update, remove
    def __init__(self, obj_info):
        self.obj_info = obj_info

    def _extract_obj_info(self):
        self.class_id: int = self.obj_info["obj_class_id"]
        self.obj_id: int = self.obj_info["obj_id"]
        self.pos: List = self.obj_info["tracker_bbox_info"]
        self.traj: List = self.obj_info["obj_id"]
        self.init_time: int = monotonic()
        self.last_time: int = monotonic()

    def remove(self):
        pass

    def register(self):
        pass

    def update(self):
        pass
