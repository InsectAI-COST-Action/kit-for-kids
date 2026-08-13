# Next session checklist

Start with the SD card disconnected from the camera and mounted on the development computer.

1. Open `dashboard.html` from the card and hard-refresh it. Confirm the total capture count includes all closed chunks plus `captures_current.js`, and test both expand/collapse buttons and the image modal.
2. Run `py tools\audit_card.py <card-root>` and save the read-only report with a backup. Resolve errors before changing any files; review warnings under `docs/reconciliation-policy.md`.
3. Confirm `manifest.js` lists every `data/captures_*.js` closed chunk and that `summary.js` agrees with the closed-capture count. Do not replace either file with the starter files in `dashboard/`.
4. Run the repository checks (`py tests\check_project.py`) and a clean PlatformIO build before hardware work.
5. Perform a controlled short capture, disconnect the battery, and reboot. Record the run manifest state, dashboard chunk count, raw CSV row count, and any orphan `.tmp` files.
6. Run the one-hour battery profile at 2 FPS. Record battery voltage, temperature, frame count, image count, SD errors, and whether the final power removal is recovered cleanly.
7. Test the offline dashboard on Windows 10/11 and a current macOS release in Chrome, Edge, Firefox, and Safari. Record any local-file or image-loading differences.
8. Test the manual reset workflow on a copied card image, keeping the original card data intact until counts and backups are confirmed.
9. Review SD endurance results and decide whether any cleanup/reconciliation utility is needed before model integration.
10. Keep the null inference adapter in place until a production model, model card, licence, input/output contract, and 2-FPS benchmark are approved.
