from pypylon import pylon
import time
import cv2
import signal
import sys

"""
Basler Camera Acquisition Script
================================

This script provides a simple and reliable way to acquire images from Basler cameras
using the pypylon library. It implements continuous image acquisition with OpenCV
display and performance monitoring.

Features:
- Continuous image acquisition from first available Basler camera
- Live image display using OpenCV
- Performance statistics (frame rate, success rate)
- Graceful shutdown with Ctrl+C
- Event-based image processing
- Configuration event reporting for diagnostics

Requirements:
- pypylon (Basler's official Python wrapper)
- OpenCV
- A connected Basler camera

Usage:
  python pylon_conn.py

Press 'q' to quit the application.
"""

# Global variable to control the main loop
running = True
prev_end_time = time.time()

def signal_handler(sig, frame):
    global running
    print("\nCtrl+C pressed. Shutting down gracefully...")
    running = False

class ImageHandler(pylon.ImageEventHandler):
    def __init__(self):
        super().__init__()
        self.success_count = 0
        self.fail_count = 0
        
    def OnImageGrabbed(self, camera, grabResult):
        global prev_end_time
        
        if grabResult.GrabSucceeded():
            # Get the image array
            image = grabResult.Array
            self.success_count += 1
            
            # Show the image using OpenCV
            cv2.imshow("Basler Camera", image)
            
            # Print statistics
            elapsed_time = time.time() - prev_end_time
            prev_end_time = time.time()
            print(f'Time: {elapsed_time:.3f}, ', end='')
            print(f'Success: {self.success_count} ({self.success_count/(self.success_count+self.fail_count):.1%}), Fail:{self.fail_count}')
        else:
            self.fail_count += 1
            print(f"Grab failed: {grabResult.ErrorDescription}")

class ConfigurationEventPrinter(pylon.ConfigurationEventHandler):
    """Handles configuration events from the camera and prints diagnostic information"""
    
    def OnAttached(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnAttached - Device: {device_name}")

    def OnOpened(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnOpened - Device: {device_name}")

    def OnGrabStarted(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStarted - Device: {device_name}")

    def OnGrabStopped(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStopped - Device: {device_name}")

    def OnClosed(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnClosed - Device: {device_name}")

    def OnDestroyed(self, camera):
        print("[CONFIG] OnDestroyed event")

    def OnDetached(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnDetached - Device: {device_name}")

    def OnGrabError(self, camera, errorMessage):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabError - Device: {device_name}")
        print(f"        Error: {errorMessage}")

    def OnCameraDeviceRemoved(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnCameraDeviceRemoved - Device: {device_name}")


def main():
    global running
    camera = None
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Create a Pylon camera instance
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

        camera.Open()
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        
        # Register configuration event printer
        camera.RegisterConfiguration(ConfigurationEventPrinter(), 
                            pylon.RegistrationMode_Append, 
                            pylon.Cleanup_Delete)

        # Configure camera for continuous frame acquisition
        """
        Camera Acquisition Configuration
        -------------------------------
        This section configures the camera for continuous image acquisition.
        
        Key settings:
        - Using free-running continuous mode (no software triggering)
        - GrabStrategy_LatestImageOnly: Only the most recent frame is kept in buffer
        - RetrieveResult(): Used to fetch images from the camera's output queue
        
        Notes:
        - For hardware-triggered cameras, you would need to implement a different approach
        - Software triggering (SoftwareTriggerConfiguration) requires the WaitForFrameTriggerReady() 
          and ExecuteSoftwareTrigger() sequence, which is more complex but offers precise timing control
        - The current approach prioritizes simplicity and reliability for most use cases
        """

        # Register image event handler
        camera.RegisterImageEventHandler(ImageHandler(), 
                                         pylon.RegistrationMode_Append,
                                         pylon.Cleanup_Delete)

        print("Camera connected:", camera.GetDeviceInfo().GetModelName())

        # Set continuous acquisition mode with latest image only strategy
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        print("Press 'q' to quit the application.")

        # Main acquisition loop
        """
        Main Image Acquisition Loop
        --------------------------
        This loop continuously retrieves frames from the camera until stopped.
        
        Process:
        1. RetrieveResult(500, ...): Fetch the next image with a 500ms timeout
        2. If valid, process with ImageHandler and release the buffer
        3. Check for user quit command ('q' key)
        4. Short delay to control acquisition rate
        
        Frame rate is primarily determined by:
        - Camera's internal frame rate setting
        - The timeout value in RetrieveResult()
        - The sleep time (0.1s) between acquisition attempts
        """
        while camera.IsGrabbing() and running:
            # Retrieve the grab result with a timeout of 500ms
            grabResult = camera.RetrieveResult(500, pylon.TimeoutHandling_Return)
            if grabResult and grabResult.IsValid():
                # The ImageHandler's OnImageGrabbed will be called automatically
                grabResult.Release()  # Important: release the grab result to avoid memory leaks
            else:
                print("[ERROR] Failed to retrieve grab result")

            # Check for quit key
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
                
            # Small delay to control acquisition rate
            time.sleep(0.1)

        print("Exiting main loop...")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if camera and camera.IsOpen():
            camera.StopGrabbing()
            camera.Close()
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
