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
    insert_flag: bool = False
    row: int = 0
    left: Optional['Centroid'] = None
    right: Optional['Centroid'] = None

    def __str__(self):
        return f"Centroid(img_x={self.img_x}, img_y={self.img_y}, robot_x={self.robot_x}, robot_y={self.robot_y}, idx={self.idx}, idx_final={self.idx_final}, insert_flag={self.insert_flag}, row={self.row})"


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

    def process_centroids(self, centroids, bounding_boxes=None):
        """
        Process centroids for robot use:
        1. Convert to Centroid objects if needed
        2. Filter centroids within bounding boxes
        3. Sort centroids by rows
        4. Convert to robot coordinates
        
        Args:
            centroids (list): List of (x, y) coordinates or Centroid objects
            bounding_boxes (list): List of [x_min, y_min, x_max, y_max] bounding boxes
            
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

        # Set insert_flag based on whether centroids are within bounding boxes
        flagged_centroids = self._filter_boundary_centroids(raw_centroids, bounding_boxes)

        # Sort the flagged centroids
        sorted_centroids = self._sort_centroids(flagged_centroids)

        # Subsample the centroids and recalculate row indices
        subsampled_centroids = self._subsample_centroids_evenly(sorted_centroids, row_subsample=6, centroid_subsample=6)

        # Convert to robot coordinates and store in the same objects
        self.centroids = self._convert_to_robot_coords(subsampled_centroids)

        # Store timestamp when processing completed
        self.last_processed_time = time.time()
        self.row_counter = 0
        
        return self.centroids

    def get_row(self):
        """
        Get the current row of centroids, filtered by insert_flag=True.
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
            
        # Filter centroids to only return those with insert_flag=True
        row_centroids = self.centroids[row_start:row_end]
        valid_centroids = [centroid for centroid in row_centroids if centroid.insert_flag]
        
        # Log for debugging
        if not valid_centroids:
            print(f"DEBUG: Row {self.row_counter} has no valid centroids")
        
        return valid_centroids


    def next_row(self):
        """
        Move to the next row that has valid centroids (insert_flag=True).
        """
        original_counter = self.row_counter
        self.row_counter += 1
        
        # Skip rows with no valid centroids
        while (self.row_counter < len(self._row_indices) and 
               not self.has_valid_centroids_in_row(self.row_counter)):
            self.row_counter += 1
    
    def get_num_rows(self):
        return len(self._row_indices)

    def has_valid_centroids_in_row(self, row_idx):
        """Check if a row has any centroids with insert_flag=True"""
        if row_idx < 0 or row_idx >= len(self._row_indices):
            return False
        
        row_start = self._row_indices[row_idx]
        row_end = self._row_indices[row_idx + 1] if row_idx + 1 < len(self._row_indices) else len(self.centroids)
        
        row_centroids = self.centroids[row_start:row_end]
        return any(centroid.insert_flag for centroid in row_centroids)

    def is_centroid_updated_recently(self):
        """Check if centroid processing was done recently. Used to make sure the centroids are not from
        previous captures."""
        if self.last_processed_time is None:
            return False
        return time.time() - self.last_processed_time < 1.0  # 1 second threshold

    def _filter_boundary_centroids(self, centroids, bounding_boxes=None):
        """
        Set insert_flag based on whether centroids are within bounding boxes.
        
        Args:
            centroids (list): List of Centroid objects
            bounding_boxes (list): List of [x_min, y_min, x_max, y_max] bounding boxes
            
        Returns:
            list: All centroids with insert_flag set based on boundary filtering
        """
        if not centroids:
            return []
        
        # If no bounding boxes provided, set all insert_flags to True
        if not bounding_boxes:
            for centroid in centroids:
                centroid.insert_flag = True
            return centroids
                
        # Set insert_flag for centroids: True if within any bounding box, False otherwise
        inside_count = 0
        for centroid in centroids:
            centroid.insert_flag = False  # Default to False
            for bbox in bounding_boxes:
                x_min, y_min, x_max, y_max = bbox
                if x_min < centroid.img_x < x_max and y_min < centroid.img_y < y_max:
                    centroid.insert_flag = True
                    inside_count += 1
                    break  # Stop checking other boxes once we find a match

        return centroids
    
    def _subsample_centroids_evenly(self, centroids, row_subsample, centroid_subsample):
        """
        Subsample centroids by setting insert_flag=False for non-selected centroids.
        This preserves all centroids for visualization while marking only selected ones for processing.
        
        Args:
            centroids (list): List of sorted Centroid objects
            row_subsample (int): Number of rows to select (evenly spaced)
            centroid_subsample (int): Number of centroids per row to select (evenly spaced)
            
        Returns:
            list: All centroids with insert_flag updated based on subsampling
        """
        if not centroids or len(self._row_indices) == 0:
            return centroids
        
        # Store which centroids were originally valid before subsampling
        originally_valid = [centroid.insert_flag for centroid in centroids]
        
        # First, set all centroids to insert_flag=False (will re-enable selected ones)
        for centroid in centroids:
            centroid.insert_flag = False
        
        total_rows = len(self._row_indices)
        
        # Step 1: Select rows to subsample evenly
        if row_subsample >= total_rows:
            # If we want more rows than available, use all rows
            selected_row_indices = list(range(total_rows))
        else:
            # Calculate evenly spaced row indices
            if row_subsample == 1:
                selected_row_indices = [total_rows // 2]  # Middle row
            else:
                step = (total_rows - 1) / (row_subsample - 1)
                selected_row_indices = [round(i * step) for i in range(row_subsample)]
        
        # Step 2: For each selected row, subsample centroids evenly and set insert_flag=True
        for row_idx in selected_row_indices:
            # Get start and end indices for this row
            row_start = self._row_indices[row_idx]
            if row_idx + 1 < len(self._row_indices):
                row_end = self._row_indices[row_idx + 1]
            else:
                row_end = len(centroids)
            
            # Get centroids in this row that were originally valid
            originally_valid_centroids = []
            for i in range(row_start, row_end):
                if originally_valid[i]:  # Was originally valid before subsampling
                    originally_valid_centroids.append((i, centroids[i]))
            
            if not originally_valid_centroids:
                continue  # Skip rows with no originally valid centroids
            
            total_valid_in_row = len(originally_valid_centroids)
            
            # Select evenly spaced centroids within this row
            if centroid_subsample >= total_valid_in_row:
                # If we want more centroids than available, use all valid ones
                selected_centroid_indices = list(range(total_valid_in_row))
            else:
                # Calculate evenly spaced centroid indices within the row
                if centroid_subsample == 1:
                    selected_centroid_indices = [total_valid_in_row // 2]  # Middle centroid
                else:
                    step = (total_valid_in_row - 1) / (centroid_subsample - 1)
                    selected_centroid_indices = [round(i * step) for i in range(centroid_subsample)]
            
            # Set insert_flag=True for selected centroids
            for idx in selected_centroid_indices:
                _, selected_centroid = originally_valid_centroids[idx]
                selected_centroid.insert_flag = True
        
        return centroids
    
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
                    row=row_num,
                    insert_flag=current_centroid.insert_flag
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