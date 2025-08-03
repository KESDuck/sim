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
[2296, 217],
[2293, 954],
[2291, 1690],
[1280, 1689],
[1283, 951],
[1285, 213],
[273, 215],
[272, 952],
[270, 1689]
    ])
    
    robot_points = np.array([
[ 83.852, 360.699],
[  6.038, 361.216],
[-71.421, 361.214],
[-71.408, 467.729],
[  6.288, 467.530],
[ 84.137, 467.530],
[ 83.739, 573.973],
[  5.936, 573.793],
[-71.528, 573.792]
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
