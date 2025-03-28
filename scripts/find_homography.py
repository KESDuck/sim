import cv2 as cv
import math
import numpy as np

# capture position: 50, 470, 0, 0
image_points = np.array(
    [
[519, 337],
[1294, 333],
[2072, 331],
[2075, 977],
[1294, 979],
[519, 981],
[521, 1629],
[1296, 1629],
[2075, 1626]
    ]
)
robot_points = np.array(
    [
[237.839, 364.944], 
[178.010, 364.635], 
[118.150, 364.369],  
[118.079, 413.798],  
[177.869, 414.005],
[237.441, 414.379],
[237.355, 464.246],
[177.584, 463.924],
[117.777, 463.581]
    ]
)

H_base, _ = cv.findHomography(image_points, robot_points)

print("Base Homography Matrix:\n", np.array2string(H_base, formatter={'float': lambda x: f'{x:.7f}'}))

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
