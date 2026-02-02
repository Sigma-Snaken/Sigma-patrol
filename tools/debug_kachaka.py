import kachaka_api

ROBOT_IP = "192.168.50.133:26400"
client = kachaka_api.KachakaApiClient(ROBOT_IP)

print(f"Connected to {ROBOT_IP}")

try:
    bat = client.get_battery_info()
    print("\n--- Battery Info Debug ---")
    print(f"Type: {type(bat)}")
    print(f"Raw: {bat}")
    print(f"Dir: {dir(bat)}")
except Exception as e:
    print(f"Battery Error: {e}")
