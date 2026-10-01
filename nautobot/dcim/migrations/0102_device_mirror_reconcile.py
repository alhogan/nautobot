from django.db import migrations

BATCH_SIZE = 1000


def reconcile_device_mirrors(apps, schema_editor):
    """
    Make the Device identity mirror columns consistent with the installed asset.

    The installed asset is authoritative: a device with an installed asset holds the asset's serial and
    asset tag (an asset with no serial yields an empty device serial), and a device with no installed
    asset holds empty mirrors. Colliding serials nulled by the backfill migration remain recorded in the
    corresponding asset's comments.
    """
    Device = apps.get_model("dcim", "Device")

    reconciled_count = 0
    devices_to_update = []

    installed = Device.objects.filter(installed_asset__isnull=False).select_related("installed_asset")
    for device in installed.iterator(chunk_size=BATCH_SIZE):
        serial = device.installed_asset.serial or ""
        asset_tag = device.installed_asset.asset_tag
        if device.serial != serial or device.asset_tag != asset_tag:
            device.serial = serial
            device.asset_tag = asset_tag
            devices_to_update.append(device)

    assetless = Device.objects.filter(installed_asset__isnull=True).exclude(serial="", asset_tag__isnull=True)
    for device in assetless.iterator(chunk_size=BATCH_SIZE):
        device.serial = ""
        device.asset_tag = None
        devices_to_update.append(device)

    while devices_to_update:
        batch, devices_to_update = devices_to_update[:BATCH_SIZE], devices_to_update[BATCH_SIZE:]
        Device.objects.bulk_update(batch, ["serial", "asset_tag"], batch_size=BATCH_SIZE)
        reconciled_count += len(batch)

    if reconciled_count:
        print(f"\n    Reconciled the serial/asset tag mirror columns on {reconciled_count} device(s).")


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0101_hardwareasset_backfill"),
    ]

    operations = [
        migrations.RunPython(reconcile_device_mirrors, migrations.RunPython.noop),
    ]
