import cv2 as cv
import math
import numpy as np

# capture position: 50, 470, 0, 0
image_points = np.array(
    [
        [513, 375],
        [1287, 369],
        [2066, 363],
        [2069, 1008],
        [1291, 1014],
        [516, 1019],
        [520, 1665],
        [1295, 1662],
        [2073, 1657],
    ]
)
robot_points = np.array(
    [
        [239.502, 369.895],
        [179.902, 369.495],
        [119.902, 368.895],
        [119.502, 418.295],
        [179.502, 418.895],
        [239.102, 419.295],
        [238.702, 469.095],
        [178.902, 468.695],
        [119.102, 468.195],
    ]
)

H_base, _ = cv.findHomography(image_points, robot_points)

print("Base Homography Matrix:\n", H_base)

def map_image_to_world(homography_matrix, image_point):
    """
    Maps an image point to world coordinates using the homography matrix.
    """
    image_point_homogeneous = np.array([image_point[0], image_point[1], 1.0])
    robo_point_homogeneous = np.dot(homography_matrix, image_point_homogeneous)
    robo_point = robo_point_homogeneous / robo_point_homogeneous[2]  # Normalize by the third coordinate
    return robo_point[0], robo_point[1]

def dist(pt1, pt2):
    return math.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)

for i in range(len(image_points)):
    wx, wy = map_image_to_world(H_base, image_points[i])
    wpt = [wx, wy]
    print(robot_points[i], wpt, dist(robot_points[i], wpt))
