"""
yolo_detector.py
----------------
Module 7 · Lecture 7.3 · Object Detection with YOLO
Hands-on: Detecting Cars (and Everything Else) on Traffic Footage

A minimal, well-commented YOLOv8 detection script that:
    - Loads a pretrained Ultralytics YOLO model (yolov8n by default)
    - Reads any image OR video the user provides
    - Runs detection on each frame
    - Draws bounding boxes and labels using OpenCV
    - Writes an annotated output and prints a per-class count summary

Usage:
    # Images
    python yolo_detector.py --image                       # bundled sample image
    python yolo_detector.py --image path/to/street.jpg    # your own photo

    # Video (bundled clip downloaded automatically on first run)
    python yolo_detector.py --video
    python yolo_detector.py --video --source path/to/your-traffic.mp4
    python yolo_detector.py --video --source 0            # webcam (no file saved)

    # Confidence threshold
    python yolo_detector.py --video --conf 0.25           # lots of detections
    python yolo_detector.py --video --conf 0.50           # 'good enough' default
    python yolo_detector.py --video --conf 0.80           # only the obvious cars

    # Class filtering (COCO indices: 2 = car, 7 = truck)
    python yolo_detector.py --video --classes 2           # cars only
    python yolo_detector.py --video --classes 2 7         # cars and trucks

    # A bare positional path/index still works (auto-detects image vs video):
    python yolo_detector.py path/to/photo.jpg
    python yolo_detector.py 0

The first run also downloads the YOLO weights automatically.
"""

import os
import argparse
import time
import urllib.request
from collections import Counter

import cv2
from ultralytics import YOLO


# Short, license-friendly samples hosted on GitHub. If a URL breaks at the time
# of class, swap in any local file and the script behaves identically.
SAMPLE_VIDEO_URL = (
    "https://github.com/intel-iot-devkit/sample-videos/raw/master/"
    "car-detection.mp4"
)
SAMPLE_VIDEO_PATH = "sample_traffic.mp4"

SAMPLE_IMAGE_URL = (
    "https://raw.githubusercontent.com/ultralytics/ultralytics/main/"
    "ultralytics/assets/bus.jpg"
)
SAMPLE_IMAGE_PATH = "sample_street.jpg"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def ensure_sample_video() -> str:
    if os.path.exists(SAMPLE_VIDEO_PATH):
        return SAMPLE_VIDEO_PATH
    print(f"Downloading sample traffic video -> {SAMPLE_VIDEO_PATH}")
    urllib.request.urlretrieve(SAMPLE_VIDEO_URL, SAMPLE_VIDEO_PATH)
    return SAMPLE_VIDEO_PATH


def ensure_sample_image() -> str:
    if os.path.exists(SAMPLE_IMAGE_PATH):
        return SAMPLE_IMAGE_PATH
    print(f"Downloading sample street image -> {SAMPLE_IMAGE_PATH}")
    urllib.request.urlretrieve(SAMPLE_IMAGE_URL, SAMPLE_IMAGE_PATH)
    return SAMPLE_IMAGE_PATH


def draw_detection(frame, x1, y1, x2, y2, label: str, conf: float, color=(0, 255, 0)):
    """Draw a single bounding box + label using only OpenCV primitives."""
    p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
    cv2.rectangle(frame, p1, p2, color, thickness=2)
    text = f"{label} {conf:.2f}"
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    # Solid background for the label so it's readable on any image.
    cv2.rectangle(frame, (p1[0], p1[1] - th - 6), (p1[0] + tw + 4, p1[1]), color, -1)
    cv2.putText(frame, text, (p1[0] + 2, p1[1] - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)


def run_on_image(model: YOLO, image_path: str, conf: float, out_path: str,
                 classes=None):
    img = cv2.imread(image_path)
    if img is None:
        raise SystemExit(f"cv2.imread returned None. Check the path: {image_path}")

    # ---- Three lines of detection
    results = model(img, conf=conf, classes=classes, verbose=False)
    # ----

    counts: Counter = Counter()
    # This is the inner loop we read together in the lecture:
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            confidence     = float(box.conf[0])
            class_id       = int(box.cls[0])
            class_name     = model.names[class_id]
            counts[class_name] += 1
            draw_detection(img, x1, y1, x2, y2, class_name, confidence)

    cv2.imwrite(out_path, img)
    print(f"\nSaved annotated image -> {out_path}")
    print("Detections by class:")
    for cls, n in counts.most_common():
        print(f"  {cls:<20s} {n}")


def run_on_video(model: YOLO, source, conf: float, out_path: str | None,
                 is_webcam: bool, classes=None):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise SystemExit(f"Could not open video source: {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    writer = None
    if out_path and not is_webcam:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))

    counts: Counter = Counter()
    seen_frames = 0
    started = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        seen_frames += 1

        # ---- One line of detection per frame
        results = model(frame, conf=conf, classes=classes, verbose=False)
        # ----

        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                confidence     = float(box.conf[0])
                class_id       = int(box.cls[0])
                class_name     = model.names[class_id]
                counts[class_name] += 1
                draw_detection(frame, x1, y1, x2, y2, class_name, confidence)

        if writer is not None:
            writer.write(frame)
        if is_webcam:
            cv2.imshow("YOLO Detector — press 'q' to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    elapsed = time.time() - started
    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()

    print(f"\nProcessed {seen_frames} frames in {elapsed:.1f}s "
          f"({seen_frames / max(elapsed, 1e-6):.1f} FPS)")
    if out_path and not is_webcam:
        print(f"Saved annotated video -> {out_path}")
    print("\nTotal detections by class (summed over all frames):")
    for cls, n in counts.most_common():
        print(f"  {cls:<20s} {n}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minimal YOLOv8 detector on images or video."
    )

    # Mode flags (used throughout the lecture demos). They're optional: if you
    # pass a bare path/index instead, the mode is inferred automatically.
    parser.add_argument("--image", action="store_true",
                        help="Treat the input as a still image. "
                             "With no source, a sample street image is downloaded.")
    parser.add_argument("--video", action="store_true",
                        help="Treat the input as video. "
                             "With no source, a sample traffic clip is downloaded.")

    # Source can be given positionally OR via --source (both demoed in class).
    parser.add_argument("source", nargs="?", default=None,
                        help="Image path, video path, or webcam index (e.g. 0). "
                             "Optional if --source is used or a sample is wanted.")
    parser.add_argument("--source", dest="source_flag", default=None,
                        help="Same as the positional source; provided so the "
                             "video demos can write --source path/to/clip.mp4.")

    parser.add_argument("--model", default="yolov8n.pt",
                        help="Ultralytics model weights. Default yolov8n.pt (smallest).")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Confidence threshold (0.0 - 1.0). Default 0.25.")
    parser.add_argument("--classes", type=int, nargs="+", default=None,
                        help="Restrict to one or more COCO class indices "
                             "(e.g. 2 for car, 7 for truck). Default: all classes.")
    parser.add_argument("--out", default="yolo_output.mp4",
                        help="Output path. For images, use a .jpg or .png extension.")
    return parser


def resolve_plan(args) -> dict:
    """Turn parsed args into a concrete run plan (mode, source, output, etc.)."""
    if args.image and args.video:
        raise SystemExit("Pass either --image or --video, not both.")

    # --source flag wins over the positional source if both are given.
    source = args.source_flag if args.source_flag is not None else args.source

    if args.image:
        mode = "image"
        if source is None:
            source = ensure_sample_image()
    elif args.video:
        mode = "video"
        if source is None:
            source = ensure_sample_video()
    else:
        # No explicit mode flag: infer from the source.
        if source is None:
            source = ensure_sample_video()
            mode = "video"
        elif source.isdigit():
            mode = "video"  # webcam index
        elif os.path.splitext(source)[1].lower() in IMAGE_EXTENSIONS:
            mode = "image"
        else:
            mode = "video"

    is_webcam = isinstance(source, str) and source.isdigit()

    if mode == "image":
        out = args.out if args.out.lower().endswith((".jpg", ".jpeg", ".png")) \
            else "yolo_output.jpg"
    else:
        out = None if is_webcam else args.out

    return {
        "mode": mode,
        "source": source,
        "is_webcam": is_webcam,
        "out": out,
        "classes": args.classes,
    }


def main():
    parser = build_parser()
    args = parser.parse_args()

    print(f"Loading model: {args.model}  (auto-downloads weights on first run)")
    model = YOLO(args.model)

    plan = resolve_plan(args)
    if plan["classes"]:
        print(f"Filtering to class indices: {plan['classes']}")

    if plan["mode"] == "image":
        run_on_image(model, plan["source"], args.conf, plan["out"],
                     classes=plan["classes"])
    else:
        run_on_video(model, int(plan["source"]) if plan["is_webcam"] else plan["source"],
                     args.conf, plan["out"], is_webcam=plan["is_webcam"],
                     classes=plan["classes"])


if __name__ == "__main__":
    main()
