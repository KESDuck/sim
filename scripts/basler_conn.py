from pypylon import pylon
import time
import cv2

"""
Recommendations:
Use GrabOne for simplicity in setups where advanced triggering is unnecessary.
Use WaitForFrameTriggerReady + ExecuteSoftwareTrigger for systems needing precise, controlled frame acquisition.
Use RetrieveResult in setups where triggers are managed externally (e.g., hardware triggers or external systems).
"""

def main():
    success_count = 0
    fail_count = 0
    try:
        # Create a Pylon camera instance
        camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        camera.Open()
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_RGB8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

        print("Camera connected:", camera.GetDeviceInfo().GetModelName())

        # Set continuous acquisition mode
        # camera.StartGrabbing(pylon.GrabStrategy_OneByOne)

        print("Press 'q' to quit the application.")

        # while camera.IsGrabbing():
        while True:
            start_time = time.time()

            grab_result = camera.GrabOne(4000)

            # if camera.WaitForFrameTriggerReady(200, pylon.TimeoutHandling_ThrowException):
            #     camera.ExecuteSoftwareTrigger()

            # grab_result = camera.RetrieveResult(1000, pylon.TimeoutHandling_ThrowException)

            if grab_result.GrabSucceeded():
                # Get the image array
                image = grab_result.Array
                # cv2.imwrite("raw.png", image)

                # no need to convert, since they look the same:
                # image = converter.Convert(grab_result).GetArray()
                # cv2.imwrite("converted.png", image)

                # image = grab_result.Array
                success_count += 1

                # Convert monochrome to color if necessary
                if len(image.shape) == 2:  # Grayscale image
                    # image = cv2.cvtColor(image, cv2.COLOR_BAYER_BG2BGR)
                    pass

                # Show the image using OpenCV
                cv2.imshow("Basler Camera", image)

                # Exit the loop when 'q' is pressed
                if cv2.waitKey(10) & 0xFF == ord('q'):  # 10 ms delay
                    break
            else:
                fail_count += 1

            grab_result.Release()
            time.sleep(max(0.5 - (time.time() - start_time), 0))
            elapsed_time = time.time() - start_time

            # Time: 1.123, Success: 123 (55%), Fail: 125
            print(f'Time: {elapsed_time:.3f}, ', end='')
            print(f'Success: {success_count} ({success_count/(success_count+fail_count):.1%}), Fail:{fail_count}')

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        camera.StopGrabbing()
        camera.Close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
