from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtWidgets import QGraphicsView

"""
graphics_view.py

This module defines the GraphicsView class, an enhanced QGraphicsView for 
displaying images with the following key features:

Key Features:
- Mouse wheel zoom with zoom-out restriction to prevent excessive scaling.
- Panning support (can be enabled/disabled per tab).
- Click handling for calibration (can be enabled/disabled per tab).
- Dynamic minimum zoom scale based on the image and viewport size.

Use `set_min_scale(scene_rect)` to initialize the minimum zoom scale.
"""


class GraphicsView(QGraphicsView):
    """Enhanced GraphicsView for vision display with zoom and pan"""
    def __init__(self, parent=None, enable_pan=False):
        super().__init__(parent)
        self.enable_pan = enable_pan
        self.enable_zoom = True
        self.enable_click = True
        self.setDragMode(QGraphicsView.ScrollHandDrag if enable_pan else QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.0
        self.min_scale = 1.0
        self.last_press_pos = None
        self.last_press_button = None
        self.main_window = parent  # Store reference to main window
        
    def set_pan_enabled(self, enabled):
        """Enable or disable panning"""
        self.enable_pan = enabled
        self.setDragMode(QGraphicsView.ScrollHandDrag if enabled else QGraphicsView.NoDrag)
    
    def set_zoom_enabled(self, enabled):
        """Enable or disable zoom"""
        self.enable_zoom = enabled
    
    def set_click_enabled(self, enabled):
        """Enable or disable click handling"""
        self.enable_click = enabled

    def set_min_scale(self, scene_rect):
        """Calculate and set the minimum scale based on the scene and view size."""
        view_width = self.viewport().width()
        view_height = self.viewport().height()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()

        if scene_width > 0 and scene_height > 0:
            # Set minimum scale to fit the image in the view
            self.min_scale = min(view_width / scene_width, view_height / scene_height)
            
            # Only reset transform if we're currently zoomed out beyond the minimum
            if self.scale_factor < self.min_scale:
                self.resetTransform()
                self.scale(self.min_scale, self.min_scale)
                self.scale_factor = self.min_scale

    def wheelEvent(self, event):
        """Handle mouse wheel zoom"""
        if not self.enable_zoom:
            return
        
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            zoom_factor = zoom_in_factor
        else:
            if self.scale_factor > self.min_scale:
                zoom_factor = zoom_out_factor
            else:
                return
        
        self.scale(zoom_factor, zoom_factor)
        self.scale_factor *= zoom_factor
        self.scale_factor = max(self.scale_factor, self.min_scale)
    
    def mousePressEvent(self, event):
        """Handle mouse click for calibration point selection or pan"""
        if not self.enable_click:
            super().mousePressEvent(event)
            return
        
        if self.enable_pan and event.button() == Qt.LeftButton:
            # Store press position to detect if it's a click or drag
            self.last_press_pos = event.pos()
            self.last_press_button = event.button()
            super().mousePressEvent(event)
        elif not self.enable_pan and event.button() == Qt.LeftButton:
            # Pan disabled - direct click handling
            scene_pos = self.mapToScene(event.pos())
            if self.main_window and hasattr(self.main_window, 'update_cross_position'):
                self.main_window.update_cross_position(scene_pos)
            super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release - detect clicks vs drags when pan is enabled"""
        if not self.enable_click:
            super().mouseReleaseEvent(event)
            return
        
        if self.enable_pan and event.button() == self.last_press_button == Qt.LeftButton and self.last_press_pos:
            # Check if this was a click (little movement) or a pan (significant movement)
            move_distance = (event.pos() - self.last_press_pos).manhattanLength() if self.last_press_pos else 0
            if move_distance < 5:  # Threshold: if moved less than 5 pixels, treat as click
                scene_pos = self.mapToScene(event.pos())
                if self.main_window and hasattr(self.main_window, 'update_cross_position'):
                    self.main_window.update_cross_position(scene_pos)
            self.last_press_pos = None
            self.last_press_button = None
        super().mouseReleaseEvent(event)
    
    def reset_view(self):
        """Reset zoom and fit image to view"""
        scene = self.scene()
        if scene and scene.items():
            self.resetTransform()
            self.scale_factor = 1.0
            items_rect = scene.itemsBoundingRect()
            if not items_rect.isEmpty():
                self.fitInView(items_rect, Qt.KeepAspectRatio)
                # Update min_scale after fitInView
                if items_rect.width() > 0 and items_rect.height() > 0:
                    view_width = self.viewport().width()
                    view_height = self.viewport().height()
                    self.min_scale = min(view_width / items_rect.width(), view_height / items_rect.height())
                    self.scale_factor = self.min_scale

    def keyPressEvent(self, event):
        """Forward key events to main window"""
        if self.main_window:
            self.main_window.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
