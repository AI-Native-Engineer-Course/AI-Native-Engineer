"""
hallway_counter.py
------------------
Module 7 · Lecture 7.4 · The Complete Pipeline
Hands-on: A Hallway People Counter (Tracking + Line Crossing)

The synthesis of Module 7. Capture, preprocess, detect, track, analyze, act —
all in one ~150-line script.

What it does:
    1. Reads a hallway/corridor video with OpenCV
    2. Runs Ultralytics YOLO + ByteTrack to get tracked detections
    3. Draws a horizontal counting line at LINE_Y
    4. For each tracked person, tracks the previous and current foot-point
    5. Counts every line crossing — distinguishing IN (down) from OUT (up)
    6. Overlays running counts on the frame
    7. Saves the annotated video AND a CSV log of every crossing event

Usage:
    python hallway_counter.py path/to/hallway.mp4
    python hallway_counter.py path/to/hallway.mp4 --line 0.6 --conf 0.4
    python hallway_counter.py 0    # webcam

--line is a fraction of frame height (0.5 = middle). The bottom-center of each
bounding box is used as the foot point — that's the part that physically crosses
the line on the floor.
"""

import os
import csv
import argparse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import cv2
from ultralytics import YOLO


SAMPLE_VIDEO_URL = (
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/"
    "people-detection.mp4"
)
SAMPLE_VIDEO_PATH = "sample_hallway.mp4"

PERSON_CLASS = 0  # COCO class id for "person"


def ensure_sample_video() -> str:
    if os.path.exists(SAMPLE_VIDEO_PATH):
        return SAMPLE_VIDEO_PATH
    print(f"Downloading sample hallway video -> {SAMPLE_VIDEO_PATH}")
    urllib.request.urlretrieve(SAMPLE_VIDEO_URL, SAMPLE_VIDEO_PATH)
    return SAMPLE_VIDEO_PATH


def foot_point(x1, y1, x2, y2) -> tuple[int, int]:
    """Bottom-center of the box — the foot point that crosses the line."""
    return int((x1 + x2) / 2.0), int(y2)


def event_timestamp(run_start: datetime, frame_idx: int, fps: float) -> str:
    """Absolute ISO-8601 UTC timestamp of this frame, anchored to run start.

    Using the video's own timeline (frame_idx / fps) means events stay correctly
    spaced even when the file is processed faster than real time.
    """
    stamp = run_start + timedelta(seconds=frame_idx / fps)
    return stamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def draw_box(frame, x1, y1, x2, y2, track_id: int, label: str, conf: float):
    p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
    cv2.rectangle(frame, p1, p2, (0, 255, 0), 2)
    text = f"ID {track_id} {label} {conf:.2f}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(frame, (p1[0], p1[1] - th - 6),
                  (p1[0] + tw + 4, p1[1]), (0, 255, 0), -1)
    cv2.putText(frame, text, (p1[0] + 2, p1[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)


def draw_overlay(frame, count_in: int, count_out: int, line_y: int):
    h, w = frame.shape[:2]
    # The counting line
    cv2.line(frame, (0, line_y), (w, line_y), (0, 0, 255), 2)
    cv2.putText(frame, "Counting line", (10, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    # Count overlay box
    overlay_text = f"IN: {count_in}   OUT: {count_out}"
    (tw, th), _ = cv2.getTextSize(overlay_text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    cv2.rectangle(frame, (10, 10), (10 + tw + 20, 10 + th + 20), (0, 0, 0), -1)
    cv2.putText(frame, overlay_text, (20, 10 + th + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)


def main():
    parser = argparse.ArgumentParser(description="Hallway people counter (YOLO + ByteTrack).")
    parser.add_argument("source", nargs="?", default=None,
                        help="Video path or webcam index. Downloads sample if omitted.")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--conf", type=float, default=0.35,
                        help="Confidence threshold for detections.")
    parser.add_argument("--line", type=float, default=0.7,
                        help="Counting line as a fraction of frame height (0.0-1.0).")
    parser.add_argument("--out", default="hallway_annotated.mp4",
                        help="Annotated video output path.")
    parser.add_argument("--log", default="crossings.csv",
                        help="CSV log of every counted crossing event.")
    parser.add_argument("--tracker", default="bytetrack.yaml",
                        help="Ultralytics tracker config. Default: bytetrack.yaml")
    args = parser.parse_args()

    source = args.source if args.source is not None else ensure_sample_video()
    is_webcam = isinstance(source, str) and source.isdigit()
    if is_webcam:
        source = int(source)

    print(f"Loading model: {args.model}")
    model = YOLO(args.model)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video source: {source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    line_y = int(h * args.line)
    print(f"Frame size {w}x{h}, fps {fps:.1f}, counting line at y={line_y}")

    writer = None
    if not is_webcam:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.out, fourcc, fps, (w, h))

    # State for line-crossing counting
    last_foot_y: dict[int, int] = {}        # track_id -> previous foot y
    counted: set[tuple[int, str]] = set()   # (track_id, direction) once per direction
    count_in, count_out = 0, 0

    # CSV log of events
    log_rows = []
    frame_idx = 0
    run_start = datetime.now(timezone.utc)   # anchor for event timestamps

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # ---- Detection + tracking in one call. persist=True is the magic.
        results = model.track(
            source=frame,
            persist=True,
            tracker=args.tracker,
            conf=args.conf,
            classes=[PERSON_CLASS],     # only people
            verbose=False,
        )
        # ----

        for r in results:
            names = r.names
            if r.boxes is None:
                continue
            for box in r.boxes:
                if box.id is None:
                    continue  # detected but not yet tracked
                track_id = int(box.id[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                label = names[class_id]

                _, foot_y = foot_point(x1, y1, x2, y2)
                draw_box(frame, x1, y1, x2, y2, track_id, label, confidence)

                prev_y = last_foot_y.get(track_id)
                if prev_y is not None:
                    # Down crossing -> entering ("IN")
                    if prev_y < line_y <= foot_y and (track_id, "in") not in counted:
                        count_in += 1
                        counted.add((track_id, "in"))
                        log_rows.append({
                            "timestamp": event_timestamp(run_start, frame_idx, fps),
                            "track_id": track_id,
                            "direction": "IN",
                            "line_y": line_y,
                        })
                    # Up crossing -> leaving ("OUT")
                    elif prev_y > line_y >= foot_y and (track_id, "out") not in counted:
                        count_out += 1
                        counted.add((track_id, "out"))
                        log_rows.append({
                            "timestamp": event_timestamp(run_start, frame_idx, fps),
                            "track_id": track_id,
                            "direction": "OUT",
                            "line_y": line_y,
                        })

                last_foot_y[track_id] = foot_y

        draw_overlay(frame, count_in, count_out, line_y)
        if writer is not None:
            writer.write(frame)
        if is_webcam:
            cv2.imshow("Hallway Counter — press 'q' to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()

    # Write the CSV log
    if log_rows:
        with open(args.log, "w", newline="") as fh:
            fieldnames = ["timestamp", "track_id", "direction", "line_y"]
            wr = csv.DictWriter(fh, fieldnames=fieldnames)
            wr.writeheader()
            wr.writerows(log_rows)
        print(f"Wrote {len(log_rows)} crossing events -> {args.log}")

    print("\n--- Final counts ---")
    print(f"Total IN  : {count_in}")
    print(f"Total OUT : {count_out}")
    print(f"Net inside: {count_in - count_out}")
    if writer is not None:
        print(f"\nAnnotated video -> {args.out}")


if __name__ == "__main__":
    main()