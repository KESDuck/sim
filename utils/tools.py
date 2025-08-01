import os
import cv2 as cv
import numpy as np
from datetime import datetime
from .centroid import Centroid

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

def draw_cross(image, x, y, color=(0, 255, 0), size=30):
    """Draw a cross marker on the image at the specified coordinates."""
    # Convert coordinates to integers
    x_int = int(x)
    y_int = int(y)
    
    # Check if we're at a half-pixel position
    if x % 1 == 0.5 or y % 1 == 0.5:
        # Draw first cross at the lower integer position
        cv.drawMarker(image, (x_int, y_int), color, markerType=cv.MARKER_CROSS, markerSize=size, thickness=1)
        
        # Draw second cross at the upper integer position
        next_x = x_int + 1 if x % 1 == 0.5 else x_int
        next_y = y_int + 1 if y % 1 == 0.5 else y_int
        cv.drawMarker(image, (next_x, next_y), color, markerType=cv.MARKER_CROSS, markerSize=size, thickness=1)
    else:
        # Draw single cross at integer position
        cv.drawMarker(image, (x_int, y_int), color, markerType=cv.MARKER_CROSS, markerSize=size, thickness=1)
    
    return image

def draw_points(image, points, current_index=None, size=5, row_indices=None):
    """
    Draw circles at the specified points on the image.
    
    Args:
        image: Image to draw on
        points: List of Centroid objects or (x, y, group_num, idx) tuples for backward compatibility
        current_index: Not used anymore, kept for backward compatibility
        size: Size of circles to draw
        row_indices: List of indices where new rows start (optional)
        
    Returns:
        Image with circles drawn
    """
    if points is None:
        return image
    
    # Check if the image is grayscale
    if len(image.shape) == 2 or image.shape[2] == 1:  # Grayscale image
        image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)

    # Define colors for different groups (BGR format)
    group_colors = [
        (0, 255, 0),    # Green
        (255, 0, 0),    # Blue  
        (0, 0, 255),    # Red
        (255, 255, 0),  # Cyan
        (255, 0, 255),  # Magenta
        (0, 255, 255),  # Yellow
        (128, 0, 128),  # Purple
        (255, 165, 0),  # Orange
    ]

    for point in points:
        # Handle both Centroid objects and tuple format for backward compatibility
        if isinstance(point, Centroid):
            x, y, group_num, idx = int(point.x), int(point.y), point.group, point.idx
        else:
            # Legacy tuple format (x, y, group_num, idx)
            x, y, group_num, idx = point
        
        # Use group-based coloring
        color = group_colors[group_num % len(group_colors)]

        cv.circle(image, (x, y), size, color, -1)
        
        # Add index label next to the circle
        label_text = str(idx)
        label_position = (x + size + 5, y + 5)  # Offset from circle
        cv.putText(image, label_text, label_position, cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1, cv.LINE_AA)
        
    return image

def map_image_to_robot(image_point, homo_matrix):
    """
    Map a 2D point from camera image coordinates to robot workspace coordinates.
    
    Args:
        image_point (array-like): A 2D point [x, y] in image pixel coordinates
        homo_matrix (ndarray): 3x3 homography transformation matrix from calibration
        
    Returns:
        ndarray: A 2D point [x, y] in robot workspace coordinates (mm)
    """
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

def add_border(image, color=(0, 0, 0), thickness=1):
    """
    Adds a border around the image with specified color and thickness.
    
    Args:
        image: The input image (numpy array)
        color: Border color in BGR format (default: black)
        thickness: Border thickness in pixels (default: 1px)
        
    Returns:
        Image with border added
    """
    # Make a copy to avoid modifying the original
    img_with_border = image.copy()
    
    # Get image dimensions
    h, w = img_with_border.shape[:2]
    
    # If grayscale, convert to BGR for the border
    if len(img_with_border.shape) == 2:
        img_with_border = cv.cvtColor(img_with_border, cv.COLOR_GRAY2BGR)
    
    # Draw rectangle around the edge
    cv.rectangle(img_with_border, (0, 0), (w-1, h-1), color, thickness)
    
    return img_with_border