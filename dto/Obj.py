from typing import List, Tuple, Dict
from time import monotonic
import numpy as np

WIN_SIZE = 8
ALARM_THRES: float = 0.8


class PgieObj:
    def __init__(self, obj_info, event_roi):
        self.class_id: int = obj_info["obj_class_id"]
        self.obj_id: int = obj_info["obj_id"]
        self.bbox: Dict = self.__parse_bbox_info(obj_info["tracker_bbox_info"])
        self.pos: List[int] = self.__get_cpos(self.bbox)
        self.traj: List[List[int]] = [self.pos]  # traj: trajectory
        self.reid_feature = obj_info["obj_reid_feature"]

        self.secondary_info: Dict[str, List] = {}

        for s in obj_info["classifier_list"]:  # s: secondary classifier
            self.secondary_info[s["classifier_id"]] = [
                s["label_info"]["result_class_id"]
            ]
            
        self.init_time: float = monotonic()
        self.last_time: float = monotonic()

        self.event_roi = event_roi
        self.alarm_filter_window: List = [self.__polygon_in_test()] * WIN_SIZE
        self.alarm_check_list: List[bool, bool] = [self.__polygon_in_test()] * 2

    def __parse_bbox_info(self, bbox_info):
        xmin = int(bbox_info["left"])
        ymin = int(bbox_info["top"])
        xmax = xmin + int(bbox_info["width"])
        ymax = ymin + int(bbox_info["height"])

        return (xmin, ymin, xmax, ymax)

    def __get_cpos(self, bbox_info):
        xmin = bbox_info[0]
        # ymin = bbox_info[1]
        xmax = bbox_info[2]
        ymax: int = bbox_info[3]

        cx = int((xmin + xmax) / 2)
        cy = ymax

        cpos = (cx, cy)

        return cpos

    def __polygon_in_test(self):
        if len(self.event_roi) < 3:
            return False

        prev_point = self.event_roi[-1]
        x0, y0 = self.pos[0], self.pos[1]
        line_count = 0
        for point in self.event_roi:
            xa, ya = prev_point[0], prev_point[1]
            xb, yb = point[0], point[1]
            if x0 >= min(xa, xb) and x0 < max(xa, xb):
                gb = (yb - ya) / ((xb - xa) + np.finfo(float).eps)
                if (x0 - xa) * gb > (y0 - ya):
                    line_count += 1
            prev_point = point

        included = bool(line_count % 2 == 1)

        return included

    def update_intrusion_flag(self):
        included = self.__polygon_in_test()
        self.alarm_filter_window.pop(0)
        self.alarm_filter_window.append(included)

    def update_alarm_state(
        self,
    ):
        average_window = self.alarm_filter_window
        window_mean = np.mean(average_window)
        alarm_check = bool(window_mean > ALARM_THRES)

        self.alarm_check_list.pop(0)
        self.alarm_check_list.append(alarm_check)
