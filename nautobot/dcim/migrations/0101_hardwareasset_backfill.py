import logging
import uuid

from django.db import migrations

logger = logging.getLogger(__name__)

# Device status name → HardwareAsset status name. Hardware in an offline or failed device is still the
# installed hardware; operational state remains the device's concern.
DEVICE_TO_ASSET_STATUS_MAP = {
    "Active": "Active",
    "Offline": "Active",
    "Failed": "Active",
    "Planned": "Staged",
    "Staged": "Staged",
    "Inventory": "Spare",
    "Decommissioning": "Decommissioning",
}
DEFAULT_ASSET_STATUS = "Active"
BATCH_SIZE = 1000


def _flush(HardwareAsset, Device, assets, devices):
    HardwareAsset.objects.bulk_create(assets, batch_size=BATCH_SIZE)
    Device.objects.bulk_update(devices, ["installed_asset"], batch_size=BATCH_SIZE)
    assets.clear()
    devices.clear()


def backfill_hardware_assets(apps, schema_editor):
    """
    Create one installed HardwareAsset for every Device that carries identity values but has no asset.

    Devices with neither a serial nor an asset tag are treated as designed-only and get no asset. Serial
    values that would collide with an existing asset of the same device type are preserved in the new
    asset's comments instead (the mirror reconciliation migration then clears the device column).
    """
    ContentType = apps.get_model("contenttypes", "ContentType")
    Device = apps.get_model("dcim", "Device")
    HardwareAsset = apps.get_model("dcim", "HardwareAsset")
    Status = apps.get_model("extras", "Status")

    hardware_asset_ct = ContentType.objects.get_for_model(HardwareAsset)
    statuses = {}
    for status_name in set(DEVICE_TO_ASSET_STATUS_MAP.values()) | {DEFAULT_ASSET_STATUS}:
        status = Status.objects.filter(content_types=hardware_asset_ct, name=status_name).first()
        if status is None:
            status, _ = Status.objects.get_or_create(name=status_name)
            status.content_types.add(hardware_asset_ct)
        statuses[status_name] = status

    seen_serials = set(HardwareAsset.objects.exclude(serial__isnull=True).values_list("device_type_id", "serial"))
    seen_asset_tags = set(HardwareAsset.objects.exclude(asset_tag__isnull=True).values_list("asset_tag", flat=True))

    devices = (
        Device.objects.filter(installed_asset__isnull=True)
        .exclude(serial="", asset_tag__isnull=True)
        .select_related("status")
    )

    created_count = 0
    serial_collision_count = 0
    assets_to_create = []
    devices_to_update = []
    for device in devices.iterator(chunk_size=BATCH_SIZE):
        comments = []

        serial = device.serial or None
        if serial is not None:
            if (device.device_type_id, serial) in seen_serials:
                comments.append(
                    f"Serial '{serial}' conflicted with an existing hardware asset of the same device type "
                    "during the hardware asset backfill, so this asset was created without a serial."
                )
                logger.warning(
                    "Device %s: serial %r collides with an existing (device type, serial) pair; "
                    "recording it in the asset's comments instead.",
                    device.pk,
                    serial,
                )
                serial = None
                serial_collision_count += 1
            else:
                seen_serials.add((device.device_type_id, serial))

        asset_tag = device.asset_tag
        if asset_tag is not None:
            if asset_tag in seen_asset_tags:
                comments.append(
                    f"Asset tag '{asset_tag}' conflicted with an existing hardware asset "
                    "during the hardware asset backfill, so this asset was created without an asset tag."
                )
                logger.warning(
                    "Device %s: asset tag %r collides with an existing hardware asset; "
                    "recording it in the asset's comments instead.",
                    device.pk,
                    asset_tag,
                )
                asset_tag = None
                serial_collision_count += 1
            else:
                seen_asset_tags.add(asset_tag)

        device_status_name = device.status.name if device.status_id else None
        asset_status_name = DEVICE_TO_ASSET_STATUS_MAP.get(device_status_name, DEFAULT_ASSET_STATUS)
        if device_status_name not in DEVICE_TO_ASSET_STATUS_MAP:
            logger.warning(
                "Device %s has status %r with no defined asset-status mapping; its asset gets status %r.",
                device.pk,
                device_status_name,
                DEFAULT_ASSET_STATUS,
            )

        asset = HardwareAsset(
            id=uuid.uuid4(),
            device_type_id=device.device_type_id,
            status=statuses[asset_status_name],
            serial=serial,
            asset_tag=asset_tag,
            device_id=device.pk,
            location=None,
            tenant_id=device.tenant_id,
            comments=" ".join(comments),
        )
        assets_to_create.append(asset)
        device.installed_asset_id = asset.id
        devices_to_update.append(device)
        created_count += 1

        if len(assets_to_create) >= BATCH_SIZE:
            _flush(HardwareAsset, Device, assets_to_create, devices_to_update)

    _flush(HardwareAsset, Device, assets_to_create, devices_to_update)

    if created_count:
        print(
            f"\n    Created {created_count} hardware asset(s) from existing device serial/asset tag values; "
            f"{serial_collision_count} colliding value(s) were preserved in asset comments instead."
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0100_alter_device_asset_tag"),
    ]

    operations = [
        migrations.RunPython(backfill_hardware_assets, migrations.RunPython.noop),
    ]
