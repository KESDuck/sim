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
(280.0, 1647.0),
(279.0, 951.0),
(276.0, 258.0),
(1227.0, 252.0),
(1231.0, 945.0),
(1234.0, 1642.0),
(2189.0, 1631.0),
(2181.0, 936.0),
(2175.0, 244.0),
    ])
    
    robot_points = np.array([
(-71.056, 511.500),
(  6.875, 511.774),
( 84.258, 512.173),
( 84.908, 405.834),
(  7.406, 405.384),
(-70.190, 404.888),
(-69.000, 298.310),
(  8.570, 299.107),
( 85.742, 299.701)
    ])
    
    try:
        mapper = HomographyMapper(image_points, robot_points)
        print("Homography Matrix:\n", np.array2string(mapper.homography_matrix, 
                                                     formatter={'float': lambda x: f'{x:.9f}'}))
        
        # Print calibration errors
        errors = mapper.calculate_error()
        print("\nCalibration Errors:")
        for i, (img_pt, expected_pt, error) in enumerate(zip(image_points, robot_points, errors)):
            mapped_pt = mapper.map_image_to_world(tuple(img_pt))
            print(f"Point {i+1}:")
            print(f"  Original robot point: ({expected_pt[0]:.3f}, {expected_pt[1]:.3f})")
            print(f"  Mapped robot point:   ({mapped_pt[0]:.3f}, {mapped_pt[1]:.3f})")
            print(f"  Error: {error:.3f} mm")
        mean_error = sum(errors)/len(errors)
        rms_error = math.sqrt(sum(e**2 for e in errors) / len(errors))
        print(f"\nMean Error: {mean_error:.3f} mm")
        print(f"RMS Error: {rms_error:.3f} mm")
        
    except Exception as e:
        print(f"Error during homography calculation: {e}")

if __name__ == "__main__":
    main()
