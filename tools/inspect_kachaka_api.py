import kachaka_api
import inspect

print("Inspecting kachaka_api.KachakaApiClient...")
client = kachaka_api.KachakaApiClient()
print(f"move_forward signature: {inspect.signature(client.move_forward)}")
print(f"rotate_in_place signature: {inspect.signature(client.rotate_in_place)}")
print(f"move_to_pose signature: {inspect.signature(client.move_to_pose)}")
