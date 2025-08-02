#!/usr/bin/env python3
"""
Pylon Camera Mac USB-C Adapter Diagnostic Tool
==============================================

This script tests Pylon camera reliability specifically for Mac with USB-C adapters.
It provides detailed diagnostics and optimization recommendations.

Usage:
    python test_pylon_mac.py

The script will:
1. Test camera connection stability
2. Optimize camera settings for USB-C adapters
3. Run a reliability test
4. Provide system configuration recommendations
"""

from pypylon import pylon
import time
import cv2
import signal
import sys
import threading
from collections import deque

# Global variables
running = True
stats = {
    'frames_captured': 0,
    'frames_failed': 0,
    'connection_drops': 0,
    'avg_frame_time': 0,
    'frame_times': deque(maxlen=100)
}

def signal_handler(sig, frame):
    global running
    print("\n\nShutdown requested...")
    running = False

class MacOptimizedImageHandler(pylon.ImageEventHandler):
    def __init__(self):
        super().__init__()
        self.last_frame_time = time.time()
        
    def OnImageGrabbed(self, camera, grabResult):
        global stats
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        self.last_frame_time = current_time
        
        if grabResult.GrabSucceeded():
            stats['frames_captured'] += 1
            stats['frame_times'].append(frame_time)
            if len(stats['frame_times']) > 0:
                stats['avg_frame_time'] = sum(stats['frame_times']) / len(stats['frame_times'])
                
            # Optional: Display frame (comment out for headless testing)
            image = grabResult.Array
            if image is not None and image.size > 0:
                # Resize for display if too large
                h, w = image.shape[:2]
                if w > 800:
                    scale = 800 / w
                    new_w, new_h = int(w * scale), int(h * scale)
                    image = cv2.resize(image, (new_w, new_h))
                cv2.imshow("Pylon Test", image)
                
        else:
            stats['frames_failed'] += 1
            print(f"[ERROR] Frame grab failed: {grabResult.ErrorDescription}")

def optimize_camera_for_mac(camera):
    """Apply Mac-specific optimizations for USB-C adapters"""
    print("Applying Mac/USB-C optimizations...")
    
    optimizations_applied = []
    
    # 1. Packet size optimization (try smaller sizes for USB-C adapters)
    try:
        current_packet_size = camera.GevSCPSPacketSize.GetValue()
        for packet_size in [1200, 1000, 800, 576]:  # Conservative sizes for USB-C
            try:
                camera.GevSCPSPacketSize.SetValue(packet_size)
                optimizations_applied.append(f"Packet size: {current_packet_size}→{packet_size}")
                break
            except Exception as e:
                continue
    except Exception as e:
        print(f"Warning: Could not optimize packet size: {e}")
    
    # 2. Inter-packet delay for adapter stability
    try:
        current_delay = camera.GevSCPD.GetValue()
        camera.GevSCPD.SetValue(3000)  # Increased to 3000 ns for USB-C stability
        optimizations_applied.append(f"Inter-packet delay: {current_delay}ns→3000ns")
    except Exception as e:
        print(f"Warning: Could not set inter-packet delay: {e}")
    
    # 3. Heartbeat timeout (longer for USB-C latency)
    try:
        current_timeout = camera.GevHeartbeatTimeout.GetValue()
        camera.GevHeartbeatTimeout.SetValue(5000)  # 5 seconds for USB-C
        optimizations_applied.append(f"Heartbeat timeout: {current_timeout}ms→5000ms")
    except Exception as e:
        print(f"Warning: Could not set heartbeat timeout: {e}")
    
    # 4. Bandwidth settings for your camera
    # Set conservative bandwidth allocation
    if hasattr(camera, 'GevSCBWA'):
        try:
            current_bw = camera.GevSCBWA.GetValue()
            # Conservative bandwidth for USB-C (50MB/s)
            camera.GevSCBWA.SetValue(50000000)  
            optimizations_applied.append(f"Bandwidth: {current_bw}→50MB/s")
        except Exception as e:
            print(f"Warning: Could not set bandwidth allocation: {e}")
    
    # 5. Enable bandwidth reserve automatic if available
    if hasattr(camera, 'GevSCBWRA'):
        try:
            current_auto = camera.GevSCBWRA.GetValue()
            camera.GevSCBWRA.SetValue(9)  # Set to a stable value
            optimizations_applied.append(f"Auto bandwidth reserve: {current_auto}→9")
        except Exception as e:
            print(f"Warning: Could not enable auto bandwidth reserve: {e}")
    
    # 6. Fire test packet settings for connection validation
    if hasattr(camera, 'GevSCFTD'):
        try:
            current_ftd = camera.GevSCFTD.GetValue()
            camera.GevSCFTD.SetValue(1000)  # 1000 ns fire test delay
            optimizations_applied.append(f"Fire test delay: {current_ftd}ns→1000ns")
        except Exception as e:
            print(f"Warning: Could not set fire test delay: {e}")
    
    # 7. Stream channel optimization (skip - seems to be read-only)
    
    # 8. Frame rate control (more conservative for USB-C)
    if hasattr(camera, 'AcquisitionFrameRateEnable'):
        try:
            camera.AcquisitionFrameRateEnable.SetValue(True)
            if hasattr(camera, 'AcquisitionFrameRate'):
                current_fps = camera.AcquisitionFrameRate.GetValue()
                camera.AcquisitionFrameRate.SetValue(3.0)  # Very conservative 3 FPS
                optimizations_applied.append(f"Frame rate: {current_fps:.1f}→3.0 FPS")
        except Exception as e:
            print(f"Warning: Could not set frame rate: {e}")
    
    # 9. Buffer settings
    try:
        # Increase stream buffer count for USB-C adapters
        current_buffers = camera.MaxNumBuffer.GetValue()
        camera.MaxNumBuffer.SetValue(15)  # More buffers for stability
        optimizations_applied.append(f"Buffer count: {current_buffers}→15")
    except Exception as e:
        print(f"Warning: Could not set buffer count: {e}")
    
    print(f"Applied optimizations: {', '.join(optimizations_applied)}")
    return len(optimizations_applied)

def print_camera_info(camera):
    """Print detailed camera and network information"""
    print(f"\n{'='*60}")
    print("CAMERA INFORMATION")
    print(f"{'='*60}")
    
    info = camera.GetDeviceInfo()
    print(f"Model: {info.GetModelName()}")
    print(f"Serial: {info.GetSerialNumber()}")
    print(f"IP Address: {info.GetIpAddress()}")
    print(f"MAC Address: {info.GetMacAddress()}")
    
    # Network settings
    print(f"\nNETWORK SETTINGS:")
    try:
        print(f"Packet Size: {camera.GevSCPSPacketSize.GetValue()}")
        print(f"Inter-packet Delay: {camera.GevSCPD.GetValue()}ns")
        print(f"Heartbeat Timeout: {camera.GevHeartbeatTimeout.GetValue()}ms")
        
        # Additional network parameters specific to your camera
        if hasattr(camera, 'GevSCBWA'):
            print(f"Bandwidth Allocated: {camera.GevSCBWA.GetValue()}")
        if hasattr(camera, 'GevSCBWR'):
            print(f"Bandwidth Reserve: {camera.GevSCBWR.GetValue()}")
        if hasattr(camera, 'GevSCBWRA'):
            print(f"Auto Bandwidth Reserve: {camera.GevSCBWRA.GetValue()}")
        if hasattr(camera, 'GevSCFTD'):
            print(f"Fire Test Delay: {camera.GevSCFTD.GetValue()}ns")
        if hasattr(camera, 'PayloadSize'):
            print(f"Payload Size: {camera.PayloadSize.GetValue()}")
        if hasattr(camera, 'GevStreamChannelSelector'):
            print(f"Stream Channel: {camera.GevStreamChannelSelector.GetValue()}")
            
    except Exception as e:
        print(f"Could not read network settings: {e}")
    
    # Image settings
    print(f"\nIMAGE SETTINGS:")
    try:
        print(f"Width: {camera.Width.GetValue()}")
        print(f"Height: {camera.Height.GetValue()}")
        print(f"Pixel Format: {camera.PixelFormat.GetValue()}")
        if hasattr(camera, 'AcquisitionFrameRate'):
            print(f"Frame Rate: {camera.AcquisitionFrameRate.GetValue():.1f} FPS")
    except Exception as e:
        print(f"Could not read image settings: {e}")

def print_system_recommendations():
    """Print Mac system configuration recommendations"""
    print(f"\n{'='*60}")
    print("MAC SYSTEM RECOMMENDATIONS")
    print(f"{'='*60}")
    
    print("1. HARDWARE:")
    print("   - Use Thunderbolt 3/4 to Gigabit Ethernet adapter (not USB-C)")
    print("   - Recommended: Apple/Belkin/CalDigit Thunderbolt adapters")
    print("   - Use managed PoE+ switch with jumbo frame support")
    print("   - Use Cat6/Cat6a cables")
    
    print("\n2. NETWORK SETTINGS:")
    print("   - Enable jumbo frames (9000 MTU):")
    print("     System Preferences → Network → Advanced → Hardware → Configure: Manually")
    print("   - Set MTU to 9000")
    print("   - Disable energy saving for Ethernet:")
    print("     System Preferences → Energy Saver → Prevent computer from sleeping")
    
    print("\n3. SYSTEM SETTINGS:")
    print("   - Disable USB power management:")
    print("     sudo pmset -a usb 0")
    print("   - Increase network buffer sizes:")
    print("     sudo sysctl -w net.inet.udp.maxdgram=65536")
    print("   - Close unnecessary applications to free up USB/Thunderbolt bandwidth")

def run_reliability_test(camera, duration_seconds=60):
    """Run a reliability test for specified duration"""
    print(f"\n{'='*60}")
    print(f"RELIABILITY TEST ({duration_seconds} seconds)")
    print(f"{'='*60}")
    
    # Reset stats
    stats['frames_captured'] = 0
    stats['frames_failed'] = 0
    stats['connection_drops'] = 0
    stats['frame_times'].clear()
    
    start_time = time.time()
    last_stats_time = start_time
    
    while running and (time.time() - start_time) < duration_seconds:
        current_time = time.time()
        
        # Print stats every 10 seconds
        if current_time - last_stats_time >= 10:
            elapsed = current_time - start_time
            total_frames = stats['frames_captured'] + stats['frames_failed']
            success_rate = (stats['frames_captured'] / total_frames * 100) if total_frames > 0 else 0
            fps = stats['frames_captured'] / elapsed if elapsed > 0 else 0
            
            print(f"[{elapsed:6.1f}s] Frames: {stats['frames_captured']}, "
                  f"Success: {success_rate:5.1f}%, FPS: {fps:4.1f}, "
                  f"Avg frame time: {stats['avg_frame_time']*1000:5.1f}ms")
            last_stats_time = current_time
        
        # Check for OpenCV window events
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
        time.sleep(0.1)
    
    # Final statistics
    total_time = time.time() - start_time
    total_frames = stats['frames_captured'] + stats['frames_failed']
    success_rate = (stats['frames_captured'] / total_frames * 100) if total_frames > 0 else 0
    avg_fps = stats['frames_captured'] / total_time if total_time > 0 else 0
    
    print(f"\n{'='*60}")
    print("FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Test Duration: {total_time:.1f} seconds")
    print(f"Frames Captured: {stats['frames_captured']}")
    print(f"Frames Failed: {stats['frames_failed']}")
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Average FPS: {avg_fps:.1f}")
    print(f"Connection Drops: {stats['connection_drops']}")
    
    if success_rate < 95:
        print(f"\n⚠️  WARNING: Success rate below 95% indicates USB-C adapter issues")
        print("   Try a different adapter or follow system recommendations above")
    elif success_rate >= 98:
        print(f"\n✅ EXCELLENT: Success rate above 98% - your setup is working well!")
    else:
        print(f"\n✅ GOOD: Success rate above 95% - acceptable performance")

def enhanced_camera_discovery():
    """Enhanced camera discovery with direct IP connection for Thunderbolt adapters"""
    import os
    
    print("🔍 Enhanced Camera Discovery Process...")
    
    # Set Pylon environment variables for better GigE discovery
    os.environ['PYLON_GIGE_HEARTBEAT_EXTENDED_TIMEOUT'] = '10000'
    os.environ['PYLON_GIGE_DISCOVERY_EXTENDED_TIMEOUT'] = '10000'
    os.environ['PYLON_GIGE_DISCOVERY_TIMEOUT'] = '10000'
    
    # Set specific camera IP (from network monitor)
    camera_ip = "192.168.0.2"
    os.environ['PYLON_GIGE_IPADDRESS'] = camera_ip
    
    tl_factory = pylon.TlFactory.GetInstance()
    
    # Try direct IP connection first (best for Thunderbolt adapters)
    print(f"  Trying direct IP connection to {camera_ip}...")
    try:
        devices = connect_by_ip(tl_factory, camera_ip)
        if len(devices) > 0:
            print(f"  ✅ Found camera via direct IP connection")
            return devices
    except Exception as e:
        print(f"  ❌ Direct IP connection failed: {e}")
    
    # Fallback to discovery methods
    discovery_methods = [
        ("Standard enumeration", lambda: tl_factory.EnumerateDevices()),
        ("After 2s delay", lambda: (time.sleep(2), tl_factory.EnumerateDevices())[1]),
        ("After 5s delay", lambda: (time.sleep(5), tl_factory.EnumerateDevices())[1]),
        ("Force GigE TL", lambda: discover_via_gige_tl(tl_factory)),
    ]
    
    for method_name, method_func in discovery_methods:
        print(f"  Trying {method_name}...")
        try:
            devices = method_func()
            if len(devices) > 0:
                print(f"  ✅ Found {len(devices)} device(s) using {method_name}")
                return devices
            else:
                print(f"  ❌ No devices found with {method_name}")
        except Exception as e:
            print(f"  ❌ Error with {method_name}: {e}")
        
        time.sleep(1)  # Brief pause between attempts
    
    print("  ❌ All discovery methods failed")
    return []

def connect_by_ip(tl_factory, camera_ip):
    """Attempt to connect directly to camera by IP address"""
    try:
        # Method 1: Create device info with specific IP
        device_info = pylon.CDeviceInfo()
        device_info.SetIpAddress(camera_ip)
        device_info.SetDeviceClass("BaslerGigE")
        
        print(f"    Creating device with IP {camera_ip}...")
        device = tl_factory.CreateDevice(device_info)
        return [device_info]  # Return the device info, not the device
        
    except Exception as e:
        print(f"    Method 1 failed: {e}")
        
        # Method 2: Use InstantCamera directly with IP
        try:
            print(f"    Trying InstantCamera with specific IP...")
            device_info = pylon.CDeviceInfo()
            device_info.SetIpAddress(camera_ip)
            camera = pylon.InstantCamera(tl_factory.CreateDevice(device_info))
            if camera:
                return [device_info]
        except Exception as e:
            print(f"    Method 2 failed: {e}")
        
        # Method 3: Force enumeration then filter
        try:
            print(f"    Trying enumeration with IP filter...")
            devices = tl_factory.EnumerateDevices()
            for device in devices:
                if device.GetIpAddress() == camera_ip:
                    return [device]
        except Exception as e:
            print(f"    Method 3 failed: {e}")
    
    return []

def discover_via_gige_tl(tl_factory):
    """Attempt discovery specifically through GigE transport layer"""
    tl_infos = tl_factory.EnumerateTls()
    for tl_info in tl_infos:
        if "GigE" in tl_info.GetFriendlyName():
            gige_tl = tl_factory.CreateTl(tl_info)
            devices = []
            gige_tl.EnumerateDevices(devices)  # Correct overload
            return devices
    return []

def main():
    global running
    
    # Register signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    print("Pylon Camera Mac USB-C Adapter Diagnostic Tool")
    print("=" * 60)
    
    camera = None
    
    try:
        # Enhanced camera discovery
        devices = enhanced_camera_discovery()
        
        if len(devices) == 0:
            print("❌ No Pylon cameras found!")
            print("\nTroubleshooting for Thunderbolt adapters:")
            print("1. Ensure Pylon Viewer is completely closed")
            print("2. Check camera power and PoE switch")
            print("3. Verify camera IP is in same subnet as Thunderbolt interface")
            print("4. Try: sudo python3 scripts/vision_pylon_mac_test.py")
            print("5. Set static IP on Thunderbolt interface (e.g., 192.168.1.10)")
            print("6. Run network diagnostic: python scripts/debug_thunderbolt_discovery.py")
            return
        
        print(f"Found {len(devices)} camera(s)")
        
        # Connect to first camera
        camera = pylon.InstantCamera(tl_factory.CreateDevice(devices[0]))
        camera.Open()
        
        # Print camera info
        print_camera_info(camera)
        
        # Apply optimizations
        num_optimizations = optimize_camera_for_mac(camera)
        print(f"Applied {num_optimizations} optimizations")
        
        # Setup image handler
        image_handler = MacOptimizedImageHandler()
        camera.RegisterImageEventHandler(image_handler, 
                                       pylon.RegistrationMode_Append,
                                       pylon.Cleanup_Delete)
        
        # Start grabbing
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
        
        # Run reliability test
        print("\nPress Ctrl+C to stop the test early")
        run_reliability_test(camera, duration_seconds=60)
        
        # Print recommendations
        print_system_recommendations()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nThis might indicate:")
        print("1. USB-C adapter compatibility issues")
        print("2. Network configuration problems") 
        print("3. Camera firmware issues")
        
    finally:
        if camera and camera.IsOpen():
            camera.StopGrabbing()
            camera.Close()
        cv2.destroyAllWindows()
        print("\nTest completed.")

if __name__ == "__main__":
    main() 