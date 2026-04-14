#!/usr/bin/env python3
"""
Document edge detection using OpenCV.
Input:  base64-encoded image via stdin (JSON: {"image_base64": "..."})
Output: JSON with detected corners as fractions [0..1] of image size
"""
import sys
import json
import base64
import numpy as np

def detect_document_corners(image_b64):
    import cv2

    # Decode base64 → image
    image_data = base64.b64decode(image_b64)
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        return None

    h, w = img.shape[:2]

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Blur to reduce noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Adaptive threshold to find document edges
    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 4
    )

    # Dilate to connect edge fragments
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return default_corners()

    # Sort by area descending, take largest
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    best_quad = None
    for cnt in contours[:5]:
        # Approximate contour to polygon
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

        # We want a quadrilateral
        if len(approx) == 4:
            area = cv2.contourArea(approx)
            # Must be at least 10% of image area
            if area > (w * h * 0.1):
                best_quad = approx
                break

    if best_quad is None:
        # Try with relaxed approximation
        cnt = contours[0]
        peri = cv2.arcLength(cnt, True)
        hull = cv2.convexHull(cnt)
        approx = cv2.approxPolyDP(hull, 0.04 * peri, True)
        if len(approx) == 4:
            best_quad = approx
        else:
            return default_corners()

    # Order corners: top-left, top-right, bottom-right, bottom-left
    pts = best_quad.reshape(4, 2).astype(float)
    ordered = order_points(pts)

    # Normalize to [0..1] fractions
    corners = [
        {"x": float(ordered[0][0] / w), "y": float(ordered[0][1] / h)},  # top-left
        {"x": float(ordered[1][0] / w), "y": float(ordered[1][1] / h)},  # top-right
        {"x": float(ordered[2][0] / w), "y": float(ordered[2][1] / h)},  # bottom-right
        {"x": float(ordered[3][0] / w), "y": float(ordered[3][1] / h)},  # bottom-left
    ]

    return {"corners": corners, "detected": True}

def order_points(pts):
    """Order points: top-left, top-right, bottom-right, bottom-left"""
    rect = np.zeros((4, 2), dtype="float32")

    # Top-left has smallest sum, bottom-right has largest sum
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left
    rect[2] = pts[np.argmax(s)]   # bottom-right

    # Top-right has smallest diff, bottom-left has largest diff
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left

    return rect

def default_corners():
    """Return default corners with 5% margin when detection fails"""
    margin = 0.05
    return {
        "corners": [
            {"x": margin, "y": margin},              # top-left
            {"x": 1 - margin, "y": margin},           # top-right
            {"x": 1 - margin, "y": 1 - margin},       # bottom-right
            {"x": margin, "y": 1 - margin},            # bottom-left
        ],
        "detected": False
    }

if __name__ == "__main__":
    try:
        data = json.loads(sys.stdin.read())
        image_b64 = data.get("image_base64", "")

        if not image_b64:
            print(json.dumps({"error": "No image_base64 provided"}))
            sys.exit(1)

        result = detect_document_corners(image_b64)

        if result is None:
            print(json.dumps(default_corners()))
        else:
            print(json.dumps(result))

    except Exception as e:
        # On any error return default corners so app still works
        result = default_corners()
        result["error"] = str(e)
        print(json.dumps(result))
