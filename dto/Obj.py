from typing import List
from time import monotonic
import numpy as np


class PgieObj:
    def __init__(self, obj_info):
        self.class_id: int = obj_info["obj_class_id"]
        self.obj_id: int = obj_info["obj_id"]
        self.pos: List[int] = self._get_cpos(obj_info["tracker_bbox_info"])
        self.traj: List[List[int]] = [self.pos]  # traj: trajectory
        self.init_time: float = monotonic()
        self.last_time: float = monotonic()
        self.intrusion_flag_list: List = [False] * 60
        # TODO list의 길이가 2개여도 될까
        # 2개 False False -> False True 가 됐을 때 init time을 기록하고
        # True True일 때도 계속 시간을 기록하고

    def _get_cpos(self, bbox_info) -> List[int]:
        xmin = int(bbox_info["left"])
        ymin = int(bbox_info["top"])
        xmax = xmin + int(bbox_info["width"])
        ymax = ymin + int(bbox_info["height"])

        cx = int((xmin + xmax) / 2)
        cy = ymax

        cpos = [cx, cy]

        return cpos

    def update_intrusion_flag(self, polygon) -> None:
        if len(polygon) < 3:
            return False

        prev_point = polygon[-1]
        x0, y0 = self.pos[0], self.pos[1]
        line_count = 0
        for point in polygon:
            xa, ya = prev_point[0], prev_point[1]
            xb, yb = point[0], point[1]
            if x0 >= min(xa, xb) and x0 < max(xa, xb):
                gb = (yb - ya) / ((xb - xa) + np.finfo(float).eps)
                if (x0 - xa) * gb > (y0 - ya):
                    line_count += 1
            prev_point = point

        included = True if line_count % 2 == 1 else False

        self.intrusion_flag_list.pop(0)
        self.intrusion_flag_list.append(included)
