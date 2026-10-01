# Hardware Assets

+++ 4.0.0

A hardware asset is a physical, serialized piece of whole-device hardware, tracked independently of any logical [device](device.md). The device carries the logical intent (name, role, interfaces, cables, IP addresses, configuration context); the hardware asset carries the physical identity (serial number, asset tag, hardware model via its [device type](devicetype.md)) and its own lifecycle status (Ordered, Received, Spare, Staged, Active, RMA, Decommissioning, Decommissioned).

A hardware asset may exist with no device at all (a spare in a depot, or incoming stock from a purchase order), may be associated to a device ahead of installation (staged for a hardware replacement), or may be the hardware currently serving as a device. Multiple assets may be associated to one device simultaneously during a staging window, but at most one is designated as installed, via the device's `installed_asset` pointer.

The installed asset is authoritative for the device's `serial`, `asset_tag`, and `device_type` fields, which are maintained as read-only mirrors: editing the installed asset updates the device, and a device with no installed asset has an empty serial and asset tag. Direct writes to these device fields are rejected; to give a device a serial number, create a hardware asset and install it.

A hardware asset's `location` records where the hardware physically sits while it is not installed (for example, a depot or warehouse). At installation the location is cleared, and the asset's physical location derives from its device. On uninstall, the location is not automatically set; the actor removing the hardware records where it went.

Replacing failed hardware (an RMA) does not require a second device record. Stage the replacement asset by associating it to the device, then change the device's `installed_asset` pointer to the replacement in a single operation. Interfaces, cables, IP addresses, and the device's history are untouched, and both assets retain their own change logs.

Serial numbers are unique per device type, matching how vendors assign them, and may be left unset (for example, while hardware is on order). Asset tags are globally unique across hardware assets.
