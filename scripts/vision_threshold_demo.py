"""
OpenCV Image Thresholding Demo
==============================

Demonstrates different image thresholding techniques using OpenCV:
- Binary threshold with fixed value (127)
- Otsu's automatic threshold method
- Adaptive Gaussian threshold
- Adaptive Mean threshold
- Displays all results side-by-side using matplotlib for comparison
- Processes a grayscale image from 'save/2025-02-03 161551.jpg'
"""

import cv2 as cv
import numpy as np
import matplotlib.pyplot as plt

# Load the image
image_path = "save/2025-02-03 161551.jpg"
image = cv.imread(image_path, cv.IMREAD_GRAYSCALE)

# Apply different thresholding methods
_, binary_thresh = cv.threshold(image, 127, 255, cv.THRESH_BINARY)
_, otsu_thresh = cv.threshold(image, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU)
adaptive_gaussian = cv.adaptiveThreshold(image, 255, cv.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv.THRESH_BINARY, 11, 2)
adaptive_mean = cv.adaptiveThreshold(image, 255, cv.ADAPTIVE_THRESH_MEAN_C,
                                     cv.THRESH_BINARY, 11, 2)

# Display results
fig, axes = plt.subplots(1, 4, figsize=(16, 4))
axes[0].imshow(binary_thresh, cmap='gray')
axes[0].set_title("Binary Threshold (127)")
axes[1].imshow(otsu_thresh, cmap='gray')
axes[1].set_title("Otsu's Threshold")
axes[2].imshow(adaptive_gaussian, cmap='gray')
axes[2].set_title("Adaptive Gaussian")
axes[3].imshow(adaptive_mean, cmap='gray')
axes[3].set_title("Adaptive Mean")

for ax in axes:
    ax.axis('off')

plt.show()
