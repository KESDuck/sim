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
    img_x: float
    img_y: float
    robot_x: float
    robot_y: float
    idx: int = 0
    idx_final: int = 0
    insert: bool = False
    row: int = 0
    left: Optional['Centroid'] = None
    right: Optional['Centroid'] = None

    def __str__(self):
        return f"Centroid(img_x={self.img_x}, img_y={self.img_y}, robot_x={self.robot_x}, robot_y={self.robot_y}, idx={self.idx}, idx_final={self.idx_final}, insert={self.insert}, row={self.row})"


class CentroidManager:
    """
    Manages centroid processing operations: sorting, filtering, and converting.
    """
    def __init__(self, homo_matrix):
        self.homo_matrix = homo_matrix
        self.centroids = []  # Single list of centroids
        self._row_indices = [] # indices of first centroid in each row

        self.row_counter = 0
        self.last_processed_time = None  # Timestamp when processing last completed

    def process_centroids(self, centroids):
        """
        Process centroids for robot use:
        1. Convert to Centroid objects if needed
        2. Filter centroids within boundary
        3. Sort centroids by rows
        4. Convert to robot coordinates
        
        Args:
            centroids (list): List of (x, y) coordinates or Centroid objects
            
        Returns:
            list: Processed Centroid objects ready for robot use
        """
        if centroids is None or len(centroids) == 0:
            self.centroids = []
            return []
        
        # Convert to Centroid objects if needed
        if centroids and not isinstance(centroids[0], Centroid):
            raw_centroids = [Centroid(img_x=x, img_y=y, robot_x=0, robot_y=0) for x, y in centroids]
        else:
            raw_centroids = centroids

        # Filter centroids to keep only those within boundary
        filtered_centroids = self._filter_boundary_centroids(raw_centroids)

        # Sort the filtered centroids
        sorted_centroids = self._sort_centroids(filtered_centroids)

        # Subsample the centroids and recalculate row indices
        subsampled_centroids = self._subsample_centroids(sorted_centroids, interval=5)

        # Convert to robot coordinates and store in the same objects
        self.centroids = self._convert_to_robot_coords(subsampled_centroids)

        # Store timestamp when processing completed
        self.last_processed_time = time.time()
        self.row_counter = 0
        
        return self.centroids

    def get_row(self):
        """
        Get the current row of centroids.
        """
        # Check bounds
        if self.row_counter < 0 or self.row_counter >= len(self._row_indices):
            return []
            
        row_start = self._row_indices[self.row_counter]
        
        # Handle last row case
        if self.row_counter + 1 < len(self._row_indices):
            row_end = self._row_indices[self.row_counter + 1]
        else:
            # Last row - use all remaining centroids
            row_end = len(self.centroids)
            
        return self.centroids[row_start:row_end]


    def next_row(self):
        """
        Move to the next row.
        """
        self.row_counter += 1
    
    def get_num_rows(self):
        return len(self._row_indices)

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
                if x_min < centroid.img_x < x_max and y_min < centroid.img_y < y_max]
    
    def _subsample_centroids(self, centroids, interval=5):
        """
        Subsample centroids by taking every nth centroid and recalculate row indices.

        Args:
            centroids (list): List of sorted Centroid objects with row information
            interval (int): Take every nth centroid (default: 5)
            
        Returns:
            list: Subsampled list of Centroid objects with updated row indices
        """
        if not centroids:
            self._row_indices = []
            return []
        
        # Subsample the centroids
        subsampled = [point for i, point in enumerate(centroids) if i % interval == 0]
        
        # Recalculate row indices based on subsampled centroids
        self._row_indices = []
        current_row = -1
        
        for i, centroid in enumerate(subsampled):
            if centroid.row != current_row:
                # New row detected
                current_row = centroid.row
                self._row_indices.append(i)
        
        return subsampled
    
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
                    if (x_min + i * x_step <= centroid.img_x <= x_min + (i + 1) * x_step and
                        y_min + j * y_step <= centroid.img_y <= y_min + (j + 1) * y_step):
                        
                        # Calculate distance to cell center
                        dist = ((centroid.img_x - cell_center_x) ** 2 + 
                                (centroid.img_y - cell_center_y) ** 2) ** 0.5
                        
                        if dist < min_distance:
                            min_distance = dist
                            closest_centroid = centroid
                
                # If found a centroid in this cell, add it
                if closest_centroid:
                    selected_centroids.append(closest_centroid)
        
        return selected_centroids

    def _sort_centroids(self, centroids):
        """
        Sort centroids by group them into horizontal rows using simplified graph-based clustering.
        For each centroid, find the closest left and right neighbors within a bounding box.

        Args:
            centroids (list): List of Centroid objects

        Returns:
            list: A flat list of Centroid objects, sorted by rows and then by x within each row
        """
        if len(centroids) == 0:
            return []
            
        # Clear previous row indices and reset connections
        self._row_indices = []
        for centroid in centroids:
            centroid.left = None
            centroid.right = None
        
        # Step 1: For each centroid, find closest left and right neighbors
        n = len(centroids)
        
        # Bounding box parameters
        x_range = 500  # x: from +0 to +500
        y_range = 15   # y: from -15 to +15
        
        for i in range(n):
            x1, y1 = centroids[i].img_x, centroids[i].img_y
            min_left_dist = float('inf')
            min_right_dist = float('inf')
            
            for j in range(n):
                if i == j:
                    continue
                    
                x2, y2 = centroids[j].img_x, centroids[j].img_y
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
        leading_indices.sort(key=lambda i: centroids[i].img_y)
        
        # Step 3: Build rows by traversing from each leading node to the right
        sorted_centroids = []
        visited = [False] * n
        final_idx = 0
        for row_num, leading_idx in enumerate(leading_indices):
            if visited[leading_idx]:
                continue
                
            # Start a new row
            self._row_indices.append(len(sorted_centroids))
            
            # Traverse the row from left to right
            current_idx = leading_idx

            while current_idx is not None:
                if visited[current_idx]:
                    break
                    
                visited[current_idx] = True
                current_centroid = centroids[current_idx]
                # Create new Centroid with updated row
                sorted_centroid = Centroid(
                    img_x=current_centroid.img_x, 
                    img_y=current_centroid.img_y,
                    robot_x=current_centroid.robot_x,
                    robot_y=current_centroid.robot_y, 
                    idx=current_idx, 
                    idx_final=final_idx, 
                    row=row_num
                )
                sorted_centroids.append(sorted_centroid)
                final_idx += 1
                
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
            list: List of Centroid objects with robot coordinates updated
        """
        if not centroids:
            return []
        
        # Import here to avoid circular import
        from .tools import map_image_to_robot
            
        for centroid in centroids:
            # Convert coordinates and update robot_x, robot_y in place
            robot_coords = map_image_to_robot((centroid.img_x, centroid.img_y), self.homo_matrix)
            centroid.robot_x = robot_coords[0]
            centroid.robot_y = robot_coords[1]
        
        return centroids