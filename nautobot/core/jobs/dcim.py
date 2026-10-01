from nautobot.dcim.models import Device, HardwareAsset
from nautobot.extras.jobs import BooleanVar, Job
from nautobot.extras.models import Status

name = "System Jobs"


class CreateMissingHardwareAssets(Job):
    """
    System job to create an installed HardwareAsset for every Device that has none.

    The identity mirror columns (serial, asset_tag) derive from the installed asset, so devices with no
    asset have empty identity. Operators who want a strict asset-per-device inventory can run this job to
    give every remaining device an empty-identity installed asset, which can then be serialized by editing
    the asset.
    """

    dry_run = BooleanVar(
        description="If set, report the devices that would receive a hardware asset without creating anything.",
        default=False,
        required=False,
    )

    class Meta:
        name = "Create Missing Hardware Assets"
        description = "Create and install an empty-identity hardware asset for every device that has none."
        has_sensitive_variables = False

    def run(self, *, dry_run=False):  # pylint: disable=arguments-differ
        active_status = Status.objects.get_for_model(HardwareAsset).get(name="Active")
        devices = Device.objects.filter(installed_asset__isnull=True).select_related("device_type")

        created_count = 0
        for device in devices.iterator():
            if dry_run:
                self.logger.info("Would create and install a hardware asset", extra={"object": device})
                created_count += 1
                continue
            asset = HardwareAsset(
                device_type=device.device_type,
                status=active_status,
                device=device,
                tenant=device.tenant,
            )
            asset.validated_save()
            device.installed_asset = asset
            device.validated_save()
            self.logger.success("Created and installed hardware asset", extra={"object": asset})
            created_count += 1

        if dry_run:
            self.logger.info("Dry run: %d device(s) would receive a hardware asset.", created_count)
        else:
            self.logger.info("Created and installed %d hardware asset(s).", created_count)
        return f"{created_count} device(s) processed."
