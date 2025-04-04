#!/usr/bin/env python
# ===========================================================================
# Grab Strategies Demo - Demonstration of Instant Camera grab strategies
# ===========================================================================
#
# This sample demonstrates the use of the Instant Camera grab strategies
# All event handlers are integrated into a single standalone file.

import sys
import time

from pypylon import pylon


# ===============================================================================
# Event Handlers
# ===============================================================================

class ImageEventPrinter(pylon.ImageEventHandler):
    """Handles image-related events and prints detailed diagnostic information"""
    
    def OnImagesSkipped(self, camera, countOfSkippedImages):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[EVENT] OnImagesSkipped - Device: {device_name}")
        print(f"       Images skipped: {countOfSkippedImages}")
        print("-" * 50)

    def OnImageGrabbed(self, camera, grabResult):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[EVENT] OnImageGrabbed - Device: {device_name}")

        # Image grabbed successfully?
        if grabResult.GrabSucceeded():
            print(f"       Resolution: {grabResult.GetWidth()}x{grabResult.GetHeight()}")
            img = grabResult.GetArray()
            print(f"       First row sample: {img[0][0:5]}...")
            print("-" * 50)
        else:
            error_code = grabResult.GetErrorCode()
            error_desc = grabResult.GetErrorDescription()
            print(f"       [ERROR] Code: {error_code}")
            print(f"               {error_desc}")
            print("-" * 50)


class ConfigurationEventPrinter(pylon.ConfigurationEventHandler):
    """Handles configuration events from the camera and prints diagnostic information"""
    
    def OnAttach(self, camera):
        print("[CONFIG] OnAttach event")
        print("-" * 50)

    def OnAttached(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnAttached - Device: {device_name}")
        print("-" * 50)

    def OnOpen(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnOpen - Device: {device_name}")
        print("-" * 50)

    def OnOpened(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnOpened - Device: {device_name}")
        print("-" * 50)

    def OnGrabStart(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStart - Device: {device_name}")
        print("-" * 50)

    def OnGrabStarted(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStarted - Device: {device_name}")
        print("-" * 50)

    def OnGrabStop(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStop - Device: {device_name}")
        print("-" * 50)

    def OnGrabStopped(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabStopped - Device: {device_name}")
        print("-" * 50)

    def OnClose(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnClose - Device: {device_name}")
        print("-" * 50)

    def OnClosed(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnClosed - Device: {device_name}")
        print("-" * 50)

    def OnDestroy(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnDestroy - Device: {device_name}")
        print("-" * 50)

    def OnDestroyed(self, camera):
        print("[CONFIG] OnDestroyed event")
        print("-" * 50)

    def OnDetach(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnDetach - Device: {device_name}")
        print("-" * 50)

    def OnDetached(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnDetached - Device: {device_name}")
        print("-" * 50)

    def OnGrabError(self, camera, errorMessage):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnGrabError - Device: {device_name}")
        print(f"        Error: {errorMessage}")
        print("-" * 50)

    def OnCameraDeviceRemoved(self, camera):
        device_name = camera.GetDeviceInfo().GetModelName()
        print(f"[CONFIG] OnCameraDeviceRemoved - Device: {device_name}")
        print("-" * 50)


# ===============================================================================
# Helper Functions
# ===============================================================================

def print_section_header(title):
    """Print a formatted section header for each grab strategy demonstration"""
    print("\n" + "=" * 80)
    print(f"STRATEGY: {title}")
    print("=" * 80)


def execute_triggers(camera, count=3):
    """Execute software triggers and wait for camera to be ready"""
    for i in range(count):
        if camera.WaitForFrameTriggerReady(200, pylon.TimeoutHandling_ThrowException):
            print(f"[TRIGGER] Executing software trigger #{i+1}")
            camera.ExecuteSoftwareTrigger()


def retrieve_results(camera):
    """Retrieve all grab results from the output queue and count them"""
    buffersInQueue = 0
    while True:
        grabResult = camera.RetrieveResult(0, pylon.TimeoutHandling_Return)
        if not grabResult.IsValid():
            break
        skipped = grabResult.GetNumberOfSkippedImages()
        if skipped > 0:
            print(f"[INFO] Skipped {skipped} image(s)")
        buffersInQueue += 1
    
    return buffersInQueue


# ===============================================================================
# Strategy Implementation Functions
# ===============================================================================

def demo_strategy_one_by_one(camera):
    """Demonstrate GrabStrategy_OneByOne strategy
    
    All images are processed in the order they are received.
    """
    print_section_header("GrabStrategy_OneByOne (Default)")
    print("[INFO] Images processed in order of arrival")

    camera.StartGrabbing(pylon.GrabStrategy_OneByOne)
    
    # Execute triggers
    execute_triggers(camera)
    
    # Wait for images to arrive in queue
    time.sleep(0.2)
    
    # Check and retrieve results
    if camera.GetGrabResultWaitObject().Wait(0):
        print("[INFO] Grab results waiting in output queue")
    
    # Simple retrieval - just count results
    buffersInQueue = 0
    while camera.RetrieveResult(0, pylon.TimeoutHandling_Return):
        buffersInQueue += 1
    
    print(f"[RESULT] Retrieved {buffersInQueue} grab results from output queue")
    
    # Stop grabbing
    camera.StopGrabbing()


def demo_strategy_latest_image_only(camera):
    """Demonstrate GrabStrategy_LatestImageOnly strategy
    
    Only the most recent image is kept in the output queue.
    """
    print_section_header("GrabStrategy_LatestImageOnly")
    print("[INFO] Only last received image kept in output queue")

    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    
    # Execute triggers
    execute_triggers(camera)
    
    # Wait for images to arrive in queue
    time.sleep(0.2)
    
    # Check results
    if camera.GetGrabResultWaitObject().Wait(0):
        print("[INFO] A grab result waiting in output queue")
    
    # Retrieve results with our helper function
    buffersInQueue = retrieve_results(camera)
    print(f"[RESULT] Retrieved {buffersInQueue} grab result from output queue")
    
    # Stop grabbing
    camera.StopGrabbing()


def demo_strategy_latest_images(camera):
    """Demonstrate GrabStrategy_LatestImages strategy
    
    A configurable number of most recent images are kept in the output queue.
    """
    print_section_header("GrabStrategy_LatestImages")
    print("[INFO] Only the last N images kept in output queue")

    # Configure queue size (important for this strategy)
    camera.OutputQueueSize.Value = 2
    print(f"[CONFIG] Output queue size set to {camera.OutputQueueSize.Value}")

    camera.StartGrabbing(pylon.GrabStrategy_LatestImages)
    
    # Execute triggers
    execute_triggers(camera)
    
    # Wait for images to arrive in queue
    time.sleep(0.2)
    
    # Check results
    if camera.GetGrabResultWaitObject().Wait(0):
        print("[INFO] Grab results waiting in output queue")
    
    # Retrieve results with our helper function
    buffersInQueue = retrieve_results(camera)
    print(f"[RESULT] Retrieved {buffersInQueue} grab results from output queue")
    
    # Show equivalence to other strategies by changing queue size
    camera.OutputQueueSize.Value = 1
    print(f"[CONFIG] Output queue size set to {camera.OutputQueueSize.Value} (equivalent to GrabStrategy_LatestImageOnly)")

    camera.OutputQueueSize.Value = camera.MaxNumBuffer.Value
    print(f"[CONFIG] Output queue size set to {camera.OutputQueueSize.Value} (equivalent to GrabStrategy_OneByOne)")
    
    # Stop grabbing
    camera.StopGrabbing()


def demo_strategy_upcoming_image(camera):
    """Demonstrate GrabStrategy_UpcomingImage strategy
    
    The next image received from the camera is grabbed.
    Not available for USB cameras.
    """
    if camera.IsUsb():
        print("\n[INFO] Skipping GrabStrategy_UpcomingImage - not supported for USB cameras")
        return
        
    print_section_header("GrabStrategy_UpcomingImage")
    print("[INFO] Image grabbed is always the next image received from camera")

    # Reconfigure for continuous acquisition
    pylon.AcquireContinuousConfiguration().OnOpened(camera)

    camera.StartGrabbing(pylon.GrabStrategy_UpcomingImage)
    
    # Queue buffer and wait for result
    print("[ACTION] Retrieving result with 5000ms timeout")
    try:
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        print("[INFO] Grab result retrieved successfully")
    except Exception as e:
        print(f"[ERROR] Failed to retrieve result: {str(e)}")

    # Brief wait
    time.sleep(0.2)
    
    # Check for results - should be none
    if not camera.GetGrabResultWaitObject().Wait(0):
        print("[INFO] No grab result waiting in output queue (expected)")
    
    # Stop grabbing
    camera.StopGrabbing()


# ===============================================================================
# Main Demo Function
# ===============================================================================

def run_demo():
    """Run the grab strategies demonstration"""
    
    # Create an instant camera object for the camera device found first
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

    # Register configuration handlers
    camera.RegisterConfiguration(pylon.SoftwareTriggerConfiguration(), 
                                pylon.RegistrationMode_ReplaceAll,
                                pylon.Cleanup_Delete)
    
    # Add event handlers for logging
    camera.RegisterConfiguration(ConfigurationEventPrinter(), 
                                pylon.RegistrationMode_Append, 
                                pylon.Cleanup_Delete)
    camera.RegisterImageEventHandler(ImageEventPrinter(), 
                                    pylon.RegistrationMode_Append, 
                                    pylon.Cleanup_Delete)

    # Print camera info
    print("\n[CAMERA INFO] Using device", camera.GetDeviceInfo().GetModelName())
    print("-" * 50)

    # Configure buffer count
    camera.MaxNumBuffer.Value = 15

    # Open the camera
    camera.Open()

    # Run all strategy demonstrations
    # demo_strategy_one_by_one(camera)
    demo_strategy_latest_image_only(camera)
    # demo_strategy_latest_images(camera)
    # demo_strategy_upcoming_image(camera)

    print("\n[INFO] Sample finished successfully")


# ===============================================================================
# Main Entry Point
# ===============================================================================

if __name__ == "__main__":
    try:
        run_demo()
    except Exception as e:
        print(f"[ERROR] An exception occurred: {str(e)}")
        sys.exit(1) 