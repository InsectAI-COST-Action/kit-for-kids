# Motion-detection spike

This tracked experiment evaluates a lightweight on-device pre-trigger policy without changing an SD card. It compares consecutive camera JPEGs as 160 x 120 grayscale previews, removes the global brightness shift, divides the image into 8 x 6 tiles, and takes the strongest tile mean absolute difference as the motion score.

Run it against a mounted card with a bounded sample before changing the threshold:

```powershell
py spikes\motion-detection\motion_detection_spike.py D:\ --pairs-per-session 100 --output artifacts\motion-detection\YYYY-MM-DD-sample
```

The accepted first threshold is **5**. On the 19 August 2026 100-pair-per-session sample, it retained 9/100 comparisons from run_000008 and 6/100 from run_000009. This is a tuning starting point, not a validated detection result. Generated reports, contact sheets, and interrupted trial output belong under ignored `artifacts/motion-detection/`; this folder contains only reproducible code and instructions.
