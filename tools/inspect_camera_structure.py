
import kachaka_api

client = kachaka_api.KachakaApiClient("192.168.50.133:26400")
try:
    img = client.get_front_camera_ros_compressed_image()
    print(f"Type: {type(img)}")
    print(f"Attributes: {dir(img)}")
    if hasattr(img, 'data'):
        print(f"Data length: {len(img.data)}")
except Exception as e:
    print(f"Error: {e}")
