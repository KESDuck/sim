from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsView

"""
graphics_view.py

This module defines the GraphicsView class, an enhanced QGraphicsView for 
displaying images with the following key features:

Key Features:
- Mouse wheel zoom with zoom-out restriction to prevent excessive scaling.
- Panning support via mouse drag.
- Dynamic minimum zoom scale based on the image and viewport size.

Use `set_min_scale(scene_rect)` to initialize the minimum zoom scale.
"""


class GraphicsView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragMode(QGraphicsView.ScrollHandDrag)  # Enable panning with mouse drag
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)  # Zoom relative to mouse position
        self.scale_factor = 1.0  # Current zoom scale
        self.min_scale = 1.0  # Minimum allowed zoom scale

    def set_min_scale(self, scene_rect):
        """Calculate and set the minimum scale based on the scene and view size."""
        view_width = self.viewport().width()
        view_height = self.viewport().height()
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()

        self.min_scale = min(view_width / scene_width, view_height / scene_height)
        self.resetTransform()  # Reset the view to the minimum scale
        self.scale(self.min_scale, self.min_scale)
        self.scale_factor = self.min_scale

    def wheelEvent(self, event):
        """Handle mouse wheel events to zoom in/out while enforcing minimum zoom."""
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:  # Zoom in
            zoom_factor = zoom_in_factor
        else:  # Zoom out
            if self.scale_factor > self.min_scale:
                zoom_factor = zoom_out_factor
            else:
                return  # Stop zooming out if at the minimum scale

        self.scale(zoom_factor, zoom_factor)
        self.scale_factor *= zoom_factor
        self.scale_factor = max(self.scale_factor, self.min_scale)  # Enforce minimum scale

    def keyPressEvent(self, event):
        """Ignore arrow key events to prevent image scrolling."""
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            self.parent().keyPressEvent(event)
        else:
            super().keyPressEvent(event)  # Pass other key events to the default handler

    def mousePressEvent(self, event):
        """Handle mouse click to update the cross position."""
        if event.button() == Qt.LeftButton:
            # Map the mouse position to scene coordinates
            scene_pos = self.mapToScene(event.pos())

            # Check if the scene position is valid and within bounds
            if self.scene() is not None:
                items = self.scene().items(scene_pos)  # Get items at this position
                if items:  # Ensure there is an image item under the click
                    # Get the parent widget (CameraApp) and update cam_cross_pos
                    parent_widget = self.parent()
                    if hasattr(parent_widget, 'update_cross_position'):
                        parent_widget.update_cross_position(scene_pos)
        super().mousePressEvent(event)  # Call the default behavior for dragging, etc.
