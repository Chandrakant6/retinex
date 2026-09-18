"""
Classical (non-learned) lesion evidence for the reviewing clinician.

This is deliberately simple: morphological image processing on the green
channel, which has the best lesion contrast in retinal photographs. It is
NOT a diagnostic lesion segmentation system — it exists to give the human
reviewer quick visual/countable evidence to sanity-check the model's grade,
and to power the "does the AI's attention line up with visible lesions?"
consistency check. See doc/model.md for accuracy caveats and a roadmap
towards a learned segmentation model.
"""
import cv2
import numpy as np


def detect(image_path: str, out_path: str) -> dict:
    img = cv2.imread(image_path)
    h, w = img.shape[:2]
    green = img[:, :, 1]

    fov = (green > 15).astype(np.uint8)
    fov = cv2.erode(fov, np.ones((15, 15), np.uint8))  # pull mask in from the frame edge

    # --- Optic disc: brightest region after heavy blur, away from the frame edge ---
    blurred = cv2.GaussianBlur(green, (0, 0), sigmaX=w / 40)
    _, _, _, od_loc = cv2.minMaxLoc(blurred, mask=fov)
    od_radius = int(0.08 * w)
    od_mask = np.zeros_like(green)
    cv2.circle(od_mask, od_loc, od_radius, 1, -1)

    # --- Bright lesions (hard exudates / cotton wool spots): white top-hat ---
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    tophat = cv2.morphologyEx(green, cv2.MORPH_TOPHAT, kernel)
    exudate_mask = (tophat > 22) & (od_mask == 0) & (fov > 0)
    exudate_area_pct = round(100.0 * exudate_mask.sum() / max(fov.sum(), 1), 2)

    # --- Dark lesions (microaneurysms / hemorrhages): black top-hat, size-split ---
    blackhat = cv2.morphologyEx(green, cv2.MORPH_BLACKHAT, kernel)
    dark_mask = ((blackhat > 18) & (od_mask == 0) & (fov > 0)).astype(np.uint8)
    n_labels, _, stats, centroids = cv2.connectedComponentsWithStats(dark_mask, connectivity=8)

    microaneurysms, hemorrhages = [], []
    for i in range(1, n_labels):  # label 0 is background
        area = stats[i, cv2.CC_STAT_AREA]
        cx, cy = centroids[i]
        if area < 3:
            continue
        elif area <= 40:
            microaneurysms.append((float(cx), float(cy)))
        elif area <= 800:
            hemorrhages.append((float(cx), float(cy)))
        # larger blobs are usually vessel crossings / noise; ignored at this
        # simple heuristic level rather than risking false lesion counts

    annotated = img.copy()
    annotated[exudate_mask] = (0, 220, 220)
    for cx, cy in microaneurysms:
        cv2.circle(annotated, (int(cx), int(cy)), 5, (0, 0, 255), 1)
    for cx, cy in hemorrhages:
        cv2.circle(annotated, (int(cx), int(cy)), 10, (255, 0, 255), 2)
    cv2.circle(annotated, od_loc, od_radius, (0, 255, 0), 2)
    cv2.imwrite(out_path, annotated)

    return {
        "optic_disc": {"x": int(od_loc[0]), "y": int(od_loc[1]), "radius": od_radius},
        "microaneurysm_count": len(microaneurysms),
        "hemorrhage_count": len(hemorrhages),
        "exudate_area_pct": exudate_area_pct,
        "points": {
            "microaneurysms": microaneurysms,
            "hemorrhages": hemorrhages,
        },
    }


def rule_based_level_floor(evidence: dict) -> int:
    """A crude, conservative ICDR floor implied by lesion counts alone —
    used only as a cross-check against the model's grade, never as the
    final grade. Thresholds are heuristic; see doc/model.md."""
    if evidence["hemorrhage_count"] >= 1 or evidence["exudate_area_pct"] > 1.5:
        return 2
    if evidence["microaneurysm_count"] >= 1:
        return 1
    return 0
