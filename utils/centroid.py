from dataclasses import dataclass
from typing import Optional
import time
import yaml

# Load config
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

@dataclass
class Centroid:
    """
    Represents a centroid with position and metadata.
    """
    x: float
    y: float
    idx: int = 0
    group: int = 0
    left: Optional['Centroid'] = None
    right: Optional['Centroid'] = None


class CentroidManager:
    """
    Manages centroid processing operations: sorting, filtering, and converting.
    """
    def __init__(self, homo_matrix):
        self.homo_matrix = homo_matrix
        self.img_raw_centroids = []
        self.img_sorted_centroids = []
        self.img_filtered_centroids = [] # used by _prepare_and_emit_frame
        self.robot_centroids = []
        self.row_indices = [] # indices of first centroid in each row

        self.last_processed_time = None  # Timestamp when processing last completed

    def process_centroids(self, centroids):
        """
        Process centroids for robot use: 
        1. Sort centroids
        2. Convert to robot coordinates if needed
        3. Filter
        
        Args:
            centroids (list): List of (x, y) coordinates or Centroid objects
            
        Returns:
            list: Processed Centroid objects ready for robot use
        """
        if centroids is None or len(centroids) == 0:
            self.img_raw_centroids = []
            self.img_sorted_centroids = []
            self.img_filtered_centroids = []   # used by _prepare_and_emit_frame
            self.robot_centroids = []
            return []
        
        # Store the raw centroids
        self.img_raw_centroids = centroids
            
        # Sort centroids
        self.img_sorted_centroids = self._sort_centroids(centroids)

        # Filter centroids to keep only those within boundary
        self.img_filtered_centroids = self._filter_boundary_centroids(self.img_sorted_centroids)
        # self.img_filtered_centroids = self._filter_mod5_centroids(self.img_filtered_centroids)

        # tmp
        # self.img_filtered_centroids = self._sfilter_test_centroids(self.img_filtered_centroids)
        # self.img_filtered_centroids = self.img_filtered_centroids[:10] if len(self.img_filtered_centroids) > 10 else self.img_filtered_centroids

        # Convert to robot coordinates if needed
        self.robot_centroids = self._convert_to_robot_coords(self.img_filtered_centroids)

        # Store timestamp when processing completed
        self.last_processed_time = time.time()
        
        return self.robot_centroids

    def is_centroid_updated_recently(self):
        """Check if centroid processing was done recently. Used to make sure the centroids are not from
        previous captures."""
        if self.last_processed_time is None:
            return False
        return time.time() - self.last_processed_time < 1.0  # 1 second threshold

    def _filter_boundary_centroids(self, centroids):
        """
        Filter centroids to keep only those within configured boundary.
        
        Args:
            centroids (list): List of Centroid objects
            
        Returns:
            list: Filtered list of centroids within boundary
        """
        if not centroids:
            return []
        
        # Get boundary values from config
        x_min = config["boundary"]["x_min"]
        x_max = config["boundary"]["x_max"]
        y_min = config["boundary"]["y_min"]
        y_max = config["boundary"]["y_max"]
        
        # Filter centroids
        return [centroid for centroid in centroids 
                if x_min < centroid.x < x_max and y_min < centroid.y < y_max]
    
    def _filter_mod5_centroids(self, centroids):
        """
        Only get centroids that are divisible by 5.

        Args:
            centroids (list): List of Centroid objects
            
        Returns:
            list: Filtered list of Centroid objects at indices divisible by 5
        """
        if not centroids:
            return []
            
        return [point for i, point in enumerate(centroids) if i % 5 == 0]
    
    def _filter_test_centroids(self, centroids):
        """
        Select 9 centroids evenly distributed in a 3x3 grid.
        
        Args:
            centroids (list): List of Centroid objects
            
        Returns:
            list: List of 9 evenly distributed Centroid objects
        """
        if not centroids or len(centroids) < 9:
            return centroids  # Return all if less than 9
        
        # Get boundary values from config
        x_min = config["boundary"]["x_min"]
        x_max = config["boundary"]["x_max"]
        y_min = config["boundary"]["y_min"]
        y_max = config["boundary"]["y_max"]
        
        # Define 3x3 grid cells
        x_step = (x_max - x_min) / 3
        y_step = (y_max - y_min) / 3
        
        selected_centroids = []
        
        # For each grid cell, find closest centroid to cell center
        for i in range(3):
            for j in range(3):
                # Calculate cell center
                cell_center_x = x_min + (i + 0.5) * x_step
                cell_center_y = y_min + (j + 0.5) * y_step
                
                # Find centroid closest to this cell center
                min_distance = float('inf')
                closest_centroid = None
                
                for centroid in centroids:
                    # Check if centroid is in this cell
                    if (x_min + i * x_step <= centroid.x <= x_min + (i + 1) * x_step and
                        y_min + j * y_step <= centroid.y <= y_min + (j + 1) * y_step):
                        
                        # Calculate distance to cell center
                        dist = ((centroid.x - cell_center_x) ** 2 + 
                                (centroid.y - cell_center_y) ** 2) ** 0.5
                        
                        if dist < min_distance:
                            min_distance = dist
                            closest_centroid = centroid
                
                # If found a centroid in this cell, add it
                if closest_centroid:
                    selected_centroids.append(closest_centroid)
        
        return selected_centroids

    def _sort_centroids(self, centroids):
        """
        Sort centroids by grouping them into horizontal rows using simplified graph-based clustering.
        For each centroid, find the closest left and right neighbors within a bounding box.

        Args:
            centroids (list): List of Centroid objects or (x, y) tuples

        Returns:
            list: A flat list of Centroid objects, sorted by rows and then by x within each row
        """
        if len(centroids) == 0:
            return []
        
        # Convert input to Centroid objects if needed
        if centroids and not isinstance(centroids[0], Centroid):
            centroids = [Centroid(x=x, y=y) for x, y in centroids]
            
        # Clear previous row indices and reset connections
        self.row_indices = []
        for centroid in centroids:
            centroid.left = None
            centroid.right = None
        
        # Step 1: For each centroid, find closest left and right neighbors
        n = len(centroids)
        
        # Bounding box parameters
        x_range = 500  # x: from +0 to +500
        y_range = 15   # y: from -15 to +15
        
        for i in range(n):
            x1, y1 = centroids[i].x, centroids[i].y
            min_left_dist = float('inf')
            min_right_dist = float('inf')
            
            for j in range(n):
                if i == j:
                    continue
                    
                x2, y2 = centroids[j].x, centroids[j].y
                dx = x2 - x1
                dy = y2 - y1
                distance = (dx**2 + dy**2)**0.5

                # Check if j is to the right of i
                if (0 <= dx <= x_range and -y_range <= dy <= y_range):
                    if distance < min_right_dist:
                        min_right_dist = distance
                        centroids[i].right = centroids[j]
                
                # Check if j is to the left of i  
                elif (0 <= -dx <= x_range and -y_range <= dy <= y_range):
                    if distance < min_left_dist:
                        min_left_dist = distance
                        centroids[i].left = centroids[j]

        # Step 2: Find leading nodes (nodes with no left neighbor)
        leading_indices = [i for i, centroid in enumerate(centroids) if centroid.left is None]
        
        # Sort leading nodes by y-coordinate (top to bottom)
        leading_indices.sort(key=lambda i: centroids[i].y)
        
        # Step 3: Build rows by traversing from each leading node to the right
        sorted_centroids = []
        visited = [False] * n
        current_idx_counter = 0
        
        for group_num, leading_idx in enumerate(leading_indices):
            if visited[leading_idx]:
                continue
                
            # Start a new row
            self.row_indices.append(len(sorted_centroids))
            
            # Traverse the row from left to right
            current_idx = leading_idx
            while current_idx is not None:
                if visited[current_idx]:
                    break
                    
                visited[current_idx] = True
                current_centroid = centroids[current_idx]
                # Create new Centroid with updated group and idx
                sorted_centroid = Centroid(x=current_centroid.x, y=current_centroid.y, idx=current_idx_counter, group=group_num)
                sorted_centroids.append(sorted_centroid)
                current_idx_counter += 1
                
                # Move to the closest right neighbor
                next_centroid = current_centroid.right
                if next_centroid is not None:
                    # Find the index of the next centroid
                    current_idx = None
                    for i, c in enumerate(centroids):
                        if c is next_centroid:
                            current_idx = i
                            break
                else:
                    current_idx = None
        
        return sorted_centroids
    
    def _convert_to_robot_coords(self, centroids):
        """
        Convert camera coordinates to robot coordinates using homography matrix.
        
        Args:
            centroids (list): List of Centroid objects in camera coordinates
            
        Returns:
            list: List of Centroid objects in robot coordinates
        """
        if not centroids:
            return []
        
        # Import here to avoid circular import
        from .tools import map_image_to_robot
            
        robot_centroids = []
        for centroid in centroids:
            # Convert coordinates
            robot_coords = map_image_to_robot((centroid.x, centroid.y), self.homo_matrix)
            # Create new Centroid object with robot coordinates
            robot_centroid = Centroid(x=robot_coords[0], y=robot_coords[1], 
                                    idx=centroid.idx, group=centroid.group)
            robot_centroids.append(robot_centroid)
        
        return robot_centroids