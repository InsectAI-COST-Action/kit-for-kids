r"""Dependency-free contract checks for the starter implementation.

Run with: py tests\check_project.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def check_platform() -> None:
    config = text("platformio.ini")
    require("platform = espressif32 @ 7.0.1" in config, "PlatformIO version is not pinned")
    require("board = seeed_xiao_esp32s3" in config, "XIAO ESP32S3 board target is missing")
    require("board_build.arduino.memory_type = qio_opi" in config, "PSRAM memory type is missing")


def check_pilot_configuration() -> None:
    config = json.loads(text("config.example.json"))
    require(config["capture_fps"] == 1, "Pilot configuration must be 1 FPS")
    require(config["max_session_seconds"] == 3600, "Pilot sessions must be one hour")
    require(config["capture_mode"] == "pilot", "Default configuration must use pilot mode")
    require(config["camera_preset"] == "qxga_q12_1fps", "Default camera preset must be recorded")
    require(config["frame_size"] == "QXGA" and config["jpeg_quality"] == 12, "Pilot must use the settled QXGA quality preset")
    require(config["model_id"] == "none", "No model must be configured by default")
    parser = text("src/config.cpp")
    require("quality_trial" in parser and "fps != 1 && fps != 2" in parser, "Quality-trial configuration bounds are missing")
    require('pilot_mode && (fps != 1 || config.frame_size != "QXGA" || quality != 12)' in parser, "Pilot bounds must enforce the settled QXGA preset")
    require('config.frame_size != "QXGA"' in parser, "Maximum trial resolution must be configuration-validated")
    trial_tool = text("tools/configure_camera_trial.py")
    require("max_qxga_q12_1fps" in trial_tool and "max_qxga_q12_2fps" in trial_tool and '"QXGA"' in trial_tool, "Maximum-resolution trial presets are missing")
    manifest = text("src/session_logger.cpp")
    require("camera_preset" in manifest and "String(config_.capture_fps)" in manifest, "Run manifest must record effective camera settings")
    require((ROOT / "tools" / "configure_camera_trial.py").is_file(), "Camera-trial setup tool is missing")
    require((ROOT / "tools" / "camera_trial_report.py").is_file(), "Camera-trial report tool is missing")


def check_camera_contract() -> None:
    source = text("src/camera_service.cpp")
    for fragment in ("kXclkPin = 10", "kSccbSdaPin = 40", "kSccbSclPin = 39", "kY9Pin = 48"):
        require(fragment in source, f"Missing expected XIAO OV3660 mapping: {fragment}")
    require("psramFound()" in source, "Camera must reject missing PSRAM")
    require("OV3660_PID" in source, "Camera must report the actual sensor PID")
    require("FRAMESIZE_QXGA" in source, "Camera must support the maximum-resolution quality trial")


def check_data_safety_contract() -> None:
    logger = text("src/session_logger.cpp")
    dashboard = text("src/dashboard_writer.cpp")
    require("/raw/captures.csv" in logger, "Authoritative captures CSV is missing")
    require("/raw/detections.csv" in logger, "Authoritative detections CSV is missing")
    require("current_part_path_" in dashboard, "Dashboard partial chunk is missing")
    require("kChunkSize = 100" in text("include/dashboard_writer.h"), "Dashboard chunks must use the optimized bounded size")
    require("raw_csv_ms" in text("include/session_logger.h"), "Logger must expose raw CSV timing")
    require("dashboard_ms" in text("include/session_logger.h"), "Logger must expose dashboard timing")
    require("writeBinaryAtomicCreate" in text("src/main.cpp"), "JPEG writes should use the unique atomic path")
    require("captures_current.js" in dashboard, "Dashboard must preserve the current open chunk")
    require("recoverCurrentChunk" in dashboard, "Dashboard must recover an open chunk")
    require("promoteCurrentChunk" in dashboard, "Dashboard chunk promotion is missing")
    require("writeTextAtomic(\"/manifest.js\"" in dashboard, "Manifest must be atomically written")
    require("every_frame" in logger, "Every-frame retention must be logged")
    require("interrupted_power_removed" in logger, "Power removal must be represented in run state")


def check_dashboard_contract() -> None:
    html = text("dashboard/dashboard.html")
    javascript = text("dashboard/dashboard.js")
    starter_manifest = text("dashboard/manifest.js")
    starter_summary = text("dashboard/summary.js")
    require("manifest.js" in html and "summary.js" in html, "Dashboard bootstrap files are missing")
    require("manifestCandidates" in starter_manifest, "Blank-card manifest starter is missing")
    require("summaryCandidates" in starter_summary, "Blank-card summary starter is missing")
    require("fetch(" not in javascript, "Dashboard must not use fetch under file://")
    require("textContent" in javascript, "Dashboard must use safe text rendering")
    require("document.createElement('script')" in javascript, "Dashboard must load local chunks")
    require("delete" not in javascript.lower(), "Dashboard must not promise browser-side deletion")
    require("capture-toggle" in html, "Dashboard must provide frame expand control")
    require("gallery-toggle" in html, "Dashboard must provide gallery expand control")
    require("image-modal" in html, "Dashboard must provide an image modal")
    require("loading-screen" in html and "welcome-count" in html and "loading-retry" in html, "Dashboard must provide the child loading and retry experience")
    analysis = text("dashboard/analysis.js")
    require("find-insects" in html and "analysis-modal" in html and "analysis.js" in html and "analysis-card" in html, "Dashboard must provide the one-folder local AI analysis journey")
    require("fetch(" not in analysis and "webgpu" not in analysis.lower(), "Browser analysis must use the local WebAssembly path without network/WebGPU dependence")
    require("Pause search" in html and "Stop search" in html and "possible insect" in analysis and "createImageBitmap" in analysis, "Browser analysis must use safe selected-file images and stay controllable")
    require("adult-details" in html, "Technical details must be separated for adult users")
    require("Insect AI Kit-for-Kids" in html, "Dashboard title must use the Kit-for-Kids name")
    require('aria-label="Close image">x</button>' in html, "Image modal must use an ASCII x close control")
    require("seconds" in javascript and " ms`" not in javascript, "Dashboard times must be displayed in seconds")
    require(".image-modal[hidden]" in text("dashboard/dashboard.css"), "Hidden modal must not overlay the page")
    require(".loading-screen[hidden]" in text("dashboard/dashboard.css"), "Loading screen must be dismissible")
    require("prefers-reduced-motion" in text("dashboard/dashboard.css"), "Dashboard must support reduced motion")
    require("Show all" in javascript and "Escape" in javascript, "Dashboard must support expansion and modal close")


def check_fixture_schema() -> None:
    fixture = text("dashboard/fixtures/captures_000001.js")
    records = [json.loads(item) for item in re.findall(r"addCapture\((\{.*?\})\);", fixture)]
    require(len(records) == 2, "Fixture must contain two capture records")
    for record in records:
        require(record["inferenceOutcome"] == "model_unavailable", "Fixture must not claim a model result")
        require(record["uptimeMs"] > 0, "Fixture must use session-relative time")


def check_development_path_docs() -> None:
    plan = text("docs/browser-inference-plan.md")
    model_card = text("docs/model-card.md")
    brief = text("docs/project-brief.md")
    require("FlatBug" in plan and "FlatBug" in model_card and "FlatBug" in brief, "FlatBug candidate must be recorded")
    require("file://" in plan, "Browser inference must preserve direct local-file operation")
    require("WebAssembly" in plan and "WebGPU" in plan, "Portable and optional browser backends must be distinguished")
    require("3,600" in plan, "Browser feasibility must cover the maximum session")
    require("pause/cancel" in plan, "Long-running browser inference must remain controllable")


def main() -> int:
    checks = [
        check_platform,
        check_pilot_configuration,
        check_camera_contract,
        check_data_safety_contract,
        check_dashboard_contract,
        check_fixture_schema,
        check_development_path_docs,
    ]
    for check in checks:
        check()
        print(f"PASS {check.__name__}")
    print(f"PASS {len(checks)} contract checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"FAIL {error}", file=sys.stderr)
        raise SystemExit(1)
