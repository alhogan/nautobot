from django.db import migrations

from nautobot.extras.management import clear_status_choices, populate_status_choices


def populate_hardware_asset_status(apps, schema_editor):
    """
    Create default Status records for the HardwareAsset content-type.
    """
    # Create HardwareAsset Statuses and add dcim.HardwareAsset to their content_types
    populate_status_choices(apps, schema_editor, models=["dcim.HardwareAsset"])


def clear_hardware_asset_status(apps, schema_editor):
    """
    De-link/delete all Status records from the HardwareAsset content-type.
    """
    clear_status_choices(apps, schema_editor, models=["dcim.HardwareAsset"])


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0098_hardwareasset"),
    ]

    operations = [
        migrations.RunPython(populate_hardware_asset_status, clear_hardware_asset_status),
    ]
