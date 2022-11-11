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


def euclidean_squared_distance(input1, input2):
    """Computes euclidean squared distance.
    Args:
        input1 (torch.Tensor): 2-D feature matrix.
        input2 (torch.Tensor): 2-D feature matrix.
    Returns:
        torch.Tensor: distance matrix.
    """
    m, n = input1.size(0), input2.size(0)
    mat1 = torch.pow(input1, 2).sum(dim=1, keepdim=True).expand(m, n)
    mat2 = torch.pow(input2, 2).sum(dim=1, keepdim=True).expand(n, m).t()
    distmat = mat1 + mat2
    distmat.addmm_(input1, input2.t(), beta=1, alpha=-2)
    return distmat


def cosine_distance(input1, input2):
    """Computes cosine distance.
    Args:
        input1 (torch.Tensor): 2-D feature matrix.
        input2 (torch.Tensor): 2-D feature matrix.
    Returns:
        torch.Tensor: distance matrix.
    """
    input1_normed = F.normalize(input1, p=2, dim=1)
    input2_normed = F.normalize(input2, p=2, dim=1)
    distmat = 1 - torch.mm(input1_normed, input2_normed.t())
    return distmat
