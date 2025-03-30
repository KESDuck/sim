import os
import cv2 as cv
import numpy as np
from datetime import datetime

def save_image(image, folder):
    """save image to file"""

    # Convert the image from RGB to BGR (if necessary)
    if image.shape[-1] == 3:  # Check if the image has 3 channels
        image_bgr = cv.cvtColor(image, cv.COLOR_RGB2BGR)
    else:
        image_bgr = image  # No conversion needed for single-channel images

    now = datetime.now()
    filename = f"{now.strftime('%Y-%m-%d %H%M%S')}.jpg"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)
    cv.imwrite(path, image_bgr)
    print(f"Image saved to {path}")

def draw_cross(image, x, y, color=(0, 0, 255), size=25):
    # Check if the image is grayscale
    if len(image.shape) == 2 or image.shape[2] == 1:  # Grayscale image
        image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)

    # Draw the cross on the image
    cv.drawMarker(image, (x, y), color, markerType=cv.MARKER_CROSS, markerSize=size, thickness=1)

    return image

def draw_points(image, points, current_index, size=5):

    if points == None:
        return image
    
    # Check if the image is grayscale
    if len(image.shape) == 2 or image.shape[2] == 1:  # Grayscale image
        image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)

    for i in range(len(points)):
        color = (0, 0, 0) # red, green, blue
        if i < current_index:
            color = (0, 125, 255)
        elif i == current_index:
            color = (0, 255, 0)
        elif i > current_index:
            color = (255, 0, 0)

        cv.circle(image, points[i], size, color, -1)
    return image

def map_image_to_robot(image_point, homo_matrix):
    """Maps a 2D image point to robot coordinates using a homography matrix."""
    point_homogeneous = np.array([image_point[0], image_point[1], 1.0])
    world_point_homogeneous = np.dot(homo_matrix, point_homogeneous)
    world_point = world_point_homogeneous / world_point_homogeneous[2]
    return world_point[:2]

def determine_bound(point, crop_region):
    if not crop_region:
        return True

    min_x, max_x, min_y, max_y = crop_region
    if point[0] > min_x and point[0] < max_x and point[1] > min_y and point[1] < max_y:
        return True

    return False

def sort_centroids(centroids, x_tolerance=30):
    """
    Sort centroids such that they are grouped by similar x-coordinates,
    and within each group sorted by y-coordinates.

    Args:
        centroids (list of tuple): List of (x, y) centroid coordinates.
        x_tolerance (int): Maximum difference in x-coordinates for grouping.

    Returns:
        list: A flat list of centroids, sorted by grouped x and then y.

    TODO: understand this...
    """
    if len(centroids) == 0:
        return []
    # Step 1: Sort by x-coordinates first
    centroids.sort(key=lambda c: c[0])  

    # Step 2: Group centroids into clusters based on x_tolerance
    groups = []
    current_group = [centroids[0]]

    for i in range(1, len(centroids)):
        if abs(centroids[i][0] - current_group[-1][0]) <= x_tolerance:
            current_group.append(centroids[i])
        else:
            groups.append(sorted(current_group, key=lambda c: c[1]))  # Sort group by y
            current_group = [centroids[i]]

    groups.append(sorted(current_group, key=lambda c: c[1]))  # Sort last group

    # Step 3: Flatten list
    return [c for group in groups for c in group]


def add_spinning_indicator(spin_angle, frame):
    """
    Adds a spinning indicator to the top-right corner of the frame.
    TODO[c]: test this
    """
    height, width, _ = frame.shape
    center = (width - 30, 30)  # Top-right corner
    radius = 20
    thickness = 2

    # Increment the spinning angle
    spin_angle = (spin_angle + 10) % 360

    # Draw the spinning arc
    start_angle = spin_angle
    end_angle = (spin_angle + 60) % 360  # 60-degree arc

    # Handle cases where the end_angle wraps around 360
    if end_angle < start_angle:
        # Draw two arcs to handle wrapping
        cv.ellipse(frame, center, (radius, radius), 0, start_angle, 360, (255, 0, 0), thickness)
        cv.ellipse(frame, center, (radius, radius), 0, 0, end_angle, (255, 0, 0), thickness)
    else:
        # Draw a single arc
        cv.ellipse(frame, center, (radius, radius), 0, start_angle, end_angle, (255, 0, 0), thickness)

    return frame