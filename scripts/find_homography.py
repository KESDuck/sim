import cv2 as cv
import math
from typing import Tuple, List, Optional
import numpy as np
import numpy.typing as npt

class HomographyMapper:
    """A class to handle image to world coordinate mapping using homography."""
    
    def __init__(self, image_points: npt.NDArray[np.float64], robot_points: npt.NDArray[np.float64]):
        """
        Initialize the homography mapper with calibration points.
        
        Args:
            image_points: Array of image coordinates (Nx2)
            robot_points: Array of corresponding world coordinates (Nx2)
        """
        if len(image_points) != len(robot_points):
            raise ValueError("Number of image points must match number of robot points")
        
        self.image_points = image_points
        self.robot_points = robot_points
        self.homography_matrix, _ = cv.findHomography(image_points, robot_points)
        
    def map_image_to_world(self, image_point: Tuple[float, float]) -> Tuple[float, float]:
        """
        Map an image point to world coordinates using the homography matrix.
        
        Args:
            image_point: Tuple of (x, y) image coordinates
            
        Returns:
            Tuple of (x, y) world coordinates
        """
        image_point_homogeneous = np.array([image_point[0], image_point[1], 1.0])
        robo_point_homogeneous = np.dot(self.homography_matrix, image_point_homogeneous)
        robo_point = robo_point_homogeneous / robo_point_homogeneous[2]
        return float(robo_point[0]), float(robo_point[1])
    
    def calculate_error(self) -> List[float]:
        """
        Calculate mapping errors for all calibration points.
        
        Returns:
            List of distances between expected and mapped points
        """
        errors = []
        for img_pt, expected_pt in zip(self.image_points, self.robot_points):
            mapped_pt = self.map_image_to_world(tuple(img_pt))
            errors.append(self._distance(expected_pt, mapped_pt))
        return errors
    
    @staticmethod
    def _distance(pt1: Tuple[float, float], pt2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return math.sqrt((pt1[0] - pt2[0])**2 + (pt1[1] - pt2[1])**2)

def main():
    # Calibration points
    image_points = np.array([
[2290.0, 179.0],
[2300.0, 914.0],
[2309.0, 1652.0],
[1283.0, 191.0],
[1293.0, 928.5],
[1303.0, 1669.0],
[272.0, 205.0],
[281.5, 944.0],
[293.0, 1685.0],
    ])
    
    robot_points = np.array([
[ 76.830, 300.066],
[ -0.376, 299.164],
[-78.165, 298.066],
[ 75.718, 405.912],
[ -1.665, 404.889],
[-79.145, 403.789],
[ 74.246, 511.397],
[ -2.928, 510.596],
[-80.526, 509.406]
    ])
    
    try:
        mapper = HomographyMapper(image_points, robot_points)
        print("Homography Matrix:\n", np.array2string(mapper.homography_matrix, 
                                                     formatter={'float': lambda x: f'{x:.9f}'}))
        
        # Print calibration errors
        errors = mapper.calculate_error()
        print("\nCalibration Errors:")
        for i, error in enumerate(errors):
            print(f"Point {i+1}: {error:.3f} units")
        print(f"\nAverage Error: {sum(errors)/len(errors):.3f} units")
        
    except Exception as e:
        print(f"Error during homography calculation: {e}")

if __name__ == "__main__":
    main()
