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

def draw_cross(image, x, y, color=(0, 0, 255)):
    # Check if the image is grayscale
    if len(image.shape) == 2 or image.shape[2] == 1:  # Grayscale image
        image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)

    # Draw the cross on the image
    cv.drawMarker(image, (x, y), color, markerType=cv.MARKER_CROSS, markerSize=20, thickness=1)

    return image

def draw_points(image, points, current_index):
    if points == None:
        return

    for i in range(len(points)):
        color = (0, 0, 0) # red, green, blue
        if i < current_index:
            color = (255, 0, 0)
        elif i == current_index:
            color = (255, 0, 255)
        elif i > current_index:
            color = (0, 0, 255)

        cv.circle(image, points[i], 4, color, -1)
    
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
    """
    # Step 1: Sort by x-coordinates first, with grouping tolerance
    centroids = sorted(centroids, key=lambda c: (c[0] // x_tolerance, c[1]))
    return centroids

# depreciated
def find_centroids(image, threshold_value=135, min_area=500, max_area=800, crop_region=None, alpha=0.5):
    """
    Processes an image to find and display contours and their centroids.

    Args:
        threshold_value (int): Threshold value for binary thresholding.
        min_area (int): Minimum area for contour filtering.
        max_area (int): Maximum area for contour filtering.
        crop_region (tuple): Crop region as (start_x, end_x, start_y, end_y).
        alpha (float): Blending alpha for visualization.

    Returns a dictionary:
            - "centroids": List of centroid coordinates as (x, y).
            - "threshold": threshold image
            - "contour_overlay": Image with contours and centroids drawn.
    """
    # crop_region = [582, 1375, 157, 757] # medium region
    crop_region = [800, 1100, 250, 550] # small region

    ##### PROCESS #####
    # Step 1: Preprocessing
    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    _, thres = cv.threshold(gray, threshold_value, 255, cv.THRESH_BINARY)

    # Step 2: Find Contours
    contours, _ = cv.findContours(thres, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE)

    # Step 3: Filter Contours
    filtered_contours = [cnt for cnt in contours if min_area < cv.contourArea(cnt) < max_area]

    # Step 4: Find Centroids
    centroids = []
    for cnt in filtered_contours:
        x, y, w, h = cv.boundingRect(cnt)
        aspect_ratio = w / h
        if 0.8 <= aspect_ratio <= 1.2:
            M = cv.moments(cnt)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                if determine_bound((cX, cY), crop_region):
                    centroids.append((cX, cY))


    ##### SAVING #####
    # All the converting and returning
    return_dict = {}
    return_dict["threshold"] = cv.cvtColor(thres, cv.COLOR_GRAY2BGR)

    contour_overlay = return_dict["threshold"].copy()
    for cnt in filtered_contours:
        # Draw the contour
        cv.drawContours(contour_overlay, [cnt], -1, (0, 255, 0), 2)  # Green for contours
    return_dict["contour_overlay"] = contour_overlay

    return_dict["centroids"] = sort_centroids(centroids)

    # Convert threshold image to color for visualization
    # gray_bgr = cv.cvtColor(thres, cv.COLOR_GRAY2BGR)
    # blended = cv.addWeighted(gray_bgr, alpha, np.ones_like(gray_bgr) * 255, 1 - alpha, 0)

    return return_dict

def add_spinning_indicator(spin_angle, frame):
    """
    Adds a spinning indicator to the top-right corner of the frame.
    TODO: test this
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