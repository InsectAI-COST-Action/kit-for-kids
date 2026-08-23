# OV3660 image-quality decision and trial record

## Settled pilot setting

The pilot now uses **QXGA (2048?1536), JPEG quality 12, 1 FPS, maximum 3,600 seconds**. This is the normal `pilot` configuration in `config.example.json`; it is deliberately separate from the short `quality_trial` mode.

This decision was made because image detail is more valuable to the project than a 2-FPS target, and the completed tests show that the maximum-resolution setting is stable at 1 FPS. A one-hour run retains up to **3,600 images**.

Install the settled one-hour setting on a mounted card without deleting any captures:

```powershell
py tools\configure_camera_trial.py D:\ --install-pilot-default
```

The older `--restore-pilot` helper restores the pre-trial backup on a card and is not the command to use for this settled configuration.

## Trial evidence

| Setting | Actual resolution | Result | Decision |
| --- | --- | --- | --- |
| VGA, quality 12, 2-FPS target | 640?480 | Completed 231 images in two minutes (about 1.92 FPS); median JPEG 15.4 KiB. | Superseded: image detail is insufficient. |
| QXGA, quality 12, 1 FPS | 2048?1536 | Completed 120 images in two minutes; 1,000 ms median interval; median JPEG 98.0 KiB. | Accepted for the one-hour pilot. |
| QXGA, quality 12, 2-FPS target | 2048?1536 | Completed 171 of 240 expected images; 674 ms median interval; sampled JPEG write 702 ms. | Rejected: the image write alone exceeds the 500 ms budget. |

The interrupted QXGA runs also produced valid images and confirmed the same 1-FPS behaviour; they are retained as evidence but are not acceptance runs. Every recorded JPEG reconciled with its raw capture record.

## Interpretation and guardrails

- Lower JPEG-quality numbers mean less compression and larger files in this camera driver. Quality 12 was retained because it produced the desired image quality without adding another variable.
- The observed QXGA file size is roughly 98?110 KiB. A one-hour 1-FPS session is therefore expected to occupy roughly 345 MiB before filesystem overhead, well within the tested card capacity.
- The current browser model resizes a full image to one 640?640 pass. Better source images help children inspect captures and preserve options for later model work, but they do not by themselves solve small-object detection; crop/tiling or a bespoke model remain future decisions.
- Do not re-enable QXGA 2 FPS without a new architecture or hardware decision. The known QXGA/quality-12 write time makes that rate unattainable on this implementation.

## One-hour acceptance run

1. Install the pilot default with `--install-pilot-default`.
2. Safely eject the card, insert it into the powered-off camera, and collect for just over one hour.
3. Disconnect power, remove the card, mount it on the computer, and run:

   ```powershell
   py tools\audit_card.py D:\n   py tools\camera_trial_report.py D:\n   ```

4. Acceptance requires 3,600 completed QXGA images, reconciling raw/dashboard/JPEG counts, no uncontrolled reboot or storage failure, and a documented recovery result after normal cable-power removal.
