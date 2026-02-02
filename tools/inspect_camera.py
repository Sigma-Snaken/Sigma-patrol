
import kachaka_api
import inspect

client = kachaka_api.KachakaApiClient()
print("Methods in KachakaApiClient:")
for name, member in inspect.getmembers(client):
    if name.startswith("get_") and "camera" in name.lower():
        print(name)
