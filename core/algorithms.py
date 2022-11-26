import numpy as np


def point_polygon_test(polygon, test_point) -> bool:
    if len(polygon) < 3:
        return False

    prev_point = polygon[-1]
    x0, y0 = test_point[0], test_point[1]

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
    return included

