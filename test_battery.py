from cuesdk import CueSdk, CorsairDeviceFilter
import time

sdk = CueSdk()
sdk.connect(lambda state: None)
time.sleep(2)

headset_id = '{93f75c13-8d78-4af5-a552-3143db3d3cfc}'

battery, _ = sdk.read_device_property(headset_id, 9, 0)
connected, _ = sdk.read_device_property(headset_id, 4, 0)
charging, _ = sdk.read_device_property(headset_id, 2, 0)

print(f"Battery: {battery.value}%")
print(f"Connected: {connected.value}")
print(f"Charging: {charging.value}")